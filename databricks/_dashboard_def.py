# Databricks notebook source
# MAGIC %md
# MAGIC # Definición del dashboard AI/BI sobre gold
# MAGIC Se incluye desde `06_dashboard` con `%run ./_dashboard_def`. Solo Python puro (sin `spark`/`dbutils`)
# MAGIC para poder generar también el `.lvdash.json` fuera de Databricks.
# MAGIC
# MAGIC | Página | Fuente gold | Pregunta que responde |
# MAGIC |---|---|---|
# MAGIC | Mercado y riesgo | `fact_prices_daily`, `asset_risk_metrics` | ¿Qué activo rindió más y con cuánto riesgo? |
# MAGIC | Fundamentales | `fundamentals_ratios` | ¿Quién es más rentable y quién está más apalancado? |
# MAGIC | Eventos | `event_impact` | ¿Cuánto movió cada evento al activo frente al universo? |
# MAGIC | Clientes | `client_asset_fit` | ¿Qué activos caben en la tolerancia de cada cliente? |
# MAGIC | Calidad de datos | `dq_scorecard` | ¿Cuánto se retuvo, corrigió y apartó en la última corrida? |

# COMMAND ----------

import json

PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
NUM = {"type": "number-plain", "decimalPlaces": {"type": "max", "places": 2}}


def dataset(name, display, sql):
    return {"name": name, "displayName": display, "queryLines": [l + "\n" for l in sql.strip().splitlines()]}


def _query(ds, fields, disaggregated, qname="main_query"):
    return {"name": qname, "query": {"datasetName": ds, "disaggregated": disaggregated,
                                     "fields": [{"name": n, "expression": e} for n, e in fields]}}


def _place(widget, x, y, w, h):
    return {"widget": widget, "position": {"x": x, "y": y, "width": w, "height": h}}


def text(name, md, x, y, w, h=1):
    return _place({"name": name, "multilineTextboxSpec": {"lines": md.strip().splitlines(True)}}, x, y, w, h)


def counter(name, title, ds, expr, x, y, w=1, h=2, fmt=None, description=None):
    value = {"fieldName": "value", "displayName": title}
    if fmt:
        value["format"] = fmt
    frame = {"showTitle": True, "title": title}
    if description:
        frame.update(showDescription=True, description=description)
    return _place({"name": name, "queries": [_query(ds, [("value", expr)], False)],
                   "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": value}, "frame": frame}},
                  x, y, w, h)


def chart(name, kind, title, ds, x_enc, y_enc, pos, color=None, description=None, mark=None):
    """x_enc / y_enc / color = (columna, nombre visible, tipo de escala[, formato])."""
    encodings, fields = {}, []
    for axis, enc in (("x", x_enc), ("y", y_enc), ("color", color)):
        if not enc:
            continue
        col, label, scale, *fmt = enc
        encodings[axis] = {"fieldName": col, "displayName": label, "scale": {"type": scale}}
        if fmt:
            encodings[axis]["format"] = fmt[0]
        fields.append((col, f"`{col}`"))
    frame = {"showTitle": True, "title": title}
    if description:
        frame.update(showDescription=True, description=description)
    spec = {"version": 3, "widgetType": kind, "encodings": encodings, "frame": frame}
    if mark:
        spec["mark"] = mark
    return _place({"name": name, "queries": [_query(ds, fields, True)], "spec": spec}, *pos)


def _column(i, col, label, kind):
    types = {"string": ("string", "string", None), "date": ("date", "datetime", None),
             "pct": ("float", "number", "0.0%"), "num": ("float", "number", "0,0.00"),
             "int": ("integer", "number", "0,0"), "bool": ("boolean", "boolean", None)}
    type_, display_as, number_format = types[kind]
    c = {"fieldName": col, "type": type_, "displayAs": display_as, "visible": True, "order": i,
         "title": label, "displayName": label, "allowSearch": kind == "string", "alignContent":
         "left" if kind in ("string", "date") else "right", "booleanValues": ["No", "Sí"],
         "allowHTML": False, "highlightLinks": False, "useMonospaceFont": False, "preserveWhitespace": False}
    if number_format:
        c["numberFormat"] = number_format
    if kind == "date":
        c["dateTimeFormat"] = "YYYY-MM-DD"
    return c


def table(name, title, ds, columns, pos):
    """columns = [(columna, nombre visible, tipo)] con tipo en string|date|pct|num|int|bool."""
    spec = {"version": 1, "widgetType": "table",
            "encodings": {"columns": [_column(i, *c) for i, c in enumerate(columns)]},
            "invisibleColumns": [], "allowHTMLByDefault": False, "itemsPerPage": 25,
            "paginationSize": "default", "condensed": True, "withRowNumber": False,
            "frame": {"showTitle": True, "title": title}}
    return _place({"name": name, "queries": [_query(ds, [(c[0], f"`{c[0]}`") for c in columns], True)],
                   "spec": spec}, *pos)


def filter_multi(name, title, col, datasets, pos, single=False, default=None):
    queries = [_query(ds, [(col, f"`{col}`")], False, qname=f"{name}_{ds}") for ds in datasets]
    spec = {"version": 2, "widgetType": "filter-single-select" if single else "filter-multi-select",
            "encodings": {"fields": [{"fieldName": col, "displayName": title, "queryName": q["name"]}
                                     for q in queries]},
            "frame": {"showTitle": True, "title": title}}
    if default:
        spec["selection"] = {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": default}]}}}
    return _place({"name": name, "queries": queries, "spec": spec}, *pos)

# COMMAND ----------

def build(catalog):
    g = f"{catalog}.gold"
    datasets = [
        dataset("ds_prices", "Precios diarios", f"""
SELECT date, asset_id, name, sector, country, close, ret, ret_abnormal, risk_regime,
       100 * close / FIRST_VALUE(close) OVER (PARTITION BY asset_id ORDER BY date) AS close_base100,
       close / MAX(close) OVER (PARTITION BY asset_id ORDER BY date
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1 AS drawdown
FROM {g}.fact_prices_daily"""),
        dataset("ds_risk", "Métricas de riesgo", f"SELECT * FROM {g}.asset_risk_metrics"),
        dataset("ds_macro", "Macro diario", f"""
WITH m AS (
  SELECT DISTINCT date, risk_regime, market_factor, us_10y_yield, usd_cop, usd_pen, usd_mxn, usd_clp
  FROM {g}.fact_prices_daily
), fx AS (
  SELECT date, risk_regime, market_factor, us_10y_yield,
         stack(4, 'USD/COP', usd_cop, 'USD/PEN', usd_pen, 'USD/MXN', usd_mxn, 'USD/CLP', usd_clp) AS (par, valor)
  FROM m
)
SELECT *, 100 * valor / FIRST_VALUE(valor, true) OVER (PARTITION BY par ORDER BY date) AS fx_base100
FROM fx"""),
        dataset("ds_fund", "Ratios trimestrales", f"""
SELECT issuer_id, asset_id, name, sector, period_end, imputed_period, revenue_usd_m, ebitda_usd_m,
       net_income_usd_m, net_debt_usd_m, ebitda_ltm_usd_m, ebitda_margin, net_margin,
       net_debt_to_ebitda_ltm, revenue_qoq
FROM {g}.fundamentals_ratios"""),
        dataset("ds_fund_last", "Último trimestre por emisor", f"""
SELECT * FROM {g}.fundamentals_ratios
QUALIFY ROW_NUMBER() OVER (PARTITION BY issuer_id ORDER BY period_end DESC) = 1"""),
        dataset("ds_events", "Impacto de eventos", f"""
SELECT event_id, event_date, event_type, severity, headline, asset_id, t, date, ret_abnormal, car,
       CONCAT(asset_id, ' · ', date_format(event_date, 'yyyy-MM-dd'), ' · ', event_type) AS serie
FROM {g}.event_impact"""),
        dataset("ds_events_summary", "CAR por evento", f"""
SELECT event_id, event_date, event_type, severity, headline, asset_id,
       MAX(CASE WHEN t = -1 THEN car END) AS car_pre,
       MAX(CASE WHEN t = 3 THEN car END) AS car_3,
       MAX(CASE WHEN t = 10 THEN car END) AS car_10
FROM {g}.event_impact
GROUP BY ALL"""),
        dataset("ds_fit", "Compatibilidad cliente-activo", f"""
SELECT CONCAT(client_id, ' · ', profile_name) AS cliente, client_id, profile_name, base_currency,
       asset_id, name, sector, country, max_drawdown_local, vol_anual_local, cumple_drawdown,
       -max_drawdown_tolerance_pct / 100 AS tolerancia_drawdown
FROM {g}.client_asset_fit"""),
        dataset("ds_dq", "Scorecard de calidad", f"""
SELECT *, filas_bronze - filas_silver - filas_cuarentena AS filas_eliminadas
FROM {g}.dq_scorecard"""),
    ]

    mercado = [
        text("t_mercado", """
## Mercado y riesgo
Precio diario limpio (silver → gold) de los 8 activos. Retornos en USD; el intradía queda fuera hasta que la fuente defina el precio oficial.""", 0, 0, 6, 2),
        filter_multi("f_activo", "Activo", "name", ["ds_prices", "ds_risk"], (0, 2, 3, 1)),
        filter_multi("f_sector", "Sector", "sector", ["ds_prices", "ds_risk"], (3, 2, 3, 1)),
        counter("c_activos", "Activos", "ds_risk", "COUNT(DISTINCT `asset_id`)", 0, 3),
        counter("c_ret_max", "Mejor retorno total", "ds_risk", "MAX(`ret_total`)", 1, 3, fmt=PCT),
        counter("c_ret_min", "Peor retorno total", "ds_risk", "MIN(`ret_total`)", 2, 3, fmt=PCT),
        counter("c_vol", "Volatilidad anual prom.", "ds_risk", "AVG(`vol_anual`)", 3, 3, fmt=PCT),
        counter("c_dd", "Peor drawdown", "ds_risk", "MIN(`max_drawdown`)", 4, 3, fmt=PCT),
        counter("c_dias", "Sesiones", "ds_risk", "MAX(`n_dias`)", 5, 3),
        chart("l_base100", "line", "Precio base 100", "ds_prices",
              ("date", "Fecha", "temporal"), ("close_base100", "Base 100", "quantitative"), (0, 5, 4, 6),
              color=("name", "Activo", "categorical"), description="100 = cierre del primer día disponible"),
        chart("s_riesgo", "scatter", "Riesgo vs retorno", "ds_risk",
              ("vol_anual", "Volatilidad anual", "quantitative", PCT),
              ("ret_anual", "Retorno anualizado", "quantitative", PCT), (4, 5, 2, 6),
              color=("name", "Activo", "categorical")),
        chart("l_drawdown", "line", "Drawdown desde el máximo", "ds_prices",
              ("date", "Fecha", "temporal"), ("drawdown", "Drawdown", "quantitative", PCT), (0, 11, 4, 5),
              color=("name", "Activo", "categorical")),
        chart("b_drawdown", "bar", "Máximo drawdown por activo", "ds_risk",
              ("max_drawdown", "Máx. drawdown", "quantitative", PCT), ("name", "Activo", "categorical"),
              (4, 11, 2, 5)),
        table("tb_riesgo", "Métricas por activo", "ds_risk", [
            ("asset_id", "ID", "string"), ("name", "Activo", "string"), ("sector", "Sector", "string"),
            ("country", "País", "string"), ("ret_total", "Retorno total", "pct"),
            ("ret_anual", "Retorno anual", "pct"), ("vol_anual", "Vol. anual", "pct"),
            ("sharpe_aprox", "Sharpe aprox.", "num"), ("max_drawdown", "Máx. drawdown", "pct"),
            ("peor_dia", "Peor día", "pct"), ("mejor_dia", "Mejor día", "pct"),
            ("volumen_prom", "Volumen prom.", "int")], (0, 16, 6, 5)),
        text("t_macro", """
### Contexto macro
Tipos de cambio contra USD (base 100) y días por régimen de riesgo.""", 0, 21, 6, 1),
        chart("l_fx", "line", "Tipo de cambio base 100", "ds_macro",
              ("date", "Fecha", "temporal"), ("fx_base100", "Base 100", "quantitative"), (0, 22, 4, 5),
              color=("par", "Par", "categorical"), description="Sube = la moneda local se deprecia frente al USD"),
        _place({"name": "b_regimen", "queries": [_query("ds_macro", [
                    ("risk_regime", "`risk_regime`"), ("dias", "COUNT(DISTINCT `date`)")], False)],
                "spec": {"version": 3, "widgetType": "bar", "encodings": {
                    "x": {"fieldName": "risk_regime", "displayName": "Régimen", "scale": {"type": "categorical"}},
                    "y": {"fieldName": "dias", "displayName": "Días", "scale": {"type": "quantitative"}}},
                    "frame": {"showTitle": True, "title": "Días por régimen de riesgo"}}}, 4, 22, 2, 5),
    ]

    fundamentales = [
        text("t_fund", """
## Fundamentales
Ratios trimestrales por emisor. Deuda neta / EBITDA usa EBITDA de los últimos 4 trimestres (LTM) y queda vacío si falta alguno.""", 0, 0, 6, 2),
        filter_multi("f_emisor", "Activo", "name", ["ds_fund", "ds_fund_last"], (0, 2, 3, 1)),
        filter_multi("f_sector_fund", "Sector", "sector", ["ds_fund", "ds_fund_last"], (3, 2, 3, 1)),
        chart("l_margen", "line", "Margen EBITDA", "ds_fund",
              ("period_end", "Trimestre", "temporal"), ("ebitda_margin", "Margen EBITDA", "quantitative", PCT),
              (0, 3, 3, 6), color=("name", "Activo", "categorical")),
        chart("l_ingresos", "line", "Ingresos (USD M)", "ds_fund",
              ("period_end", "Trimestre", "temporal"), ("revenue_usd_m", "Ingresos USD M", "quantitative"),
              (3, 3, 3, 6), color=("name", "Activo", "categorical")),
        chart("b_apalancamiento", "bar", "Deuda neta / EBITDA LTM (último trimestre)", "ds_fund_last",
              ("name", "Activo", "categorical"), ("net_debt_to_ebitda_ltm", "Veces", "quantitative", NUM),
              (0, 9, 3, 5), description="Negativo = caja neta"),
        chart("b_margen_neto", "bar", "Margen neto (último trimestre)", "ds_fund_last",
              ("name", "Activo", "categorical"), ("net_margin", "Margen neto", "quantitative", PCT), (3, 9, 3, 5)),
        table("tb_fund", "Detalle trimestral", "ds_fund", [
            ("name", "Activo", "string"), ("period_end", "Trimestre", "date"),
            ("revenue_usd_m", "Ingresos USD M", "num"), ("ebitda_margin", "Margen EBITDA", "pct"),
            ("net_margin", "Margen neto", "pct"), ("revenue_qoq", "Ingresos QoQ", "pct"),
            ("net_debt_usd_m", "Deuda neta USD M", "num"), ("net_debt_to_ebitda_ltm", "DN / EBITDA LTM", "num"),
            ("imputed_period", "Periodo imputado", "bool")], (0, 14, 6, 6)),
    ]

    eventos = [
        text("t_eventos", """
## Impacto de eventos
Retorno anormal acumulado (CAR = retorno del activo − promedio del universo) de −5 a +10 sesiones alrededor de cada evento. Día 0 = primera sesión en o después del evento.""", 0, 0, 6, 2),
        filter_multi("f_evento", "Evento", "headline", ["ds_events", "ds_events_summary"], (0, 2, 3, 1)),
        filter_multi("f_severidad", "Severidad", "severity", ["ds_events", "ds_events_summary"], (3, 2, 3, 1)),
        chart("l_car", "line", "CAR alrededor del evento", "ds_events",
              ("t", "Sesiones relativas al evento", "quantitative"), ("car", "CAR", "quantitative", PCT),
              (0, 3, 6, 7), color=("serie", "Activo · fecha · tipo", "categorical")),
        table("tb_car", "CAR antes y después", "ds_events_summary", [
            ("event_date", "Fecha", "date"), ("asset_id", "Activo", "string"), ("event_type", "Tipo", "string"),
            ("severity", "Severidad", "string"), ("headline", "Titular", "string"),
            ("car_pre", "CAR día −1", "pct"), ("car_3", "CAR día +3", "pct"), ("car_10", "CAR día +10", "pct")],
              (0, 10, 6, 5)),
    ]

    clientes = [
        text("t_clientes", """
## Compatibilidad cliente-activo
Drawdown y volatilidad de cada activo medidos **en la moneda base del cliente** (incluye el efecto cambiario), contra su tolerancia máxima de drawdown.""", 0, 0, 6, 2),
        filter_multi("f_cliente", "Cliente", "cliente", ["ds_fit"], (0, 2, 3, 1), single=True,
                     default="CL_01 · Crecimiento Global"),
        counter("c_cumplen", "Activos dentro de tolerancia", "ds_fit", "SUM(CAST(`cumple_drawdown` AS INT))", 3, 2, 1, 2),
        counter("c_tolerancia", "Tolerancia de drawdown", "ds_fit", "MAX(`tolerancia_drawdown`)", 4, 2, 1, 2, fmt=PCT),
        counter("c_vol_cli", "Vol. anual prom. (moneda local)", "ds_fit", "AVG(`vol_anual_local`)", 5, 2, 1, 2, fmt=PCT),
        chart("b_dd_cliente", "bar", "Máx. drawdown en moneda del cliente", "ds_fit",
              ("name", "Activo", "categorical"), ("max_drawdown_local", "Máx. drawdown", "quantitative", PCT),
              (0, 4, 4, 6), color=("cumple_drawdown", "Cumple tolerancia", "categorical"),
              description="Compara cada barra con la tolerancia del cliente (contador superior)"),
        chart("s_fit", "scatter", "Volatilidad vs drawdown (moneda local)", "ds_fit",
              ("vol_anual_local", "Vol. anual", "quantitative", PCT),
              ("max_drawdown_local", "Máx. drawdown", "quantitative", PCT), (4, 4, 2, 6),
              color=("cumple_drawdown", "Cumple", "categorical")),
        table("tb_fit", "Detalle por cliente y activo", "ds_fit", [
            ("cliente", "Cliente", "string"), ("base_currency", "Moneda", "string"), ("asset_id", "ID", "string"),
            ("name", "Activo", "string"), ("sector", "Sector", "string"), ("country", "País", "string"),
            ("max_drawdown_local", "Máx. drawdown", "pct"), ("tolerancia_drawdown", "Tolerancia", "pct"),
            ("vol_anual_local", "Vol. anual", "pct"), ("cumple_drawdown", "Cumple", "bool")], (0, 10, 6, 6)),
    ]

    calidad = [
        text("t_dq", """
## Calidad de datos
Resultado de la última corrida bronze → silver: filas retenidas, corregidas, eliminadas (duplicados) y en cuarentena.""", 0, 0, 6, 2),
        counter("c_bronze", "Filas bronze", "ds_dq", "SUM(`filas_bronze`)", 0, 2, 1),
        counter("c_silver", "Filas silver", "ds_dq", "SUM(`filas_silver`)", 1, 2, 1),
        counter("c_correcciones", "Correcciones", "ds_dq", "SUM(`correcciones`)", 2, 2, 1),
        counter("c_eliminadas", "Eliminadas", "ds_dq", "SUM(`filas_eliminadas`)", 3, 2, 1),
        counter("c_cuarentena", "En cuarentena", "ds_dq", "SUM(`filas_cuarentena`)", 4, 2, 1),
        counter("c_ret", "% retenido global", "ds_dq", "SUM(`filas_silver`) / SUM(`filas_bronze`)", 5, 2, 1, fmt=PCT),
        chart("b_retenido", "bar", "% retenido por tabla", "ds_dq",
              ("pct_retenido", "% retenido", "quantitative"), ("silver", "Tabla silver", "categorical"), (0, 4, 3, 5)),
        chart("b_correcciones", "bar", "Correcciones por tabla", "ds_dq",
              ("correcciones", "Correcciones", "quantitative"), ("silver", "Tabla silver", "categorical"), (3, 4, 3, 5)),
        table("tb_dq", "Scorecard", "ds_dq", [
            ("bronze", "Bronze", "string"), ("silver", "Silver", "string"), ("filas_bronze", "Filas bronze", "int"),
            ("filas_silver", "Filas silver", "int"), ("filas_cuarentena", "Cuarentena", "int"),
            ("filas_eliminadas", "Eliminadas", "int"), ("correcciones", "Correcciones", "int"),
            ("pct_retenido", "% retenido", "num"), ("run_ts", "Corrida", "date")], (0, 9, 6, 4)),
    ]

    pages = [("p_mercado", "Mercado y riesgo", mercado), ("p_fund", "Fundamentales", fundamentales),
             ("p_eventos", "Eventos", eventos), ("p_clientes", "Clientes", clientes),
             ("p_calidad", "Calidad de datos", calidad)]
    return {"datasets": datasets,
            "pages": [{"name": n, "displayName": d, "pageType": "PAGE_TYPE_CANVAS", "layout": l} for n, d, l in pages]}


def serialize(catalog):
    return json.dumps(build(catalog), ensure_ascii=False, indent=2)
