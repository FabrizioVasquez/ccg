# Databricks notebook source
# MAGIC %md
# MAGIC # Configuración compartida
# MAGIC Se incluye desde los demás notebooks con `%run ./_config`.

# COMMAND ----------

dbutils.widgets.text("catalog", "credicorp_dq", "Catálogo Unity Catalog")
CATALOG = dbutils.widgets.get("catalog")

BRONZE = f"{CATALOG}.bronze"
SILVER = f"{CATALOG}.silver"
GOLD = f"{CATALOG}.gold"
LANDING = f"/Volumes/{CATALOG}/bronze/landing"

# tabla bronze -> archivo en el volume
SOURCES = {
    "market_prices_raw":          "01_market_prices_raw.csv",
    "market_prices_intraday_raw": "01_market_prices_raw_expanded.csv",
    "macro_raw":                  "02_macro_raw.csv",
    "fundamentals_raw":           "03_fundamentals_raw.csv",
    "asset_reference":            "04_asset_reference.csv",
    "client_profiles":            "05_client_profiles.csv",
    "events":                     "06_events.csv",
    "scenario_twist":             "dataset_twist.csv",
}

print(f"catalog={CATALOG} | landing={LANDING}")
