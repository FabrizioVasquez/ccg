# Databricks notebook source
# MAGIC %md
# MAGIC # Etapa 4 — LSTM para pronosticar el riesgo de CL_02
# MAGIC
# MAGIC ## Hipótesis (definida ANTES de entrenar)
# MAGIC **H2:** una LSTM que lee las últimas 3 semanas de cada activo pronostica la **volatilidad de los próximos 21 días** mejor que los métodos estándar (histórica, ventana de 21 días, EWMA de RiskMetrics).
# MAGIC Si lo logra, permite ajustar la exposición de CL_02 (más en calma, menos en turbulencia) en vez de mantener un 20% fijo.
# MAGIC
# MAGIC | Elemento | Definición |
# MAGIC |---|---|
# MAGIC | **Unidad de análisis** | activo × día (8 activos), retornos en COP (moneda de CL_02) |
# MAGIC | **Objetivo (y)** | log de la volatilidad realizada anualizada de los días t+1 … t+21 |
# MAGIC | **Entradas (X)** | secuencia de 21 días: retorno, \|retorno\|, vol 5d, vol 21d, vol 63d, activo (one-hot) |
# MAGIC | **Por qué volatilidad y no precio** | El retorno no es predecible (ρ train→test ≈ 0, retornos ~ruido independiente). La volatilidad es lo que mueve la decisión de exposición |
# MAGIC | **Modelos** | LSTM solo con datos diarios · LSTM pre-entrenada con el intradía 2020-25 y ajustada con el diario · línea base: histórica, vol 21d, EWMA λ=0,94 |
# MAGIC | **Validación** | Walk-forward con 5 cortes mensuales (feb → jun 2026); nunca se entrena con datos posteriores al corte |
# MAGIC | **Métricas** | QLIKE (estándar para pronóstico de varianza; castiga más subestimar el riesgo), RMSE de volatilidad, ranking entre activos (Spearman) |
# MAGIC | **Criterio de éxito (fijado antes)** | QLIKE de la LSTM ≥ 10% mejor que EWMA **y** cambia la decisión de CL_02 (núcleo o exposición) |
# MAGIC
# MAGIC **Advertencia previa (de la etapa 3):** en el diario la volatilidad no se agrupa (ARCH p ≥ 0,08) y la vol pasada predice poco la futura (corr 0,10). El intradía 2020-25 sí tiene rachas (ARCH p < 0,001).
# MAGIC Por eso probamos el pre-entrenamiento: si hay estructura que aprender, está ahí.

# COMMAND ----------

# MAGIC %pip install "torch==2.5.1" "typing_extensions>=4.12" --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --quiet

# COMMAND ----------

# reinicia Python para que tome las versiones recién instaladas (en local no aplica)
try:
    dbutils.library.restartPython()  # noqa: F821
except NameError:
    pass

# COMMAND ----------

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import torch
import torch.nn as nn
from scipy import stats

SEED, L, H = 7, 21, 21                      # secuencia de 21 días, horizonte de 21 días
CUTS = pd.date_range("2026-02-01", "2026-06-01", freq="MS")
HIDDEN, EPOCHS, PRE_EPOCHS, LR = 16, 80, 25, 2e-3
N_SEEDS = 3                                  # ensamble de 3 semillas para estabilizar
torch.set_num_threads(4)
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})
COLORS = {"LSTM diario": "#E45756", "LSTM pre-entrenada": "#B279A2", "EWMA 0.94": "#4C78A8",
          "Vol 21d": "#72B7B2", "Histórica": "#9D9D9D"}

try:
    spark  # noqa: F821
    ON_DBX = True
except NameError:
    ON_DBX = False
    import sys, os  # noqa: E401
    sys.path.insert(0, "src/analysis")
    import clean
    def display(x):  # noqa: E301
        print(x.to_string() if isinstance(x, pd.DataFrame) else x)

if ON_DBX:
    t = lambda n: spark.table(f"credicorp_dq.silver.{n}").toPandas()  # noqa: E731,F821
    prices, macro = t("market_prices_daily"), t("macro_daily")
    intra = (spark.table("credicorp_dq.silver.market_prices_intraday")  # noqa: F821
             .groupBy("asset_id", "date").agg({"close": "last"}).withColumnRenamed("last(close)", "close").toPandas())
else:
    prices, macro = clean.prices_daily(), clean.macro_daily()
    intra = clean.prices_expanded_daily().rename(columns={"day": "date"})
for d in (prices, macro, intra):
    d["date"] = pd.to_datetime(d["date"])
macro = macro.set_index("date").sort_index()
px = prices.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
ASSETS = list(px.columns)
R = px.mul(macro.usd_cop.astype(float), axis=0).pct_change().dropna()          # diario en COP
ip = intra.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
R_pre = ip[ip.index < px.index.min()][ASSETS].pct_change().dropna()            # intradía 2020-25 (USD; sin FX disponible)
print(f"Diario: {R.index.min().date()} → {R.index.max().date()} ({len(R)} días) | Intradía pre: {R_pre.index.min().date()} → {R_pre.index.max().date()} ({len(R_pre)} días)")

# COMMAND ----------

# MAGIC %md ## 1. Construcción de secuencias (sin fuga de información)
# MAGIC Las entradas en t usan solo datos ≤ t. El objetivo usa t+1 … t+21. En el walk-forward, un ejemplo entra a entrenamiento solo si **su objetivo termina antes del corte**.

# COMMAND ----------

ANN = np.sqrt(252)

def features(Rm: pd.DataFrame) -> dict:
    out = {}
    for a in ASSETS:
        r = Rm[a]
        f = pd.DataFrame({"r": r, "abs_r": r.abs(), "vol5": r.rolling(5).std() * ANN,
                          "vol21": r.rolling(21).std() * ANN, "vol63": r.rolling(63, min_periods=21).std() * ANN})
        fut = pd.Series([r.iloc[i + 1:i + 1 + H].std() * ANN if i + H < len(r) else np.nan for i in range(len(r))], index=r.index)
        f["y"] = np.log(fut)
        out[a] = f
    return out

def sequences(F: dict):
    X, y, meta = [], [], []
    for k, a in enumerate(ASSETS):
        f = F[a]
        cols = f[["r", "abs_r", "vol5", "vol21", "vol63"]].values
        onehot = np.zeros((len(f), len(ASSETS))); onehot[:, k] = 1
        Z = np.hstack([cols, onehot])
        for i in range(L - 1, len(f)):
            win = Z[i - L + 1:i + 1]
            if np.isnan(win).any():
                continue
            X.append(win); y.append(f["y"].iloc[i])
            meta.append((a, f.index[i], f.index[min(i + H, len(f) - 1)]))
    meta = pd.DataFrame(meta, columns=["asset_id", "origen", "fin_objetivo"])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32), meta

F_d, F_p = features(R), features(R_pre)
X_d, y_d, M_d = sequences(F_d)
X_p, y_p, M_p = sequences(F_p)
ok_p = ~np.isnan(y_p); X_p, y_p = X_p[ok_p], y_p[ok_p]
print(f"Secuencias diario: {len(X_d):,} | pre-entrenamiento intradía: {len(X_p):,} | forma {X_d.shape[1:]}")

# líneas base (en t, solo con información ≤ t)
def baselines(Rm: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    b = {}
    for a in ASSETS:
        r = Rm[a]
        b[a] = pd.DataFrame({"Histórica": r.expanding(21).std() * ANN, "Vol 21d": r.rolling(21).std() * ANN,
                             "EWMA 0.94": np.sqrt((r ** 2).ewm(alpha=0.06, adjust=False).mean()) * ANN})
    rows = [b[a].loc[o].values for a, o in zip(meta.asset_id, meta.origen)]
    return pd.DataFrame(rows, columns=["Histórica", "Vol 21d", "EWMA 0.94"], index=meta.index)

B_d = baselines(R, M_d)

# COMMAND ----------

# MAGIC %md ## 2. Modelo

# COMMAND ----------

class VolLSTM(nn.Module):
    def __init__(self, n_in, hidden=HIDDEN):
        super().__init__()
        self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
        self.drop = nn.Dropout(0.2)
        self.head = nn.Linear(hidden, 1)
    def forward(self, x):  # noqa: E301
        out, _ = self.lstm(x)
        return self.head(self.drop(out[:, -1])).squeeze(-1)

def fit(model, X, y, epochs, lr, seed):
    torch.manual_seed(seed)
    n_val = max(16, int(0.15 * len(X)))                 # validación = el tramo más reciente (respeta el tiempo)
    Xt, yt = torch.tensor(X[:-n_val]), torch.tensor(y[:-n_val])
    Xv, yv = torch.tensor(X[-n_val:]), torch.tensor(y[-n_val:])
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    best, best_state, wait, hist = np.inf, None, 0, []
    g = torch.Generator().manual_seed(seed)
    for ep in range(epochs):
        model.train()
        for idx in torch.randperm(len(Xt), generator=g).split(64):
            opt.zero_grad(); loss = nn.functional.mse_loss(model(Xt[idx]), yt[idx]); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vl = nn.functional.mse_loss(model(Xv), yv).item()
        hist.append(vl)
        if vl < best - 1e-5:
            best, best_state, wait = vl, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            wait += 1
            if wait >= 12:
                break
    model.load_state_dict(best_state)
    return model, hist

def scaler(X):
    mu = X[:, :, :5].reshape(-1, 5).mean(0); sd = X[:, :, :5].reshape(-1, 5).std(0) + 1e-8
    def tr(Z):  # noqa: E306
        Z = Z.copy(); Z[:, :, :5] = (Z[:, :, :5] - mu) / sd; return Z
    return tr

# COMMAND ----------

# MAGIC %md ## 3. Walk-forward
# MAGIC En cada corte: (a) LSTM entrenada solo con el diario previo al corte; (b) LSTM pre-entrenada con el intradía 2020-25 y ajustada con el diario previo.
# MAGIC Se pronostica el mes siguiente. Las líneas base se calculan con la misma información.

# COMMAND ----------

preds, curves = [], {}
for ci, cut in enumerate(CUTS):
    nxt = CUTS[ci + 1] if ci + 1 < len(CUTS) else R.index.max() + pd.Timedelta(days=1)
    tr_mask = (M_d.fin_objetivo < cut).values & ~np.isnan(y_d)
    te_mask = ((M_d.origen >= cut) & (M_d.origen < nxt)).values & ~np.isnan(y_d)
    if tr_mask.sum() < 100 or te_mask.sum() == 0:
        continue
    order = np.argsort(M_d.origen.values[tr_mask], kind="stable")
    Xtr, ytr = X_d[tr_mask][order], y_d[tr_mask][order]
    sc = scaler(Xtr)
    p_d, p_p = [], []
    for s in range(N_SEEDS):
        m1, h1 = fit(VolLSTM(X_d.shape[2]), sc(Xtr), ytr, EPOCHS, LR, SEED + s)
        m2, _ = fit(VolLSTM(X_d.shape[2]), sc(X_p), y_p, PRE_EPOCHS, LR, SEED + s)      # pre-entrenamiento
        m2, h2 = fit(m2, sc(Xtr), ytr, EPOCHS, LR / 4, SEED + s)                         # ajuste fino
        with torch.no_grad():
            m1.eval(); m2.eval()
            p_d.append(m1(torch.tensor(sc(X_d[te_mask]))).numpy()); p_p.append(m2(torch.tensor(sc(X_d[te_mask]))).numpy())
        if s == 0:
            curves[cut.date().isoformat()] = (h1, h2)
    dfp = M_d[te_mask].copy()
    dfp["corte"] = cut.date().isoformat()
    dfp["real"] = np.exp(y_d[te_mask])
    dfp["LSTM diario"] = np.exp(np.mean(p_d, axis=0))
    dfp["LSTM pre-entrenada"] = np.exp(np.mean(p_p, axis=0))
    dfp = dfp.join(B_d[te_mask])
    preds.append(dfp)
    print(f"corte {cut.date()}: train {tr_mask.sum():,} · test {te_mask.sum():,}")
P = pd.concat(preds, ignore_index=True)
MODELS = ["LSTM diario", "LSTM pre-entrenada", "EWMA 0.94", "Vol 21d", "Histórica"]

# COMMAND ----------

# MAGIC %md ## 4. Resultados: ¿la LSTM pronostica mejor?

# COMMAND ----------

def qlike(real, pred):
    r = (real / pred) ** 2
    return float(np.mean(r - np.log(r) - 1))

rng = np.random.default_rng(SEED)
rows = []
for mname in MODELS:
    q = qlike(P.real, P[mname]); rmse = float(np.sqrt(np.mean((P.real - P[mname]) ** 2)))
    rank = P.groupby("origen").apply(lambda g: stats.spearmanr(g.real, g[mname]).statistic if len(g) > 2 else np.nan).mean()
    # IC bootstrap por día de origen
    days = P.origen.unique()
    bs = []
    for _ in range(300):
        pick = rng.choice(days, len(days)); sub = P.set_index("origen").loc[pick]
        bs.append(qlike(sub.real.values, sub[mname].values))
    rows.append({"modelo": mname, "QLIKE": q, "QLIKE_ic90_lo": float(np.quantile(bs, .05)), "QLIKE_ic90_hi": float(np.quantile(bs, .95)),
                 "RMSE_vol": rmse, "ranking_spearman": float(rank)})
res = pd.DataFrame(rows)
q_ewma = res.set_index("modelo").loc["EWMA 0.94", "QLIKE"]
res["mejora_vs_EWMA"] = 1 - res.QLIKE / q_ewma
display(res.round(4))

fig, axes = plt.subplots(1, 3, figsize=(14, 3.9))
cols = [COLORS[m] for m in res.modelo]
axes[0].bar(res.modelo, res.QLIKE, color=cols,
            yerr=[res.QLIKE - res.QLIKE_ic90_lo, res.QLIKE_ic90_hi - res.QLIKE], capsize=3)
axes[0].set_title("QLIKE fuera de muestra (menor = mejor)\nbarras = IC90 bootstrap"); axes[0].tick_params(axis="x", rotation=30)
axes[1].bar(res.modelo, res.RMSE_vol, color=cols); axes[1].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
axes[1].set_title("Error en volatilidad anual (RMSE)"); axes[1].tick_params(axis="x", rotation=30)
axes[2].bar(res.modelo, res.ranking_spearman, color=cols); axes[2].set_ylim(0, 1)
axes[2].set_title("¿Ordena bien qué activo es más riesgoso?\n(Spearman entre activos, mismo día)"); axes[2].tick_params(axis="x", rotation=30)
fig.tight_layout()
if not ON_DBX:
    os.makedirs("outputs/lstm", exist_ok=True); fig.savefig("outputs/lstm/01_metricas.png", bbox_inches="tight")
plt.show(); plt.close(fig)

# COMMAND ----------

# pronóstico vs realidad para el NÚCLEO de CL_02 (promedio ponderado de los activos del núcleo)
vol_all = R.std() * ANN
core = vol_all[vol_all <= 0.30].index; w = (1 / vol_all[core]); w = w / w.sum()
Pc = P[P.asset_id.isin(core)].copy(); Pc["w"] = Pc.asset_id.map(w)
agg = Pc.groupby("origen").apply(lambda g: pd.Series({m: np.average(g[m], weights=g.w) for m in ["real"] + MODELS}))

fig, axes = plt.subplots(1, 2, figsize=(14, 3.9), gridspec_kw={"width_ratios": [2, 1]})
axes[0].plot(agg.index, agg.real, color="k", lw=2, label="volatilidad realizada (siguientes 21 días)")
for mname in MODELS:
    axes[0].plot(agg.index, agg[mname], color=COLORS[mname], lw=1.2, label=mname, alpha=0.9)
for c in CUTS:
    axes[0].axvline(c, color="#ccc", lw=0.8, ls=":")
axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1.0)); axes[0].legend(fontsize=7.5, ncol=3)
axes[0].set_title("Activos del núcleo: pronóstico de volatilidad vs realidad (fuera de muestra)")
name0 = list(curves)[-1]; h1, h2 = curves[name0]
axes[1].plot(h1, color=COLORS["LSTM diario"], label="LSTM diario"); axes[1].plot(h2, color=COLORS["LSTM pre-entrenada"], label="pre-entrenada (ajuste fino)")
axes[1].set_title(f"Pérdida de validación por época (corte {name0})"); axes[1].legend(fontsize=8); axes[1].set_xlabel("época")
fig.tight_layout()
if not ON_DBX:
    fig.savefig("outputs/lstm/02_pronostico_nucleo.png", bbox_inches="tight")
plt.show(); plt.close(fig)

# COMMAND ----------

# MAGIC %md ## 5. ¿Cambia la decisión de CL_02?
# MAGIC Una mejora estadística solo importa si cambia lo que haríamos. Revisamos dos cosas:
# MAGIC 1. **Núcleo:** ¿la LSTM elegiría activos distintos (vol pronosticada ≤ 30%)?
# MAGIC 2. **Exposición:** escalado por volatilidad, X = 20% × (vol de referencia / vol pronosticada), acotado a [10%, 30%]. ¿Se aleja del 20% fijo?

# COMMAND ----------

last = P[P.origen == P.origen.max()].set_index("asset_id")
best_lstm = res[res.modelo.str.startswith("LSTM")].sort_values("QLIKE").modelo.iloc[0]
core_lstm = last.index[last[best_lstm] <= 0.30].tolist()
core_hist = last.index[last["Histórica"] <= 0.30].tolist()
v_ref = float(np.average(last.loc[core, "Histórica"], weights=w))
v_lstm = float(np.average(last.loc[core, best_lstm], weights=w))
X_lstm = float(np.clip(0.20 * v_ref / v_lstm, 0.10, 0.30))
decision = pd.DataFrame({
    "aspecto": ["Mejor LSTM", "Núcleo con volatilidad histórica", f"Núcleo con {best_lstm}", "¿Cambia el núcleo?",
                "Vol pronosticada núcleo (histórica)", f"Vol pronosticada núcleo ({best_lstm})", "Exposición implicada", "¿Cambia la exposición (>2 pp)?"],
    "valor": [best_lstm, ", ".join(core_hist), ", ".join(core_lstm), str(set(core_hist) != set(core_lstm)),
              f"{v_ref:.1%}", f"{v_lstm:.1%}", f"{X_lstm:.0%} (vs 20% fijo)", str(abs(X_lstm - 0.20) > 0.02)]})
display(decision)

mejora = float(res.set_index("modelo").loc[best_lstm, "mejora_vs_EWMA"])
ic_hi = float(res.set_index("modelo").loc[best_lstm, "QLIKE_ic90_hi"])
cambia = (set(core_hist) != set(core_lstm)) or abs(X_lstm - 0.20) > 0.02
supera = mejora >= 0.10
best_base = res[~res.modelo.str.startswith("LSTM")].sort_values("QLIKE").iloc[0]
q_lstm = float(res.set_index("modelo").loc[best_lstm, "QLIKE"])
vs_best = 1 - q_lstm / float(best_base.QLIKE)
if supera and cambia and vs_best > 0:
    veredicto = "✅ H2 se sostiene: la LSTM mejora el pronóstico frente a todas las líneas base y cambia la decisión."
else:
    motivos = []
    motivos.append(f"supera a EWMA en {mejora:+.0%}" if supera else f"no supera a EWMA por ≥10% ({mejora:+.0%})")
    motivos.append(f"pero la línea base más simple ({best_base.modelo}) le gana ({vs_best:+.0%} de QLIKE)" if vs_best <= 0
                   else f"y supera a la mejor línea base ({best_base.modelo}) en {vs_best:+.0%}")
    motivos.append("y NO cambia la decisión de CL_02 (mismo núcleo, misma exposición)" if not cambia else "y sí cambia la decisión")
    veredicto = ("❌ H2 no se sostiene: la LSTM " + ", ".join(motivos) +
                 ". Con volatilidad casi constante, el mejor pronóstico es el promedio de largo plazo. Se mantiene la regla simple (núcleo por volatilidad + 20%).")
print(f"Mejor LSTM: {best_lstm} | mejora QLIKE vs EWMA: {mejora:+.1%} | vs mejor línea base: {1 - float(res.set_index('modelo').loc[best_lstm, 'QLIKE']) / float(res[~res.modelo.str.startswith('LSTM')].QLIKE.min()):+.1%} | ¿cambia decisión?: {cambia}")
print(veredicto)

# COMMAND ----------

if ON_DBX:
    for df_, name, cm in [(res, "etapa4_lstm_metricas", "Etapa 4: LSTM vs líneas base, pronóstico de vol 21d fuera de muestra (walk-forward)."),
                          (P.assign(origen=P.origen.astype(str), fin_objetivo=P.fin_objetivo.astype(str))
                            .rename(columns=lambda c: c.lower().replace(" ", "_").replace(".", "").replace("-", "_").replace("í", "i")),
                           "etapa4_lstm_predicciones",
                           "Etapa 4: predicciones de vol 21d por activo y día (LSTM y líneas base)."),
                          (decision.assign(veredicto=veredicto), "etapa4_lstm_decision", "Etapa 4: impacto de la LSTM en la decisión de CL_02 y veredicto de H2.")]:
        spark.createDataFrame(df_).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"credicorp_dq.gold.{name}")  # noqa: F821
        spark.sql(f"COMMENT ON TABLE credicorp_dq.gold.{name} IS '{cm}'")  # noqa: F821
        print("✓", name)
    try:
        import mlflow
        with mlflow.start_run(run_name="etapa4_lstm_vol_cl02"):
            mlflow.log_params({"seq_len": L, "horizon": H, "hidden": HIDDEN, "epochs": EPOCHS, "pre_epochs": PRE_EPOCHS,
                               "lr": LR, "n_seeds": N_SEEDS, "cuts": len(CUTS)})
            for _, r_ in res.iterrows():
                key = r_.modelo.replace(" ", "_").replace(".", "")
                mlflow.log_metric(f"qlike_{key}", r_.QLIKE); mlflow.log_metric(f"rmse_{key}", r_.RMSE_vol)
            mlflow.log_metric("mejora_vs_ewma", mejora)
            mlflow.set_tag("veredicto_H2", veredicto[:250])
        print("✓ MLflow run registrado")
    except Exception as e:  # MLflow es opcional
        print("MLflow no disponible:", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Cómo leer este resultado en el pitch
# MAGIC - **Si H2 no se sostiene:** "Probamos una LSTM, con y sin pre-entrenamiento en 5 años de historia, contra los estándares de la industria. Con criterios fijados de antemano no mejoró la decisión. En estos datos el riesgo no tiene rachas que anticipar, así que recomendamos la regla simple, que es más transparente, auditable y explicable para el cliente."
# MAGIC - **Si H2 se sostiene:** la exposición pasa a ser dinámica (X = 20% × vol objetivo / vol pronosticada), y se valida de nuevo en el simulador Monte Carlo (notebook `etapa3_simulador_montecarlo_cl02`).
# MAGIC
# MAGIC **Limitaciones:** hay un año de datos diarios sintéticos; el pre-entrenamiento usa una fuente que contradice al diario (solo aporta dinámica de volatilidad, no niveles de precio); y el intradía no tiene FX, así que se pre-entrena en USD.
