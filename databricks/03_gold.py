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
# MAGIC | `dq_scorecard` | tabla | Filas bronze → silver → cuarentena y correcciones aplicadas |
# MAGIC | `dim_*` / `fact_*` (estrella) | ver sección final | Modelo dimensional para BI |
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

pairs = [("market_prices_raw", "market_prices_daily"), ("market_prices_intraday_raw", "market_prices_intraday"),
         ("fundamentals_raw", "fundamentals"), ("macro_raw", "macro_daily"),
         ("asset_reference", "asset_reference"), ("client_profiles", "client_profiles"), ("events", "events")]
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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Modelo dimensional (estrella)
# MAGIC Las mismas métricas de arriba reorganizadas en dimensiones + hechos.
# MAGIC Las tablas anchas se mantienen porque el dashboard y `05_reporte_calidad` las leen.
# MAGIC
# MAGIC | Tabla | Grano |
# MAGIC |---|---|
# MAGIC | `dim_fecha` | día calendario (`sk_fecha = yyyymmdd`) |
# MAGIC | `dim_activo` | activo (emisor aplanado, 1:1) |
# MAGIC | `dim_cliente` | cliente |
# MAGIC | `dim_evento` | evento |
# MAGIC | `dim_regimen` | régimen de mercado |
# MAGIC | `fact_precio_diario` | activo × día |
# MAGIC | `fact_macro_diario` | día |
# MAGIC | `fact_fundamentales` | activo × trimestre |
# MAGIC | `fact_impacto_evento` | evento × activo × día relativo |
# MAGIC | `fact_ajuste_cliente_activo` | cliente × activo |
# MAGIC
# MAGIC Las claves sustitutas se asignan con `row_number` sobre la llave de negocio (deterministas entre corridas).
# MAGIC Los ratios no aditivos (márgenes, deuda neta/EBITDA, Sharpe) no se guardan en los hechos: se calculan al consultar.

# COMMAND ----------

STAR_DIMS = ["dim_fecha", "dim_activo", "dim_cliente", "dim_evento", "dim_regimen"]
STAR_FACTS = ["fact_precio_diario", "fact_macro_diario", "fact_fundamentales", "fact_impacto_evento",
              "fact_ajuste_cliente_activo"]
REGIMES = [("Normal", 1), ("Recovery", 2), ("Stress", 3)]  # sk_regimen = orden de estrés

# Las FK impiden reemplazar una dimensión referenciada: se borran primero los hechos y luego las dimensiones
for t in STAR_FACTS + STAR_DIMS:
    spark.sql(f"DROP TABLE IF EXISTS {GOLD}.{t}")

def sk(order_cols):
    return F.row_number().over(W.orderBy(*order_cols)).cast("int")

def sk_fecha(col):
    return F.date_format(col, "yyyyMMdd").cast("int")

# COMMAND ----------

# Dimensiones
bounds = (fact.select(F.col("date").alias("d"))
          .unionByName(ratios.select(F.col("period_end").alias("d")))
          .unionByName(ratios.select(F.col("available_date").alias("d")))
          .agg(F.min("d").alias("a"), F.max("d").alias("b")).first())
sessions = fact.select("date").distinct().withColumn("es_sesion", F.lit(True))
dim_fecha = (spark.range(1)
             .select(F.explode(F.sequence(F.lit(bounds["a"]), F.lit(bounds["b"]))).alias("fecha"))
             .join(sessions.withColumnRenamed("date", "fecha"), "fecha", "left")
             .select(sk_fecha("fecha").alias("sk_fecha"), "fecha",
                     F.year("fecha").alias("anio"), F.quarter("fecha").alias("trimestre"), F.month("fecha").alias("mes"),
                     F.date_format("fecha", "MMMM").alias("nombre_mes"), F.weekofyear("fecha").alias("semana_anio"),
                     F.dayofweek("fecha").alias("dia_semana"),
                     (F.col("fecha") == F.last_day("fecha")).alias("es_fin_mes"),
                     ((F.col("fecha") == F.last_day("fecha")) & (F.month("fecha") % 3 == 0)).alias("es_fin_trimestre"),
                     F.coalesce("es_sesion", F.lit(False)).alias("es_sesion")))
write(dim_fecha, f"{GOLD}.dim_fecha", "Dimensión calendario; sk_fecha = yyyymmdd")

dim_regimen = spark.createDataFrame([(o, r, o) for r, o in REGIMES], "sk_regimen INT, risk_regime STRING, orden_estres INT")
write(dim_regimen, f"{GOLD}.dim_regimen", "Regímenes de mercado ordenados por estrés")

dim_activo = (assets.join(risk.select("asset_id", "alta_volatilidad"), "asset_id", "left")
              .select(sk(["asset_id"]).alias("sk_activo"), "asset_id", "issuer_id", F.col("name").alias("nombre"),
                      "sector", F.col("country").alias("pais"), F.col("market").alias("mercado"),
                      F.col("currency").alias("moneda"), "alta_volatilidad"))
write(dim_activo, f"{GOLD}.dim_activo", "Dimensión de activos con su emisor (1:1)")

dim_evento = events.select(sk(["event_date", "event_id"]).alias("sk_evento"), "event_id", "event_date", "scope",
                           "scope_type", "event_type", "severity", "headline")
write(dim_evento, f"{GOLD}.dim_evento", "Eventos de mercado por activo o sector")

dim_cliente = clients.select(sk(["client_id"]).alias("sk_cliente"), *clients.columns)
write(dim_cliente, f"{GOLD}.dim_cliente", "Perfiles de cliente con restricciones parseadas")

# COMMAND ----------

# Hechos: llaves de negocio -> claves sustitutas
k_activo = spark.table(f"{GOLD}.dim_activo").select("asset_id", "sk_activo")
k_regimen = spark.table(f"{GOLD}.dim_regimen").select("risk_regime", "sk_regimen")
k_evento = spark.table(f"{GOLD}.dim_evento").select("event_id", "sk_evento")
k_cliente = spark.table(f"{GOLD}.dim_cliente").select("client_id", "sk_cliente")

f_precio = (fact.join(k_activo, "asset_id", "left").join(k_regimen, "risk_regime", "left")
            .select(sk_fecha("date").alias("sk_fecha"), "sk_activo", "sk_regimen",
                    "open", "high", "low", "close", "volume", "ret", "ret_universe", "ret_abnormal",
                    (F.col("close") * F.col("usd_cop")).alias("close_cop"),
                    (F.col("close") * F.col("usd_pen")).alias("close_pen")))
write(f_precio, f"{GOLD}.fact_precio_diario", "Hecho: precio diario por activo")

f_macro = (macro.join(k_regimen, "risk_regime", "left")
           .select(sk_fecha("date").alias("sk_fecha"), "sk_regimen", "us_10y_yield", "us_inflation_yoy_ffill",
                   "us_inflation_yoy_asof", "usd_cop", "usd_pen", "usd_mxn", "usd_clp", "market_factor"))
write(f_macro, f"{GOLD}.fact_macro_diario", "Hecho: variables macro diarias")

f_fund = (ratios.join(k_activo, "asset_id", "left")
          .select("sk_activo", sk_fecha("period_end").alias("sk_fecha_periodo"),
                  sk_fecha("available_date").alias("sk_fecha_disponible"),
                  "revenue_usd_m", "ebitda_usd_m", "net_income_usd_m", "debt_usd_m", "cash_usd_m",
                  "net_debt_usd_m", "ebitda_ltm_usd_m", "suspect_revenue", "imputed_cash"))
write(f_fund, f"{GOLD}.fact_fundamentales", "Hecho: fundamentales trimestrales por activo/emisor")

f_evento = (impact.join(k_evento, "event_id", "left").join(k_activo, "asset_id", "left")
            .select("sk_evento", "sk_activo", sk_fecha("date").alias("sk_fecha"), "t", "ret_abnormal", "car"))
write(f_evento, f"{GOLD}.fact_impacto_evento", "Hecho: retorno anormal acumulado alrededor de cada evento")

f_ajuste = (fit.join(k_cliente, "client_id", "left").join(k_activo, "asset_id", "left")
            .select("sk_cliente", "sk_activo", "max_drawdown_local", "vol_anual_local", "cumple_drawdown"))
write(f_ajuste, f"{GOLD}.fact_ajuste_cliente_activo", "Hecho: drawdown y volatilidad por cliente y activo")

# COMMAND ----------

# PK/FK informativas (Unity Catalog no las valida al escribir; las usan el optimizador y Power BI).
# La integridad se comprueba en 04_validacion.
PKS = {"dim_fecha": ["sk_fecha"], "dim_activo": ["sk_activo"], "dim_cliente": ["sk_cliente"],
       "dim_evento": ["sk_evento"], "dim_regimen": ["sk_regimen"],
       "fact_precio_diario": ["sk_fecha", "sk_activo"], "fact_macro_diario": ["sk_fecha"],
       "fact_fundamentales": ["sk_activo", "sk_fecha_periodo"], "fact_impacto_evento": ["sk_evento", "sk_activo", "t"],
       "fact_ajuste_cliente_activo": ["sk_cliente", "sk_activo"]}
FKS = {"fact_precio_diario": [("sk_fecha", "dim_fecha"), ("sk_activo", "dim_activo"), ("sk_regimen", "dim_regimen")],
       "fact_macro_diario": [("sk_fecha", "dim_fecha"), ("sk_regimen", "dim_regimen")],
       "fact_fundamentales": [("sk_activo", "dim_activo"), ("sk_fecha_periodo", "dim_fecha"),
                              ("sk_fecha_disponible", "dim_fecha")],
       "fact_impacto_evento": [("sk_evento", "dim_evento"), ("sk_activo", "dim_activo"), ("sk_fecha", "dim_fecha")],
       "fact_ajuste_cliente_activo": [("sk_cliente", "dim_cliente"), ("sk_activo", "dim_activo")]}

for t in STAR_DIMS + STAR_FACTS:
    for c in PKS[t]:
        spark.sql(f"ALTER TABLE {GOLD}.{t} ALTER COLUMN {c} SET NOT NULL")
    spark.sql(f"ALTER TABLE {GOLD}.{t} ADD CONSTRAINT pk_{t} PRIMARY KEY ({', '.join(PKS[t])})")
for t, fks in FKS.items():
    for c, dim in fks:
        spark.sql(f"ALTER TABLE {GOLD}.{t} ADD CONSTRAINT fk_{t}_{c} FOREIGN KEY ({c}) REFERENCES {GOLD}.{dim}")

display(spark.createDataFrame([(t, spark.table(f"{GOLD}.{t}").count()) for t in STAR_DIMS + STAR_FACTS],
                              "tabla STRING, filas LONG"))
