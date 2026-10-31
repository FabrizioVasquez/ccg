# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Dashboard AI/BI sobre gold
# MAGIC Crea (o actualiza) y publica el dashboard **Credicorp DQ · Gold** a partir de `_dashboard_def`.
# MAGIC
# MAGIC 1. Valida que cada dataset del dashboard corra contra las tablas gold actuales.
# MAGIC 2. Crea el dashboard junto a este notebook (o lo actualiza si ya existe) y lo publica en un SQL warehouse.
# MAGIC
# MAGIC Correr después de `03_gold`. Si no se indica `warehouse_id`, se usa el primer warehouse disponible.
# MAGIC
# MAGIC > Alternativa manual: *Dashboards → Create → Import dashboard from file* con `dashboard/credicorp_gold.lvdash.json`
# MAGIC > (generado para el catálogo `credicorp_dq`).

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %run ./_dashboard_def

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

dbutils.widgets.text("warehouse_id", "", "SQL warehouse (vacío = automático)")
DASHBOARD_NAME = "Credicorp DQ · Gold"

w = WorkspaceClient()
definition = build(CATALOG)

# COMMAND ----------

# Cada dataset debe correr tal cual sobre gold antes de publicar
checks = []
for ds in definition["datasets"]:
    sql = "".join(ds["queryLines"])
    try:
        checks.append((ds["name"], spark.sql(sql).count(), "✅"))
    except Exception as e:
        checks.append((ds["name"], -1, f"❌ {str(e)[:120]}"))
display(spark.createDataFrame(checks, "dataset STRING, filas LONG, estado STRING"))
failed = [c for c in checks if c[2] != "✅"]
assert not failed, f"Datasets con error: {[c[0] for c in failed]}"

# COMMAND ----------

warehouse_id = dbutils.widgets.get("warehouse_id")
if not warehouse_id:
    warehouses = sorted(w.warehouses.list(), key=lambda wh: str(wh.state) != "State.RUNNING")
    assert warehouses, "No hay SQL warehouses disponibles; crea uno o indica warehouse_id"
    warehouse_id = warehouses[0].id
    print(f"warehouse: {warehouses[0].name} ({warehouse_id})")

notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
parent_path = os.path.dirname(notebook_path)
if parent_path.startswith("/Workspace"):
    parent_path = parent_path[len("/Workspace"):]

body = {"display_name": DASHBOARD_NAME, "warehouse_id": warehouse_id,
        "serialized_dashboard": serialize(CATALOG)}
try:
    status = w.workspace.get_status(f"{parent_path}/{DASHBOARD_NAME}.lvdash.json")
    dashboard_id = status.resource_id
    w.api_client.do("PATCH", f"/api/2.0/lakeview/dashboards/{dashboard_id}", body=body)
    print("Dashboard actualizado")
except NotFound:
    dashboard_id = w.api_client.do("POST", "/api/2.0/lakeview/dashboards",
                                   body={**body, "parent_path": parent_path})["dashboard_id"]
    print("Dashboard creado")

w.api_client.do("POST", f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",
                body={"warehouse_id": warehouse_id, "embed_credentials": True})
url = f"{w.config.host.rstrip('/')}/dashboardsv3/{dashboard_id}/published"
displayHTML(f'<a href="{url}" target="_blank">Abrir dashboard publicado: {DASHBOARD_NAME}</a>')
