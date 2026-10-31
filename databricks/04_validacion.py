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
                   "fundamentals_raw": 65, "asset_reference": 8, "client_profiles": 3, "events": 5, "scenario_twist": 3}

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
check("silver", "intradía: sin volumen centinela 99999999", lambda: count(intra, "volume = 99999999"), 0, requires=[intra])
check("silver", "intradía: centinelas registrados en _dq_fixes",
      lambda: count(intra, "array_contains(_dq_fixes, 'Volumen centinela → nulo')"), 8, requires=[intra])
check("silver", "intradía: cubre hasta 2026-08-14 (no se filtran 2023+)",
      lambda: str(spark.table(intra).agg(F.max("date")).first()[0]) == "2026-08-14", True, requires=[intra])

check("silver", "macro: filas (una por fecha)", lambda: count(macro_t), 271, requires=[macro_t])
check("silver", "macro: inflación ffill sin nulos", lambda: count(macro_t, "us_inflation_yoy_ffill IS NULL"), 0, requires=[macro_t])
check("silver", "macro: inflación as-of nula solo antes de la 1.ª publicación", lambda: count(macro_t, "us_inflation_yoy_asof IS NULL"), 31, requires=[macro_t])
check("silver", "caso: inflación de 2025-08 visible desde 2025-09-15 (3.00)",
      lambda: value(macro_t, "us_inflation_yoy_asof", "date = '2025-09-15'"), 3.0, tol=1e-9, requires=[macro_t])
check("silver", "caso: 2025-12-01 ve el dato publicado en nov (2.96), no el del propio mes",
      lambda: value(macro_t, "us_inflation_yoy_asof", "date = '2025-12-01'"), 2.96, tol=1e-9, requires=[macro_t])
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
check("silver", "caso: revenue ISS_06 2025-06-30 marcado suspect_revenue (único)",
      lambda: count(fund, "suspect_revenue") == count(fund, "suspect_revenue AND issuer_id = 'ISS_06' AND period_end = '2025-06-30'") == 1,
      True, requires=[fund])
check("silver", "caso: cash ISS_07 2025-09-30 interpolado ≈ 335.6",
      lambda: value(fund, "cash_usd_m", "issuer_id = 'ISS_07' AND period_end = '2025-09-30' AND imputed_cash"), 335.6, tol=1e-6, requires=[fund])
check("silver", "fundamentales: cash nulo", lambda: count(fund, "cash_usd_m IS NULL"), 0, requires=[fund])
check("silver", "fundamentales: available_date = period_end + 45", lambda: count(fund, "datediff(available_date, period_end) != 45"), 0, requires=[fund])

clients_t, twist_t = S("client_profiles"), S("scenario_twist")
check("silver", "clientes: rango ordinal Media-Baja < Media < Alta",
      lambda: [r.client_id for r in spark.table(clients_t).orderBy("risk_tolerance_rank").collect()] == ["CL_02", "CL_03", "CL_01"],
      True, requires=[clients_t])
check("silver", "clientes: restricciones parseadas (45% sector, 25% alta vol, 3 países / 3 sectores)",
      lambda: sorted((r.client_id, r.max_weight_per_sector, r.max_weight_high_vol, r.min_countries, r.min_sectors)
                     for r in spark.table(clients_t).collect())
              == [("CL_01", 0.45, None, None, None), ("CL_02", None, 0.25, None, None), ("CL_03", None, None, 3, 3)],
      True, requires=[clients_t])
check("silver", "twist: 3 choques mapeados, 0 en cuarentena",
      lambda: (count(twist_t), count(S("scenario_twist_quarantine"))) == (3, 0), True, requires=[twist_t])
check("silver", "dq_log tiene registros", lambda: count(S("dq_log")) > 0, True, requires=[S("dq_log")])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold

# COMMAND ----------

G = lambda name: f"{GOLD}.{name}"
check("gold", "fact_prices_daily: filas = silver diario", lambda: count(G("fact_prices_daily")) - count(daily), 0, requires=[G("fact_prices_daily"), daily])
check("gold", "fact_prices_daily: retorno extremo (>50%)", lambda: count(G("fact_prices_daily"), "abs(ret) > 0.5"), 0, requires=[G("fact_prices_daily")])
check("gold", "asset_risk_metrics: 8 activos", lambda: count(G("asset_risk_metrics")), 8, requires=[G("asset_risk_metrics")])
check("gold", "caso: vol anual VF_A02 ≈ 46.03% (anualizada con ~261.9 sesiones observadas/año)",
      lambda: value(G("asset_risk_metrics"), "vol_anual", "asset_id = 'VF_A02'"), 0.4603, tol=0.001, requires=[G("asset_risk_metrics")])
check("gold", "asset_risk_metrics: la mitad del universo es alta volatilidad",
      lambda: count(G("asset_risk_metrics"), "alta_volatilidad"), 4, requires=[G("asset_risk_metrics")])
check("gold", "caso: max drawdown VF_A02 ≈ -55.41%",
      lambda: value(G("asset_risk_metrics"), "max_drawdown", "asset_id = 'VF_A02'"), -0.5541, tol=0.001, requires=[G("asset_risk_metrics")])
check("gold", "fundamentals_ratios: filas", lambda: count(G("fundamentals_ratios")), 64, requires=[G("fundamentals_ratios")])
check("gold", "caso: sin margen para el revenue sospechoso de ISS_06",
      lambda: count(G("fundamentals_ratios"), "suspect_revenue AND ebitda_margin IS NULL AND net_margin IS NULL"), 1, requires=[G("fundamentals_ratios")])
check("gold", "fundamentals_ratios: ninguna variación QoQ > 30% tras excluir el sospechoso",
      lambda: count(G("fundamentals_ratios"), "abs(revenue_qoq) > 0.3"), 0, requires=[G("fundamentals_ratios")])
sc = G("scenario_twist_impact")
check("gold", "caso: escenario tasa 10y 4.10 → 4.75",
      lambda: value(sc, "shocked_value", "target_column = 'us_10y_yield'"), 4.75, tol=1e-9, requires=[sc])
check("gold", "caso: escenario USD/COP 4195.52 × 1.08",
      lambda: value(sc, "shocked_value", "target_column = 'usd_cop'"), 4195.52 * 1.08, tol=1e-6, requires=[sc])
check("gold", "caso: escenario CL_02 30% líquido en 6 meses",
      lambda: spark.table(sc).filter("client_id = 'CL_02'").select("shocked_value", "horizon_months").first()[:] == (0.3, 6),
      True, requires=[sc])
check("gold", "event_impact: 5 eventos", lambda: spark.table(G("event_impact")).select("event_id").distinct().count(), 5, requires=[G("event_impact")])
check("gold", "client_asset_fit: 3 clientes × 8 activos", lambda: count(G("client_asset_fit")), 24, requires=[G("client_asset_fit")])
check("gold", "caso: CL_01 cumple con VF_A04 y VF_A05",
      lambda: sorted(r.asset_id for r in spark.table(G("client_asset_fit")).filter("client_id = 'CL_01' AND cumple_drawdown").collect()) == ["VF_A04", "VF_A05"],
      True, requires=[G("client_asset_fit")])
check("gold", "dq_scorecard: 8 tablas", lambda: count(G("dq_scorecard")), 8, requires=[G("dq_scorecard")])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold · modelo estrella
# MAGIC Las PK/FK de Unity Catalog son informativas, así que la integridad referencial se prueba aquí.

# COMMAND ----------

STAR_FKS = {"fact_precio_diario": [("sk_fecha", "dim_fecha"), ("sk_activo", "dim_activo"), ("sk_regimen", "dim_regimen")],
            "fact_macro_diario": [("sk_fecha", "dim_fecha"), ("sk_regimen", "dim_regimen")],
            "fact_fundamentales": [("sk_activo", "dim_activo"), ("sk_fecha_periodo", "dim_fecha"),
                                   ("sk_fecha_disponible", "dim_fecha")],
            "fact_impacto_evento": [("sk_evento", "dim_evento"), ("sk_activo", "dim_activo"), ("sk_fecha", "dim_fecha")],
            "fact_ajuste_cliente_activo": [("sk_cliente", "dim_cliente"), ("sk_activo", "dim_activo")]}

def orphans(fact, col, dim):
    # sk nulo o sin fila en la dimensión
    return (spark.table(G(fact)).join(spark.table(G(dim)).select(col), col, "left_anti").count())

for fact_t, fks in STAR_FKS.items():
    for col, dim in fks:
        check("gold", f"{fact_t}.{col}: sin huérfanos en {dim}", lambda f=fact_t, c=col, d=dim: orphans(f, c, d), 0,
              requires=[G(fact_t), G(dim)])

check("gold", "dim_activo: 8 activos", lambda: count(G("dim_activo")), 8, requires=[G("dim_activo")])
check("gold", "dim_regimen: 3 regímenes", lambda: count(G("dim_regimen")), 3, requires=[G("dim_regimen")])
check("gold", "dim_evento: 5 eventos", lambda: count(G("dim_evento")), 5, requires=[G("dim_evento")])
check("gold", "dim_cliente: 3 clientes + 1 versión SCD2 de CL_02", lambda: count(G("dim_cliente")), 4, requires=[G("dim_cliente")])
check("gold", "dim_cliente: una versión vigente por cliente",
      lambda: count(G("dim_cliente"), "is_current"), 3, requires=[G("dim_cliente")])
check("gold", "caso: CL_02 vigente con 30% de liquidez desde 2026-08-17",
      lambda: spark.table(G("dim_cliente")).filter("client_id = 'CL_02' AND is_current")
                   .select("liquidity_need_pct", F.col("valid_from").cast("string")).first()[:] == (0.3, "2026-08-17"),
      True, requires=[G("dim_cliente")])
check("gold", "dim_fecha: sin huecos en el calendario",
      lambda: spark.table(G("dim_fecha")).agg((F.datediff(F.max("fecha"), F.min("fecha")) + 1 - F.count("*")).alias("x")).first()["x"],
      0, requires=[G("dim_fecha")])
check("gold", "fact_precio_diario: filas = fact_prices_daily",
      lambda: count(G("fact_precio_diario")) - count(G("fact_prices_daily")), 0,
      requires=[G("fact_precio_diario"), G("fact_prices_daily")])
check("gold", "fact_macro_diario: filas = silver macro", lambda: count(G("fact_macro_diario")) - count(S("macro_daily")), 0,
      requires=[G("fact_macro_diario"), S("macro_daily")])
check("gold", "fact_fundamentales: filas", lambda: count(G("fact_fundamentales")), 64, requires=[G("fact_fundamentales")])
check("gold", "fact_impacto_evento: filas = event_impact",
      lambda: count(G("fact_impacto_evento")) - count(G("event_impact")), 0,
      requires=[G("fact_impacto_evento"), G("event_impact")])
check("gold", "fact_ajuste_cliente_activo: 3 clientes × 8 activos", lambda: count(G("fact_ajuste_cliente_activo")), 24,
      requires=[G("fact_ajuste_cliente_activo")])

# COMMAND ----------

res = spark.createDataFrame(results, "capa STRING, prueba STRING, obtenido STRING, esperado STRING, estado STRING")
display(res)
display(res.groupBy("capa").pivot("estado").count().orderBy("capa"))

failed = [r for r in results if r[4] == "❌"]
assert not failed, f"{len(failed)} pruebas fallaron: " + "; ".join(r[1] for r in failed)
print("✅ Todas las capas construidas pasan la validación")
