# Databricks notebook source
# MAGIC %md
# MAGIC # Simulador Monte Carlo — CL_02 (Patrimonio Estable)
# MAGIC
# MAGIC **Cómo usarlo:** cambia los controles (widgets) de arriba y pulsa **Run all**. Todo se recalcula: métricas, gráficos y la exposición recomendada.
# MAGIC
# MAGIC | Control | Qué cambia | Valor por defecto (perfil de CL_02) |
# MAGIC |---|---|---|
# MAGIC | `horizonte_meses` | Duración de cada simulación | **36** (`horizon_months` del perfil) |
# MAGIC | `exposicion` | % del patrimonio en el núcleo; `auto` = el máximo que cumple con la confianza elegida | auto |
# MAGIC | `confianza` | Probabilidad exigida de no superar el 10% de caída | 95% |
# MAGIC | `rebalanceo` | Cada cuánto se vuelve a la exposición objetivo | trimestral |
# MAGIC | `observacion_dd` | Con qué frecuencia "mira" el cliente su saldo: diaria (estricta) o mensual (estado de cuenta) | diaria |
# MAGIC | `retiro_30_mes6` | Aplica TW_02: retiro de 30% del patrimonio inicial en el mes 6 | si |
# MAGIC | `shock_inicial` | Aplica un shock del twist el día 1 | ninguno |
# MAGIC | `n_simulaciones` | Número de trayectorias Monte Carlo | 2000 |
# MAGIC | `deriva` | `cero` = quita la tendencia del año de muestra y deja solo el riesgo. `historica` = repite esa tendencia (núcleo +6,3%/año, equiponderada −2,1%/año), lo que **favorece al núcleo** | **cero** (coherente con que el retorno no persiste: ρ ≈ 0) |
# MAGIC
# MAGIC ## Métricas que mostramos (y por qué)
# MAGIC | # | Métrica | Pregunta que responde | Por qué es la correcta |
# MAGIC |---|---|---|---|
# MAGIC | 1 | **P(cumplir)** = % de simulaciones con caída máxima ≤ 10% | ¿Cumpliremos la promesa al cliente? | Es la tolerancia que el cliente declaró. Es la **métrica de decisión** |
# MAGIC | 2 | **Caída máxima típica (p50) y en el peor 5% (p95)** | ¿Cuánto podría llegar a caer? | Muestra el centro y la cola, no solo el promedio |
# MAGIC | 3 | **CVaR 95% de la caída** = caída promedio en el peor 5% de escenarios | Si sale mal, ¿qué tan mal? | Mide la severidad de la cola; es estándar en gestión de riesgo |
# MAGIC | 4 | **Patrimonio al final del horizonte en S/ (p5 / p50 / p95)** | ¿Con cuánto termina el cliente? | Traduce el riesgo a dinero en la moneda de reporte |
# MAGIC | 5 | **P(terminar con pérdida)** | ¿Qué tan probable es terminar abajo? | Responde a la prioridad "preservación + crecimiento moderado" |
# MAGIC | 6 | **Cobertura del retiro** = el retiro se paga con liquidez, sin vender acciones | ¿Puede retirar su 30% sin malvender? | Es la restricción nueva del twist (TW_02) |
# MAGIC | 7 | **Comparación con la equiponderada al 100%** (las mismas simulaciones) | ¿Qué ganamos frente al consejo ingenuo? | Es la línea base que hay que superar |
# MAGIC
# MAGIC **Método:** bootstrap por bloques de 10 días sobre los retornos diarios reales en COP (ago-25 → ago-26) de `credicorp_dq.silver`. Conserva las rachas y los co-movimientos entre activos.
# MAGIC Las trayectorias más largas que un año se arman encadenando bloques. **Moneda:** el riesgo se mide en COP; los montos se muestran en S/ al FX del 2026-08-14 (cruce constante).

# COMMAND ----------

import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

DEFAULTS = {"horizonte_meses": "36", "exposicion": "auto", "confianza": "95", "rebalanceo": "trimestral",
            "observacion_dd": "diaria", "retiro_30_mes6": "si", "shock_inicial": "ninguno", "n_simulaciones": "2000", "deriva": "cero"}
CHOICES = {"horizonte_meses": ["6", "12", "18", "24", "36"],
           "exposicion": ["auto", "10", "15", "20", "25", "30", "35", "40", "50", "70", "100"],
           "confianza": ["90", "95", "99"],
           "rebalanceo": ["ninguno", "mensual", "trimestral"],
           "observacion_dd": ["diaria", "semanal", "mensual"],
           "retiro_30_mes6": ["si", "no"],
           "shock_inicial": ["ninguno", "TW_03 COP -8%", "TW_01 estres (peor semana 2020-25)", "TW_01 + TW_03"],
           "n_simulaciones": ["1000", "2000", "5000"],
           "deriva": ["historica", "cero"]}

try:
    dbutils  # noqa: F821
    ON_DBX = True
    for k, v in DEFAULTS.items():
        dbutils.widgets.dropdown(k, v, CHOICES[k], k)  # noqa: F821
    P = {k: dbutils.widgets.get(k) for k in DEFAULTS}  # noqa: F821
except NameError:
    ON_DBX = False
    P = {**DEFAULTS, **json.loads(os.environ.get("SIM_PARAMS", "{}"))}
    def display(x):  # noqa: E301
        print(x.to_string() if isinstance(x, pd.DataFrame) else x)
print("Parámetros:", P)

H_M = int(P["horizonte_meses"]); T = 21 * H_M
CONF = int(P["confianza"]) / 100
REBAL = {"ninguno": 0, "mensual": 21, "trimestral": 63}[P["rebalanceo"]]
OBS = {"diaria": 1, "semanal": 5, "mensual": 21}[P["observacion_dd"]]
RETIRO = P["retiro_30_mes6"] == "si"
N_SIM = int(P["n_simulaciones"])
LIM, PATRIMONIO_PEN, SEED, BLOCK, HIGH_VOL = 0.10, 1_000_000, 7, 10, 0.30
DIA_RETIRO, MONTO_RETIRO = 126, 0.30
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})
C_PROP, C_EW = "#E45756", "#9D9D9D"

# COMMAND ----------

# --- datos ---
if ON_DBX:
    t = lambda n: spark.table(f"credicorp_dq.silver.{n}").toPandas()  # noqa: E731,F821
    prices, macro = t("market_prices_daily"), t("macro_daily")
    intra = (spark.table("credicorp_dq.silver.market_prices_intraday")  # noqa: F821
             .groupBy("asset_id", "date").agg({"close": "last"}).withColumnRenamed("last(close)", "close").toPandas())
else:
    import sys
    sys.path.insert(0, "src/analysis")
    import clean
    prices, macro = clean.prices_daily(), clean.macro_daily()
    intra = clean.prices_expanded_daily().rename(columns={"day": "date"})
prices["date"] = pd.to_datetime(prices["date"]); macro["date"] = pd.to_datetime(macro["date"])
intra["date"] = pd.to_datetime(intra["date"])
macro = macro.set_index("date").sort_index()
px_usd = prices.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
R = px_usd.mul(macro.usd_cop.astype(float), axis=0).pct_change().dropna()      # retornos diarios en COP
ASSETS = list(R.columns)
COP_POR_PEN = float(macro.usd_cop.iloc[-1]) / float(macro.usd_pen.iloc[-1])

vol = R.std() * np.sqrt(252)
core = vol[vol <= HIGH_VOL].index
w_core = (1 / vol[core]); w_core = (w_core / w_core.sum()).reindex(ASSETS).fillna(0.0)
r_core = R.values @ w_core.values
r_ew = R.values.mean(axis=1)
if P["deriva"] == "cero":            # quita la tendencia media: solo queda la volatilidad / co-movimiento
    r_core = r_core - r_core.mean(); r_ew = r_ew - r_ew.mean()
print(f"Retorno anual medio usado → núcleo {r_core.mean()*252:+.1%} | equiponderada {r_ew.mean()*252:+.1%} (deriva {P['deriva']})")

# shocks del twist (sobre el valor en COP de la parte invertida, día 1)
ir = intra.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
ir = ir[ir.index < px_usd.index.min()].pct_change().dropna()
worst_week_core = float(((ir[ASSETS] @ w_core.values).rolling(5).apply(lambda x: np.prod(1 + x) - 1)).min())
worst_week_ew = float((ir[ASSETS].mean(axis=1).rolling(5).apply(lambda x: np.prod(1 + x) - 1)).min())
SHOCK = {"ninguno": (0.0, 0.0), "TW_03 COP -8%": (0.08, 0.08),
         "TW_01 estres (peor semana 2020-25)": (worst_week_core, worst_week_ew),
         "TW_01 + TW_03": ((1 + worst_week_core) * 1.08 - 1, (1 + worst_week_ew) * 1.08 - 1)}[P["shock_inicial"]]
print("Núcleo:", {a: round(float(w), 3) for a, w in w_core[w_core > 0].items()})
print(f"Shock día 1 → núcleo {SHOCK[0]:+.1%} | equiponderada {SHOCK[1]:+.1%}")

# COMMAND ----------

# --- motor de simulación ---
rng = np.random.default_rng(SEED)
nb = int(np.ceil(T / BLOCK))
starts = rng.integers(0, len(R) - BLOCK + 1, size=(N_SIM, nb))
IDX = (starts[:, :, None] + np.arange(BLOCK)).reshape(N_SIM, -1)[:, :T]
RC, REW = r_core[IDX], r_ew[IDX]          # mismas trayectorias para propuesta y línea base

def simulate(X, rets, shock=0.0, retiro=RETIRO, rebal=REBAL, rebal_post_retiro=True):
    """Devuelve (valor del patrimonio T+1 x N en múltiplos del inicial, índice de rendimiento sin flujos, retiro_con_liquidez)."""
    n = rets.shape[0]
    E = np.full(n, X * (1 + shock)); C = np.full(n, 1 - X)
    V = np.empty((T + 1, n)); I = np.empty((T + 1, n))
    V[0] = 1.0; I[0] = 1.0
    cubierto = np.ones(n, bool)
    # el índice de rendimiento excluye el retiro (sacar dinero no es una pérdida); el shock del día 1 sí cuenta
    prev_v, idx_val = np.ones(n), np.ones(n)
    for t in range(T):
        E = E * (1 + rets[:, t])
        v_pre = E + C
        idx_val = idx_val * v_pre / prev_v
        if retiro and t + 1 == DIA_RETIRO:
            cubierto = C >= MONTO_RETIRO
            from_c = np.minimum(C, MONTO_RETIRO)
            C = C - from_c; E = E - (MONTO_RETIRO - from_c)
            if rebal_post_retiro:
                tot = E + C; E = np.minimum(E, X * tot); C = tot - E
        elif rebal and (t + 1) % rebal == 0:
            tot = E + C; E = X * tot; C = tot - E
        prev_v = E + C
        V[t + 1] = prev_v; I[t + 1] = idx_val
    return V, I, cubierto

def max_dd(I, obs=OBS):
    s = I[::obs]
    return (s / np.maximum.accumulate(s, axis=0) - 1).min(axis=0)

def p_cumple(X):
    _, I, _ = simulate(X, RC, SHOCK[0])
    return float((max_dd(I) >= -LIM).mean())

GRID = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.70, 1.00]
curve = pd.Series({x: p_cumple(x) for x in GRID})
X_auto = max([x for x in GRID if curve[x] >= CONF], default=min(GRID))
X = X_auto if P["exposicion"] == "auto" else int(P["exposicion"]) / 100
print(f"Exposición usada: {X:.0%} ({'auto: máxima con P(cumplir) ≥ ' + f'{CONF:.0%}' if P['exposicion']=='auto' else 'manual'})")

V, I, cubierto = simulate(X, RC, SHOCK[0])
Ve, Ie, _ = simulate(1.0, REW, SHOCK[1], retiro=RETIRO, rebal=0)
dd, dde = max_dd(I), max_dd(Ie)
fin_pen = V[-1] * PATRIMONIO_PEN; fin_pen_e = Ve[-1] * PATRIMONIO_PEN
ret_tot, ret_tot_e = I[-1] - 1, Ie[-1] - 1

def cvar(x, q=0.05):
    k = max(1, int(len(x) * q)); return float(np.sort(x)[:k].mean())

kpi = pd.DataFrame({
    "metrica": ["1. P(cumplir: caída máx ≤ 10%)", "2a. Caída máxima típica (p50)", "2b. Caída máxima peor 5% (p95)",
                "3. CVaR 95% de la caída", "4a. Patrimonio final p5 (S/)", "4b. Patrimonio final p50 (S/)",
                "4c. Patrimonio final p95 (S/)", "4d. Patrimonio final + retiro entregado p50 (S/)",
                "5. P(terminar con pérdida)", "6. Retiro pagado sin vender acciones"],
    "propuesta": [(dd >= -LIM).mean(), np.median(dd), np.quantile(dd, 0.05), cvar(dd),
                  np.quantile(fin_pen, .05), np.median(fin_pen), np.quantile(fin_pen, .95),
                  np.median(fin_pen) + (MONTO_RETIRO * PATRIMONIO_PEN if RETIRO else 0), (ret_tot < 0).mean(),
                  cubierto.mean() if RETIRO else np.nan],
    "equiponderada_100": [(dde >= -LIM).mean(), np.median(dde), np.quantile(dde, 0.05), cvar(dde),
                          np.quantile(fin_pen_e, .05), np.median(fin_pen_e), np.quantile(fin_pen_e, .95),
                          np.median(fin_pen_e) + (MONTO_RETIRO * PATRIMONIO_PEN if RETIRO else 0), (ret_tot_e < 0).mean(),
                          0.0 if RETIRO else np.nan],
})
def fmt(m, v):
    if pd.isna(v): return "—"
    return f"S/ {v:,.0f}" if "S/" in m else f"{v:.1%}"
kpi_view = kpi.assign(propuesta=[fmt(m, v) for m, v in zip(kpi.metrica, kpi.propuesta)],
                      equiponderada_100=[fmt(m, v) for m, v in zip(kpi.metrica, kpi.equiponderada_100)])
display(kpi_view)

# COMMAND ----------

# MAGIC %md ## Vista 1 — Tablero de métricas y trayectorias del patrimonio

# COMMAND ----------

months = np.arange(T + 1) / 21
step = OBS
fig = plt.figure(figsize=(13, 7.2))
gs = fig.add_gridspec(2, 3, height_ratios=[1, 2.3])
# KPIs
kp = fig.add_subplot(gs[0, :]); kp.axis("off")
p_ok = kpi.propuesta.iloc[0]
cards = [("P(cumplir ≤10%)", f"{p_ok:.0%}", "#2E7D32" if p_ok >= CONF else "#C62828", f"equiponderada: {kpi.equiponderada_100.iloc[0]:.0%}"),
         ("Caída máx. peor 5%", f"{kpi.propuesta.iloc[2]:.1%}", "#333", f"equiponderada: {kpi.equiponderada_100.iloc[2]:.1%}"),
         ("CVaR 95% caída", f"{kpi.propuesta.iloc[3]:.1%}", "#333", f"equiponderada: {kpi.equiponderada_100.iloc[3]:.1%}"),
         ("Final + retiro (p50)", f"S/ {kpi.propuesta.iloc[7]/1e3:,.0f}k", "#333", f"equiponderada: S/ {kpi.equiponderada_100.iloc[7]/1e3:,.0f}k"),
         ("P(terminar en pérdida)", f"{kpi.propuesta.iloc[8]:.0%}", "#333", f"equiponderada: {kpi.equiponderada_100.iloc[8]:.0%}")]
for i, (t_, v_, c_, s_) in enumerate(cards):
    x0 = i / len(cards) + 0.01
    kp.add_patch(plt.Rectangle((x0, 0.05), 1 / len(cards) - 0.02, 0.9, transform=kp.transAxes, fc="#F5F5F5", ec="#DDD"))
    kp.text(x0 + 0.01, 0.75, t_, transform=kp.transAxes, fontsize=9, color="#555")
    kp.text(x0 + 0.01, 0.38, v_, transform=kp.transAxes, fontsize=18, weight="bold", color=c_)
    kp.text(x0 + 0.01, 0.12, s_, transform=kp.transAxes, fontsize=7.5, color="#777")
kp.set_title(f"CL_02 · exposición {X:.0%} · horizonte {H_M} meses · rebalanceo {P['rebalanceo']} · caída observada {P['observacion_dd']}"
             f" · retiro {'sí' if RETIRO else 'no'} · shock: {P['shock_inicial']} · deriva {P['deriva']} · {N_SIM:,} sims", fontsize=10, loc="left")
# fan chart: rendimiento acumulado (excluye el retiro: sacar dinero no es perder)
ax = fig.add_subplot(gs[1, :2])
Ip, Ipe = I - 1, Ie - 1
for lo, hi, a in [(5, 95, 0.18), (25, 75, 0.35)]:
    ax.fill_between(months, np.percentile(Ip, lo, axis=1), np.percentile(Ip, hi, axis=1), color=C_PROP, alpha=a, lw=0,
                    label=f"propuesta: 90% / 50% de escenarios" if lo == 5 else None)
for j in range(30):
    ax.plot(months, Ip[:, j], color=C_PROP, lw=0.4, alpha=0.35)
ax.plot(months, np.median(Ip, axis=1), color=C_PROP, lw=2.2, label=f"propuesta {X:.0%} (mediana)")
ax.plot(months, np.percentile(Ipe, 5, axis=1), color="#666", lw=1, ls=":", label="equiponderada 100%: peor 5%")
ax.plot(months, np.median(Ipe, axis=1), color="#666", lw=1.5, ls="--", label="equiponderada 100%: mediana")
ax.axhline(0, color="k", lw=0.8)
ax.axhline(-LIM, color="k", ls="--", lw=0.8); ax.text(0.2, -LIM - 0.012, "−10% desde el inicio", fontsize=7.5)
if RETIRO and DIA_RETIRO <= T:
    ax.axvline(DIA_RETIRO / 21, color="k", ls=":", lw=1)
    ax.text(DIA_RETIRO / 21 + 0.3, 0.13, "mes 6: retiro de 30%\n(S/ 300 000, pagado\ncon liquidez)", fontsize=7.5, va="top")
lo_y = min(-0.25, float(np.percentile(Ip, 1)) - 0.03)
ax.set_ylim(lo_y, max(0.15, float(np.percentile(Ip, 99)) + 0.03))
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.set_xlabel("meses"); ax.set_title("Rendimiento acumulado simulado (sin contar el retiro)")
ax.legend(fontsize=7.5, loc="lower left", ncol=2)
# histograma de caída máxima
ax2 = fig.add_subplot(gs[1, 2])
bins = np.linspace(min(dde.min(), dd.min()), 0, 45)
ax2.hist(dde, bins=bins, color=C_EW, alpha=0.6, label="equiponderada 100%")
ax2.hist(dd, bins=bins, color=C_PROP, alpha=0.8, label=f"propuesta {X:.0%}")
ax2.axvline(-LIM, color="k", ls="--", lw=1.2); ax2.text(-LIM, ax2.get_ylim()[1] * 0.92, " límite −10%", fontsize=8)
ax2.xaxis.set_major_formatter(mtick.PercentFormatter(1.0)); ax2.legend(fontsize=7.5)
ax2.set_title("Caída máxima en el horizonte")
fig.tight_layout()
if not ON_DBX:
    os.makedirs("outputs/simulador", exist_ok=True)
    fig.savefig(f"outputs/simulador/tablero_{os.environ.get('SIM_TAG','default')}.png", bbox_inches="tight")
plt.show(); plt.close(fig)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Vista 2 — ¿Cuánto invertir según la periodicidad del cliente?
# MAGIC A la izquierda: la probabilidad de cumplir según la exposición, para el horizonte elegido.
# MAGIC A la derecha: el mapa completo **horizonte × exposición**, que muestra cómo un horizonte más largo exige invertir menos.

# COMMAND ----------

H_LIST = [6, 12, 18, 24, 36]
heat = pd.DataFrame(index=H_LIST, columns=GRID, dtype=float)
T_saved = T
for h in H_LIST:
    T = 21 * h
    RC_h = r_core[(rng.integers(0, len(R) - BLOCK + 1, size=(1000, int(np.ceil(T / BLOCK))))[:, :, None] + np.arange(BLOCK)).reshape(1000, -1)[:, :T]]
    for x in GRID:
        _, I_h, _ = simulate(x, RC_h, SHOCK[0])
        heat.loc[h, x] = float((max_dd(I_h) >= -LIM).mean())
T = T_saved

fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1, 1.25]})
axes[0].plot([g * 100 for g in GRID], curve.values, marker="o", color=C_PROP)
axes[0].axhline(CONF, color="k", ls="--", lw=1); axes[0].text(62, CONF + 0.015, f"confianza exigida {CONF:.0%}", fontsize=8)
axes[0].axvline(X * 100, color=C_PROP, ls=":"); axes[0].text(X * 100 + 1, 0.15, f"usada: {X:.0%}", color=C_PROP)
axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1.0)); axes[0].set_ylim(0, 1.03)
axes[0].set_xlabel("% invertido en el núcleo"); axes[0].set_ylabel("P(caída máx ≤ 10%)")
axes[0].set_title(f"Horizonte {H_M} meses")
im = axes[1].imshow(heat.values.astype(float), cmap="RdYlGn", vmin=0.5, vmax=1, aspect="auto")
axes[1].set_xticks(range(len(GRID)), [f"{g:.0%}" for g in GRID]); axes[1].set_yticks(range(len(H_LIST)), [f"{h} m" for h in H_LIST])
for i in range(len(H_LIST)):
    for j in range(len(GRID)):
        v = heat.values[i, j]
        axes[1].text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7.5,
                     color="k" if v > 0.7 else "w", weight="bold" if v >= CONF else None)
axes[1].set_xlabel("% invertido en el núcleo"); axes[1].set_ylabel("horizonte")
axes[1].set_title(f"P(cumplir) por horizonte y exposición (negrita ≥ {CONF:.0%})")
fig.colorbar(im, ax=axes[1], format=mtick.PercentFormatter(1.0), fraction=0.03)
fig.tight_layout()
if not ON_DBX:
    fig.savefig(f"outputs/simulador/periodicidad_{os.environ.get('SIM_TAG','default')}.png", bbox_inches="tight")
plt.show(); plt.close(fig)
x_by_h = {h: max([x for x in GRID if heat.loc[h, x] >= CONF], default=None) for h in H_LIST}
print("Exposición máxima con P(cumplir) ≥", f"{CONF:.0%}", "por horizonte:", {f"{h}m": (f"{x:.0%}" if x else "<10%") for h, x in x_by_h.items()})

# COMMAND ----------

# MAGIC %md ## Registro del escenario (para comparar corridas)

# COMMAND ----------

row = {**P, "exposicion_usada": X, **{m: float(v) if not pd.isna(v) else None for m, v in zip(kpi.metrica, kpi.propuesta)}}
log = pd.DataFrame([row]); log["run_ts"] = pd.Timestamp.utcnow().isoformat()
log.columns = [c.replace(" ", "_").replace(".", "").replace(":", "").replace("(", "").replace(")", "").replace("≤", "le")
               .replace("%", "pct").replace("/", "").replace(",", "") for c in log.columns]
display(log)
if ON_DBX:
    spark.createDataFrame(log).write.mode("append").option("mergeSchema", "true").saveAsTable("credicorp_dq.gold.etapa3_montecarlo_escenarios")  # noqa: F821
    spark.sql("COMMENT ON TABLE credicorp_dq.gold.etapa3_montecarlo_escenarios IS 'Etapa 3: cada corrida del simulador Monte Carlo de CL_02 (parámetros + métricas).'")  # noqa: F821

# COMMAND ----------

# MAGIC %md ## Asignación resultante (en S/)
# MAGIC Con los parámetros por defecto, esta es la **recomendación vigente** para el dashboard (`gold.etapa3_recomendacion_simulador`).

# COMMAND ----------

res_ret = MONTO_RETIRO if RETIRO else 0.0
alloc = pd.DataFrame({"bloque": ["Núcleo defensivo (acciones USD)", "Reserva retiro mes 6 (liquidez COP)", "Liquidez adicional (COP)"],
                      "pct_patrimonio": [X, res_ret, 1 - X - res_ret]})
det = (w_core[w_core > 0] * X).rename("pct_patrimonio").reset_index().rename(columns={"index": "asset_id"})
det["bloque"] = "Núcleo: " + det.asset_id
alloc = pd.concat([alloc, det[["bloque", "pct_patrimonio"]]], ignore_index=True)
alloc["monto_S/"] = (alloc.pct_patrimonio * PATRIMONIO_PEN).round(0)
alloc["parametros"] = json.dumps(P)
display(alloc)
if ON_DBX and all(P[k] == v for k, v in DEFAULTS.items()):
    spark.createDataFrame(alloc).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("credicorp_dq.gold.etapa3_recomendacion_simulador")  # noqa: F821
    spark.sql("COMMENT ON TABLE credicorp_dq.gold.etapa3_recomendacion_simulador IS 'Etapa 3: recomendación vigente CL_02 (horizonte 36m, 95%, deriva cero, retiro mes 6). Reemplaza a etapa3_recomendacion (horizonte 1 año).'")  # noqa: F821
    print("✓ credicorp_dq.gold.etapa3_recomendacion_simulador")
