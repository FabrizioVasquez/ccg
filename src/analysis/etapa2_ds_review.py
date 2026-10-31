"""Etapa 2 — Revisión de ciencia de datos (hallazgos, limpieza, robustez de CL_02 y twist).

Genera todas las cifras de docs/etapa2_reporte_cientifico_datos.md.

Uso (desde la raíz del repo, con dataset_start/ en local):
    .venv/bin/python src/analysis/etapa2_ds_review.py
Requiere: pandas, numpy, scipy, statsmodels. Semilla fija (SEED); tarda ~2-4 min.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox

sys.path.insert(0, str(Path(__file__).parent))
import clean  # noqa: E402

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

SEED = 7
D = "dataset_start/"
CORE = ["VF_A01", "VF_A04", "VF_A05", "VF_A08"]
HV30 = ["VF_A02", "VF_A03", "VF_A06", "VF_A07"]  # definición base (vol > 30%)
CUT = pd.Timestamp("2026-04-10")
STRESS = (pd.Timestamp("2026-02-09"), pd.Timestamp("2026-02-20"))
CLIENTS = [("CL_01", "USD", 0.22), ("CL_02", "COP", 0.10), ("CL_03", "PEN", 0.15)]
BLOCK, B_BOOT, N_BOOT_W = 20, 300, 20_000
ANN = np.sqrt(252)


def h(t: str) -> None:
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


# ----------------------------------------------------------------------------- utilidades
def dd_of(nav: np.ndarray) -> np.ndarray:
    """Max drawdown por columna de una matriz de NAV (T x K)."""
    return (nav / np.maximum.accumulate(nav, axis=0) - 1).min(axis=0)


def nav_stats(rel: np.ndarray, W: np.ndarray):
    """rel: precios relativos (T x n), W: (K x n). Buy & hold."""
    nav = rel @ W.T
    return nav[-1] - 1, dd_of(nav)


def mix_dd(nav_eq: np.ndarray, x: float) -> np.ndarray:
    """DD de una cartera con x invertido y (1-x) en liquidez a rendimiento 0 (nav_eq empieza en 1)."""
    return dd_of(x * nav_eq + (1 - x))


def max_exposure(nav_eq: np.ndarray, tol: float, grid=np.arange(0.0, 1.0001, 0.01)) -> float:
    ok = [x for x in grid if mix_dd(nav_eq[:, None], x)[0] >= -tol]
    return max(ok)


def block_boot_idx(n: int, rng, L: int = BLOCK) -> np.ndarray:
    """Índices de un bootstrap circular por bloques (longitud n)."""
    starts = rng.integers(0, n, int(np.ceil(n / L)))
    return (starts[:, None] + np.arange(L)[None, :]).ravel()[:n] % n


def hv_mask(W, assets, hv):
    return W[:, np.isin(assets, hv)].sum(axis=1) <= 0.25


def constraint_mask(cid, W, assets, ref, hv=HV30):
    sec = ref.loc[assets, "sector"].values
    ctry = ref.loc[assets, "country"].values
    if cid == "CL_01":
        return pd.DataFrame(W, columns=sec).T.groupby(level=0).sum().T.values.max(axis=1) <= 0.45
    if cid == "CL_02":
        return hv_mask(W, assets, hv)
    held = W > 0.05
    n_c = pd.DataFrame(held, columns=ctry).T.groupby(level=0).any().T.sum(axis=1).values
    n_s = pd.DataFrame(held, columns=sec).T.groupby(level=0).any().T.sum(axis=1).values
    return (n_c >= 3) & (n_s >= 3)


def ols_hac(y, X, lags=5):
    r = sm.OLS(y, sm.add_constant(X), missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return r


# ----------------------------------------------------------------------------- datos
p, macro = clean.prices_daily(), clean.macro_daily().set_index("date")
ref = clean.ref().set_index("asset_id")
ev = clean.events()
px = p.pivot(index="date", columns="asset_id", values="close").sort_index()
assets = list(px.columns)
fxmap = {"USD": pd.Series(1.0, index=macro.index), "COP": macro.usd_cop, "PEN": macro.usd_pen}
loc = {c: px.mul(fxmap[c], axis=0) for c in fxmap}
ret = np.log(px).diff().dropna()  # log retornos USD
ret_cop = np.log(loc["COP"]).diff().dropna()
dy_bp = (macro.us_10y_yield.diff() * 100).loc[ret.index]
dfx = np.log(macro.usd_cop).diff().loc[ret.index]
mf = macro.market_factor.loc[ret.index]
regime = macro.risk_regime.loc[ret.index]

# ============================================================================= 1. HALLAZGOS
h("1A. Volatilidad y correlación por régimen (retornos diarios en USD)")
vol = pd.DataFrame({rg: ret[regime == rg].std() * ANN for rg in ["Normal", "Stress", "Recovery"]})
vol["n_Normal"], vol["n_Stress"] = (regime == "Normal").sum(), (regime == "Stress").sum()
vol["ratio_S/N"] = vol.Stress / vol.Normal
vol["F_p"] = [2 * min(stats.f.cdf(r**2, vol.n_Stress.iloc[0] - 1, vol.n_Normal.iloc[0] - 1),
                      1 - stats.f.cdf(r**2, vol.n_Stress.iloc[0] - 1, vol.n_Normal.iloc[0] - 1)) for r in vol["ratio_S/N"]]
vol["Levene_p"] = [stats.levene(ret.loc[regime == "Stress", a], ret.loc[regime == "Normal", a]).pvalue for a in assets]
vol["vol_anual_total"] = ret.std() * ANN
vol["vol_anual_COP"] = ret_cop.std() * ANN
print(vol.round(3))

iu = np.triu_indices(len(assets), 1)
def avgcorr(df):
    return df.corr().values[iu].mean()
rc = {rg: avgcorr(ret[regime == rg]) for rg in ["Normal", "Stress", "Recovery"]}
print("Correlación media entre pares:", {k: round(v, 3) for k, v in rc.items()})
# distribución de la correlación media en TODAS las ventanas de 10 días (referencia empírica)
win = 10
roll_c = np.array([avgcorr(ret.iloc[i:i + win]) for i in range(len(ret) - win + 1)])
roll_v = np.array([(ret.iloc[i:i + win].mean(axis=1)).std() * ANN for i in range(len(ret) - win + 1)])
s_c = avgcorr(ret.loc[STRESS[0]:STRESS[1]])
s_v = ret.loc[STRESS[0]:STRESS[1]].mean(axis=1).std() * ANN
print(f"Ventana Stress: corr media {s_c:.3f} -> percentil {stats.percentileofscore(roll_c, s_c):.0f} de {len(roll_c)} ventanas de 10d "
      f"(mediana {np.median(roll_c):.3f}, p5-p95 {np.percentile(roll_c,5):.3f}..{np.percentile(roll_c,95):.3f})")
print(f"Ventana Stress: vol EW {s_v:.3f} -> percentil {stats.percentileofscore(roll_v, s_v):.0f} (mediana {np.median(roll_v):.3f})")
cS, cN = ret[regime == "Stress"].corr(), ret[regime == "Normal"].corr()
print("Pares del núcleo, corr Normal -> Stress:")
for i, a in enumerate(CORE):
    for b in CORE[i + 1:]:
        print(f"  {a}-{b}: {cN.loc[a, b]:.2f} -> {cS.loc[a, b]:.2f}")
print("Retorno acumulado (USD) en la ventana Stress por activo:",
      (px.loc[STRESS[1]] / px.shift(1).loc[STRESS[0]] - 1).round(3).to_dict())
print("Retorno acumulado (COP) en la ventana Stress por activo:",
      (loc["COP"].loc[STRESS[1]] / loc["COP"].shift(1).loc[STRESS[0]] - 1).round(3).to_dict())
print(f"Cambio de tasa 10y en Stress: {(macro.us_10y_yield.loc[STRESS[1]] - macro.us_10y_yield.shift(1).loc[STRESS[0]])*100:.1f} pb; "
      f"USD/COP {macro.usd_cop.loc[STRESS[1]] / macro.usd_cop.shift(1).loc[STRESS[0]] - 1:.3%}")

h("1B. Estabilidad temporal de la volatilidad: train (< 2026-04-10) vs test")
tr_m = ret.index < CUT
st = pd.DataFrame({"vol_train": ret[tr_m].std() * ANN, "vol_test": ret[~tr_m].std() * ANN})
st["ratio"] = st.vol_test / st.vol_train
st["Levene_p"] = [stats.levene(ret.loc[tr_m, a], ret.loc[~tr_m, a]).pvalue for a in assets]
print(st.round(3))
print(f"Corr media train {avgcorr(ret[tr_m]):.3f} | test {avgcorr(ret[~tr_m]):.3f}")
c_tr, c_te = ret[tr_m].corr().values[iu], ret[~tr_m].corr().values[iu]
print(f"Correlación entre matrices de correlación train/test (28 pares): {np.corrcoef(c_tr, c_te)[0,1]:.2f}; "
      f"diferencia absoluta media {np.abs(c_tr - c_te).mean():.3f}")

h("1C. Sensibilidad a la tasa US 10y (beta por pb, OLS con errores HAC Newey-West)")
print(f"Δ tasa diaria: desv. {dy_bp.std():.2f} pb; mín {dy_bp.min():.2f}; máx {dy_bp.max():.2f}; "
      f"cambio total del año {dy_bp.sum():.1f} pb; mayor cambio de 5 días |{(macro.us_10y_yield.diff(5)*100).abs().max():.1f}| pb; "
      f"rango de nivel {macro.us_10y_yield.min():.3f}..{macro.us_10y_yield.max():.3f}%")
wk = np.log(px).resample("W-FRI").last().diff().dropna()
wk_dy = (macro.us_10y_yield.resample("W-FRI").last().diff() * 100).loc[wk.index]
rows = []
for a in assets:
    r1 = ols_hac(ret[a], dy_bp)
    r2 = ols_hac(ret[a], pd.concat([dy_bp, mf], axis=1))
    rw = ols_hac(wk[a], wk_dy, lags=2)
    b, se = rw.params.iloc[1], rw.bse.iloc[1]
    rows.append(dict(asset=a, beta_d_pct_por_pb=r1.params.iloc[1] * 100, se_d=r1.bse.iloc[1] * 100,
                     t_d=r1.tvalues.iloc[1], R2_d=r1.rsquared, beta_d_ctrl_mf=r2.params.iloc[1] * 100, t_ctrl=r2.tvalues.iloc[1],
                     beta_w_pct_por_pb=b * 100, se_w=se * 100, R2_w=rw.rsquared,
                     impacto_65pb=65 * b, ic95_lo=65 * (b - 1.96 * se), ic95_hi=65 * (b + 1.96 * se)))
rb = pd.DataFrame(rows).set_index("asset")
print(rb.round(4))
print(f"corr(Δtasa, market_factor) = {np.corrcoef(dy_bp, mf)[0,1]:.3f}")
rate_ratio = 65 / (macro.us_10y_yield.diff(5) * 100).abs().max()
print(f"El shock TW_01 (+65 pb/semana) es {rate_ratio:.0f}x el mayor movimiento semanal observado.")

h("1D. Sensibilidad a USD/COP (beta del retorno en USD al log-cambio de USD/COP)")
rows = []
for a in assets:
    r = ols_hac(ret[a], dfx)
    rows.append(dict(asset=a, beta=r.params.iloc[1], se=r.bse.iloc[1], t=r.tvalues.iloc[1], R2=r.rsquared))
print(pd.DataFrame(rows).set_index("asset").round(3))
r_fx_mf = ols_hac(dfx, mf)
print(f"corr(ΔlogUSD/COP, market_factor) = {np.corrcoef(dfx, mf)[0,1]:.3f} (beta {r_fx_mf.params.iloc[1]:.3f}, t {r_fx_mf.tvalues.iloc[1]:.2f})")
print(f"USD/COP: cambio total {macro.usd_cop.iloc[-1]/macro.usd_cop.iloc[0]-1:.2%}, vol anual {dfx.std()*ANN:.2%}, "
      f"mayor depreciación COP en 5 días {np.log(macro.usd_cop).diff(5).max():.2%}, en 20 días {np.log(macro.usd_cop).diff(20).max():.2%}")
fx5 = np.log(macro.usd_cop).diff(5).dropna()
print(f"Un +8% en pocos días equivale a {np.log(1.08)/fx5.std():.1f} desviaciones del cambio de 5 días observado.")

h("1E. Market factor y risk_regime")
rows = []
ew_ret = np.log((px / px.iloc[0]).mean(axis=1)).diff().dropna()
for a in assets:
    r = ols_hac(ret[a], mf)
    rows.append(dict(asset=a, beta_mf=r.params.iloc[1], se=r.bse.iloc[1], R2=r.rsquared,
                     ret_med_Normal_pb=ret.loc[regime == "Normal", a].mean() * 1e4,
                     ret_med_Stress_pb=ret.loc[regime == "Stress", a].mean() * 1e4,
                     ret_med_Recovery_pb=ret.loc[regime == "Recovery", a].mean() * 1e4))
print(pd.DataFrame(rows).set_index("asset").round(3))
print(f"corr(retorno EW, market_factor) = {np.corrcoef(ew_ret, mf)[0,1]:.3f}; R² 1 factor medio = {np.mean([r['R2'] for r in rows]):.3f}")
print("market_factor medio por régimen (pb/día):", (macro.market_factor.groupby(macro.risk_regime).mean() * 1e4).round(1).to_dict())
kw = stats.kruskal(*[mf[regime == g] for g in ["Normal", "Stress", "Recovery"]])
print(f"Kruskal-Wallis market_factor ~ régimen: p={kw.pvalue:.3f}")
print("Rachas de régimen:", macro.risk_regime[macro.risk_regime != macro.risk_regime.shift()].to_dict())

h("1F. Intradía 2020-2025: ¿historia útil o inconsistente?")
x = clean.prices_expanded_daily()
xp = x.pivot(index="day", columns="asset_id", values="close").sort_index()
raw_x = pd.read_csv(D + "01_market_prices_raw_expanded.csv", encoding="utf-8-sig", usecols=["date", "asset_id"])
xr = np.log(xp).diff()
ov = xr.loc["2025-08-04":].join(ret, lsuffix="_i", rsuffix="_d", how="inner")
print("Correlación de retornos diarios intradía vs diario en el periodo común (por activo):",
      {a: round(ov[f"{a}_i"].corr(ov[f"{a}_d"]), 3) for a in assets})
pre = xr.loc[:"2025-07-31"].dropna()
cmp_ = pd.DataFrame({"vol_intradia_2020_25": pre.std() * ANN, "vol_diario_25_26": ret.std() * ANN})
cmp_["maxDD_intradia_2020_25"] = [dd_of((xp.loc[:"2025-07-31", a] / xp.loc[:"2025-07-31", a].iloc[0]).values[:, None])[0] for a in assets]
cmp_["maxDD_diario_USD"] = [dd_of((px[a] / px[a].iloc[0]).values[:, None])[0] for a in assets]
cmp_["peor_5d_intradia"] = np.log(xp.loc[:"2025-07-31"]).diff(5).min()
cmp_["peor_5d_diario"] = np.log(px).diff(5).min()
print(cmp_.round(3))
print(f"Corr media entre pares: intradía 2020-25 {avgcorr(pre):.3f} vs diario {avgcorr(ret):.3f}; "
      f"similitud de la estructura (corr de las 28 correlaciones) {np.corrcoef(pre.corr().values[iu], ret.corr().values[iu])[0,1]:.2f}")
print(f"Continuidad de nivel 2025-07-31 (intradía) -> 2025-08-01 (diario): "
      f"{(px.iloc[0] / xp.loc['2025-07-31'] - 1).round(3).to_dict()}")
x_raw = pd.read_csv(D + "01_market_prices_raw_expanded.csv", encoding="utf-8-sig", usecols=["date", "asset_id", "close", "volume"])
print(f"Intradía crudo: {len(x_raw)} filas; close nulo {x_raw.close.isna().sum()}; volume nulo {x_raw.volume.isna().sum()}; "
      f"volumen con sufijo K/M {x_raw.volume.astype(str).str.contains('[KM]$').sum()}")
core_x = (xp.loc[:"2025-07-31", CORE] / xp.loc[:"2025-07-31", CORE].iloc[0]).mean(axis=1)
roll_dd = np.array([dd_of((core_x.iloc[i:i + 252] / core_x.iloc[i]).values[:, None])[0] for i in range(0, len(core_x) - 252, 5)])
print(f"Núcleo EW (USD) en el intradía 2020-25: DD máx total {dd_of(core_x.values[:, None])[0]:.1%}; DD en ventanas de 1 año: "
      f"mediana {np.median(roll_dd):.1%}, p10 {np.percentile(roll_dd,10):.1%}, peor {roll_dd.min():.1%}; "
      f"% de años con DD peor que -10%: {(roll_dd < -0.10).mean():.0%}")
core_d = (px[CORE] / px[CORE].iloc[0]).mean(axis=1)
print(f"Núcleo EW (USD) en el diario 2025-26: DD {dd_of(core_d.values[:, None])[0]:.1%}")

h("1G. Colas, autocorrelación y estacionalidad (retornos diarios USD)")
rows = []
for a in assets:
    r = ret[a]
    z = (r - r.mean()) / r.std()
    lb = acorr_ljungbox(r, lags=[10], return_df=True).lb_pvalue.iloc[0]
    lb2 = acorr_ljungbox(r**2, lags=[10], return_df=True).lb_pvalue.iloc[0]
    dow = stats.kruskal(*[r[r.index.dayofweek == d] for d in range(5)]).pvalue
    rows.append(dict(asset=a, asimetria=stats.skew(r), curtosis_exceso=stats.kurtosis(r), JB_p=stats.jarque_bera(r).pvalue,
                     dias_3sd=(z.abs() > 3).sum(), esperado_normal=round(0.0027 * len(r), 1), peor_dia=r.min(),
                     fecha_peor=r.idxmin().date(), ac1=r.autocorr(1), LB10_p=lb, LB10_cuadrados_p=lb2, dia_semana_p=dow))
tails = pd.DataFrame(rows).set_index("asset")
print(tails.round(3))
print(f"IC95 de la autocorrelación bajo H0: ±{1.96/np.sqrt(len(ret)):.3f}. Umbral Bonferroni (8 activos): p<{0.05/8:.4f}")
mf_lb = acorr_ljungbox(mf, lags=[10], return_df=True).lb_pvalue.iloc[0]
print(f"market_factor: ac1 {mf.autocorr():.3f}, LB10 p {mf_lb:.3f}")
print("Inflación EE. UU. (rango):", macro.us_inflation_yoy.min(), "-", macro.us_inflation_yoy.max(), "(casi constante: sin poder explicativo)")

h("1H. Estudio de eventos (modelo de mercado con market_factor; CAR [0,+5] días hábiles)")
expected = {"Operational": -1, "Commodity": 1, "Earnings": 1, "Demand": -1, "Sector": -1}
rows = []
for _, e in ev.iterrows():
    a = e.scope if e.scope in assets else ref.index[ref.sector == e.scope][0]
    d0 = ret.index[ret.index >= e.event_date][0]
    i0 = ret.index.get_loc(d0)
    win_idx = ret.index[i0:i0 + 6]
    est = ret.index[(ret.index < ret.index[max(i0 - 5, 0)]) | (ret.index > ret.index[min(i0 + 15, len(ret) - 1)])]
    m_ = sm.OLS(ret.loc[est, a], sm.add_constant(mf.loc[est])).fit()
    ar = ret.loc[win_idx, a] - m_.predict(sm.add_constant(mf.loc[win_idx]))
    car, se = ar.sum(), m_.resid.std() * np.sqrt(len(win_idx))
    rows.append(dict(fecha=e.event_date.date(), activo=a, tipo=e.event_type, sev=e.severity, CAR=car, se=se, t=car / se,
                     signo_esperado=expected[e.event_type], coincide=np.sign(car) == expected[e.event_type]))
evt = pd.DataFrame(rows)
print(evt.round(3))
print(f"Eventos con CAR en la dirección esperada: {evt.coincide.sum()}/5; con |t|>1.96: {(evt.t.abs() > 1.96).sum()}/5")

h("1I. Fundamentales: apalancamiento trimestral vs LTM (último trimestre)")
f = clean.fundamentals()
f_raw_cash = pd.read_csv(D + "03_fundamentals_raw.csv", encoding="utf-8-sig")
f["net_debt"] = f.debt_usd_m - f.cash_usd_m
f["ebitda_ltm"] = f.groupby("issuer_id").ebitda_usd_m.transform(lambda s: s.rolling(4).sum())
last = f.groupby("issuer_id").tail(1).set_index("issuer_id")
lev = pd.DataFrame({"ND/EBITDA_trimestral(usado en etapa2)": last.net_debt / last.ebitda_usd_m,
                    "ND/EBITDA_LTM": last.net_debt / last.ebitda_ltm})
print(lev.round(2))
i6 = f[(f.issuer_id == "ISS_06")].set_index("period_end")
print(f"ISS_06 2025-06-30 revenue {i6.loc['2025-06-30','revenue_usd_m']} vs vecinos {i6.loc['2025-03-31','revenue_usd_m']} / "
      f"{i6.loc['2025-09-30','revenue_usd_m']}; desvío vs media vecinos "
      f"{i6.loc['2025-06-30','revenue_usd_m']/np.mean([i6.loc['2025-03-31','revenue_usd_m'], i6.loc['2025-09-30','revenue_usd_m']])-1:.1%}; "
      f"margen EBITDA con el dato {437.4/1845.7:.1%} vs con 2845.7 {437.4/2845.7:.1%}")

# ============================================================================= 2. LIMPIEZA (conteos)
h("2. Plan de limpieza: conteos de filas afectadas (crudo)")
rp = pd.read_csv(D + "01_market_prices_raw.csv", encoding="utf-8-sig", dtype=str)
rp_c = rp.assign(a=clean._canon(rp.asset_id), d=clean._date(rp.date))
print(f"01 diario: filas {len(rp)}; alias {rp.asset_id.isin(clean.ALIAS).sum()}; fecha no ISO {rp.date.str.contains('/').sum()}; "
      f"currency nulo {rp.currency.isna().sum()}; volumen K/M {rp.volume.str.contains('[KM]$', na=False).sum()}; "
      f"duplicados (asset,fecha) {rp_c.duplicated(['a','d']).sum()} (exactos: {rp_c.drop(columns=['asset_id','date']).duplicated().sum()}); "
      f"close fuera de [low,high] {((rp.close.astype(float) > rp.high.astype(float)) | (rp.close.astype(float) < rp.low.astype(float))).sum()}")
a6 = px["VF_A06"].copy()
a6_silver = a6.copy(); a6_silver.loc["2026-03-23"] = 35.89
print(f"VF_A06 2026-03-23: local (o+h+l)/3 = {a6.loc['2026-03-23']}, silver /100 = 35.89; "
      f"DD COP local {dd_of((a6*macro.usd_cop/ (a6*macro.usd_cop).iloc[0]).values[:,None])[0]:.2%} vs silver "
      f"{dd_of((a6_silver*macro.usd_cop/(a6_silver*macro.usd_cop).iloc[0]).values[:,None])[0]:.2%}")
bdays = pd.bdate_range(macro.index.min(), macro.index.max())
print(f"Calendario: {len(macro)} días = {len(bdays)} días hábiles lun-vie (incluye feriados de EE. UU., p. ej. 2025-11-27 en datos: "
      f"{pd.Timestamp('2025-11-27') in macro.index})")
mr = pd.read_csv(D + "02_macro_raw.csv", encoding="utf-8-sig")
print(f"02 macro: nulos por columna {mr.isna().sum()[mr.isna().sum() > 0].to_dict()}")
fr = pd.read_csv(D + "03_fundamentals_raw.csv", encoding="utf-8-sig")
non_iso = (~fr.period_end.str.match(r"^\d{4}-\d{2}-\d{2}$")).sum()
print(f"03 fundamentals: filas {len(fr)}; duplicados exactos {fr.duplicated().sum()}; alias {fr.issuer_id.isin(clean.ALIAS).sum()}; "
      f"periodo no ISO {non_iso}; revenue texto {fr.revenue_usd_m.astype(str).str.contains(',').sum()}; "
      f"cash nulo {fr.cash_usd_m.isna().sum()}")
print(f"ISS_07 2025-09-30 cash: local clean.py ffill = {f.loc[(f.issuer_id=='ISS_07') & (f.period_end=='2025-09-30'),'cash_usd_m'].iloc[0]}; "
      f"interpolación lineal = {(328.0+343.2)/2:.1f}; silver = NULL")

# ============================================================================= 3. ROBUSTEZ CL_02
h("3A. Criterio formal (valor de la información) con bootstrap por bloques")
rng = np.random.default_rng(SEED)
Wb = rng.dirichlet(np.full(len(assets), 0.6), N_BOOT_W)
ew = np.full((1, len(assets)), 1 / len(assets))
rets_loc = {c: (loc[c] / loc[c].shift(1)).dropna().values for c in fxmap}  # retornos simples en moneda base
T = len(rets_loc["USD"])
masks = {cid: constraint_mask(cid, Wb, assets, ref) for cid, _, _ in CLIENTS}
res = {cid: dict(feas=[], ew_dd=[], best_dd=[]) for cid, _, _ in CLIENTS}
# carteras "factibles" en la muestra original (CL_02, 200k) para medir su riesgo en bootstrap
W200 = np.random.default_rng(SEED).dirichlet(np.full(len(assets), 0.6), 200_000)
rel_cop = (loc["COP"] / loc["COP"].iloc[0]).values
_, dd200 = nav_stats(rel_cop, W200)
feas200 = W200[constraint_mask("CL_02", W200, assets, ref) & (dd200 >= -0.10)]
print(f"Carteras factibles CL_02 en la muestra original (200k): {len(feas200)}; peso medio por activo: "
      f"{dict(zip(assets, feas200.mean(axis=0).round(2)))}")
feas200_boot = []
core_w = np.array([[0.25 if a in CORE else 0 for a in assets]])
core_boot, ew_cop_boot, core_paths = [], [], []
boot_rng = np.random.default_rng(SEED + 1)
for b in range(B_BOOT):
    idx = np.r_[block_boot_idx(T, boot_rng)]
    for cid, ccy, tol in CLIENTS:
        rel = np.vstack([np.ones(len(assets)), np.cumprod(rets_loc[ccy][idx], axis=0)])
        _, dd = nav_stats(rel, Wb)
        ok = masks[cid]
        res[cid]["feas"].append((ok & (dd >= -tol)).mean())
        res[cid]["best_dd"].append(dd[ok].max())
        res[cid]["ew_dd"].append(nav_stats(rel, ew)[1][0])
        if cid == "CL_02":
            feas200_boot.append((nav_stats(rel, feas200)[1] >= -tol).mean())
            nav_core = rel @ core_w.T
            core_paths.append(nav_core[:, 0])
            core_boot.append(dd_of(nav_core)[0])
summ = []
for cid, ccy, tol in CLIENTS:
    fe, ed, bd = map(np.array, (res[cid]["feas"], res[cid]["ew_dd"], res[cid]["best_dd"]))
    loc_rel = (loc[ccy] / loc[ccy].iloc[0]).values
    _, dd_full = nav_stats(loc_rel, Wb)
    summ.append(dict(cliente=cid, tol=tol, feas_muestra=(masks[cid] & (dd_full >= -tol)).mean(),
                     feas_boot_mediana=np.median(fe), feas_ic90_lo=np.percentile(fe, 5), feas_ic90_hi=np.percentile(fe, 95),
                     P_feas_cero=(fe == 0).mean(),
                     ew_dd_muestra=nav_stats(loc_rel, ew)[1][0], P_ew_incumple=(ed < -tol).mean(),
                     exceso_esperado_ew=np.mean(np.maximum(0, -ed - tol)), exceso_relativo=np.mean(np.maximum(0, -ed - tol)) / tol,
                     mejor_dd_mediana=np.median(bd), P_mejor_incumple=(bd < -tol).mean()))
summ = pd.DataFrame(summ).set_index("cliente")
print(f"(bootstrap circular por bloques de {BLOCK} días, {B_BOOT} réplicas, {N_BOOT_W} carteras Dirichlet α=0.6; retornos conjuntos activos+FX)")
print(summ.round(4).T)
print(f"Las {len(feas200)} carteras factibles de CL_02 en la muestra cumplen DD<=10% en el {np.mean(feas200_boot):.1%} de las trayectorias bootstrap")
core_boot = np.array(core_boot)
print(f"Núcleo 25% c/u (100% invertido, COP): DD muestra {dd_of(rel_cop @ core_w.T)[0]:.1%}; bootstrap mediana {np.median(core_boot):.1%}, "
      f"p10 {np.percentile(core_boot,10):.1%}, P(DD peor que -10%) {(core_boot < -0.10).mean():.0%}")

h("3B. Sensibilidad: semilla x α de Dirichlet x umbral de alta volatilidad (50k carteras, in-sample)")
vol_cop = ret_cop.std() * ANN
hv_sets = {thr: [a for a in assets if vol_cop[a] > thr] for thr in (0.25, 0.30, 0.35)}
print("Vol anual en COP:", vol_cop.round(3).to_dict())
print("Conjuntos de alta volatilidad:", hv_sets)
grid = []
for seed in (7, 11, 23, 42, 99):
    for alpha in (0.3, 0.6, 1.0, 2.0):
        Wg = np.random.default_rng(seed).dirichlet(np.full(len(assets), alpha), 50_000)
        row = dict(seed=seed, alpha=alpha)
        for cid, ccy, tol in CLIENTS:
            _, ddg = nav_stats((loc[ccy] / loc[ccy].iloc[0]).values, Wg)
            if cid == "CL_02":
                for thr, hv in hv_sets.items():
                    row[f"CL_02_hv{int(thr*100)}"] = (hv_mask(Wg, assets, hv) & (ddg >= -tol)).mean()
                    row[f"CL_02_hv{int(thr*100)}_mejorDD"] = ddg[hv_mask(Wg, assets, hv)].max()
            else:
                row[cid] = (constraint_mask(cid, Wg, assets, ref) & (ddg >= -tol)).mean()
        grid.append(row)
grid = pd.DataFrame(grid)
print(grid.round(5).to_string(index=False))
print("Resumen por columna (mín / máx):")
print(grid.drop(columns=["seed", "alpha"]).agg(["min", "max"]).round(5).T)
print("¿CL_02 siempre es el cliente con menor % factible? ",
      bool((grid[["CL_02_hv25", "CL_02_hv30", "CL_02_hv35"]].max(axis=1) < grid[["CL_01", "CL_03"]].min(axis=1)).all()))

h("3C. Walk-forward: selección en train, evaluación en test (CL_02, COP)")
Wwf = np.random.default_rng(SEED).dirichlet(np.full(len(assets), 0.6), 50_000)
Wwf = Wwf[hv_mask(Wwf, assets, HV30)]
cuts = pd.to_datetime(["2025-12-01", "2026-01-02", "2026-02-02", "2026-03-02", "2026-04-10", "2026-05-01", "2026-06-01"])
wf = []
for c in cuts:
    trp, tep = loc["COP"][loc["COP"].index < c], loc["COP"][loc["COP"].index >= c]
    rel_tr, rel_te = (trp / trp.iloc[0]).values, (tep / tep.iloc[0]).values
    _, d_tr = nav_stats(rel_tr, Wwf)
    r_te, d_te = nav_stats(rel_te, Wwf)
    i = int(np.argmax(d_tr))
    # núcleo elegido sin mirar el futuro: 4 activos de menor DD en train
    dd_assets_tr = pd.Series(dd_of(rel_tr), index=assets)
    core_tr = list(dd_assets_tr.nlargest(4).index)
    w_core_tr = np.array([0.25 if a in core_tr else 0 for a in assets])
    nav_core_tr, nav_core_te = rel_tr @ w_core_tr, rel_te @ w_core_tr
    # regla de exposición: X = min(1, 10% / |DD train del núcleo|) * 0.8 (colchón 20%)
    dd_core_tr = dd_of(nav_core_tr[:, None])[0]
    X = min(1.0, 0.10 / abs(dd_core_tr)) * 0.8
    wf.append(dict(corte=c.date(), dias_train=len(trp), dias_test=len(tep), mejorDD_train=d_tr[i], su_DD_test=d_te[i],
                   pct_validas_ok_test=(d_te >= -0.10).mean(), EW_DD_test=nav_stats(rel_te, ew)[1][0],
                   nucleo_train=",".join(s[-2:] for s in core_tr), nucleo_coincide=len(set(core_tr) & set(CORE)),
                   nucleo_DD_train=dd_core_tr, nucleo100_DD_test=dd_of(nav_core_te[:, None])[0],
                   X_regla=X, mix_DD_test=mix_dd(nav_core_te[:, None], X)[0]))
wf = pd.DataFrame(wf)
print(wf.round(3).to_string(index=False))
print(f"Cartera min-DD de train: cumple 10% en test en {(wf.su_DD_test >= -0.10).sum()}/{len(wf)} cortes; "
      f"núcleo 100%: {(wf.nucleo100_DD_test >= -0.10).sum()}/{len(wf)}; núcleo con exposición X (regla): {(wf.mix_DD_test >= -0.10).sum()}/{len(wf)}")

h("3D. Exposición máxima para DD <= 10% (COP, liquidez a rendimiento 0)")
nav_ew_cop = rel_cop @ ew.T
nav_core_cop = rel_cop @ core_w.T
print(f"EW 100%: DD {dd_of(nav_ew_cop)[0]:.1%} -> exposición máx. en muestra {max_exposure(nav_ew_cop, 0.10):.0%}")
print(f"Núcleo 100%: DD {dd_of(nav_core_cop)[0]:.1%} -> exposición máx. en muestra {max_exposure(nav_core_cop, 0.10):.0%}")
core_paths = np.array(core_paths)  # (B, T+1)
xs = np.arange(0.30, 1.0001, 0.05)
p_ok = {round(xx, 2): np.mean([mix_dd(cp[:, None], xx)[0] >= -0.10 for cp in core_paths]) for xx in xs}
print("Núcleo: P(DD <= 10%) en bootstrap según exposición X:", {k: round(v, 2) for k, v in p_ok.items()})
x90 = max([k for k, v in p_ok.items() if v >= 0.90], default=np.nan)
x95 = max([k for k, v in p_ok.items() if v >= 0.95], default=np.nan)
print(f"Exposición máx. con P(cumplir) >= 90%: {x90:.0%}; >= 95%: {x95:.0%}")
ew_paths = []
boot_rng2 = np.random.default_rng(SEED + 2)
for b in range(B_BOOT):
    idx = block_boot_idx(T, boot_rng2)
    rel = np.vstack([np.ones(len(assets)), np.cumprod(rets_loc["COP"][idx], axis=0)])
    ew_paths.append((rel @ ew.T)[:, 0])
ew_paths = np.array(ew_paths)
p_ok_ew = {round(xx, 2): np.mean([mix_dd(cp[:, None], xx)[0] >= -0.10 for cp in ew_paths]) for xx in xs}
print("EW: P(DD <= 10%) en bootstrap según exposición X:", {k: round(v, 2) for k, v in p_ok_ew.items()})

# ============================================================================= 4. TWIST
h("4A. TW_01: +65 pb en una semana")
print("Impacto implícito con betas semanales (extrapolación, IC95):")
print(rb.loc[CORE, ["beta_w_pct_por_pb", "se_w", "R2_w", "impacto_65pb", "ic95_lo", "ic95_hi"]].round(3))
w_core = core_w[0]
b_core = (rb.loc[assets, "beta_w_pct_por_pb"].values / 100 * w_core).sum()
se_core = np.sqrt(w_core @ (np.diag((rb.loc[assets, "se_w"].values / 100) ** 2)) @ w_core)  # ignora covarianzas
print(f"Núcleo: impacto implícito {65*b_core:.1%} (IC95 aprox. {65*(b_core-1.96*se_core):.1%} a {65*(b_core+1.96*se_core):.1%}) -> no informativo")
stress_cop = (loc["COP"].loc[STRESS[1]] / loc["COP"].shift(1).loc[STRESS[0]] - 1)
worst5_d = (loc["COP"] / loc["COP"].shift(5) - 1).min()
worst5_x = (xp.loc[:"2025-07-31"] / xp.loc[:"2025-07-31"].shift(5) - 1).min()
scen = pd.DataFrame({"replay_Stress_feb26_COP": stress_cop, "peor_5d_diario_COP": worst5_d, "peor_5d_intradia_USD_2020_25": worst5_x})
print(scen.round(3))
for col in scen:
    print(f"  {col}: núcleo 100% {(scen[col] * w_core).sum():.1%}; EW 100% {scen[col].mean():.1%}")

h("4B. TW_02: 30% del portafolio en 6 meses")
# retorno del núcleo a 126 días: ventanas solapadas en la muestra y bootstrap
r126 = (nav_core_cop[126:, 0] / nav_core_cop[:-126, 0] - 1)
print(f"Núcleo (COP) retorno a 6 meses en la muestra ({len(r126)} ventanas solapadas): mín {r126.min():.1%}, p10 {np.percentile(r126,10):.1%}, "
      f"P(pérdida) {(r126 < 0).mean():.0%}")
r126b = core_paths[:, 126] - 1
dd126b = np.array([dd_of(cp[:127, None])[0] for cp in core_paths])
print(f"Bootstrap: retorno a 6m p5 {np.percentile(r126b,5):.1%}, p10 {np.percentile(r126b,10):.1%}, P(pérdida) {(r126b<0).mean():.0%}; "
      f"DD dentro de los 6m p10 {np.percentile(dd126b,10):.1%}")
ew126 = ew_paths[:, 126] - 1
print(f"EW 100% a 6m (bootstrap): p5 {np.percentile(ew126,5):.1%}, P(pérdida) {(ew126<0).mean():.0%}")
for X_star in (x90, x95):
    e0 = 0.70 * X_star
    print(f"Si la exposición objetivo post-retiro es X*={X_star:.0%}: invertido hoy <= {e0:.0%}; liquidez hoy >= {1-e0:.0%} "
          f"(30% reservado + {0.70*(1-X_star):.0%} de colchón)")
for e0 in (0.49, 0.60, 0.70):
    # si no hay reserva y se retira 30% del valor inicial de la parte líquida, exposición residual
    post = e0 / (1 - 0.30)
    print(f"Invertido hoy {e0:.0%} -> tras retirar 30% desde liquidez, exposición del saldo = {post:.0%} "
          f"(P(DD<=10%) bootstrap del núcleo a esa exposición ~ {p_ok.get(round(min(1.0, round(post/0.05)*0.05),2), np.nan):.2f})")
# vender en caída: si la liquidez no alcanza y hay que vender acciones en el p10 de 6 meses
loss_p10 = np.percentile(r126b, 10)
print(f"Si el 30% dependiera de vender el núcleo (100% invertido): en el escenario p10 se vende con {loss_p10:.1%} -> "
      f"pérdida materializada {0.30*abs(min(loss_p10,0)):.1%} del patrimonio inicial sólo por el retiro")

h("4C. TW_03: COP se deprecia 8%")
shock = 0.08
def tw3(e, l_usd, l_cop, s=shock):
    return e * (1 + s) + l_usd * (1 + s) + l_cop - 1
for name, e, lu, lc in [("EW 100% invertido", 1.0, 0, 0), ("Núcleo 49% + liquidez COP 51%", 0.49, 0, 0.51),
                        ("Núcleo 49% + liquidez USD 51%", 0.49, 0.51, 0),
                        ("Núcleo 49% + 30% COP (retiro) + 21% USD", 0.49, 0.21, 0.30)]:
    up = tw3(e, lu, lc)
    rev = (e + lu) * (1 + shock) * (1 / (1 + shock) - 1) / (1 + up)  # reversión total desde el nuevo pico
    print(f"{name}: impacto inmediato en COP {up:+.1%}; si el COP revierte el 8% -> caída desde el nuevo pico {rev:.1%}")
fx126 = (macro.usd_cop.shift(-126) / macro.usd_cop - 1).dropna()
fx_vol6 = dfx.std() * np.sqrt(126)
print(f"USD/COP: vol a 6 meses {fx_vol6:.1%}; rango de cambios a 6m en muestra {fx126.min():.1%}..{fx126.max():.1%}")
print(f"Reserva de retiro (30%) en USD: IC95 de su valor en COP a 6m ≈ ±{1.96*fx_vol6:.1%} -> ±{0.30*1.96*fx_vol6:.1%} del patrimonio; en COP: 0%")
print(f"corr(ΔUSD/COP, núcleo COP-neutral): {np.corrcoef(dfx, (ret[CORE].mean(axis=1)))[0,1]:.3f} (no hay cobertura natural medible)")

h("4D. Escenario combinado (TW_01 replay Stress + TW_03 +8% + TW_02 reserva)")
stress_usd = (px.loc[STRESS[1]] / px.shift(1).loc[STRESS[0]] - 1)
for name, w, e, lu, lc in [("EW 100%", ew[0], 1.0, 0, 0), ("Núcleo 100%", w_core, 1.0, 0, 0),
                           (f"Núcleo {0.70*x90:.0%} + 30% COP + resto COP", w_core, 0.70 * x90, 0, 1 - 0.70 * x90)]:
    eq = e * (1 + (stress_usd * w).sum())
    v = eq * (1 + shock) + lu * (1 + shock) + lc
    print(f"{name}: valor COP tras Stress USD + depreciación = {v-1:+.1%} (sin el FX: {eq + lu + lc - 1:+.1%})")

# ============================================================================= 5. MONTOS EN S/ (moneda de reporte PEN)
h("5. Montos en S/ (moneda de reporte PEN; el riesgo se mide en la moneda base del cliente)")
d_ref = macro.index[-1]
usd_pen, usd_cop = macro.usd_pen.iloc[-1], macro.usd_cop.iloc[-1]
cop_per_pen = usd_cop / usd_pen
PAT = 1_000_000  # S/
print(f"FX al {d_ref.date()}: USD/PEN {usd_pen:.4f}; USD/COP {usd_cop:.2f}; cruce COP/PEN {cop_per_pen:.2f}")
print(f"Patrimonio de referencia S/ {PAT:,.0f} = USD {PAT/usd_pen:,.0f} = COP {PAT*cop_per_pen:,.0f}")
def soles(pct):
    return f"S/ {pct*PAT:,.0f}"
dd_samples = {
    "EW 100%": (dd_of(nav_ew_cop)[0], np.array([dd_of(p_[:, None])[0] for p_ in ew_paths])),
    "Núcleo 100%": (dd_of(nav_core_cop)[0], core_boot),
}
for X_ in (0.50, 0.35):
    dd_samples[f"Núcleo {X_:.0%} + liquidez"] = (mix_dd(nav_core_cop, X_)[0],
                                                  np.array([mix_dd(p_[:, None], X_)[0] for p_ in core_paths]))
print("Drawdown (medido en COP) convertido a S/ sobre S/ 1 000 000 (tipo de cambio fijo de referencia):")
base_med = np.median(dd_samples["EW 100%"][1]); base_p10 = np.percentile(dd_samples["EW 100%"][1], 10)
for k, (dd_in, dd_b) in dd_samples.items():
    med, p10 = np.median(dd_b), np.percentile(dd_b, 10)
    print(f"  {k:>24}: muestra {dd_in:.1%} ({soles(dd_in)}); bootstrap mediana {med:.1%} ({soles(med)}); p10 {p10:.1%} ({soles(p10)}); "
          f"pérdida evitada vs EW (mediana) {soles(med - base_med)}, (p10) {soles(p10 - base_p10)}")
print(f"TW_02: retiro 30% = {soles(0.30)} (= COP {0.30*PAT*cop_per_pen:,.0f} al cruce de referencia)")
print(f"TW_02: vender el núcleo en el p10 a 6 meses ({loss_p10:.1%}) para fondear el retiro materializa {soles(0.30*loss_p10)}")
print(f"TW_02: reserva de retiro en USD: IC95 ±{1.96*fx_vol6:.1%} en COP -> ±{soles(0.30*1.96*fx_vol6)}")
# TW_03 en PEN: USD/COP +8%, USD/PEN constante -> COP/PEN +8%; un saldo en COP pierde 1-1/1.08 en S/
pen_cop = 1 / (1 + shock) - 1
print(f"TW_03: con USD/PEN constante, el cruce COP/PEN pasa de {cop_per_pen:.2f} a {cop_per_pen*(1+shock):.2f} "
      f"(COP se deprecia {shock:.0%} frente al PEN; un saldo en COP vale {pen_cop:.1%} en S/)")
for name, e, lu, lc in [("EW 100% invertido", 1.0, 0, 0), ("Núcleo 49% + liquidez COP 51%", 0.49, 0, 0.51),
                        ("Núcleo 49% + liquidez USD 51%", 0.49, 0.51, 0),
                        ("Núcleo 49% + 30% COP (retiro) + 21% USD", 0.49, 0.21, 0.30),
                        ("Núcleo 35% + 65% COP", 0.35, 0, 0.65)]:
    in_cop = tw3(e, lu, lc)
    in_pen = lc * pen_cop
    print(f"  {name}: en COP {in_cop:+.1%} ({soles(in_cop)} equivalentes al cruce inicial); en S/ {in_pen:+.1%} ({soles(in_pen)})")
print(f"TW_03: el retiro de 30% (pasivo en COP) vale en S/ {soles(0.30*(1+pen_cop))} tras el shock (antes {soles(0.30)})")
for name, w, e, lc in [("EW 100%", ew[0], 1.0, 0), ("Núcleo 100%", w_core, 1.0, 0),
                       (f"Núcleo {0.70*x90:.0%} + resto COP", w_core, 0.70 * x90, 1 - 0.70 * x90)]:
    eq = e * (1 + (stress_usd * w).sum())
    v_cop = eq * (1 + shock) + lc - 1
    v_pen = eq + lc * (1 + pen_cop) - 1
    print(f"Combinado {name}: en COP {v_cop:+.1%} ({soles(v_cop)}); en S/ {v_pen:+.1%} ({soles(v_pen)})")
print("\nFin.")
