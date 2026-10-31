# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Validación de salidas
# MAGIC Se puede correr **después de cada capa**: las capas que todavía no existen se marcan como `⏭️ pendiente`.
# MAGIC
# MAGIC Tres tipos de prueba:
# MAGIC 1. **Reconciliación**: filas en bronze = líneas del CSV en el volume (sin perder ni inventar filas).
# MAGIC 2. **Valores esperados**: conteos y casos puntuales conocidos del análisis (p. ej. el `close = 3589` debe quedar en `35.89`).
# MAGIC 3. **Reglas**: ningún ID fuera del maestro, sin duplicados, OHLC coherente, etc.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from pyspark.sql import functions as F

results = []

def exists(table):
    return spark.catalog.tableExists(table)

def check(layer, name, actual_fn, expected, tol=None, requires=()):
    if not all(exists(t) for t in requires):
        results.append((layer, name, "", str(expected), "⏭️ pendiente"))
        return
    try:
        actual = actual_fn()
        ok = abs(actual - expected) <= tol if tol is not None else actual == expected
        results.append((layer, name, str(actual), str(expected), "✅" if ok else "❌"))
    except Exception as e:
        results.append((layer, name, f"ERROR: {str(e)[:80]}", str(expected), "❌"))

def count(table, where=None):
    df = spark.table(table)
    return (df.filter(where) if where else df).count()

def value(table, col, where):
    return spark.table(table).filter(where).select(col).first()[0]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze

# COMMAND ----------

EXPECTED_BRONZE = {"market_prices_raw": 2175, "market_prices_intraday_raw": 538836, "macro_raw": 271,
                   "fundamentals_raw": 65, "asset_reference": 8, "client_profiles": 3, "events": 5}

for table, fname in SOURCES.items():
    t = f"{BRONZE}.{table}"
    # reconciliación contra el archivo: líneas no vacías menos el encabezado
    check("bronze", f"{table}: filas = líneas del CSV",
          lambda t=t, fname=fname: count(t) - (spark.read.text(f"{LANDING}/{fname}").filter("trim(value) != ''").count() - 1),
          0, requires=[t])
    check("bronze", f"{table}: filas esperadas", lambda t=t: count(t), EXPECTED_BRONZE[table], requires=[t])
    check("bronze", f"{table}: todas las columnas STRING",
          lambda t=t: sum(1 for f in spark.table(t).schema if f.name != "_ingest_ts" and f.dataType.simpleString() != "string"),
          0, requires=[t])
    check("bronze", f"{table}: sin BOM en encabezados",
          lambda t=t: sum("﻿" in c for c in spark.table(t).columns), 0, requires=[t])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver

# COMMAND ----------

S = lambda name: f"{SILVER}.{name}"
daily, intra, fund, macro_t = S("market_prices_daily"), S("market_prices_intraday"), S("fundamentals"), S("macro_daily")

check("silver", "precios diarios: filas", lambda: count(daily), 2168, requires=[daily])
check("silver", "precios diarios: 8 activos válidos", lambda: spark.table(daily).select("asset_id").distinct().count(), 8, requires=[daily])
check("silver", "precios diarios: IDs fuera del maestro",
      lambda: spark.table(daily).join(spark.table(S("asset_reference")), "asset_id", "left_anti").count(), 0, requires=[daily])
check("silver", "precios diarios: llave (asset_id, date) duplicada",
      lambda: spark.table(daily).groupBy("asset_id", "date").count().filter("count > 1").count(), 0, requires=[daily])
check("silver", "precios diarios: OHLC incoherente",
      lambda: count(daily, "close > high OR close < low OR high < low"), 0, requires=[daily])
check("silver", "precios diarios: currency nula", lambda: count(daily, "currency IS NULL"), 0, requires=[daily])
check("silver", "precios diarios: fecha mínima", lambda: str(spark.table(daily).agg(F.min("date")).first()[0]) == "2025-08-01", True, requires=[daily])
check("silver", "precios diarios: fecha máxima", lambda: str(spark.table(daily).agg(F.max("date")).first()[0]) == "2026-08-14", True, requires=[daily])
check("silver", "caso: close 3589 → 35.89 (VF_A06 2026-03-23)",
      lambda: value(daily, "close", "asset_id = 'VF_A06' AND date = '2026-03-23'"), 35.89, tol=1e-6, requires=[daily])
check("silver", "caso: volumen '3635.6K' → 3635600 (VF_A07 2025-08-19)",
      lambda: value(daily, "volume", "asset_id = 'VF_A07' AND date = '2025-08-19'"), 3635600, requires=[daily])
check("silver", "caso: fecha '09/05/2025' → 2025-09-05 (VF_A02)",
      lambda: count(daily, "asset_id = 'VF_A02' AND date = '2025-09-05'"), 1, requires=[daily])
check("silver", "filas con correcciones registradas en _dq_fixes",
      lambda: count(daily, "size(_dq_fixes) > 0"), 15, requires=[daily])

check("silver", "intradía: filas", lambda: count(intra), 538800, requires=[intra])
check("silver", "intradía: cuarentena (close nulo)", lambda: count(S("market_prices_intraday_quarantine")), 24, requires=[intra])

check("silver", "macro: filas (una por fecha)", lambda: count(macro_t), 271, requires=[macro_t])
check("silver", "macro: inflación ffill sin nulos", lambda: count(macro_t, "us_inflation_yoy_ffill IS NULL"), 0, requires=[macro_t])
check("silver", "macro: todas las fechas de mercado tienen macro",
      lambda: spark.table(daily).select("date").distinct().join(spark.table(macro_t), "date", "left_anti").count(), 0,
      requires=[daily, macro_t])

check("silver", "fundamentales: filas", lambda: count(fund), 64, requires=[fund])
check("silver", "fundamentales: 8 trimestres por emisor",
      lambda: spark.table(fund).groupBy("issuer_id").count().filter("count != 8").count(), 0, requires=[fund])
check("silver", "caso: 'ISS04' normalizado (ISS_04 completo)", lambda: count(fund, "issuer_id = 'ISS_04'"), 8, requires=[fund])
check("silver", "caso: 'Q4-2024' de ISS_02 → 2025-06-30 imputado",
      lambda: count(fund, "issuer_id = 'ISS_02' AND period_end = '2025-06-30' AND imputed_period"), 1, requires=[fund])
check("silver", "caso: revenue '1,845.7' → 1845.7 (ISS_06 2025-06-30)",
      lambda: value(fund, "revenue_usd_m", "issuer_id = 'ISS_06' AND period_end = '2025-06-30'"), 1845.7, tol=1e-6, requires=[fund])
check("silver", "dq_log tiene registros", lambda: count(S("dq_log")) > 0, True, requires=[S("dq_log")])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold

# COMMAND ----------

G = lambda name: f"{GOLD}.{name}"
check("gold", "fact_prices_daily: filas = silver diario", lambda: count(G("fact_prices_daily")) - count(daily), 0, requires=[G("fact_prices_daily"), daily])
check("gold", "fact_prices_daily: retorno extremo (>50%)", lambda: count(G("fact_prices_daily"), "abs(ret) > 0.5"), 0, requires=[G("fact_prices_daily")])
check("gold", "asset_risk_metrics: 8 activos", lambda: count(G("asset_risk_metrics")), 8, requires=[G("asset_risk_metrics")])
check("gold", "caso: vol anual VF_A02 ≈ 45.15%",
      lambda: value(G("asset_risk_metrics"), "vol_anual", "asset_id = 'VF_A02'"), 0.4515, tol=0.001, requires=[G("asset_risk_metrics")])
check("gold", "caso: max drawdown VF_A02 ≈ -55.41%",
      lambda: value(G("asset_risk_metrics"), "max_drawdown", "asset_id = 'VF_A02'"), -0.5541, tol=0.001, requires=[G("asset_risk_metrics")])
check("gold", "fundamentals_ratios: filas", lambda: count(G("fundamentals_ratios")), 64, requires=[G("fundamentals_ratios")])
check("gold", "event_impact: 5 eventos", lambda: spark.table(G("event_impact")).select("event_id").distinct().count(), 5, requires=[G("event_impact")])
check("gold", "client_asset_fit: 3 clientes × 8 activos", lambda: count(G("client_asset_fit")), 24, requires=[G("client_asset_fit")])
check("gold", "caso: CL_01 cumple con VF_A04 y VF_A05",
      lambda: sorted(r.asset_id for r in spark.table(G("client_asset_fit")).filter("client_id = 'CL_01' AND cumple_drawdown").collect()) == ["VF_A04", "VF_A05"],
      True, requires=[G("client_asset_fit")])
check("gold", "dq_scorecard: 7 tablas", lambda: count(G("dq_scorecard")), 7, requires=[G("dq_scorecard")])

# COMMAND ----------

res = spark.createDataFrame(results, "capa STRING, prueba STRING, obtenido STRING, esperado STRING, estado STRING")
display(res)
display(res.groupBy("capa").pivot("estado").count().orderBy("capa"))

failed = [r for r in results if r[4] == "❌"]
assert not failed, f"{len(failed)} pruebas fallaron: " + "; ".join(r[1] for r in failed)
print("✅ Todas las capas construidas pasan la validación")
