# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Gold: tablas de negocio
# MAGIC | Tabla | Grano | Uso |
# MAGIC |---|---|---|
# MAGIC | `fact_prices_daily` | activo × día | Precio + retorno + retorno anormal + macro (FX, régimen) |
# MAGIC | `asset_risk_metrics` | activo | Retorno, volatilidad, max drawdown, Sharpe |
# MAGIC | `fundamentals_ratios` | emisor × trimestre | Márgenes, deuda neta, deuda neta / EBITDA LTM |
# MAGIC | `event_impact` | evento × activo × día relativo | Retorno anormal acumulado (CAR) de −5 a +10 días |
# MAGIC | `client_asset_fit` | cliente × activo | Drawdown y volatilidad en la moneda del cliente vs su tolerancia |
# MAGIC | `scenario_twist_impact` | choque | Valor base (último dato) vs valor con el choque de `dataset_twist.csv` |
# MAGIC | `dq_scorecard` | tabla | Filas bronze → silver → cuarentena y correcciones aplicadas |
# MAGIC
# MAGIC > Gold usa **solo el precio diario**. El intradía no reconcilia con el diario (ver notebook de análisis);
# MAGIC > queda disponible en `silver.market_prices_intraday` hasta que la fuente defina cuál es la oficial.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from pyspark.sql import functions as F, Window as W

HIGH_VOL_QUANTILE = 0.5  # "alta volatilidad" (restricción de CL_02): vol anual sobre la mediana del universo

def write(df, table, comment):
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)
    spark.sql(f"COMMENT ON TABLE {table} IS '{comment}'")

prices = spark.table(f"{SILVER}.market_prices_daily")
macro = spark.table(f"{SILVER}.macro_daily")
assets = spark.table(f"{SILVER}.asset_reference")
w_asset = W.partitionBy("asset_id").orderBy("date")

# El calendario de la fuente incluye feriados de EE.UU. (~262 sesiones/año, no 252): se anualiza con lo observado
_cal = prices.agg(F.countDistinct("date").alias("n"), F.min("date").alias("a"), F.max("date").alias("b")).first()
TRADING_DAYS = _cal["n"] / ((_cal["b"] - _cal["a"]).days / 365.25)
print(f"Sesiones por año observadas: {TRADING_DAYS:.1f}")

# COMMAND ----------

fact = (prices.select("asset_id", "date", "open", "high", "low", "close", "volume")
        .join(assets.select("asset_id", "issuer_id", "name", "sector", "country"), "asset_id")
        .join(macro.select("date", "usd_cop", "usd_pen", "usd_mxn", "usd_clp", "us_10y_yield",
                           "us_inflation_yoy_ffill", "us_inflation_yoy_asof", "market_factor", "risk_regime"), "date", "left")
        .withColumn("ret", F.col("close") / F.lag("close").over(w_asset) - 1))
universe = fact.groupBy("date").agg(F.avg("ret").alias("ret_universe"))
fact = fact.join(universe, "date", "left").withColumn("ret_abnormal", F.col("ret") - F.col("ret_universe"))
write(fact, f"{GOLD}.fact_prices_daily", "Precio diario limpio por activo con retornos y variables macro")

# COMMAND ----------

dd = (fact.withColumn("_peak", F.max("close").over(w_asset.rowsBetween(W.unboundedPreceding, 0)))
          .withColumn("_dd", F.col("close") / F.col("_peak") - 1))
risk = (dd.groupBy("asset_id", "name", "sector", "country")
          .agg(F.min("date").alias("desde"), F.max("date").alias("hasta"), F.count("*").alias("n_dias"),
               (F.max_by("close", "date") / F.min_by("close", "date") - 1).alias("ret_total"),
               (F.pow(1 + F.avg("ret"), TRADING_DAYS) - 1).alias("ret_anual"),
               (F.stddev("ret") * F.sqrt(F.lit(TRADING_DAYS))).alias("vol_anual"),
               F.min("_dd").alias("max_drawdown"),
               F.min("ret").alias("peor_dia"), F.max("ret").alias("mejor_dia"),
               F.avg("volume").alias("volumen_prom"))
          .withColumn("sharpe_aprox", F.col("ret_anual") / F.col("vol_anual")))
vol_cut = risk.agg(F.percentile_approx("vol_anual", HIGH_VOL_QUANTILE)).first()[0]
risk = risk.withColumn("alta_volatilidad", F.col("vol_anual") > F.lit(vol_cut))
write(risk, f"{GOLD}.asset_risk_metrics", "Métricas de riesgo y retorno por activo")
display(risk.orderBy("vol_anual"))

# COMMAND ----------

w_ltm = W.partitionBy("issuer_id").orderBy("period_end").rowsBetween(-3, 0)
ratios = (spark.table(f"{SILVER}.fundamentals")
          .join(assets.select("issuer_id", "asset_id", "name", "sector"), "issuer_id", "left")
          # revenue marcado como atípico en silver no entra a márgenes ni a variaciones
          .withColumn("_rev_ok", F.when(~F.col("suspect_revenue"), F.col("revenue_usd_m")))
          .withColumn("ebitda_margin", F.col("ebitda_usd_m") / F.col("_rev_ok"))
          .withColumn("net_margin", F.col("net_income_usd_m") / F.col("_rev_ok"))
          .withColumn("net_debt_usd_m", F.col("debt_usd_m") - F.col("cash_usd_m"))
          .withColumn("_n_q", F.count("ebitda_usd_m").over(w_ltm))
          .withColumn("ebitda_ltm_usd_m", F.when(F.col("_n_q") == 4, F.sum("ebitda_usd_m").over(w_ltm)))
          .withColumn("net_debt_to_ebitda_ltm", F.col("net_debt_usd_m") / F.col("ebitda_ltm_usd_m"))
          .withColumn("revenue_qoq", F.col("_rev_ok") / F.lag("_rev_ok").over(W.partitionBy("issuer_id").orderBy("period_end")) - 1)
          .drop("_n_q", "_rev_ok", "_dq_fixes"))
write(ratios, f"{GOLD}.fundamentals_ratios", "Ratios financieros trimestrales por emisor")

# COMMAND ----------

# Event study: índice de día hábil común para medir ventanas de -5 a +10 sesiones
days = fact.select("date").distinct().withColumn("day_idx", F.row_number().over(W.orderBy("date")))
events = spark.table(f"{SILVER}.events")
targets = events.join(assets.select("asset_id", "sector"),
                      (events.scope == assets.asset_id) | (events.scope == assets.sector))
t0 = (events.join(days, days.date >= events.event_date)
            .groupBy("event_id").agg(F.min("day_idx").alias("t0_idx")))

abn = fact.select("asset_id", "date", "ret_abnormal").join(days, "date")
impact = (targets.join(t0, "event_id")
          .join(abn, ["asset_id"])
          .withColumn("t", F.col("day_idx") - F.col("t0_idx"))
          .filter(F.col("t").between(-5, 10))
          .withColumn("car", F.sum("ret_abnormal").over(
              W.partitionBy("event_id", "asset_id").orderBy("t").rowsBetween(W.unboundedPreceding, 0)))
          .select("event_id", "event_date", "scope", "event_type", "severity", "headline",
                  "asset_id", "t", "date", "ret_abnormal", "car"))
write(impact, f"{GOLD}.event_impact", "Retorno anormal acumulado alrededor de cada evento")

display(impact.filter(F.col("t").isin(-1, 3, 10))
              .groupBy("event_id", "headline", "asset_id").pivot("t", [-1, 3, 10]).agg(F.first("car"))
              .orderBy("event_id"))

# COMMAND ----------

clients = spark.table(f"{SILVER}.client_profiles")
fx = (F.when(F.col("base_currency") == "COP", F.col("usd_cop"))
       .when(F.col("base_currency") == "PEN", F.col("usd_pen"))
       .when(F.col("base_currency") == "MXN", F.col("usd_mxn"))
       .when(F.col("base_currency") == "CLP", F.col("usd_clp"))
       .otherwise(F.lit(1.0)))
w_ca = W.partitionBy("client_id", "asset_id").orderBy("date")
local = (fact.select("asset_id", "date", "close", "usd_cop", "usd_pen", "usd_mxn", "usd_clp")
         .crossJoin(F.broadcast(clients.select("client_id", "profile_name", "base_currency", "max_drawdown_tolerance_pct")))
         .withColumn("close_local", F.col("close") * fx)
         .withColumn("ret_local", F.col("close_local") / F.lag("close_local").over(w_ca) - 1)
         .withColumn("_dd", F.col("close_local") / F.max("close_local").over(w_ca.rowsBetween(W.unboundedPreceding, 0)) - 1))
fit = (local.groupBy("client_id", "profile_name", "base_currency", "max_drawdown_tolerance_pct", "asset_id")
            .agg(F.min("_dd").alias("max_drawdown_local"),
                 (F.stddev("ret_local") * F.sqrt(F.lit(TRADING_DAYS))).alias("vol_anual_local"))
            .withColumn("cumple_drawdown", F.col("max_drawdown_local") >= -F.col("max_drawdown_tolerance_pct") / 100)
            .join(assets.select("asset_id", "name", "sector", "country"), "asset_id")
            .join(risk.select("asset_id", "alta_volatilidad"), "asset_id")
            .join(clients.select("client_id", "risk_tolerance_rank", "max_weight_per_sector", "max_weight_high_vol",
                                 "min_countries", "min_sectors"), "client_id"))
write(fit, f"{GOLD}.client_asset_fit", "Drawdown y volatilidad por activo en la moneda base de cada cliente")
display(fit.groupBy("client_id", "profile_name")
           .agg(F.array_sort(F.collect_list(F.when(F.col("cumple_drawdown"), F.col("asset_id")))).alias("activos_que_cumplen")))

# COMMAND ----------

# Escenario: choques de dataset_twist sobre el último dato observado (no se mezclan con la historia)
shocks = spark.table(f"{SILVER}.scenario_twist")
last_macro = macro.orderBy(F.desc("date")).limit(1)
macro_base = (shocks.filter("target_table = 'macro_daily'").crossJoin(last_macro)
              .withColumn("base_value", F.expr("""CASE target_column
                  WHEN 'us_10y_yield' THEN us_10y_yield WHEN 'usd_cop' THEN usd_cop WHEN 'usd_pen' THEN usd_pen
                  WHEN 'usd_mxn' THEN usd_mxn WHEN 'usd_clp' THEN usd_clp END"""))
              .withColumn("base_date", F.col("date")))
# liquidez de CL_02: hoy no hay % cuantificado (solo 'Media'), así que el choque fija un valor nuevo sin base
client_base = (shocks.filter("target_table = 'client_profiles'")
               .withColumn("base_value", F.lit(None).cast("double")).withColumn("base_date", F.lit(None).cast("date")))
scenario = (macro_base.select(*shocks.columns, "base_date", "base_value")
            .unionByName(client_base.select(*shocks.columns, "base_date", "base_value"))
            .withColumn("shocked_value", F.expr("""CASE operation
                WHEN 'add' THEN base_value + shock_value WHEN 'multiply' THEN base_value * shock_value
                WHEN 'set' THEN shock_value END""")))
write(scenario, f"{GOLD}.scenario_twist_impact", "Choques del escenario twist sobre el último dato observado")
display(scenario.select("release_id", "target_table", "client_id", "target_column", "operation",
                        "base_date", "base_value", "shock_value", "shocked_value", "horizon_months"))

# COMMAND ----------

pairs = [("market_prices_raw", "market_prices_daily"), ("market_prices_intraday_raw", "market_prices_intraday"),
         ("fundamentals_raw", "fundamentals"), ("macro_raw", "macro_daily"),
         ("asset_reference", "asset_reference"), ("client_profiles", "client_profiles"), ("events", "events"),
         ("scenario_twist", "scenario_twist")]
existing = {r.tableName for r in spark.sql(f"SHOW TABLES IN {SILVER}").collect()}

def count_or_zero(table):
    return spark.table(f"{SILVER}.{table}").count() if table in existing else 0

last_run = spark.table(f"{SILVER}.dq_log").agg(F.max("run_ts")).first()[0]
fixes = (spark.table(f"{SILVER}.dq_log").filter(F.col("run_ts") == last_run)
         .filter(~F.col("rule").startswith("Cuarentena"))
         .groupBy("source_table").agg(F.sum("rows_affected").alias("correcciones")))
rows = [(b, s, spark.table(f"{BRONZE}.{b}").count(), count_or_zero(s), count_or_zero(f"{s}_quarantine")) for b, s in pairs]
scorecard = (spark.createDataFrame(rows, "bronze STRING, silver STRING, filas_bronze LONG, filas_silver LONG, filas_cuarentena LONG")
             .join(fixes.withColumnRenamed("source_table", "bronze"), "bronze", "left")
             .fillna(0, ["correcciones"])
             .withColumn("pct_retenido", F.round(F.col("filas_silver") / F.col("filas_bronze") * 100, 2))
             .withColumn("run_ts", F.lit(last_run)))
write(scorecard, f"{GOLD}.dq_scorecard", "Resumen de calidad por tabla en la última corrida")
display(scorecard)
