# Databricks notebook source
# MAGIC %md
# MAGIC # Etapa 3 — La propuesta para CL_02, defendida punto por punto
# MAGIC
# MAGIC **Pregunta del reto:** ¿qué decisión de inversión recomendamos hoy a este cliente y qué evidencia nos permite defenderla?
# MAGIC
# MAGIC **Respuesta en una línea:** para CL_02 (Patrimonio Estable, COP, tolera caídas de hasta 10%), la decisión correcta no es *qué* acciones comprar sino **cuánto invertir**:
# MAGIC un núcleo defensivo elegido por volatilidad (A01, A04, A05, A08), con una exposición limitada y el resto en liquidez en COP, que incluye la reserva del 30% que el cliente retirará en 6 meses.
# MAGIC
# MAGIC | Sección | Qué defiende |
# MAGIC |---|---|
# MAGIC | 1. Cuestionar los datos | Qué datos usamos, cuáles descartamos y qué limitaciones tienen |
# MAGIC | 2. Métricas defendibles | Por qué medimos con drawdown y probabilidad de cumplir, y por qué elegimos por volatilidad |
# MAGIC | 3. Por qué CL_02 y no CL_01 ni CL_03 | El criterio de valor de la información |
# MAGIC | 4. La propuesta | Núcleo + exposición, validados sin mirar el futuro |
# MAGIC | 5. El twist | Cómo cambian la recomendación el retiro del 30%, el COP −8% y la tasa +65 pb |
# MAGIC | 6. Valor en S/ | Cuánto dinero protege la decisión |
# MAGIC | 7. Qué cambiaría la recomendación | Riesgos y supuestos |
# MAGIC
# MAGIC **Moneda:** el riesgo se mide en la moneda base del cliente (COP). Los montos se reportan en **soles (S/)** sobre un patrimonio de referencia de S/ 1 000 000.
# MAGIC **Fuente:** `credicorp_dq.silver.*`. **Salida:** `credicorp_dq.gold.etapa3_*`. Semilla fija (7), así que es reproducible.

# COMMAND ----------

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

SEED = 7
CAT = "credicorp_dq"
PATRIMONIO_PEN = 1_000_000
HIGH_VOL = 0.30            # umbral de "alta volatilidad" (supuesto explícito; ver sección 2)
CONF = 0.95                # confianza exigida para cumplir el límite de CL_02
N_BOOT, BLOCK = 2000, 10   # bootstrap por bloques de 10 días (conserva rachas y co-movimientos)
RETIRO = 0.30              # TW_02: CL_02 retira 30% en 6 meses
CUTS = pd.date_range("2025-12-01", "2026-06-01", freq="MS")  # cortes walk-forward
rng = np.random.default_rng(SEED)

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})
C_CL = {"CL_01": "#4C78A8", "CL_02": "#E45756", "CL_03": "#72B7B2"}
C_PROP, C_EW, C_GREY = "#E45756", "#9D9D9D", "#BBBBBB"

# --- modo dual: Databricks (silver) o local (réplica con clean.py) para pruebas ---
try:
    spark  # noqa: F821
    ON_DBX = True
except NameError:
    ON_DBX = False
    import sys
    sys.path.insert(0, "src/analysis")
    import clean
    def display(x):  # noqa: E301
        print(x.to_string() if isinstance(x, pd.DataFrame) else x)

def load():
    if ON_DBX:
        t = lambda n: spark.table(f"{CAT}.{n}").toPandas()  # noqa: E731,F821
        p, m = t("silver.market_prices_daily"), t("silver.macro_daily")
        ref, cl, f = t("silver.asset_reference"), t("silver.client_profiles"), t("silver.fundamentals")
        ev = t("silver.events")
        intra = (spark.table(f"{CAT}.silver.market_prices_intraday")  # noqa: F821
                 .groupBy("asset_id", "date").agg({"close": "last"}).withColumnRenamed("last(close)", "close")
                 .toPandas())
    else:
        p, m, ref, cl, f, ev = (clean.prices_daily(), clean.macro_daily(), clean.ref(), clean.clients(),
                                clean.fundamentals(), clean.events())
        intra = clean.prices_expanded_daily().rename(columns={"day": "date"})
    p["date"] = pd.to_datetime(p["date"]); m["date"] = pd.to_datetime(m["date"])
    intra["date"] = pd.to_datetime(intra["date"])
    f["period_end"] = pd.to_datetime(f["period_end"])
    ev["event_date"] = pd.to_datetime(ev["event_date"])
    return p, m.set_index("date").sort_index(), ref.set_index("asset_id"), cl.set_index("client_id"), f, ev, intra

prices, macro, ref, clients, fund, events, intra = load()
px_usd = prices.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
ASSETS = list(px_usd.columns)
FX = {"USD": pd.Series(1.0, index=macro.index), "COP": macro.usd_cop.astype(float), "PEN": macro.usd_pen.astype(float)}
px = {ccy: px_usd.mul(FX[ccy], axis=0) for ccy in FX}
rets = {ccy: px[ccy].pct_change().dropna() for ccy in FX}
FX_HOY = {"usd_pen": float(macro.usd_pen.iloc[-1]), "usd_cop": float(macro.usd_cop.iloc[-1])}
COP_POR_PEN = FX_HOY["usd_cop"] / FX_HOY["usd_pen"]
print(f"Datos: {px_usd.index.min().date()} → {px_usd.index.max().date()} | {len(px_usd)} días | {len(ASSETS)} activos")
print(f"FX al cierre: USD/PEN {FX_HOY['usd_pen']:.4f} | USD/COP {FX_HOY['usd_cop']:.2f} | COP por S/ {COP_POR_PEN:.2f}")

def save(df, name, comment):
    if not ON_DBX:
        return
    full = f"{CAT}.gold.{name}"
    spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(full)  # noqa: F821
    spark.sql(f"COMMENT ON TABLE {full} IS '{comment}'")  # noqa: F821
    spark.sql(f"ALTER TABLE {full} SET TAGS ('etapa'='3-find-the-value', 'owner'='fabrizio.vx', 'source'='silver')")  # noqa: F821
    print(f"✓ {full}")

def show(fig, name):
    fig.tight_layout()
    if not ON_DBX:
        import os
        os.makedirs("outputs/etapa3", exist_ok=True)
        fig.savefig(f"outputs/etapa3/{name}.png", bbox_inches="tight")
    plt.show()
    plt.close(fig)

# ---------- utilidades de cartera ----------
def max_dd(nav: np.ndarray) -> np.ndarray:
    """nav: T x K -> drawdown máximo por columna (negativo)."""
    return (nav / np.maximum.accumulate(nav, axis=0) - 1).min(axis=0)

def nav_bh(r: np.ndarray, w: np.ndarray) -> np.ndarray:
    """compra y mantenimiento: r = T x N retornos, w = N pesos -> NAV T (inicia en 1)."""
    growth = np.vstack([np.ones(r.shape[1]), np.cumprod(1 + r, axis=0)])
    return growth @ w

def block_bootstrap(r: np.ndarray, n_boot: int, block: int, rng) -> np.ndarray:
    """remuestrea bloques de días completos (todas las columnas juntas): n_boot x T x N."""
    T = r.shape[0]
    n_blocks = int(np.ceil(T / block))
    starts = rng.integers(0, T - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :T]
    return r[idx]

def inv_vol_weights(vol: pd.Series) -> pd.Series:
    w = 1 / vol
    return w / w.sum()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Cuestionar los datos: ¿qué estamos usando y cuánto podemos creerle?
# MAGIC
# MAGIC Antes de recomendar, verificamos cuatro preguntas sobre los datos. Una conclusión no puede ser más confiable que los datos que la sustentan.

# COMMAND ----------

# 1a. ¿Hay dos versiones de la verdad? diario vs intradía en el periodo común
both = prices[["asset_id", "date", "close"]].merge(intra[["asset_id", "date", "close"]], on=["asset_id", "date"],
                                                    suffixes=("_diario", "_intradia"))
both[["close_diario", "close_intradia"]] = both[["close_diario", "close_intradia"]].astype(float)
corr_src = (both.sort_values("date").groupby("asset_id")
            .apply(lambda g: g.close_diario.pct_change().corr(g.close_intradia.pct_change())))

fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
g = both[both.asset_id == "VF_A05"].sort_values("date")
axes[0].plot(g.date, g.close_diario, color=C_PROP, label="Diario (01_market_prices_raw)")
axes[0].plot(g.date, g.close_intradia, color=C_GREY, label="Intradía (expanded, cierre del día)")
axes[0].set_title("VF_A05: mismo activo, mismo día inicial… dos historias distintas")
axes[0].set_ylabel("USD"); axes[0].legend(fontsize=8)
axes[1].bar(corr_src.index, corr_src.values, color=C_GREY)
axes[1].axhline(1, ls="--", color="k", lw=0.8); axes[1].text(-0.4, 0.93, "si fueran la misma serie: 1,0", fontsize=8)
axes[1].set_ylim(-0.2, 1.05); axes[1].set_title("Correlación de retornos diarios: diario vs intradía")
show(fig, "01_fuentes")
print(f"Correlación media: {corr_src.mean():.2f} → son series independientes. Usamos el DIARIO (reacciona a 4/5 eventos vs 2/5).")

# COMMAND ----------

# MAGIC %md
# MAGIC **Qué muestra:** el diario y el intradía parten del mismo precio el 2025-08-01 y luego divergen; sus retornos tienen correlación ≈ 0.
# MAGIC **Decisión:** usamos el diario como fuente única. Se mueve en la dirección de 4 de 5 eventos, y el intradía en 2 de 5.
# MAGIC **Límite honesto:** solo la caída de A02 tras su evento operacional es estadísticamente significativa. La elección se apoya en la dirección, no en la significancia.

# COMMAND ----------

# 1b. ¿Cuánta información hay realmente? (tamaño de muestra e incertidumbre del drawdown)
r_cop = rets["COP"].values
w_ew = np.full(len(ASSETS), 1 / len(ASSETS))
boot = block_bootstrap(r_cop, N_BOOT, BLOCK, rng)
dd_ew_boot = np.array([max_dd(nav_bh(b, w_ew)[:, None])[0] for b in boot])
dd_ew_hist = max_dd(nav_bh(r_cop, w_ew)[:, None])[0]

# 1c. ¿Los retornos tienen colas gruesas? (si no, el riesgo real podría ser mayor que el simulado)
from scipy import stats
kurt = pd.Series(stats.kurtosis(r_cop, axis=0), index=ASSETS)
jb_p = pd.Series([stats.jarque_bera(r_cop[:, i]).pvalue for i in range(len(ASSETS))], index=ASSETS)

fig, axes = plt.subplots(1, 2, figsize=(12, 3.6))
axes[0].hist(dd_ew_boot, bins=40, color=C_GREY)
axes[0].axvline(dd_ew_hist, color="k", lw=1.2, label=f"histórico {dd_ew_hist:.1%}")
axes[0].axvline(-0.10, color=C_PROP, ls="--", label="límite CL_02 −10%")
axes[0].xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
axes[0].set_title("Con 1 año de datos, el drawdown es incierto\n(cartera equiponderada, 2000 réplicas bootstrap)")
axes[0].legend(fontsize=8)
axes[1].bar(ASSETS, kurt.values, color=[C_PROP if p < 0.05 else C_GREY for p in jb_p])
axes[1].set_title("Exceso de curtosis por activo (0 = normal)\nrojo = no normal (p<0,05)")
show(fig, "02_incertidumbre")
print(f"DD equiponderada: histórico {dd_ew_hist:.1%}; IC90 bootstrap [{np.quantile(dd_ew_boot,.05):.1%}, {np.quantile(dd_ew_boot,.95):.1%}]")
print(f"Activos con colas no normales (p<0,05): {int((jb_p<0.05).sum())}/8 → datos sintéticos ~gaussianos: el riesgo real podría ser MAYOR.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Inventario crítico de los datos
# MAGIC
# MAGIC | Dato | Lo que usamos | Lo que cuestionamos | Cómo lo mitigamos |
# MAGIC |---|---|---|---|
# MAGIC | Precios | Diario, 271 días (ago-25 → ago-26) | Un solo año, **sintético**; el intradía lo contradice | Bootstrap por bloques: medimos la incertidumbre en vez de confiar en un solo camino |
# MAGIC | Distribución | Retornos ~normales e independientes | Los mercados reales tienen colas gruesas | Exigimos 95% de confianza y probamos el peor escenario del intradía 2020-25 como estrés |
# MAGIC | Eventos | 5 eventos | n = 5; solo 1 significativo | Se usan como contexto, no como señal predictiva |
# MAGIC | Fundamentales | 8 trimestres × 8 emisores | Revenue ISS_06 2025-06-30 anómalo; cash ISS_07 nulo | Se excluyen de los ratios; los fundamentales solo **confirman**, no deciden |
# MAGIC | Macro | Tasa, FX, régimen | Tasa casi plana (−25 pb en el año) | No estimamos sensibilidad a tasas: usamos escenarios (sección 5) |
# MAGIC | Liquidez | No existe en el universo | Su rendimiento es desconocido | Supuesto conservador: rinde 0% |
# MAGIC | Perfil del cliente | Tolerancia 10%, máx. 25% en alta volatilidad, liquidez Media | "Alta volatilidad" no está definida | Umbral explícito de 30%, probado con 25% y 35% |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Métricas: cuáles son defendibles y por qué
# MAGIC
# MAGIC Una métrica es defendible si (a) mide lo que le importa al cliente y (b) **lo que medimos en el pasado se mantiene en el futuro**. Lo probamos.

# COMMAND ----------

pers = []
for c in CUTS:
    rr = rets["COP"]
    tr, te = rr[rr.index < c], rr[rr.index >= c]
    m_tr = {"Volatilidad": tr.std(), "Max drawdown": max_dd(np.cumprod(1 + tr.values, axis=0)),
            "Retorno": (1 + tr).prod().values - 1}
    m_te = {"Volatilidad": te.std(), "Max drawdown": max_dd(np.cumprod(1 + te.values, axis=0)),
            "Retorno": (1 + te).prod().values - 1}
    for k in m_tr:
        rho = stats.spearmanr(np.asarray(m_tr[k]), np.asarray(m_te[k])).statistic
        pers.append({"corte": c.date().isoformat(), "metrica": k, "spearman_train_test": float(rho)})
pers = pd.DataFrame(pers)
piv = pers.pivot(index="corte", columns="metrica", values="spearman_train_test")

fig, ax = plt.subplots(figsize=(10, 3.8))
for k, col in [("Volatilidad", C_PROP), ("Max drawdown", "#F58518"), ("Retorno", C_GREY)]:
    ax.plot(piv.index, piv[k], marker="o", color=col, label=k)
ax.axhline(0, color="k", lw=0.8)
ax.set_ylim(-1, 1.05)
ax.set_title("¿El ranking de activos en el pasado predice el ranking en el futuro?\n(correlación de Spearman train vs test, 7 cortes)")
ax.legend()
show(fig, "03_persistencia")
display(piv.round(2))
save(pers, "etapa3_metric_persistence", "Etapa 3: persistencia train->test del ranking de volatilidad, drawdown y retorno (7 cortes).")

# COMMAND ----------

# MAGIC %md
# MAGIC **Qué muestra:** el ranking de **volatilidad** se mantiene casi perfecto (ρ ≈ 0,93–0,98). El de **drawdown** es inestable y el de **retorno** es ruido (ρ ≈ 0).
# MAGIC **Consecuencia:** elegimos activos por la única métrica que el pasado predice, la volatilidad, y no por retornos ni caídas pasadas. Así evitamos el sesgo retrospectivo.
# MAGIC
# MAGIC | Métrica | ¿La usamos? | Para qué | Por qué es defendible / por qué no |
# MAGIC |---|---|---|---|
# MAGIC | **Max drawdown en COP** | ✅ Métrica objetivo | Medir si cumplimos la promesa al cliente | Es exactamente lo que el cliente declaró tolerar (10%). Se mide en **su** moneda |
# MAGIC | **P(cumplir) = P(DD ≤ 10%)** | ✅ Criterio de decisión | Elegir la exposición | Un año es un solo camino; la probabilidad (bootstrap) incorpora la incertidumbre. Exigimos 95% |
# MAGIC | **Exceso esperado sobre la tolerancia** | ✅ Elegir cliente | Medir el costo de la heurística ingenua | Mide cuánto se equivoca el consejo "reparte en partes iguales", en pp y en % de la tolerancia |
# MAGIC | **Volatilidad** | ✅ Selección de activos | Construir el núcleo | Es la única métrica persistente (ρ ≈ 0,95). Además, el perfil del cliente la menciona (máx. 25% en alta volatilidad) |
# MAGIC | **Pérdida evitada en S/** | ✅ Valor de negocio | Comunicar el impacto | Traduce pp a dinero en la moneda de reporte |
# MAGIC | Retorno esperado | ❌ No se optimiza | Solo se reporta | ρ ≈ 0: optimizarlo sería sobreajustar ruido |
# MAGIC | Sharpe | ❌ | — | Depende del retorno, que no es predecible con 1 año de datos |
# MAGIC | VaR diario | ❌ | — | El cliente no habla de pérdidas diarias sino de caída acumulada |
# MAGIC | Betas a tasa/FX | ❌ como señal | — | No son significativas (R² ≤ 5%); la tasa casi no se movió |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Por qué CL_02 y no CL_01 ni CL_03
# MAGIC
# MAGIC **Criterio formal (valor de la información):** elegimos al cliente donde la decisión basada en datos difiere más de la heurística ingenua ("reparte en partes iguales") y donde el error es más caro.
# MAGIC Lo medimos de tres formas: (1) qué fracción de carteras le sirve, (2) con qué probabilidad la heurística ingenua rompe su límite y (3) cuánto lo rompe.

# COMMAND ----------

N_PORT = 200_000
W = rng.dirichlet(np.full(len(ASSETS), 0.6), N_PORT)
vol_usd = rets["USD"].std() * np.sqrt(252)
HV_ASSETS = vol_usd[vol_usd > HIGH_VOL].index
sec, ctry = ref.loc[ASSETS, "sector"].values, ref.loc[ASSETS, "country"].values

def constraint_ok(cid, Wm):
    if cid == "CL_01":
        return pd.DataFrame(Wm, columns=sec).T.groupby(level=0).sum().T.values.max(axis=1) <= 0.45
    if cid == "CL_02":
        return Wm[:, np.isin(ASSETS, HV_ASSETS)].sum(axis=1) <= 0.25
    held = Wm > 0.05
    n_c = pd.DataFrame(held, columns=ctry).T.groupby(level=0).any().T.sum(axis=1).values
    n_s = pd.DataFrame(held, columns=sec).T.groupby(level=0).any().T.sum(axis=1).values
    return (n_c >= 3) & (n_s >= 3)

rows = []
for cid, c in clients.iterrows():
    ccy, tol = c.base_currency, float(c.max_drawdown_tolerance_pct) / 100
    r = rets[ccy].values
    nav = np.vstack([np.ones(len(ASSETS)), np.cumprod(1 + r, axis=0)]) @ W.T
    dd = max_dd(nav)
    ok = constraint_ok(cid, W)
    b = block_bootstrap(r, N_BOOT, BLOCK, np.random.default_rng(SEED))
    dd_b = np.array([max_dd(nav_bh(x, w_ew)[:, None])[0] for x in b])
    exceso = np.maximum(0, -dd_b - tol)
    rows.append({"client_id": cid, "perfil": c.profile_name, "moneda": ccy, "tolerancia": tol,
                 "pct_carteras_factibles": float((ok & (dd >= -tol)).mean()),
                 "dd_equiponderada_hist": float(max_dd(nav_bh(r, w_ew)[:, None])[0]),
                 "p_incumple_equiponderada": float((dd_b < -tol).mean()),
                 "exceso_esperado_pp": float(exceso.mean()),
                 "exceso_esperado_pct_tolerancia": float(exceso.mean() / tol)})
voi = pd.DataFrame(rows)
display(voi.round(4))
save(voi, "etapa3_client_choice", "Etapa 3: criterio de valor de la información por cliente (factibilidad, P incumplir y exceso de la equiponderada).")

fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
cols = [C_CL[c] for c in voi.client_id]
axes[0].bar(voi.client_id, voi.pct_carteras_factibles, color=cols)
axes[0].set_yscale("log"); axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=2))
axes[0].set_title("① % de 200k carteras que cumplen\nrestricción + drawdown (escala log)")
axes[1].bar(voi.client_id, voi.p_incumple_equiponderada, color=cols)
axes[1].yaxis.set_major_formatter(mtick.PercentFormatter(1.0)); axes[1].set_ylim(0, 1)
axes[1].set_title("② P(la equiponderada rompe\nel límite del cliente)")
axes[2].bar(voi.client_id, voi.exceso_esperado_pct_tolerancia, color=cols)
axes[2].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
axes[2].set_title("③ Exceso esperado sobre la tolerancia\n(% de lo que el cliente tolera)")
for ax in axes:
    for p_ in ax.patches:
        ax.annotate(f"{p_.get_height():.1%}" if p_.get_height() >= 0.001 else f"{p_.get_height():.2%}",
                    (p_.get_x() + p_.get_width() / 2, p_.get_height()), ha="center", va="bottom", fontsize=8)
show(fig, "04_eleccion_cliente")

# COMMAND ----------

# MAGIC %md
# MAGIC **Lectura:**
# MAGIC - **CL_01 (Crecimiento, USD, 22%):** 1 de cada 3 carteras le sirve y la heurística ingenua casi no se excede. El análisis **cambia poco** su decisión: es el caso más favorable, y por eso mismo el que menos valor demuestra.
# MAGIC - **CL_03 (Regional, PEN, 15%):** es un caso intermedio y una alternativa válida, pero tiene una tensión: sus mejores carteras se concentran en EE. UU. (A05), en contra de su objetivo de diversificación regional. Es el candidato #2.
# MAGIC - **CL_02 (Patrimonio Estable, COP, 10%):** casi ninguna cartera le sirve, y la heurística ingenua rompe su límite casi siempre y por mucho. Es el cliente que busca **preservar**, donde el error cuesta más. Además, **2 de los 3 shocks del twist** (retiro del 30% y COP −8%) apuntan a él.
# MAGIC
# MAGIC **Decisión: CL_02.** Es el cliente donde los datos cambian más la recomendación.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. La propuesta: núcleo por volatilidad + exposición limitada
# MAGIC
# MAGIC **Regla (sin mirar el futuro):**
# MAGIC 1. **Núcleo** = activos con volatilidad ≤ 30% en los datos disponibles a la fecha. Pesos **inversos a la volatilidad**: más peso al más estable. Así 0% queda en alta volatilidad (el límite es ≤ 25%).
# MAGIC 2. **Exposición X** = el mayor % invertido en el núcleo tal que **P(drawdown ≤ 10%) ≥ 95%**, estimada con bootstrap sobre los datos disponibles a la fecha.
# MAGIC 3. El resto, **(1 − X)**, queda en liquidez en COP.
# MAGIC
# MAGIC Primero validamos la regla en 7 cortes de tiempo (walk-forward). Después la aplicamos a hoy.

# COMMAND ----------

GRID = np.round(np.arange(0.10, 1.001, 0.05), 2)

def core_rule(r_train: pd.DataFrame):
    v = r_train.std() * np.sqrt(252)
    core = v[v <= HIGH_VOL].index
    return inv_vol_weights(v[core]).reindex(ASSETS).fillna(0.0)

def p_cumple_por_exposicion(r_train: np.ndarray, w: np.ndarray, rng_) -> pd.Series:
    b = block_bootstrap(r_train, N_BOOT, BLOCK, rng_)
    core_nav = np.stack([nav_bh(x, w) for x in b], axis=1)            # T x B
    out = {}
    for e in GRID:
        out[e] = float((max_dd((1 - e) + e * core_nav) >= -0.10).mean())
    return pd.Series(out)

def choose_exposure(pc: pd.Series) -> float:
    ok = pc[pc >= CONF]
    return float(ok.index.max()) if len(ok) else float(GRID.min())

wf = []
for c in CUTS:
    rr = rets["COP"]
    tr, te = rr[rr.index < c], rr[rr.index >= c]
    w = core_rule(tr)
    X = choose_exposure(p_cumple_por_exposicion(tr.values, w.values, np.random.default_rng(SEED)))
    # alternativa "ingenua informada": la cartera de menor DD en train entre 200k (lo que haría un optimizador)
    Wc = W[constraint_ok("CL_02", W)]
    nav_tr = np.vstack([np.ones(len(ASSETS)), np.cumprod(1 + tr.values, axis=0)]) @ Wc.T
    w_opt = Wc[int(np.argmax(max_dd(nav_tr)))]
    dd = lambda wv, e=1.0: float(max_dd(((1 - e) + e * nav_bh(te.values, wv))[:, None])[0])  # noqa: E731
    wf.append({"corte": c.date().isoformat(), "nucleo": ",".join(w[w > 0].index), "exposicion_X": X,
               "dd_test_propuesta": dd(w.values, X), "dd_test_equiponderada_X": dd(w_ew, X),
               "dd_test_nucleo_100": dd(w.values),
               "dd_test_optimizada_100": dd(w_opt), "dd_test_equiponderada": dd(w_ew)})
wf = pd.DataFrame(wf)
for k in ["propuesta", "equiponderada_X", "nucleo_100", "optimizada_100", "equiponderada"]:
    wf[f"cumple_{k}"] = wf[f"dd_test_{k}"] >= -0.10
display(wf)
save(wf, "etapa3_walkforward", "Etapa 3: walk-forward de 7 cortes. Propuesta (núcleo por volatilidad + exposición al 95%) vs alternativas.")

fig, ax = plt.subplots(figsize=(11, 4.6))
xs = np.arange(len(wf)); wdt = 0.16
for i, (k, lab, col) in enumerate([("propuesta", "Propuesta (núcleo × X)", C_PROP),
                                   ("equiponderada_X", "Equiponderada × X (misma exposición)", "#B279A2"),
                                   ("nucleo_100", "Núcleo al 100%", "#F58518"),
                                   ("optimizada_100", "Optimizada en train al 100%", "#4C78A8"),
                                   ("equiponderada", "Equiponderada al 100%", C_EW)]):
    ax.bar(xs + (i - 2) * wdt, wf[f"dd_test_{k}"], wdt, label=f"{lab}: cumple {wf[f'cumple_{k}'].sum()}/{len(wf)}", color=col)
ax.axhline(-0.10, color="k", ls="--", lw=1); ax.text(len(wf) - 0.6, -0.095, "límite −10%", fontsize=8)
ax.set_xticks(xs, wf.corte, rotation=0, fontsize=8)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.set_title("Drawdown FUERA de muestra (en COP) según la fecha de decisión\nla propuesta se decide solo con datos anteriores a cada corte")
ax.legend(fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
show(fig, "05_walkforward")
gap = (wf.dd_test_propuesta - wf.dd_test_equiponderada_X)
print(f"A igual exposición, el núcleo cae en promedio {gap.mean():+.1%} menos que la equiponderada (positivo = mejor); mejor en {int((gap>0).sum())}/{len(wf)} cortes.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Qué muestra:** en cada fecha de decisión aplicamos la regla solo con el pasado y medimos el drawdown en el periodo siguiente.
# MAGIC Optimizar los pesos al 100% (azul) y usar el núcleo al 100% (naranja) **no cumplen**. La propuesta, que dimensiona la exposición, **sí cumple**.
# MAGIC La palanca robusta es la **exposición**, no la selección fina de pesos.
# MAGIC
# MAGIC **Prueba justa ("¿no pierde menos solo porque invierte menos?"):** la barra morada invierte el **mismo X** pero repartido en partes iguales entre los 8 activos.
# MAGIC La diferencia entre la roja y la morada es el aporte de **elegir el núcleo por volatilidad**. La diferencia entre la morada y la gris es el aporte de **dimensionar la exposición**.
# MAGIC
# MAGIC **Resultado honesto:** a igual exposición, la equiponderada también cumple en 6 de 7 cortes. **La mayor parte del valor viene de decidir cuánto invertir.**
# MAGIC El núcleo por volatilidad agrega un margen menor pero **consistente**: cae ~0,7 pp menos en 7 de 7 cortes, y en dic-25 marca la diferencia entre cumplir y no cumplir.
# MAGIC Por eso el mensaje del pitch es "la decisión es la exposición"; el núcleo es la forma más segura de ejecutarla y no la fuente principal del valor.

# COMMAND ----------

# Aplicación HOY (2026-08-14), con todos los datos disponibles
r_all = rets["COP"]
w_hoy = core_rule(r_all)
pc_hoy = p_cumple_por_exposicion(r_all.values, w_hoy.values, np.random.default_rng(SEED))
X_star = choose_exposure(pc_hoy)
print("Núcleo hoy (pesos inversos a la volatilidad):")
display((w_hoy[w_hoy > 0] * 100).round(1).to_frame("peso_%_del_nucleo").join(ref[["name", "sector", "country"]]))
print(f"Exposición máxima con P(DD≤10%) ≥ {CONF:.0%}: X* = {X_star:.0%}")

fig, ax = plt.subplots(figsize=(9, 3.8))
ax.plot(pc_hoy.index, pc_hoy.values, marker="o", color=C_PROP)
ax.axhline(CONF, color="k", ls="--", lw=1); ax.text(0.11, CONF + 0.01, f"confianza exigida {CONF:.0%}", fontsize=8)
ax.axvline(X_star, color=C_PROP, ls=":", lw=1.2); ax.text(X_star + 0.01, 0.3, f"X* = {X_star:.0%}", color=C_PROP)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0)); ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.set_xlabel("% del patrimonio invertido en el núcleo (resto en liquidez COP)")
ax.set_ylabel("P(drawdown ≤ 10%)")
ax.set_title("¿Cuánto invertir? Probabilidad de respetar el límite de CL_02 según la exposición")
show(fig, "06_curva_exposicion")
save(pc_hoy.rename_axis("exposicion").reset_index(name="p_cumple"), "etapa3_exposure_curve",
     "Etapa 3: P(DD<=10% en COP) vs exposición al núcleo, bootstrap por bloques (2000 réplicas).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Los fundamentales confirman el núcleo (no lo eligen)
# MAGIC Elegimos por volatilidad. Los fundamentales sirven como **chequeo de sanidad**: ninguna empresa del núcleo debería tener un deterioro grave.

# COMMAND ----------

f = fund.sort_values(["issuer_id", "period_end"]).copy()
for k in ["revenue_usd_m", "ebitda_usd_m", "net_income_usd_m", "debt_usd_m", "cash_usd_m"]:
    f[k] = pd.to_numeric(f[k], errors="coerce")
f["ebitda_ltm"] = f.groupby("issuer_id").ebitda_usd_m.transform(lambda s: s.rolling(4).sum())
f["nd_ebitda_ltm"] = (f.debt_usd_m - f.cash_usd_m) / f.ebitda_ltm
fz = f.groupby("issuer_id").agg(nd_ebitda_ltm=("nd_ebitda_ltm", "last"),
                                ni_yoy=("net_income_usd_m", lambda s: s.iloc[-1] / s.iloc[-5] - 1))
fz.index = [ref.index[ref.issuer_id == i][0] for i in fz.index]
fz["en_nucleo"] = fz.index.isin(w_hoy[w_hoy > 0].index)
display(fz.round(2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. El twist (vigente desde 2026-08-17)
# MAGIC
# MAGIC | Shock | Qué cambia para CL_02 | Cómo lo incorporamos |
# MAGIC |---|---|---|
# MAGIC | **TW_02**: retira 30% en 6 meses | La liquidez pasa a ser una **restricción dura**. Si ese 30% sale de la liquidez, el % invertido del saldo restante **sube** | Reserva de 30% en COP, intocable. Invertir hoy ≤ (1 − 30%) × X* para que, tras el retiro, la exposición siga ≤ X* |
# MAGIC | **TW_03**: COP −8% vs USD | Las acciones (en USD) suben en COP; la liquidez en COP no se mueve | La reserva se queda en **COP**: el retiro es en COP y tenerla en USD añadiría riesgo cambiario |
# MAGIC | **TW_01**: tasa 10Y +65 pb | El dato histórico no permite estimar la sensibilidad (la tasa casi no se movió) | Escenarios de estrés sobre el núcleo (abajo) |

# COMMAND ----------

X_hoy = round((1 - RETIRO) * X_star, 4)
liq = 1 - X_hoy
alloc = pd.DataFrame({
    "bloque": ["Núcleo defensivo (acciones USD)", "Reserva retiro 6 meses (liquidez COP)", "Liquidez adicional (COP)"],
    "pct_patrimonio": [X_hoy, RETIRO, liq - RETIRO],
})
alloc["monto_S/"] = (alloc.pct_patrimonio * PATRIMONIO_PEN).round(0)
detalle = (w_hoy[w_hoy > 0] * X_hoy).rename("pct_patrimonio").to_frame().join(ref[["name", "sector", "country"]])
detalle["monto_S/"] = (detalle.pct_patrimonio * PATRIMONIO_PEN).round(0)
print(f"RECOMENDACIÓN HOY: invertir {X_hoy:.1%} en el núcleo (= 70% × X* {X_star:.0%}); {liq:.1%} en liquidez COP (incluye 30% de reserva).")
display(alloc); display(detalle)
save(alloc, "etapa3_recomendacion", "Etapa 3: asignación recomendada para CL_02 en S/ (patrimonio de referencia S/ 1 000 000).")
save(detalle.reset_index().rename(columns={"index": "asset_id"}), "etapa3_recomendacion_activos",
     "Etapa 3: detalle por activo del núcleo recomendado para CL_02 en S/.")

# escenarios de estrés sobre el núcleo (en COP)
core_ret = (r_all * w_hoy).sum(axis=1)
worst_week_daily = float(core_ret.rolling(5).apply(lambda x: np.prod(1 + x) - 1).min())
st = macro.index[macro.risk_regime == "Stress"]
stress_rep = float(np.prod(1 + core_ret.loc[st.min():st.max()]) - 1)
intra_px = intra.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
intra_hist = intra_px[intra_px.index < px_usd.index.min()]
ir = intra_hist.pct_change().dropna()
core_i = (ir[w_hoy.index] * w_hoy).sum(axis=1)
worst_week_intra = float(core_i.rolling(5).apply(lambda x: np.prod(1 + x) - 1).min())
esc = pd.DataFrame({
    "escenario": ["TW_01 ≈ repetición del Stress feb-26", "TW_01 ≈ peor semana del diario", "TW_01 ≈ peor semana intradía 2020-25",
                  "TW_03: COP −8% (efecto en COP)"],
    "shock_nucleo": [stress_rep, worst_week_daily, worst_week_intra, 0.08],
})
esc["impacto_patrimonio_propuesta"] = esc.shock_nucleo * X_hoy
esc["impacto_patrimonio_equiponderada"] = [np.nan, np.nan, np.nan, 0.08]
esc["impacto_S/_propuesta"] = (esc.impacto_patrimonio_propuesta * PATRIMONIO_PEN).round(0)
display(esc)
save(esc, "etapa3_twist_escenarios", "Etapa 3: escenarios del twist sobre la propuesta de CL_02 (impacto en patrimonio y en S/).")

fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
axes[0].barh(alloc.bloque, alloc.pct_patrimonio, color=[C_PROP, "#F2CF5B", "#C9E7E5"])
for i, (pp, s) in enumerate(zip(alloc.pct_patrimonio, alloc["monto_S/"])):
    axes[0].text(pp + 0.01, i, f"{pp:.0%} · S/ {s:,.0f}", va="center", fontsize=9)
axes[0].xaxis.set_major_formatter(mtick.PercentFormatter(1.0)); axes[0].set_xlim(0, 0.9)
axes[0].set_title("Recomendación para CL_02 (patrimonio S/ 1 000 000)")
e3 = esc.iloc[:3]
axes[1].barh(e3.escenario, e3.impacto_patrimonio_propuesta, color=C_PROP, label="Propuesta")
axes[1].barh(e3.escenario, e3.shock_nucleo, color=C_GREY, alpha=0.45, label="Núcleo al 100%")
axes[1].axvline(-0.10, color="k", ls="--", lw=1)
axes[1].xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
axes[1].set_title("TW_01: estrés sobre el patrimonio (límite −10%)"); axes[1].legend(fontsize=8)
show(fig, "07_recomendacion_twist")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Valor en soles: ¿cuánto protege la decisión?
# MAGIC Comparamos, en las mismas 2000 trayectorias simuladas, el drawdown de la propuesta frente al consejo ingenuo (equiponderada al 100%).
# MAGIC **Pérdida evitada** = (DD equiponderada − DD propuesta) × patrimonio, en S/. Mide cuánto menos cae el patrimonio en su peor momento.
# MAGIC
# MAGIC También reportamos (a) la equiponderada con la **misma exposición**, para no atribuir todo el valor a "invertir menos", y (b) el **costo de oportunidad**: el retorno mediano que se resigna.

# COMMAND ----------

b_all = block_bootstrap(r_all.values, N_BOOT, BLOCK, np.random.default_rng(SEED + 1))
dd_prop = np.array([max_dd(((1 - X_hoy) + X_hoy * nav_bh(x, w_hoy.values))[:, None])[0] for x in b_all])
dd_ewb = np.array([max_dd(nav_bh(x, w_ew)[:, None])[0] for x in b_all])
dd_ewx = np.array([max_dd(((1 - X_hoy) + X_hoy * nav_bh(x, w_ew))[:, None])[0] for x in b_all])
ret_prop = np.array([((1 - X_hoy) + X_hoy * nav_bh(x, w_hoy.values))[-1] - 1 for x in b_all])
ret_ewb = np.array([nav_bh(x, w_ew)[-1] - 1 for x in b_all])
evitada = (dd_prop - dd_ewb) * PATRIMONIO_PEN
val = pd.DataFrame({
    "metrica": ["P(cumple DD≤10%) propuesta", "P(cumple DD≤10%) equiponderada 100%", "P(cumple DD≤10%) equiponderada misma exposición",
                "DD mediano propuesta", "DD mediano equiponderada 100%", "DD mediano equiponderada misma exposición",
                "Pérdida evitada mediana S/", "Pérdida evitada escenario adverso (p90) S/",
                "Retorno mediano 1 año propuesta", "Retorno mediano 1 año equiponderada 100%"],
    "valor": [float((dd_prop >= -0.10).mean()), float((dd_ewb >= -0.10).mean()), float((dd_ewx >= -0.10).mean()),
              float(np.median(dd_prop)), float(np.median(dd_ewb)), float(np.median(dd_ewx)),
              float(np.median(evitada)), float(np.quantile(evitada, 0.90)),
              float(np.median(ret_prop)), float(np.median(ret_ewb))],
})
display(val)
save(val, "etapa3_valor", "Etapa 3: valor de la propuesta vs equiponderada en S/ (bootstrap 2000 réplicas).")

fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
axes[0].hist(dd_ewb, bins=40, color=C_EW, alpha=0.7, label="Equiponderada 100%")
axes[0].hist(dd_prop, bins=40, color=C_PROP, alpha=0.8, label=f"Propuesta ({X_hoy:.0%} núcleo)")
axes[0].axvline(-0.10, color="k", ls="--", lw=1)
axes[0].xaxis.set_major_formatter(mtick.PercentFormatter(1.0)); axes[0].legend(fontsize=8)
axes[0].set_title("Distribución del drawdown en COP (2000 escenarios)")
axes[1].hist(evitada, bins=40, color=C_PROP)
axes[1].axvline(np.median(evitada), color="k", lw=1.2)
axes[1].text(np.median(evitada), axes[1].get_ylim()[1] * 0.9, f"  mediana S/ {np.median(evitada):,.0f}", fontsize=9)
axes[1].xaxis.set_major_formatter(mtick.StrMethodFormatter("S/ {x:,.0f}"))
axes[1].set_title("Pérdida evitada vs equiponderada, por S/ 1 000 000")
show(fig, "08_valor")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. ¿Qué cambiaría la recomendación? (y cuál es el costo)
# MAGIC
# MAGIC | Riesgo / supuesto | Efecto | Qué haríamos |
# MAGIC |---|---|---|
# MAGIC | **Costo de oportunidad:** con poca exposición, CL_02 gana menos si el mercado sube | Es el precio de cumplir su límite | Es coherente con su prioridad: "preservación + crecimiento moderado" |
# MAGIC | Colas gruesas reales (los datos sintéticos son ~normales) | El riesgo real es mayor que el simulado | Exigimos 95% de confianza y probamos el estrés intradía 2020-25 |
# MAGIC | Un nuevo episodio de Stress o la tasa +65 pb | Caída del núcleo | Ya está en los escenarios; con la exposición propuesta el impacto queda dentro del límite |
# MAGIC | Un cliente que acepte una tolerancia mayor | Permite más exposición | La curva de la sección 4 da la exposición para cualquier tolerancia |
# MAGIC | "Alta volatilidad" definida en 25% | A04 sale del núcleo | La regla se recalcula sola; probado en el reporte de ciencia de datos |
# MAGIC | La liquidez rinde > 0% | La propuesta mejora | El supuesto de 0% es conservador |
# MAGIC
# MAGIC **Recomendación final para CL_02:** invertir hoy solo la parte calculada arriba en el núcleo defensivo (A05, A08, A01, A04, con pesos inversos a la volatilidad), mantener la reserva del 30% en COP para el retiro de 6 meses y el resto en liquidez en COP. Revisar trimestralmente: si la volatilidad del núcleo baja o el cliente amplía su tolerancia, subir la exposición siguiendo la curva.
