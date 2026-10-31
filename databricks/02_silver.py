# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Silver: limpieza, tipado y control de calidad
# MAGIC Aplica las mismas reglas validadas en `analisis_calidad_datos.ipynb`:
# MAGIC
# MAGIC | Problema | Regla |
# MAGIC |---|---|
# MAGIC | IDs mal escritos (`VF-A1`, `VFA03`, `VF_A6`, `ISS04`) | Normalizar por regex al patrón del maestro |
# MAGIC | Fechas `MM/DD/YYYY` | Parsear como mes-primero |
# MAGIC | `3635.6K`, `"1,845.7"` | Expandir sufijos K/M/B y quitar separador de miles |
# MAGIC | `currency` nula | Completar desde el maestro |
# MAGIC | `close` fuera de `[low, high]` | Si `close/100` cae en rango → error de escala; si no → cuarentena |
# MAGIC | Duplicados | Conservar una fila por llave |
# MAGIC | Periodo `Qn-YYYY` | Fecha de cierre del trimestre; si ya existe, el único trimestre faltante del emisor (`imputed_period = true`) |
# MAGIC | Inflación mensual | Forward-fill en columna aparte |
# MAGIC | Inflación fechada al inicio del mes de referencia | `us_inflation_yoy_asof`: visible solo desde su publicación (día 15 del mes siguiente) |
# MAGIC | Volumen centinela `99999999` | → nulo |
# MAGIC | Revenue que se desvía >25% de **ambos** trimestres vecinos | Se conserva, marcado `suspect_revenue` (gold no lo usa en márgenes) |
# MAGIC | `cash_usd_m` nulo entre dos trimestres con dato | Interpolación lineal (`imputed_cash = true`) |
# MAGIC | Estados financieros se publican después del cierre | `available_date = period_end + 45 días` |
# MAGIC | Perfiles: tolerancia ordinal y restricciones en texto libre | `risk_tolerance_rank` y límites numéricos parseados |
# MAGIC | `dataset_twist.csv`: `field` no coincide con columnas | Mapeo explícito a tabla/columna/operación; lo no mapeable → cuarentena |
# MAGIC
# MAGIC Cada fila guarda en `_dq_fixes` qué correcciones recibió. Lo que no se puede corregir va a tablas `*_quarantine`,
# MAGIC y los conteos por regla se acumulan en `silver.dq_log`.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from datetime import datetime, timezone
from pyspark.sql import functions as F, Window as W

RUN_TS = datetime.now(timezone.utc)
dq_log = []

def norm_id(col, pattern, fmt):
    # 'VF-A1' / 'VFA03' / 'VF_A6' -> 'VF_A01'; si no calza con el patrón se deja igual (y caerá en cuarentena)
    num = F.regexp_extract(F.col(col), pattern, 1)
    return F.when(num != "", F.format_string(fmt, num.cast("int"))).otherwise(F.col(col))

def to_num(col):
    s = f"regexp_replace(trim(`{col}`), ',', '')"
    return F.expr(f"""
        CASE WHEN upper(right({s}, 1)) IN ('K', 'M', 'B')
             THEN try_cast(left({s}, length({s}) - 1) AS DOUBLE)
                  * CASE upper(right({s}, 1)) WHEN 'K' THEN 1e3 WHEN 'M' THEN 1e6 ELSE 1e9 END
             ELSE try_cast({s} AS DOUBLE) END""")

def is_non_numeric(col):
    return F.col(col).isNotNull() & F.expr(f"try_cast(`{col}` AS DOUBLE)").isNull()

def to_ts(col):
    return F.expr(f"""coalesce(
        try_to_timestamp(`{col}`, 'yyyy-MM-dd HH:mm:ss'), try_to_timestamp(`{col}`, 'MM/dd/yyyy HH:mm:ss'),
        try_to_timestamp(`{col}`, 'yyyy-MM-dd'),          try_to_timestamp(`{col}`, 'MM/dd/yyyy'))""")

def fixes_array(flags: dict):
    # flags = {nombre_regla: columna_booleana} -> array con las reglas aplicadas a la fila
    return F.array_compact(F.array(*[F.when(F.col(c), F.lit(name)) for name, c in flags.items()]))

def log_flags(table, df, flags: dict):
    counts = df.agg(*[F.sum(F.col(c).cast("int")).alias(c) for c in flags.values()]).first()
    for name, c in flags.items():
        dq_log.append((table, name, int(counts[c] or 0)))

def write(df, table):
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Maestros: assets, clients, events

# COMMAND ----------

assets = spark.table(f"{BRONZE}.asset_reference").drop("_source_file", "_ingest_ts")
write(assets, f"{SILVER}.asset_reference")
spark.sql(f"ALTER TABLE {SILVER}.asset_reference ALTER COLUMN asset_id SET NOT NULL")

# tolerancia ordinal: ordenar alfabéticamente daría Alta < Media < Media-Baja
RISK_RANK = F.create_map(*[F.lit(x) for kv in {"Baja": 0, "Media-Baja": 1, "Media": 2, "Media-Alta": 3, "Alta": 4}.items() for x in kv])

def extract_num(pattern, dtype):
    # regexp_extract devuelve '' si no calza; se evita el cast de '' (falla con ANSI)
    s = F.regexp_extract("constraint", pattern, 1)
    return F.when(s != "", s.cast(dtype))

def pct_after(pattern):
    # 'Máx. 45% en un solo sector' -> 0.45
    return extract_num(pattern, "double") / 100

def int_before(word):
    # 'Al menos 3 países y 3 sectores' -> 3
    return extract_num(rf"(\d+)\s+{word}", "int")

clients = (spark.table(f"{BRONZE}.client_profiles").drop("_source_file", "_ingest_ts")
           .withColumn("horizon_months", F.col("horizon_months").cast("int"))
           .withColumn("max_drawdown_tolerance_pct", F.col("max_drawdown_tolerance_pct").cast("double"))
           .withColumn("risk_tolerance_rank", RISK_RANK[F.col("risk_tolerance")])
           .withColumn("max_weight_per_sector", F.when(F.col("constraint").rlike("(?i)un solo sector"), pct_after(r"(\d+)%")))
           .withColumn("max_weight_high_vol", F.when(F.col("constraint").rlike("(?i)alta volatilidad"), pct_after(r"(\d+)%")))
           .withColumn("min_countries", int_before("pa[ií]ses"))
           .withColumn("min_sectors", int_before("sectores")))
write(clients, f"{SILVER}.client_profiles")
parsed = F.coalesce("max_weight_per_sector", "max_weight_high_vol", "min_countries", "min_sectors").isNotNull()
dq_log.append(("client_profiles", "Restricción en texto sin parsear (revisar)", clients.filter(~parsed).count()))
dq_log.append(("client_profiles", "Tolerancia de riesgo sin rango ordinal", clients.filter("risk_tolerance_rank IS NULL").count()))

valid_scopes = (assets.select(F.col("asset_id").alias("scope"))
                .union(assets.select(F.col("sector").alias("scope"))).distinct()
                .withColumn("_scope_ok", F.lit(True)))
events = (spark.table(f"{BRONZE}.events").drop("_source_file", "_ingest_ts")
          .withColumn("event_date", F.to_date(to_ts("event_date")))
          .join(F.broadcast(valid_scopes), "scope", "left")
          .withColumn("scope_type", F.when(F.col("scope").rlike(r"^VF_A\d{2}$"), "asset").otherwise("sector")))
write(events.filter("_scope_ok").drop("_scope_ok").withColumn("event_id", F.concat_ws("_", F.date_format("event_date", "yyyyMMdd"), "scope")),
      f"{SILVER}.events")
dq_log.append(("events", "Scope no mapeable (cuarentena)", events.filter(F.col("_scope_ok").isNull()).count()))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Precios (diario e intradía)

# COMMAND ----------

ref = F.broadcast(spark.table(f"{SILVER}.asset_reference")
                  .select("asset_id", F.col("currency").alias("_ref_currency")))

PRICE_FLAGS = {
    "Normalizar asset_id": "_f_id",
    "Parsear fecha no ISO": "_f_date",
    "Expandir volumen K/M": "_f_volume",
    "Completar currency desde maestro": "_f_currency",
    "Corregir close escala x100": "_f_close_scale",
    "Volumen centinela → nulo": "_f_volume_sentinel",
}
VOLUME_SENTINEL = 99999999  # marcador de "sin dato" en el intradía, no un volumen real

def clean_prices(bronze_table, silver_table, intraday: bool):
    src = spark.table(f"{BRONZE}.{bronze_table}")
    df = (src
          .withColumn("_f_id", ~F.col("asset_id").rlike(r"^VF_A\d{2}$"))
          .withColumn("_f_date", ~F.col("date").rlike(r"^\d{4}-"))
          .withColumn("_f_volume", F.upper(F.trim("volume")).rlike(r"^[0-9.,]+[KMB]$"))  # 'N/A' -> nulo, no cuenta
          .withColumn("_f_currency", F.col("currency").isNull())
          .select(
              norm_id("asset_id", r"^VF[-_]?A?0*(\d+)$", "VF_A%02d").alias("asset_id"),
              to_ts("date").alias("ts"),
              "market", "currency",
              *[to_num(c).alias(c) for c in ["open", "high", "low", "close"]],
              to_num("volume").cast("long").alias("volume"),
              "_f_id", "_f_date", "_f_volume", "_f_currency", "_ingest_ts", "_source_file")
          .join(ref, "asset_id", "left")
          .withColumn("currency", F.coalesce("currency", "_ref_currency"))
          .withColumn("_f_volume_sentinel", F.coalesce(F.col("volume") == VOLUME_SENTINEL, F.lit(False)))
          .withColumn("volume", F.when(~F.col("_f_volume_sentinel"), F.col("volume"))))

    out_of_range = F.coalesce((F.col("close") > F.col("high")) | (F.col("close") < F.col("low")), F.lit(False))
    rescaled_ok = (F.col("close") / 100).between(F.col("low"), F.col("high"))
    df = (df.withColumn("_f_close_scale", out_of_range & rescaled_ok)
            .withColumn("_f_close_bad", out_of_range & ~rescaled_ok)
            .withColumn("close", F.when(F.col("_f_close_scale"), F.col("close") / 100).otherwise(F.col("close"))))

    # duplicados: una fila por (asset_id, ts)
    w = W.partitionBy("asset_id", "ts").orderBy("_ingest_ts")
    df = df.withColumn("_rn", F.row_number().over(w))

    quarantine_reason = (F.when(F.col("_ref_currency").isNull(), "asset_id no existe en maestro")
                          .when(F.col("ts").isNull(), "fecha no parseable")
                          .when(F.col("_f_close_bad"), "close fuera de [low, high] no recuperable")
                          .when(F.col("close").isNull(), "close nulo"))
    df = df.withColumn("_quarantine_reason", quarantine_reason).cache()

    log_flags(bronze_table, df, PRICE_FLAGS)
    dq_log.append((bronze_table, "Eliminar duplicados", df.filter("_rn > 1").count()))

    keep = df.filter("_rn = 1")
    write(keep.filter(F.col("_quarantine_reason").isNotNull())
              .select("asset_id", "ts", "market", "currency", "open", "high", "low", "close", "volume",
                      "_quarantine_reason", "_source_file", "_ingest_ts"),
          f"{silver_table}_quarantine")
    for row in keep.groupBy("_quarantine_reason").count().filter("_quarantine_reason IS NOT NULL").collect():
        dq_log.append((bronze_table, f"Cuarentena: {row['_quarantine_reason']}", row["count"]))

    time_cols = ["ts", F.to_date("ts").alias("date")] if intraday else [F.to_date("ts").alias("date")]
    clean = (keep.filter(F.col("_quarantine_reason").isNull())
                 .select("asset_id", *time_cols, "market", "currency", "open", "high", "low", "close", "volume",
                         fixes_array(PRICE_FLAGS).alias("_dq_fixes"), "_source_file", "_ingest_ts"))
    write(clean, silver_table)
    df.unpersist()

    # restricciones Delta: las escrituras futuras que las violen fallan
    spark.sql(f"ALTER TABLE {silver_table} DROP CONSTRAINT IF EXISTS ohlc_coherente")
    spark.sql(f"ALTER TABLE {silver_table} ADD CONSTRAINT ohlc_coherente "
              "CHECK (high >= low AND close BETWEEN low AND high AND open BETWEEN low AND high)")
    spark.sql(f"ALTER TABLE {silver_table} DROP CONSTRAINT IF EXISTS volumen_no_negativo")
    spark.sql(f"ALTER TABLE {silver_table} ADD CONSTRAINT volumen_no_negativo CHECK (volume IS NULL OR volume >= 0)")
    return spark.table(silver_table)

market_daily = clean_prices("market_prices_raw", f"{SILVER}.market_prices_daily", intraday=False)
market_intraday = clean_prices("market_prices_intraday_raw", f"{SILVER}.market_prices_intraday", intraday=True)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Macro

# COMMAND ----------

MACRO_NUM = ["us_10y_yield", "us_inflation_yoy", "usd_cop", "usd_pen", "usd_mxn", "usd_clp", "market_factor"]
w_ffill = W.orderBy("date").rowsBetween(W.unboundedPreceding, 0)

INFLATION_RELEASE_DAY = 15  # el dato del mes M se publica ~día 15 del mes M+1

macro = (spark.table(f"{BRONZE}.macro_raw")
         .select(F.to_date(to_ts("date")).alias("date"), *[to_num(c).alias(c) for c in MACRO_NUM], "risk_regime")
         .dropDuplicates(["date"])
         .withColumn("us_inflation_yoy_ffill", F.last("us_inflation_yoy", ignorenulls=True).over(w_ffill)))

# as-of: cada dato se vuelve visible el primer día con macro desde su publicación (evita look-ahead en modelos/backtests)
releases = (macro.filter("us_inflation_yoy IS NOT NULL")
            .select(F.date_add(F.trunc(F.add_months("date", 1), "month"), INFLATION_RELEASE_DAY - 1).alias("_release"),
                    F.col("us_inflation_yoy").alias("_infl")))
visible = (releases.join(macro.select("date"), F.col("date") >= F.col("_release"))
           .groupBy("_release", "_infl").agg(F.min("date").alias("date")))
macro = (macro.join(visible.select("date", "_infl"), "date", "left")
         .withColumn("us_inflation_yoy_asof", F.last("_infl", ignorenulls=True).over(w_ffill))
         .drop("_infl"))
write(macro, f"{SILVER}.macro_daily")
dq_log.append(("macro_raw", "Forward-fill inflación mensual", macro.filter("us_inflation_yoy IS NULL").count()))
dq_log.append(("macro_raw", "Rezagar inflación a fecha de publicación (as-of)", releases.count()))
dq_log.append(("macro_raw", "Nulos en inflación as-of antes de la primera publicación",
               macro.filter("us_inflation_yoy_asof IS NULL").count()))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Fundamentales

# COMMAND ----------

FUND_NUM = ["revenue_usd_m", "ebitda_usd_m", "net_income_usd_m", "debt_usd_m", "cash_usd_m"]
fb = spark.table(f"{BRONZE}.fundamentals_raw")
n_raw = fb.count()

f = (fb.withColumn("_f_id", ~F.col("issuer_id").rlike(r"^ISS_\d{2}$"))
       .withColumn("_f_num", F.greatest(*[is_non_numeric(c) for c in FUND_NUM]))
       .select(norm_id("issuer_id", r"^ISS_?0*(\d+)$", "ISS_%02d").alias("issuer_id"),
               "period_end", *[to_num(c).alias(c) for c in FUND_NUM], "_f_id", "_f_num")
       .dropDuplicates(["issuer_id", "period_end", *FUND_NUM]))
dq_log.append(("fundamentals_raw", "Eliminar duplicados exactos", n_raw - f.count()))

# periodos tipo 'Q4-2024'
q = F.regexp_extract("period_end", r"^Q(\d)-(\d{4})$", 1)
y = F.regexp_extract("period_end", r"^Q(\d)-(\d{4})$", 2)
f = (f.withColumn("_period_iso", F.to_date(F.expr("try_to_timestamp(period_end, 'yyyy-MM-dd')")))
      .withColumn("_period_literal", F.when(q != "", F.last_day(F.make_date(y.cast("int"), q.cast("int") * 3, F.lit(1))))))

iso_rows = f.filter("_period_iso IS NOT NULL").select("issuer_id", F.col("_period_iso").alias("p"))
missing = (f.select("issuer_id").distinct()
            .crossJoin(iso_rows.select("p").distinct())
            .join(iso_rows, ["issuer_id", "p"], "left_anti")
            .groupBy("issuer_id").agg(F.count("*").alias("_n_missing"), F.min("p").alias("_missing_p")))
collisions = iso_rows.select("issuer_id", F.col("p").alias("_period_literal"), F.lit(True).alias("_collides"))

f = (f.join(collisions, ["issuer_id", "_period_literal"], "left")
      .join(missing, "issuer_id", "left")
      .withColumn("period_end", F.coalesce(
          "_period_iso",
          F.when(F.col("_collides") & (F.col("_n_missing") == 1), F.col("_missing_p")),
          F.when(F.col("_collides").isNull(), F.col("_period_literal"))))
      .withColumn("imputed_period", F.col("_period_iso").isNull()))

# revenue atípico: se desvía > umbral de AMBOS vecinos en la misma dirección (pico/valle aislado, p. ej. 2845.7 tipeado 1,845.7).
# No se corrige: se marca y gold lo excluye de márgenes.
SUSPECT_REVENUE_DEV = 0.25
FUND_PUB_LAG_DAYS = 45  # los estados se conocen ~45 días después del cierre del trimestre
w_q = W.partitionBy("issuer_id").orderBy("period_end")
dev_prev = F.col("revenue_usd_m") / F.lag("revenue_usd_m").over(w_q) - 1
dev_next = F.col("revenue_usd_m") / F.lead("revenue_usd_m").over(w_q) - 1
cash_prev, cash_next = F.lag("cash_usd_m").over(w_q), F.lead("cash_usd_m").over(w_q)
f = (f.filter("period_end IS NOT NULL")
      .withColumn("suspect_revenue", F.coalesce(
          (F.abs(dev_prev) > SUSPECT_REVENUE_DEV) & (F.abs(dev_next) > SUSPECT_REVENUE_DEV)
          & (F.signum(dev_prev) == F.signum(dev_next)), F.lit(False)))
      .withColumn("imputed_cash", F.col("cash_usd_m").isNull() & cash_prev.isNotNull() & cash_next.isNotNull())
      .withColumn("cash_usd_m", F.when(F.col("imputed_cash"), F.round((cash_prev + cash_next) / 2, 1))
                                 .otherwise(F.col("cash_usd_m")))
      .withColumn("available_date", F.date_add("period_end", FUND_PUB_LAG_DAYS))
      .unionByName(f.filter("period_end IS NULL"), allowMissingColumns=True))

FUND_FLAGS = {"Normalizar issuer_id": "_f_id", "Quitar separador de miles": "_f_num",
              "Reasignar periodo no ISO (imputed_period)": "imputed_period",
              "Interpolar cash nulo (imputed_cash)": "imputed_cash",
              "Marcar revenue atípico (suspect_revenue)": "suspect_revenue"}
log_flags("fundamentals_raw", f.fillna(False, ["imputed_cash", "suspect_revenue"]), FUND_FLAGS)

fund_cols = ["issuer_id", "period_end", "available_date", *FUND_NUM, "imputed_period", "imputed_cash", "suspect_revenue",
             fixes_array(FUND_FLAGS).alias("_dq_fixes")]
write(f.filter("period_end IS NULL").select(*fund_cols), f"{SILVER}.fundamentals_quarantine")
write(f.filter("period_end IS NOT NULL").select(*fund_cols), f"{SILVER}.fundamentals")
dq_log.append(("fundamentals_raw", "Nulos en cash_usd_m sin vecinos para interpolar",
               spark.table(f"{SILVER}.fundamentals").filter("cash_usd_m IS NULL").count()))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Escenario (`dataset_twist.csv`)
# MAGIC Cada novedad se traduce a un choque sobre una columna real. **No** se inserta como historia: gold lo aplica sobre el
# MAGIC último dato observado. `field` no coincide con los nombres de columna (`USD_COP` vs `usd_cop`, `CL_02_liquidity`),
# MAGIC así que el mapeo es explícito; lo que no se reconoce va a cuarentena.

# COMMAND ----------

import re

def parse_shock(field, text):
    """-> (target_table, client_id, target_column, operation, shock_value, horizon_months) o None si no se reconoce."""
    pct = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    bps = re.search(r"(\d+(?:\.\d+)?)\s*pb", text)
    months = re.search(r"(\d+)\s*meses", text)
    client = re.match(r"^(CL_\d{2})_(\w+)$", field)
    if field.lower() in MACRO_NUM and bps:
        sign = -1 if re.search(r"(?i)\b(baja|cae)\b", text) else 1
        return ("macro_daily", None, field.lower(), "add", sign * float(bps.group(1)) / 100, None)  # pb -> puntos %
    if field.lower() in MACRO_NUM and pct:
        # USD/XXX: la moneda local se deprecia -> el par sube
        sign = -1 if re.search(r"(?i)\b(aprecia|baja|cae)", text) else 1  # \b: 'deprecia' no debe calzar con 'aprecia'
        return ("macro_daily", None, field.lower(), "multiply", 1 + sign * float(pct.group(1)) / 100, None)
    if client and client.group(2) == "liquidity" and pct:
        return ("client_profiles", client.group(1), "liquidity_need_pct", "set", float(pct.group(1)) / 100,
                int(months.group(1)) if months else None)
    return None

twist_rows = []
for r in spark.table(f"{BRONZE}.scenario_twist").collect():
    shock = parse_shock(r["field"], r["new_information"])
    twist_rows.append((r["release_id"], r["effective_date"], r["type"], r["field"], *(shock or (None,) * 6),
                       r["new_information"], r["required_action"], None if shock else "field/valor no mapeable"))
twist = (spark.createDataFrame(twist_rows,
            "release_id STRING, effective_date STRING, type STRING, field STRING, target_table STRING, client_id STRING, "
            "target_column STRING, operation STRING, shock_value DOUBLE, horizon_months INT, new_information STRING, "
            "required_action STRING, _quarantine_reason STRING")
         .withColumn("effective_date", F.to_date(to_ts("effective_date"))))
write(twist.filter("_quarantine_reason IS NULL").drop("_quarantine_reason"), f"{SILVER}.scenario_twist")
write(twist.filter("_quarantine_reason IS NOT NULL"), f"{SILVER}.scenario_twist_quarantine")
dq_log.append(("scenario_twist", "Mapear field a tabla/columna/operación", twist.filter("_quarantine_reason IS NULL").count()))
dq_log.append(("scenario_twist", "Cuarentena: field/valor no mapeable", twist.filter("_quarantine_reason IS NOT NULL").count()))
display(twist)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bitácora de calidad y validación final

# COMMAND ----------

log_df = (spark.createDataFrame(dq_log, "source_table STRING, rule STRING, rows_affected LONG")
          .withColumn("run_ts", F.lit(RUN_TS)))
log_df.write.mode("append").saveAsTable(f"{SILVER}.dq_log")
display(log_df.filter("rows_affected > 0").orderBy("source_table", "rule"))

# COMMAND ----------

# Chequeos que deben dar 0 en silver; si alguno falla, el job se detiene antes de gold
checks = {
    "precios con asset_id fuera del maestro":
        market_daily.join(ref, "asset_id", "left_anti").count(),
    "precios diarios con llave duplicada":
        market_daily.groupBy("asset_id", "date").count().filter("count > 1").count(),
    "fundamentales con issuer fuera del maestro":
        spark.table(f"{SILVER}.fundamentals").join(spark.table(f"{SILVER}.asset_reference").select("issuer_id"), "issuer_id", "left_anti").count(),
    "fundamentales con llave duplicada":
        spark.table(f"{SILVER}.fundamentals").groupBy("issuer_id", "period_end").count().filter("count > 1").count(),
    "fechas de mercado sin dato macro":
        market_daily.select("date").distinct().join(spark.table(f"{SILVER}.macro_daily"), "date", "left_anti").count(),
    "volumen centinela en silver":
        market_intraday.filter(F.col("volume") == VOLUME_SENTINEL).count(),
    "inflación as-of visible antes de su publicación":
        spark.table(f"{SILVER}.macro_daily").filter("us_inflation_yoy_asof IS NOT NULL")
             .join(releases.withColumnRenamed("_infl", "us_inflation_yoy_asof"), "us_inflation_yoy_asof")
             .groupBy("date").agg(F.min("_release").alias("_r")).filter("date < _r").count(),  # min: hay valores repetidos entre meses
}
display(spark.createDataFrame(list(checks.items()), "chequeo STRING, filas_con_problema LONG"))
assert all(v == 0 for v in checks.values()), "Silver no pasó la validación final"
print("✅ Silver validado")
