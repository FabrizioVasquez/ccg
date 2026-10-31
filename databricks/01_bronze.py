# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze: ingesta cruda
# MAGIC Regla de oro de bronze: **no transformar**. Todo se carga como `STRING` (para no perder valores como `3635.6K` o `09/05/2025`)
# MAGIC y se agregan solo metadatos de linaje: archivo de origen y timestamp de ingesta.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from pyspark.sql import functions as F

def clean_name(c: str) -> str:
    # varios CSV traen BOM (﻿) pegado al primer encabezado
    return c.replace("﻿", "").strip()

summary = []
for table, fname in SOURCES.items():
    raw = (spark.read
           .option("header", True)
           .option("inferSchema", False)
           .option("encoding", "UTF-8")
           .csv(f"{LANDING}/{fname}"))
    df = raw.select(
        *[F.col(f"`{c}`").alias(clean_name(c)) for c in raw.columns],
        F.col("_metadata.file_path").alias("_source_file"),
        F.current_timestamp().alias("_ingest_ts"),
    )
    (df.write.mode("overwrite")
       .option("overwriteSchema", True)
       .saveAsTable(f"{BRONZE}.{table}"))
    summary.append((table, fname, spark.table(f"{BRONZE}.{table}").count(), len(raw.columns)))

display(spark.createDataFrame(summary, "tabla STRING, archivo STRING, filas LONG, columnas INT"))

# COMMAND ----------

# MAGIC %md
# MAGIC > **Ingesta incremental (opcional):** si los CSV van a llegar periódicamente, reemplaza el `spark.read.csv` por Auto Loader
# MAGIC > (`spark.readStream.format("cloudFiles").option("cloudFiles.format", "csv")...`) con `trigger(availableNow=True)`,
# MAGIC > para procesar solo archivos nuevos.
