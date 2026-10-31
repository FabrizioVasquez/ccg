# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup: catálogo, esquemas y volume de aterrizaje
# MAGIC Crea la estructura medallón en Unity Catalog:
# MAGIC
# MAGIC | Esquema | Contenido |
# MAGIC |---|---|
# MAGIC | `bronze` | CSV tal cual llegan (todo `STRING`) + metadatos de ingesta. Incluye el volume `landing` donde se suben los archivos. |
# MAGIC | `silver` | Datos tipados, IDs/fechas normalizados, sin duplicados, con cuarentena y bitácora de calidad. |
# MAGIC | `gold`   | Tablas de negocio: métricas de riesgo, ratios, impacto de eventos, compatibilidad cliente-activo. |
# MAGIC
# MAGIC > Si no tienes permiso para crear catálogos (p. ej. Free Edition), usa el widget `catalog` con uno existente, como `workspace`.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
for schema, comment in [
    ("bronze", "Datos crudos tal cual llegan de la fuente"),
    ("silver", "Datos limpios, tipados y validados"),
    ("gold", "Tablas de negocio listas para análisis"),
]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema} COMMENT '{comment}'")

spark.sql(f"CREATE VOLUME IF NOT EXISTS {BRONZE}.landing COMMENT 'Archivos CSV de origen'")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Subir los CSV
# MAGIC **Opción UI:** Catalog → `credicorp_dq` → `bronze` → Volumes → `landing` → *Upload to this volume* → arrastra los 8 CSV (incluye `dataset_twist.csv`).
# MAGIC
# MAGIC **Opción CLI (desde tu máquina):**
# MAGIC ```bash
# MAGIC databricks fs cp ./*.csv dbfs:/Volumes/credicorp_dq/bronze/landing/ --overwrite
# MAGIC ```
# MAGIC Luego ejecuta la celda siguiente para verificar que están todos.

# COMMAND ----------

present = {f.name for f in dbutils.fs.ls(LANDING)}
missing = [f for f in SOURCES.values() if f not in present]
display(spark.createDataFrame([(f.name, f.size) for f in dbutils.fs.ls(LANDING)], "archivo STRING, bytes LONG"))
assert not missing, f"Faltan archivos en {LANDING}: {missing}"
print("✅ Todos los archivos están en el volume")
