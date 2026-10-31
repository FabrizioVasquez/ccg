"""Rentabilidad de la propuesta CL_02 por trimestre, año y 36 meses (backtest + Monte Carlo) y gráficos del reporte.
Uso: .venv/bin/python src/analysis/etapa4_rentabilidad.py  → docs/img/etapa4_reporte/"""
import sys, json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, "src/analysis"); import clean
OUT = "docs/img/etapa4_reporte/"
prices, macro = clean.prices_daily(), clean.macro_daily()
prices["date"] = pd.to_datetime(prices.date); macro["date"] = pd.to_datetime(macro.date); macro = macro.set_index("date")
px = prices.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
R = px.mul(macro.usd_cop.astype(float), axis=0).pct_change().dropna()
pen_cop = (macro.usd_cop / macro.usd_pen).astype(float)         # COP por PEN
vol = R.std() * np.sqrt(252); core = vol[vol <= .30].index
w = (1 / vol[core]); w = (w / w.sum()).reindex(R.columns).fillna(0)
rc_hist, rew_hist = R.values @ w.values, R.values.mean(1)
print("vol anual", vol.round(3).to_dict()); print("pesos", w[w > 0].round(3).to_dict())
print("ret anual medio hist: core %.2f%% ew %.2f%%" % (rc_hist.mean()*252*100, rew_hist.mean()*252*100))

# ---------- 1. Backtest real del año (ago-25 → ago-26) ----------
X = .20
def backtest(r, X, rebal=63):
    E, C, vals = X, 1 - X, [1.0]
    for t, x in enumerate(r):
        E *= 1 + x
        if rebal and (t + 1) % rebal == 0:
            tot = E + C; E, C = X * tot, (1 - X) * tot
        vals.append(E + C)
    return np.array(vals)
idx = [R.index[0] - pd.Timedelta(days=1)] + list(R.index)
bt = pd.DataFrame({"Propuesta 20% núcleo": backtest(rc_hist, .2), "Núcleo 100%": backtest(rc_hist, 1, 0),
                   "Equiponderada 100%": backtest(rew_hist, 1, 0)}, index=pd.DatetimeIndex(idx))
bt.index = [R.index[0]] + list(R.index)  # primer valor = día base
q = bt.resample("QE").last(); q = pd.concat([bt.iloc[[0]], q]); qret = q.pct_change().dropna()
qret.index = [f"{d.year}-T{(d.month-1)//3+1}" for d in qret.index]
dd = (bt / bt.cummax() - 1).min()
pen = bt.mul(pen_cop.iloc[0] / pen_cop.reindex(bt.index).ffill(), axis=0)   # valor en soles
res_bt = pd.DataFrame({"retorno_total_COP": bt.iloc[-1] - 1, "retorno_total_PEN": pen.iloc[-1] - 1, "max_drawdown_COP": dd})
print(qret.round(4)); print(res_bt.round(4)); print("COP vs PEN en el año: %.2f%%" % ((pen_cop.iloc[-1]/pen_cop.iloc[0]-1)*100))
print("fechas", bt.index[0].date(), bt.index[-1].date(), len(R))

# ---------- 2. Monte Carlo 36 meses ----------
T, N, BLOCK = 21 * 36, 2000, 10
rng = np.random.default_rng(7); nb = int(np.ceil(T / BLOCK))
st = rng.integers(0, len(R) - BLOCK + 1, size=(N, nb)); IDX = (st[:, :, None] + np.arange(BLOCK)).reshape(N, -1)[:, :T]
def sim(r, X, retiro=True, rebal=63, cash=0.0):
    rets = r[IDX]; n = N; E = np.full(n, X); C = np.full(n, 1 - X)
    I = np.empty((T + 1, n)); I[0] = 1; prev = np.ones(n); iv = np.ones(n); cd = (1 + cash) ** (1 / 252) - 1
    for t in range(T):
        E = E * (1 + rets[:, t]); C = C * (1 + cd); v = E + C; iv = iv * v / prev
        if retiro and t + 1 == 126:
            fc = np.minimum(C, .3); C = C - fc; E = E - (.3 - fc); tot = E + C; E = np.minimum(E, X * tot); C = tot - E
        elif rebal and (t + 1) % rebal == 0:
            tot = E + C; E = X * tot; C = tot - E
        prev = E + C; I[t + 1] = iv
    return I
esc = {"base (deriva 0, caja 0%)": (rc_hist - rc_hist.mean(), rew_hist - rew_hist.mean(), 0.0),
       "histórica (deriva del año)": (rc_hist, rew_hist, 0.0)}
tabs, fan = {}, {}
for k, (rc, rew, cash) in esc.items():
    Ip, Ie = sim(rc, .2), sim(rew, 1, rebal=0)
    fan[k] = (Ip, Ie)
    rows = []
    for m in [3, 6, 9, 12, 18, 24, 30, 36]:
        t = 21 * m
        for name, I in [("propuesta", Ip), ("equiponderada", Ie)]:
            r = I[t] - 1
            rows.append({"mes": m, "cartera": name, "p5": np.quantile(r, .05), "p50": np.median(r), "p95": np.quantile(r, .95),
                         "media": r.mean(), "P_perdida": (r < 0).mean()})
    tabs[k] = pd.DataFrame(rows)
    ddp = (Ip / np.maximum.accumulate(Ip, 0) - 1).min(0); dde = (Ie / np.maximum.accumulate(Ie, 0) - 1).min(0)
    print("\n==", k, "P(cumple) prop %.3f ew %.3f" % ((ddp >= -.1).mean(), (dde >= -.1).mean()))
    print(tabs[k].round(4).to_string())
    # retornos por trimestre individual (distribución) y anual
    qr = np.array([Ip[21*3*(i+1)] / Ip[21*3*i] - 1 for i in range(12)])
    yr = np.array([Ip[252*(i+1)] / Ip[252*i] - 1 for i in range(3)])
    print("trimestral p5/p50/p95 (todos los Q):", np.quantile(qr, [.05, .5, .95]).round(4), "P(Q negativo) %.2f" % (qr < 0).mean())
    print("anual p5/p50/p95:", np.quantile(yr, [.05, .5, .95]).round(4), "P(año negativo) %.2f" % (yr < 0).mean())
    ann = Ip[-1] ** (1/3) - 1
    print("anualizado 36m p5/p50/p95:", np.quantile(ann, [.05, .5, .95]).round(4))
# sensibilidad a la tasa de la caja
for cash in [0, .02, .04, .06]:
    I = sim(esc["base (deriva 0, caja 0%)"][0], .2, cash=cash)
    ddp = (I / np.maximum.accumulate(I, 0) - 1).min(0)
    print("caja %.0f%%: retorno 36m p50 %.2f%% anualizado %.2f%% P(cumple) %.3f" % (cash*100, (np.median(I[-1])-1)*100, (np.median(I[-1])**(1/3)-1)*100, (ddp >= -.1).mean()))


# ---------- gráficos ----------
plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": .25, "font.size": 10})
Ip, Ie = fan["base (deriva 0, caja 0%)"]; mths = np.arange(T + 1) / 21
fig, ax = plt.subplots(figsize=(10, 5))
for I, c, lab in [(Ie, "#9D9D9D", "Equiponderada 100% (consejo ingenuo)"), (Ip, "#E45756", "Propuesta: 20% núcleo + 80% liquidez")]:
    P = np.quantile(I, [.05, .25, .5, .75, .95], axis=1) * 1_000_000
    ax.fill_between(mths, P[0], P[4], color=c, alpha=.15); ax.fill_between(mths, P[1], P[3], color=c, alpha=.3)
    ax.plot(mths, P[2], color=c, lw=2, label=lab)
for i in range(30): ax.plot(mths, Ip[:, i] * 1e6, color="#E45756", lw=.4, alpha=.35)
ax.axhline(900_000, ls="--", color="k", lw=1); ax.text(0.5, 905_000, "−10% (límite de caída de CL_02)", fontsize=8)
ax.axvline(6, ls=":", color="k"); ax.text(6.2, ax.get_ylim()[1] * .98 if False else 1_330_000, "retiro 30% (mes 6)", fontsize=8)
ax.set_xticks(range(0, 37, 3)); ax.set_xlabel("meses"); ax.set_ylabel("S/ (por cada S/ 1 000 000, sin contar el retiro)")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1e3:,.0f}k"))
ax.set_title("2000 futuros posibles a 36 meses\nbanda clara = 90% de los casos · banda oscura = 50% · línea = caso típico", fontsize=10)
ax.legend(loc="upper left"); fig.tight_layout(); fig.savefig(OUT + "01_montecarlo_abanico.png"); plt.close(fig)

t = tabs["base (deriva 0, caja 0%)"]; t2 = tabs["histórica (deriva del año)"]
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for ax, tb, ttl in [(axs[0], t, "Escenario base (sin suponer que el mercado sube)"), (axs[1], t2, "Escenario optimista (se repite la tendencia del año)")]:
    for name, c in [("propuesta", "#E45756"), ("equiponderada", "#9D9D9D")]:
        s = tb[tb.cartera == name]
        ax.errorbar(s.mes + (.4 if name == "propuesta" else -.4), s.p50 * 100, yerr=[(s.p50 - s.p5) * 100, (s.p95 - s.p50) * 100], fmt="o", color=c, capsize=3, label=name)
    ax.axhline(0, color="k", lw=.8); ax.set_xticks([3, 6, 9, 12, 18, 24, 30, 36]); ax.set_xlabel("mes"); ax.set_title(ttl, fontsize=10)
axs[0].set_ylabel("rentabilidad acumulada (%)"); axs[0].legend(); fig.suptitle("Rentabilidad acumulada: punto = caso típico (p50); barra = del 5% peor al 5% mejor")
fig.tight_layout(); fig.savefig(OUT + "02_rentabilidad_por_periodo.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 4))
(bt * 1e6).plot(ax=ax, color=["#E45756", "#4C78A8", "#9D9D9D"], lw=1.8)
ax.axhline(900_000, ls="--", color="k", lw=1); ax.set_ylabel("S/ (en COP convertidos a PEN fijo)")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1e3:,.0f}k"))
ax.set_title("Lo que realmente pasó en el año de datos (ago-25 → ago-26), medido en pesos colombianos"); fig.tight_layout(); fig.savefig(OUT + "03_backtest_anual.png"); plt.close(fig)
