"""Gráficos de la presentación (paleta del evento): qué ocurre, curva de exposición a 36 m, pérdida evitada y arquitectura.
Uso: .venv/bin/python src/analysis/pitch_graficos.py → docs/img/pitch/"""
import sys, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
sys.path.insert(0, "src/analysis"); import clean
NAVY, RED, BLUE, GREY, LIGHT = "#141B2D", "#E5482D", "#2F6BDB", "#9AA3AF", "#EEF0F4"
OUT = "docs/img/pitch/"
plt.rcParams.update({"figure.dpi": 160, "axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
                     "axes.edgecolor": "#555", "axes.titleweight": "bold", "axes.titlesize": 13})
p, m = clean.prices_daily(), clean.macro_daily(); p["date"] = pd.to_datetime(p.date); m["date"] = pd.to_datetime(m.date); m = m.set_index("date")
px = p.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
pc = px.mul(m.usd_cop.astype(float), axis=0); R = pc.pct_change().dropna()
names = {"VF_A01": "A01 Consumo CO", "VF_A02": "A02 Tecnología PE", "VF_A03": "A03 Energía CO", "VF_A04": "A04 Financiero PE",
         "VF_A05": "A05 Salud US", "VF_A06": "A06 Industrial MX", "VF_A07": "A07 Materiales CL", "VF_A08": "A08 Utilities US"}
vol = R.std() * np.sqrt(252); core = vol[vol <= .30].index
w = (1 / vol[core]); w = (w / w.sum()).reindex(R.columns).fillna(0)

# 1. Qué está ocurriendo: caída máxima y retorno por activo (COP)
nav = (1 + R).cumprod(); dd = (nav / nav.cummax() - 1).min(); ret = nav.iloc[-1] - 1
ew = (1 + R.mean(axis=1)).cumprod(); dd_ew = float((ew / ew.cummax() - 1).min())
o = dd.sort_values()
fig, ax = plt.subplots(figsize=(8, 4.6))
cols = [BLUE if a in core else RED for a in o.index]
ax.barh([names[a] for a in o.index], o.values * 100, color=cols)
ax.barh(["Equiponderada (8 activos)"], [dd_ew * 100], color=GREY)
ax.axvline(-10, color=NAVY, ls="--", lw=1.5); ax.text(-10.3, 8.6, "límite CL_02: −10%", ha="right", fontsize=10, color=NAVY, weight="bold")
for i, a in enumerate(o.index):
    ax.text(o[a] * 100 + .6, i, f"{o[a]:.0%}  (ret. {ret[a]:+.0%})", va="center", ha="left", fontsize=8.5, color="white", weight="bold")
ax.text(dd_ew * 100 + .6, 8, f"{dd_ew:.0%}", va="center", ha="left", fontsize=9, color="white", weight="bold")
ax.set_xlabel("caída máxima en el año, en COP (%)"); ax.set_title("Ningún activo, solo, respeta el −10% de CL_02", loc="left")
ax.set_xlabel("caída máxima en el año, en COP (%)\nazul = núcleo defensivo (vol ≤ 30%) · rojo = alta volatilidad")
fig.tight_layout(); fig.savefig(OUT + "01_que_ocurre.png", transparent=False); plt.close(fig)
print("dd", dd.round(3).to_dict(), "ew", round(dd_ew, 3), "ret", ret.round(3).to_dict())

# 2. Curva de exposición por horizonte (Monte Carlo, bloques de 10 días, deriva 0, retiro mes 6, rebalanceo trimestral)
rc = R.values @ w.values; rc = rc - rc.mean(); rew = R.values.mean(1); rew = rew - rew.mean()
N, B = 2000, 10; rng = np.random.default_rng(7)
def sim(r, X, T, retiro=True, rebal=63):
    nb = int(np.ceil(T / B)); st = rng.integers(0, len(r) - B + 1, size=(N, nb)); idx = (st[:, :, None] + np.arange(B)).reshape(N, -1)[:, :T]
    rets = r[idx]; E = np.full(N, X); C = np.full(N, 1 - X); I = np.ones(N); prev = np.ones(N); peak = np.ones(N); mdd = np.zeros(N)
    for t in range(T):
        E = E * (1 + rets[:, t]); v = E + C; I = I * v / prev
        peak = np.maximum(peak, I); mdd = np.minimum(mdd, I / peak - 1)
        if retiro and t + 1 == 126:
            fc = np.minimum(C, .3); C = C - fc; E = E - (.3 - fc); tot = E + C; E = np.minimum(E, X * tot); C = tot - E
        elif rebal and (t + 1) % rebal == 0:
            tot = E + C; E = X * tot; C = tot - E
        prev = E + C
    return I, mdd
grid = [.1, .15, .2, .25, .3, .35, .4, .5, .7, 1.0]
fig, ax = plt.subplots(figsize=(8, 4.6))
for H, c in [(6, "#9DB8F0"), (12, BLUE), (36, RED)]:
    pc_ = [float((sim(rc, x, 21 * H)[1] >= -.1).mean()) for x in grid]
    ax.plot(np.array(grid) * 100, np.array(pc_) * 100, "o-", color=c, lw=2.2, label=f"horizonte {H} meses")
ax.axhline(95, color=NAVY, ls="--", lw=1.2); ax.text(99, 96, "confianza exigida 95%", ha="right", fontsize=9, color=NAVY)
ax.axvline(20, color=RED, ls=":", lw=1.5); ax.annotate("20% a 36 meses", (20, 95.7), xytext=(32, 70), color=RED, weight="bold",
                                                      arrowprops=dict(arrowstyle="->", color=RED))
ax.set_xlabel("% del patrimonio en el núcleo de acciones"); ax.set_ylabel("P(caída ≤ 10%)  %")
ax.set_title("¿Cuánto invertir? A más horizonte, menos exposición", loc="left"); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(OUT + "02_curva_exposicion_36m.png"); plt.close(fig)

# 3. Pérdida evitada a 36 meses (mismas trayectorias)
rng = np.random.default_rng(7); T = 756
nb = int(np.ceil(T / B)); st = rng.integers(0, len(R) - B + 1, size=(N, nb)); idx = (st[:, :, None] + np.arange(B)).reshape(N, -1)[:, :T]
def path(r, X, rebal):
    rets = r[idx]; E = np.full(N, X); C = np.full(N, 1 - X); I = np.ones(N); prev = np.ones(N); peak = np.ones(N); mdd = np.zeros(N)
    for t in range(T):
        E = E * (1 + rets[:, t]); v = E + C; I = I * v / prev; peak = np.maximum(peak, I); mdd = np.minimum(mdd, I / peak - 1)
        if t + 1 == 126:
            fc = np.minimum(C, .3); C = C - fc; E = E - (.3 - fc); tot = E + C; E = np.minimum(E, X * tot); C = tot - E
        elif rebal and (t + 1) % 63 == 0:
            tot = E + C; E = X * tot; C = tot - E
        prev = E + C
    return I, mdd
Ip, ddp = path(rc, .2, True); Ie, dde = path(rew, 1.0, False)
gap_dd = (ddp - dde) * 1e6        # caída evitada en S/ por cada S/ 1 M
print("P(cumple) prop/ew", (ddp >= -.1).mean(), (dde >= -.1).mean(),
      "| caida evitada S/ p50 %.0f p90 %.0f" % (np.median(gap_dd), np.quantile(gap_dd, .9)),
      "| dd p50 prop %.3f ew %.3f" % (np.median(ddp), np.median(dde)))
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.hist(dde * 100, bins=60, color=GREY, alpha=.85, label="Equiponderada 100%")
ax.hist(ddp * 100, bins=30, color=RED, alpha=.9, label="Propuesta 20% núcleo")
ax.axvline(-10, color=NAVY, ls="--"); ax.text(-10.5, ax.get_ylim()[1] * .9, "−10%", ha="right", color=NAVY, weight="bold")
ax.set_xlabel("peor caída en 36 meses (%) · 2000 escenarios"); ax.set_yticks([]); ax.spines["left"].set_visible(False)
ax.set_title("Riesgo: la propuesta vive a la derecha del límite", loc="left"); ax.legend(frameon=False, loc="upper left")
fig.tight_layout(); fig.savefig(OUT + "03_distribucion_caida_36m.png"); plt.close(fig)

# 4. Arquitectura
fig, ax = plt.subplots(figsize=(14, 7.2)); ax.set_xlim(0, 14); ax.set_ylim(0, 7.2); ax.axis("off")
def box(x, y, w_, h, title, body, fc, tc="white", bc=None):
    ax.add_patch(FancyBboxPatch((x, y), w_, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=bc or fc, lw=1.5))
    ax.text(x + .15, y + h - .15, title, ha="left", va="top", color=tc, weight="bold", fontsize=11.5)
    ax.text(x + .15, y + h - .55, body, ha="left", va="top", color=tc, fontsize=8.6, linespacing=1.45)
def arr(x1, y1, x2, y2, c=NAVY, ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=1.8, color=c, linestyle=ls))
ax.text(0, 7.05, "Arquitectura de la solución en Databricks · Unity Catalog credicorp_dq", fontsize=15, weight="bold", color=NAVY, va="top")
# carril de orquestación
box(1.75, 5.55, 10.4, .85, "Orquestación: Databricks Jobs (serverless) + Asset Bundle (databricks.yml)", "bronze → silver → validación → gold → señal (etapa 2) → propuesta y Monte Carlo (etapa 3) → LSTM + MLflow (etapa 4)", "#DCE6FA", NAVY, BLUE)
box(0, .9, 1.55, 4.3, "Fuentes", "7 CSV del reto\n\n• precios diario\n• precios intradía\n• macro y FX\n• fundamentales\n• referencia\n• perfiles cliente\n• eventos\n\n+ twist", LIGHT, NAVY, "#BBB")
box(1.85, .9, 1.9, 4.3, "Bronze", "Volume de aterrizaje\n\ntodo como texto\n+ _source_file\n+ _ingest_ts\n\n(copia fiel,\nnada se pierde)", "#8C5A2B")
box(4.05, .9, 2.1, 4.3, "Silver", "tipado y limpio\n\n• IDs, fechas, N/A\n• precio ×100 → ÷100\n• _dq_fixes por fila\n• cuarentena\n• dq_log\n• restricciones Delta\n\n99,99% aprovechable", "#8A9099")
box(6.45, .9, 2.3, 4.3, "Gold", "listo para negocio\n\n• riesgo por activo\n  en moneda base\n• cliente × activo\n• etapa2_* señal\n• etapa3_* propuesta\n  y simulador\n• etapa4_lstm_*", "#C9A227")
box(9.05, 3.2, 2.5, 2.0, "MLflow", "experimento por etapa\n• hiperparámetros\n• pérdida por época\n• métricas y gráficos\n• modelo versionado", RED)
box(9.05, .9, 2.5, 2.0, "Modelos", "Monte Carlo (bootstrap)\nwalk-forward\nLSTM vs EWMA\n(volatilidad 21d)", BLUE)
box(11.85, .9, 2.1, 4.3, "Consumo", "Decision Dashboard\n(AI/BI)\n\nSimulador\ninteractivo\n(widgets)\n\nValue Pitch\n\nGenie (propuesto)", NAVY)
arr(1.55, 3.05, 1.85, 3.05); arr(3.75, 3.05, 4.05, 3.05); arr(6.15, 3.05, 6.45, 3.05)
arr(8.75, 2.0, 9.05, 2.0); arr(8.75, 4.2, 9.05, 4.2); arr(10.3, 2.9, 10.3, 3.2); arr(11.55, 3.05, 11.85, 3.05)
box(0, .05, 13.95, .6, "Gobierno transversal (Unity Catalog)", "", "#E3F1E0", NAVY, "#7FB77E")
ax.text(.15, .33, "permisos · comentarios por tabla · linaje automático tabla→columna · contratos de datos .v1 · validación bloqueante antes de gold · data mesh (dominios market-data / clientele-data)", fontsize=8.6, color=NAVY, va="top")
fig.savefig(OUT + "04_arquitectura.png", bbox_inches="tight"); plt.close(fig)
