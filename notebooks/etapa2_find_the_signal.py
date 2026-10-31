# Databricks notebook source
# MAGIC %md
# MAGIC # Etapa 2 — Find the signal
# MAGIC
# MAGIC **Pregunta:** ¿a qué cliente le cambia más la decisión el análisis de datos y cuál es la señal que vale la pena seguir?
# MAGIC
# MAGIC **Entrada:** `credicorp_dq.silver.*` (limpieza del dominio, sin modificar).
# MAGIC **Salida (tablas nuevas en `credicorp_dq.gold`):**
# MAGIC
# MAGIC | Tabla | Qué responde |
# MAGIC |---|---|
# MAGIC | `etapa2_source_reconciliation` | ¿Qué fuente de precios es la verdad: la diaria o la intradía? |
# MAGIC | `etapa2_client_feasibility` | ¿Qué tan difícil es cumplir el perfil de cada cliente? Define el foco |
# MAGIC | `etapa2_cl02_oos_backtest` | ¿La mejor cartera 100% en acciones sigue cumpliendo para CL_02 fuera de muestra? |
# MAGIC | `etapa2_cl02_asset_view` | ¿Qué activos sirven de núcleo defensivo para CL_02 y por qué? |
# MAGIC | `etapa2_findings` | Bitácora de hallazgos de la etapa (evidencia para el pitch) |
# MAGIC
# MAGIC Reproducible: semilla fija (7), 200 000 carteras aleatorias long-only (Dirichlet α=0.6), compra y mantenimiento.

# COMMAND ----------

import numpy as np
import pandas as pd
from pyspark.sql import functions as F

CAT = "credicorp_dq"
SEED, N = 7, 200_000
HIGH_VOL_THRESHOLD = 0.30          # supuesto: vol anual > 30% = "alta volatilidad" (CL_02)
CUT = pd.Timestamp("2026-04-10")    # 2/3 entrenamiento, 1/3 prueba
CLIENT_CCY = {"USD": None, "COP": "usd_cop", "PEN": "usd_pen"}

def t(name):  # lector
    return spark.table(f"{CAT}.{name}").toPandas()

def save(df: pd.DataFrame, name: str, comment: str):
    full = f"{CAT}.gold.{name}"
    spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(full)
    spark.sql(f"COMMENT ON TABLE {full} IS '{comment}'")
    spark.sql(f"ALTER TABLE {full} SET TAGS ('etapa'='2-find-the-signal', 'owner'='fabrizio.vx', 'source'='silver')")
    print(f"✓ {full}: {len(df)} filas")

# COMMAND ----------

# MAGIC %md ## 1. Carga desde silver

# COMMAND ----------

prices = t("silver.market_prices_daily")
prices["date"] = pd.to_datetime(prices["date"])
macro = t("silver.macro_daily")
macro["date"] = pd.to_datetime(macro["date"])
macro = macro.set_index("date").sort_index()
ref = t("silver.asset_reference").set_index("asset_id")
clients = t("silver.client_profiles").set_index("client_id")
fund = t("silver.fundamentals")
fund["period_end"] = pd.to_datetime(fund["period_end"])
events = t("silver.events")
events["event_date"] = pd.to_datetime(events["event_date"])

px = prices.pivot(index="date", columns="asset_id", values="close").sort_index().astype(float)
assets = list(px.columns)
assert px.index.equals(macro.index), "precios y macro deben estar alineados por fecha"

def to_ccy(frame: pd.DataFrame, ccy: str) -> pd.DataFrame:
    col = CLIENT_CCY[ccy]
    return frame if col is None else frame.mul(macro[col].astype(float), axis=0)

# COMMAND ----------

# MAGIC %md ## 2. Reconciliación de fuentes: diario vs intradía
# MAGIC Ambas parten del mismo precio el 2025-08-01. Si fueran la misma serie, sus retornos diarios estarían correlacionados ~1.
# MAGIC Prueba de verdad: ¿cuál reacciona en la dirección esperada a los eventos?

# COMMAND ----------

intra = (spark.table(f"{CAT}.silver.market_prices_intraday")
         .groupBy("asset_id", "date").agg(F.max_by("close", "ts").alias("close_intraday"))
         .toPandas())
intra["date"] = pd.to_datetime(intra["date"])
both = prices[["asset_id", "date", "close"]].merge(intra, on=["asset_id", "date"])
rows = []
for a, g in both.sort_values("date").groupby("asset_id"):
    r1, r2 = g.close.astype(float).pct_change(), g.close_intraday.astype(float).pct_change()
    rows.append({"asset_id": a, "dias_comunes": len(g),
                 "corr_retornos": float(r1.corr(r2)),
                 "dif_abs_media_usd": float((g.close - g.close_intraday).abs().mean()),
                 "close_diario_final": float(g.close.iloc[-1]),
                 "close_intradia_final": float(g.close_intraday.iloc[-1])})
recon = pd.DataFrame(rows)

# dirección esperada por evento (lectura del titular)
EXPECTED = {"Operational": -1, "Commodity": +1, "Earnings": +1, "Demand": -1, "Sector": -1}
px_i = both.pivot(index="date", columns="asset_id", values="close_intraday").sort_index().astype(float)
def car(frame, members, d, post=5):
    out = []
    for a in members:
        s = frame[a].dropna(); i = s.index.searchsorted(d)
        if 0 < i and i + post < len(s):
            out.append(s.iloc[i + post] / s.iloc[i - 1] - 1)
    return float(np.mean(out)) if out else np.nan
ev_rows = []
for _, e in events.iterrows():
    members = [e.scope] if e.scope in assets else ref.index[ref.sector == e.scope].tolist()
    exp = EXPECTED.get(e.event_type, 0)
    cd, ci = car(px, members, e.event_date), car(px_i, members, e.event_date)
    ev_rows.append({"event_date": e.event_date.date().isoformat(), "scope": e.scope, "event_type": e.event_type,
                    "severity": e.severity, "direccion_esperada": exp,
                    "ret_d0_d5_diario": cd, "ret_d0_d5_intradia": ci,
                    "diario_acierta": bool(np.sign(cd) == exp), "intradia_acierta": bool(np.sign(ci) == exp)})
ev_check = pd.DataFrame(ev_rows)
display(recon); display(ev_check)
print("aciertos diario:", ev_check.diario_acierta.sum(), "/", len(ev_check),
      "| intradía:", ev_check.intradia_acierta.sum(), "/", len(ev_check))

# COMMAND ----------

recon_out = recon.assign(tipo="activo", detalle=recon.asset_id)
ev_out = ev_check.assign(tipo="evento", detalle=ev_check.event_date + " " + ev_check.scope)
save(pd.concat([recon_out, ev_out], ignore_index=True),
     "etapa2_source_reconciliation",
     "Etapa 2: diario vs intradía. Las series divergen (corr ~0); el diario reacciona a 4/5 eventos y se usa como fuente.")

# COMMAND ----------

# MAGIC %md ## 3. Selección de foco: factibilidad por cliente
# MAGIC Para cada cliente: de 200k carteras aleatorias, ¿qué % cumple su restricción y además su drawdown máximo, en su moneda base?

# COMMAND ----------

vol_usd = px.pct_change().std() * np.sqrt(252)
high_vol = vol_usd[vol_usd > HIGH_VOL_THRESHOLD].index.tolist()
sec = ref.loc[assets, "sector"].values
ctry = ref.loc[assets, "country"].values
W = np.random.default_rng(SEED).dirichlet(np.full(len(assets), 0.6), N)
EW = np.full((1, len(assets)), 1 / len(assets))

def nav_stats(frame, weights):
    nav = (frame / frame.iloc[0]).values @ weights.T
    dd = (nav / np.maximum.accumulate(nav, axis=0) - 1).min(axis=0)
    return nav[-1] - 1, dd

def constraint_ok(cid, weights):
    if cid == "CL_01":
        by_sec = pd.DataFrame(weights, columns=sec).T.groupby(level=0).sum().T.values
        return by_sec.max(axis=1) <= 0.45
    if cid == "CL_02":
        return weights[:, np.isin(assets, high_vol)].sum(axis=1) <= 0.25
    held = weights > 0.05
    n_c = pd.DataFrame(held, columns=ctry).T.groupby(level=0).any().T.sum(axis=1).values
    n_s = pd.DataFrame(held, columns=sec).T.groupby(level=0).any().T.sum(axis=1).values
    return (n_c >= 3) & (n_s >= 3)

feas_rows = []
for cid, c in clients.iterrows():
    loc = to_ccy(px, c.base_currency)
    tol = float(c.max_drawdown_tolerance_pct) / 100
    ret, dd = nav_stats(loc, W)
    ok = constraint_ok(cid, W)
    feas = ok & (dd >= -tol)
    r_ew, d_ew = nav_stats(loc, EW)
    feas_rows.append({"client_id": cid, "profile_name": c.profile_name, "base_currency": c.base_currency,
                      "max_dd_tolerancia": tol, "restriccion": c.constraint,
                      "pct_cumple_restriccion": float(ok.mean()), "pct_cumple_restriccion_y_dd": float(feas.mean()),
                      "n_carteras_factibles": int(feas.sum()), "mejor_dd_posible": float(dd[ok].max()),
                      "dd_equiponderada": float(d_ew[0]), "ret_equiponderada": float(r_ew[0]),
                      "equiponderada_cumple": bool(d_ew[0] >= -tol)})
feas_df = pd.DataFrame(feas_rows)
feas_df["foco"] = feas_df.pct_cumple_restriccion_y_dd == feas_df.pct_cumple_restriccion_y_dd.min()
display(feas_df)
save(feas_df, "etapa2_client_feasibility",
     "Etapa 2: % de 200k carteras que cumplen restricción + drawdown por cliente. El menor define el foco (CL_02).")

# COMMAND ----------

# MAGIC %md ## 4. CL_02 fuera de muestra
# MAGIC Elegimos la cartera con menor drawdown usando solo datos hasta 2026-04-10 y medimos qué pasó después.

# COMMAND ----------

c2 = clients.loc["CL_02"]
loc2 = to_ccy(px, c2.base_currency)
tol2 = float(c2.max_drawdown_tolerance_pct) / 100
Wc = W[constraint_ok("CL_02", W)]
tr, te = loc2[loc2.index < CUT], loc2[loc2.index >= CUT]
r_tr, d_tr = nav_stats(tr, Wc); r_te, d_te = nav_stats(te, Wc)
i_min = int(np.argmax(d_tr))
feas_tr = d_tr >= -tol2
i_ret = int(np.where(feas_tr)[0][np.argmax(r_tr[feas_tr])])
er_tr, ed_tr = nav_stats(tr, EW); er_te, ed_te = nav_stats(te, EW)

def row(name, w, rtr, dtr, rte, dte):
    d = {"estrategia": name, "train_desde": str(tr.index.min().date()), "train_hasta": str(tr.index.max().date()),
         "test_desde": str(te.index.min().date()), "test_hasta": str(te.index.max().date()),
         "ret_train": float(rtr), "dd_train": float(dtr), "ret_test": float(rte), "dd_test": float(dte),
         "cumple_dd_train": bool(dtr >= -tol2), "cumple_dd_test": bool(dte >= -tol2)}
    d.update({f"w_{a}": float(x) for a, x in zip(assets, w)})
    return d

bt = pd.DataFrame([
    row("min_drawdown_en_train", Wc[i_min], r_tr[i_min], d_tr[i_min], r_te[i_min], d_te[i_min]),
    row("max_retorno_factible_en_train", Wc[i_ret], r_tr[i_ret], d_tr[i_ret], r_te[i_ret], d_te[i_ret]),
    row("equiponderada", EW[0], er_tr[0], ed_tr[0], er_te[0], ed_te[0]),
])
bt["pct_carteras_validas_cumplen_test"] = float((d_te >= -tol2).mean())
display(bt)
save(bt, "etapa2_cl02_oos_backtest",
     "Etapa 2: CL_02 fuera de muestra. Ni la mejor cartera 100% acciones elegida en train cumple DD<=10% en test.")

# COMMAND ----------

# MAGIC %md ## 5. Vista por activo para CL_02 (en COP) + fundamentales

# COMMAND ----------

f = fund.sort_values(["issuer_id", "period_end"]).copy()
for c in ["revenue_usd_m", "ebitda_usd_m", "net_income_usd_m", "debt_usd_m", "cash_usd_m"]:
    f[c] = f[c].astype(float)
med = f.groupby("issuer_id").revenue_usd_m.transform("median")
f["revenue_outlier"] = f.revenue_usd_m < 0.75 * med     # ISS_06 2025-06-30 = 1845.7 (typo probable)
f["ebitda_margin"] = np.where(f.revenue_outlier, np.nan, f.ebitda_usd_m / f.revenue_usd_m)
# apalancamiento con EBITDA LTM (suma de 4 trimestres), igual que gold.fundamentals_ratios.
# Con EBITDA de un solo trimestre el ratio se infla ~4x.
f["ebitda_ltm"] = f.groupby("issuer_id").ebitda_usd_m.transform(lambda s: s.rolling(4).sum())
f["net_debt_ebitda"] = (f.debt_usd_m - f.cash_usd_m) / f.ebitda_ltm
g = f.groupby("issuer_id")
fz = pd.DataFrame({
    "ni_yoy": g.net_income_usd_m.apply(lambda s: s.iloc[-1] / s.iloc[-5] - 1),
    "revenue_yoy": g.revenue_usd_m.apply(lambda s: s.iloc[-1] / s.iloc[-5] - 1),
    "ebitda_margin_ult": g.ebitda_margin.last(),
    "net_debt_ebitda_ult": g.net_debt_ebitda.last(),
    "net_debt_ebitda_hace_1a": g.net_debt_ebitda.apply(lambda s: s.iloc[-5]),
})

st = macro.index[macro.risk_regime == "Stress"]
win = loc2.loc[st.min() - pd.Timedelta(days=3): st.max()]
rets = loc2.pct_change()
av = pd.DataFrame({
    "ret_total_cop": loc2.iloc[-1] / loc2.iloc[0] - 1,
    "ret_3m_cop": loc2.iloc[-1] / loc2.iloc[-64] - 1,
    "vol_anual_cop": rets.std() * np.sqrt(252),
    "max_dd_cop": (loc2 / loc2.cummax() - 1).min(),
    "ret_en_stress_cop": win.iloc[-1] / win.iloc[0] - 1,
}).join(ref[["name", "sector", "country", "issuer_id"]])
av = av.join(fz, on="issuer_id")
av["alta_volatilidad"] = av.index.isin(high_vol)
av["rol_cl02"] = np.where(av.alta_volatilidad, "limitado (≤25% total)", "núcleo defensivo")
av = av.reset_index().rename(columns={"index": "asset_id"})
display(av)
save(av, "etapa2_cl02_asset_view",
     "Etapa 2: riesgo/retorno de cada activo en COP para CL_02 + fundamentales; rol núcleo vs limitado.")

# COMMAND ----------

# MAGIC %md ## 6. Bitácora de hallazgos

# COMMAND ----------

fx_cop = macro.usd_cop.astype(float)
fx_pen = macro.usd_pen.astype(float)
cl02 = feas_df.set_index("client_id").loc["CL_02"]
mn = bt.set_index("estrategia").loc["min_drawdown_en_train"]
findings = pd.DataFrame([
    ("calidad", "Diario e intradía divergen en el periodo común",
     f"corr retornos media {recon.corr_retornos.mean():.2f}; diario acierta {ev_check.diario_acierta.sum()}/5 eventos vs intradía {ev_check.intradia_acierta.sum()}/5",
     "Se usa el diario como fuente de verdad", "gold.etapa2_source_reconciliation"),
    ("calidad", "Revenue ISS_06 2025-06-30 fuera de patrón",
     "1845.7 vs mediana ~2850; margen salta de 15% a 24%",
     "Se excluye de ratios (silver no se modifica)", "gold.etapa2_cl02_asset_view"),
    ("hipotesis_descartada", "El FX no es la señal",
     f"USD/COP {fx_cop.iloc[-1]/fx_cop.iloc[0]-1:+.1%} (vol {fx_cop.pct_change().std()*np.sqrt(252):.1%}); USD/PEN {fx_pen.iloc[-1]/fx_pen.iloc[0]-1:+.1%}",
     "El FX mueve el drawdown 1-2 pp; no decide", "silver.macro_daily"),
    ("foco", "CL_02 es el cliente donde los datos más cambian la decisión",
     f"{cl02.pct_cumple_restriccion_y_dd:.2%} de carteras factibles; equiponderada DD {cl02.dd_equiponderada:.1%} vs límite -10%",
     "Foco de la solución: CL_02", "gold.etapa2_client_feasibility"),
    ("senal", "100% acciones no cumple de forma robusta el límite de CL_02",
     f"mejor cartera en train DD {mn.dd_train:.1%} -> test {mn.dd_test:.1%}; solo {bt.pct_carteras_validas_cumplen_test.iloc[0]:.1%} cumplen en test",
     "La palanca es la exposición (núcleo defensivo + liquidez)", "gold.etapa2_cl02_oos_backtest"),
], columns=["tipo", "hallazgo", "evidencia", "decision", "tabla_soporte"])
findings["etapa"] = "2-find-the-signal"
display(findings)
save(findings, "etapa2_findings", "Etapa 2: bitácora de hallazgos, evidencia y decisión (insumo del pitch).")
