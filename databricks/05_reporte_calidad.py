# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Reporte del proceso de curación
# MAGIC Resume **qué llegó, qué se corrigió, qué se eliminó y qué se apartó** en la última corrida del pipeline,
# MAGIC y qué habilita la capa gold. Se puede agregar como 4.ª tarea del Job (después de `gold`)
# MAGIC o abrir como dashboard: *View → Dashboard*.

# COMMAND ----------

# MAGIC %pip install -q plotly

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyspark.sql import functions as F

# Paleta validada (categórica en orden fijo, estado reservado, secuencial azul)
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
GOOD, CRITICAL, NEUTRAL = "#0ca30c", "#d03b3b", "#c3c2b7"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e7e6e2", "#fcfcfb"

def style(fig, title, subtitle=None, height=420):
    sub = f"<br><span style='font-size:13px;color:{INK2}'>{subtitle}</span>" if subtitle else ""
    fig.update_layout(
        template="plotly_white", height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        title=dict(text=f"<b>{title}</b>{sub}", x=0, xanchor="left", xref="paper", y=1, yref="container", yanchor="top", pad=dict(t=14)),
        font=dict(family="Inter, Helvetica, Arial, sans-serif", color=INK, size=13),
        margin=dict(l=10, r=30, t=110, b=40),
        legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", title=None, font=dict(color=INK2), traceorder="normal"),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=GRID),
        bargap=0.35)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=INK2), title_font=dict(color=INK2))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=INK2), title_font=dict(color=INK2))
    return fig

def fmt(n):
    return f"{n:,.0f}".replace(",", ".")

# COMMAND ----------

dq = spark.table(f"{SILVER}.dq_log")
last_run = dq.agg(F.max("run_ts")).first()[0]
log = dq.filter(F.col("run_ts") == last_run).toPandas()
score = spark.table(f"{GOLD}.dq_scorecard").toPandas()

ACTIONS = {  # acción -> color (orden categórico fijo; 'sin cambio' en neutro)
    "Corregido": CAT[0],
    "Eliminado (duplicado)": CAT[1],
    "Completado / imputado": CAT[2],
    "Enviado a cuarentena": CAT[3],
    "Detectado, sin cambio": NEUTRAL,
}

def action(rule):
    if rule.startswith("Cuarentena") or rule.startswith("Scope no mapeable"): return "Enviado a cuarentena"
    if rule.startswith("Eliminar"): return "Eliminado (duplicado)"
    if rule.startswith(("Completar", "Forward-fill", "Reasignar", "Interpolar")): return "Completado / imputado"
    if rule.startswith(("Nulos", "Marcar", "Restricción", "Tolerancia")): return "Detectado, sin cambio"
    return "Corregido"

log["accion"] = log.rule.map(action)
log = log[log.rows_affected > 0]
print(f"Corrida analizada: {last_run}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Resumen de la corrida

# COMMAND ----------

def fixed_rows(table):
    df = spark.table(table)
    return df.filter("size(_dq_fixes) > 0").count() if "_dq_fixes" in df.columns else 0

tot_bronze = int(score.filas_bronze.sum())
tot_silver = int(score.filas_silver.sum())
tot_quar = int(score.filas_cuarentena.sum())
tot_dup = int(log.loc[log.accion == "Eliminado (duplicado)", "rows_affected"].sum())
tot_fixed = sum(fixed_rows(f"{SILVER}.{t}") for t in ["market_prices_daily", "market_prices_intraday", "fundamentals"])
n_rules = log.rule.nunique()

tiles = [
    ("Filas recibidas (bronze)", fmt(tot_bronze), f"{len(SOURCES)} archivos CSV"),
    ("Filas en silver", fmt(tot_silver), f"{tot_silver / tot_bronze:.2%} retenido"),
    ("Filas corregidas", fmt(tot_fixed), f"{n_rules} reglas con efecto"),
    ("Duplicados eliminados", fmt(tot_dup), "una fila por llave"),
    ("En cuarentena", fmt(tot_quar), "no recuperables"),
]
displayHTML(f"""
<div style="font-family:Inter,Helvetica,Arial,sans-serif;background:{SURFACE};padding:8px 4px;display:flex;flex-wrap:wrap;gap:12px">
  {''.join(f'''<div style="flex:1 1 170px;border:1px solid {GRID};border-radius:10px;padding:14px 16px;background:#fff">
      <div style="font-size:12px;color:{INK2};text-transform:uppercase;letter-spacing:.04em">{label}</div>
      <div style="font-size:30px;font-weight:600;color:{INK};margin:4px 0">{value}</div>
      <div style="font-size:12px;color:{INK2}">{note}</div></div>''' for label, value, note in tiles)}
</div>
<div style="font-family:Inter,Helvetica,Arial,sans-serif;font-size:12px;color:{INK2};margin-top:6px">
Corrida: {last_run:%Y-%m-%d %H:%M} UTC</div>""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. ¿Qué le pasó a cada tabla?

# COMMAND ----------

special = {"macro_daily": spark.table(f"{SILVER}.macro_daily").filter("us_inflation_yoy IS NULL").count()}
rows = []
for r in score.itertuples():
    eliminated = r.filas_bronze - r.filas_silver - r.filas_cuarentena
    rows.append({"tabla": r.silver,
                 "Corregido": fixed_rows(f"{SILVER}.{r.silver}") if r.silver != "macro_daily" else 0,
                 "Completado / imputado": special.get(r.silver, 0),
                 "Eliminado (duplicado)": eliminated,
                 "Enviado a cuarentena": r.filas_cuarentena,
                 "intactas_pct": 1 - (fixed_rows(f"{SILVER}.{r.silver}") + special.get(r.silver, 0) + eliminated + r.filas_cuarentena) / r.filas_bronze,
                 "filas_bronze": r.filas_bronze})
impact = pd.DataFrame(rows).sort_values("filas_bronze")

fig = go.Figure()
for act in ["Corregido", "Completado / imputado", "Eliminado (duplicado)", "Enviado a cuarentena"]:
    fig.add_bar(y=impact.tabla, x=impact[act], name=act, orientation="h", marker_color=ACTIONS[act],
                marker_line=dict(color=SURFACE, width=2),
                hovertemplate="<b>%{y}</b><br>" + act + ": %{x:,} filas<extra></extra>")
fig.add_scatter(y=impact.tabla, x=impact[["Corregido", "Completado / imputado", "Eliminado (duplicado)", "Enviado a cuarentena"]].sum(axis=1),
                mode="text", text=[f"  {p:.2%} intactas · {fmt(b)} filas" for p, b in zip(impact.intactas_pct, impact.filas_bronze)],
                textposition="middle right", textfont=dict(color=INK2, size=12), showlegend=False, hoverinfo="skip")
fig.update_layout(barmode="stack")
fig.update_xaxes(title="filas afectadas", range=[0, impact[list(ACTIONS)[:4]].sum(axis=1).max() * 1.9])
style(fig, "Filas afectadas por tabla", "Cuántas filas de cada tabla recibieron alguna acción; el resto pasó intacto", height=380).show()
display(impact.drop(columns="intactas_pct"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Detalle por regla de calidad

# COMMAND ----------

d = log.assign(etiqueta=log.source_table.str.replace("_raw", "") + " · " + log.rule).sort_values("rows_affected")
fig = px.bar(d, x="rows_affected", y="etiqueta", color="accion", orientation="h", text="rows_affected",
             color_discrete_map=ACTIONS, category_orders={"accion": list(ACTIONS)},
             custom_data=["source_table", "rule", "accion"])
fig.update_traces(textposition="outside", textfont=dict(color=INK2), cliponaxis=False,
                  hovertemplate="<b>%{customdata[1]}</b><br>Tabla: %{customdata[0]}<br>%{customdata[2]}: %{x:,} filas<extra></extra>")
fig.update_layout(yaxis=dict(categoryorder="array", categoryarray=d.etiqueta.tolist(), title=None))
fig.update_xaxes(title="filas (escala log)", type="log", dtick=1)
style(fig, "Qué reglas se aplicaron y a cuántas filas", "Escala logarítmica: la imputación de inflación (258) no opaca las correcciones puntuales",
      height=140 + 28 * len(d)).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Antes y después: ejemplos concretos

# COMMAND ----------

def norm_asset(c):
    num = F.regexp_extract(c, r"^VF[-_]?A?0*(\d+)$", 1)
    return F.when(num != "", F.format_string("VF_A%02d", num.cast("int"))).otherwise(c)

parsed_date = F.to_date(F.expr("coalesce(try_to_timestamp(date, 'yyyy-MM-dd'), try_to_timestamp(date, 'MM/dd/yyyy'))"))
close_raw, high_raw = F.expr("try_cast(close AS DOUBLE)"), F.expr("try_cast(high AS DOUBLE)")

anomalies = (spark.table(f"{BRONZE}.market_prices_raw")
             .filter(~F.col("asset_id").rlike(r"^VF_A\d{2}$") | ~F.col("date").rlike(r"^\d{4}-")
                     | F.upper("volume").rlike("[KMB]$") | F.col("currency").isNull() | (close_raw > high_raw))
             .withColumn("asset_key", norm_asset(F.col("asset_id"))).withColumn("date_key", parsed_date))
after = spark.table(f"{SILVER}.market_prices_daily").select(
    F.col("asset_id").alias("asset_key"), F.col("date").alias("date_key"),
    F.col("asset_id").alias("asset_id_new"), F.col("date").cast("string").alias("date_new"),
    F.col("currency").alias("currency_new"), F.col("close").alias("close_new"), F.col("volume").alias("volume_new"),
    "_dq_fixes")
pairs = anomalies.join(after, ["asset_key", "date_key"], "left").toPandas()

changes = []
for r in pairs.itertuples():
    for field, old, new in [("asset_id", r.asset_id, r.asset_id_new), ("date", r.date, r.date_new),
                            ("currency", r.currency, r.currency_new), ("volume", r.volume, r.volume_new),
                            ("close", r.close, r.close_new)]:
        same = str(old) == str(new)
        if field in ("volume", "close") and not same:
            try: same = float(old) == float(new)
            except (TypeError, ValueError): pass
        if not same:
            changes.append({"activo": r.asset_key, "fecha": str(r.date_key), "campo": field,
                            "antes (bronze)": "∅ nulo" if old is None else str(old),
                            "después (silver)": "∅ nulo" if pd.isna(new) else (f"{new:,.0f}" if field == "volume" else str(new))})
changes = pd.DataFrame(changes).sort_values(["campo", "activo"])

td = f"padding:5px 14px 5px 0;border-bottom:1px solid {GRID}"
rows_html = "".join(
    f"<tr><td style='{td}'>{c['campo']}</td><td style='{td}'>{c['activo']}</td><td style='{td}'>{c['fecha']}</td>"
    f"<td style='{td};color:{CRITICAL};font-family:monospace'>{c['antes (bronze)']}</td>"
    f"<td style='{td};color:{INK2}'>→</td>"
    f"<td style='{td};color:{INK};font-family:monospace;font-weight:600'>{c['después (silver)']}</td></tr>"
    for c in changes.to_dict("records"))
displayHTML(f"""
<div style="font-family:Inter,Helvetica,Arial,sans-serif;background:{SURFACE};padding:4px">
<div style="font-weight:600;font-size:16px;margin-bottom:2px">Precios diarios: cada valor que cambió</div>
<div style="color:{INK2};font-size:13px;margin-bottom:8px">{len(changes)} cambios en {len(pairs)} filas crudas con anomalías</div>
<table style="border-collapse:collapse;font-size:13px">
<thead><tr style="text-align:left;color:{INK2};border-bottom:1px solid {GRID}">
<th style="padding:6px 14px 6px 0">Campo</th><th style="padding:6px 14px 6px 0">Activo</th><th style="padding:6px 14px 6px 0">Fecha</th>
<th style="padding:6px 14px 6px 0">Antes</th><th></th><th style="padding:6px 14px 6px 0">Después</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>""")

# COMMAND ----------

fb = (spark.table(f"{BRONZE}.fundamentals_raw")
      .filter(~F.col("issuer_id").rlike(r"^ISS_\d{2}$") | ~F.col("period_end").rlike(r"^\d{4}-") | F.col("revenue_usd_m").contains(","))
      .drop("_source_file", "_ingest_ts"))
print("Fundamentales · ANTES (bronze, filas con anomalías)")
display(fb)
print("Fundamentales · DESPUÉS (silver, filas corregidas)")
display(spark.table(f"{SILVER}.fundamentals").filter("size(_dq_fixes) > 0"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. El error que más distorsionaba: precio ×100

# COMMAND ----------

target = (spark.table(f"{BRONZE}.market_prices_raw").filter(close_raw > high_raw)
          .select(norm_asset(F.col("asset_id")).alias("a"), parsed_date.alias("d")).first())
if target:
    a, d = target["a"], target["d"]
    before = (spark.table(f"{BRONZE}.market_prices_raw").withColumn("asset_key", norm_asset(F.col("asset_id")))
              .filter(F.col("asset_key") == a).select(parsed_date.alias("date"), close_raw.alias("close"))
              .dropna().dropDuplicates(["date"]).orderBy("date").toPandas())
    after_s = spark.table(f"{SILVER}.market_prices_daily").filter(F.col("asset_id") == a).select("date", "close").orderBy("date").toPandas()
    bad_pt, good_pt = before[before.date == d].iloc[0], after_s[after_s.date == d].iloc[0]

    for df, pt, color, label, sub in [
        (before, bad_pt, CRITICAL, f"{bad_pt.close:,.2f}", "ANTES (bronze): un solo valor mal escalado aplasta toda la serie"),
        (after_s, good_pt, GOOD, f"{good_pt.close:,.2f} ✓ corregido", "DESPUÉS (silver): close ÷ 100 cae dentro de [low, high] del día"),
    ]:
        fig = go.Figure()
        fig.add_scatter(x=df.date, y=df.close, mode="lines", line=dict(color=CAT[0], width=2), showlegend=False,
                        hovertemplate="%{x|%Y-%m-%d}<br>close: %{y:,.2f}<extra></extra>")
        fig.add_scatter(x=[pt.date], y=[pt.close], mode="markers", showlegend=False,
                        marker=dict(color=color, size=11, line=dict(color=SURFACE, width=2)),
                        hovertemplate="%{x|%Y-%m-%d}<br>close: %{y:,.2f}<extra></extra>")
        fig.add_annotation(x=pt.date, y=pt.close, text=label, showarrow=True, arrowhead=0, arrowcolor=INK2,
                           ax=60, ay=-30, bgcolor=SURFACE, font=dict(color=INK))
        fig.update_yaxes(title="close (USD)")
        style(fig, f"{a} · precio de cierre", sub, height=320).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Filas en cuarentena

# COMMAND ----------

quar = [t.tableName for t in spark.sql(f"SHOW TABLES IN {SILVER}").collect() if t.tableName.endswith("_quarantine")]
for t in quar:
    q = spark.table(f"{SILVER}.{t}")
    n = q.count()
    print(f"{t}: {n} filas")
    if n and "_quarantine_reason" in q.columns:
        display(q.groupBy("_quarantine_reason").count())
        display(q.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Hallazgo: intradía vs diario no reconcilian
# MAGIC Se reconstruye el cierre diario desde las barras de 10 min y se compara con el archivo diario.

# COMMAND ----------

intra_close = (spark.table(f"{SILVER}.market_prices_intraday")
               .groupBy("asset_id", "date").agg(F.max_by("close", "ts").alias("close_intra")))
rec = (intra_close.join(spark.table(f"{SILVER}.market_prices_daily").select("asset_id", "date", F.col("close").alias("close_daily")),
                        ["asset_id", "date"])
       .withColumn("diff_pct", (F.col("close_intra") / F.col("close_daily") - 1) * 100).toPandas())
share = (rec.diff_pct.abs() > 1).mean()

fig = go.Figure(go.Histogram(x=rec.diff_pct, nbinsx=60, marker_color=CAT[0], marker_line=dict(color=SURFACE, width=1),
                             hovertemplate="diferencia %{x:.1f}%<br>%{y} días-activo<extra></extra>"))
for x in (-1, 1):
    fig.add_vline(x=x, line=dict(color=INK2, width=1, dash="dot"))
fig.add_annotation(x=0, y=1, yref="paper", text="±1%", showarrow=False, font=dict(color=INK2), yanchor="bottom")
fig.update_xaxes(title="diferencia % (cierre intradía vs cierre diario)")
fig.update_yaxes(title="días-activo")
style(fig, f"{share:.0%} de los días difiere más de 1%",
      f"{len(rec):,} días-activo comparados · si fueran la misma fuente, todo estaría en la franja ±1%").show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Lo que habilita la capa gold

# COMMAND ----------

risk = spark.table(f"{GOLD}.asset_risk_metrics").toPandas()
crowded = lambda r: any((abs(o.vol_anual - r.vol_anual) < 0.03) and (0 < o.ret_anual - r.ret_anual < 0.05) for o in risk.itertuples())
positions = ["bottom center" if crowded(r) else "top center" for r in risk.itertuples()]
fig = go.Figure(go.Scatter(
    x=risk.vol_anual, y=risk.ret_anual, mode="markers+text", text=risk.name, textposition=positions,
    marker=dict(color=CAT[0], size=12, line=dict(color=SURFACE, width=2)), textfont=dict(color=INK2, size=12),
    customdata=risk[["asset_id", "sector", "max_drawdown"]],
    hovertemplate="<b>%{text}</b> (%{customdata[0]})<br>%{customdata[1]}<br>Retorno anual: %{y:.1%}<br>"
                  "Volatilidad: %{x:.1%}<br>Max drawdown: %{customdata[2]:.1%}<extra></extra>"))
fig.add_hline(y=0, line=dict(color=INK2, width=1))
fig.update_xaxes(title="volatilidad anual", tickformat=".0%")
fig.update_yaxes(title="retorno anual", tickformat=".0%")
style(fig, "Riesgo vs retorno por activo", "gold.asset_risk_metrics · calculado sobre precios ya curados", height=460).show()

# COMMAND ----------

fit = spark.table(f"{GOLD}.client_asset_fit").toPandas()
fit["col"] = fit.client_id + "<br>" + fit.profile_name + "<br>tol. -" + fit.max_drawdown_tolerance_pct.map("{:.0f}%".format)
z = fit.pivot(index="asset_id", columns="col", values="cumple_drawdown").astype(int)
txt = fit.pivot(index="asset_id", columns="col", values="max_drawdown_local")
txt = txt.map(lambda v: f"{v:.1%}") + z.map(lambda c: "  ✓" if c else "  ✗")
fig = go.Figure(go.Heatmap(z=z.values, x=z.columns, y=z.index, text=txt.values, texttemplate="%{text}",
                           colorscale=[[0, "#efeeea"], [1, GOOD]], zmin=0, zmax=1, showscale=False, xgap=3, ygap=3,
                           hovertemplate="%{y} · %{x}<br>Max drawdown en moneda del cliente: %{text}<extra></extra>"))
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(side="top", showgrid=False)
style(fig, "¿Qué activos caben en la tolerancia de cada cliente?",
      "Max drawdown histórico en la moneda base del cliente · ✓ dentro de tolerancia · ✗ la excede", height=480).show()

# COMMAND ----------

car = spark.table(f"{GOLD}.event_impact").toPandas()
car["evento"] = car.event_date.astype(str) + " · " + car.scope + "<br>" + car.event_type + " (" + car.severity + ")"
fig = px.line(car, x="t", y="car", facet_col="evento", facet_col_wrap=3, color_discrete_sequence=[CAT[0]],
              custom_data=["asset_id", "headline"], facet_row_spacing=0.18)
fig.update_traces(line=dict(width=2), hovertemplate="%{customdata[0]} · t=%{x}<br>CAR: %{y:.1%}<br>%{customdata[1]}<extra></extra>")
fig.for_each_annotation(lambda a: a.update(text=a.text.split("=", 1)[-1], font=dict(size=12, color=INK)))
fig.add_vline(x=0, line=dict(color=INK2, width=1, dash="dot"), row="all", col="all")
fig.add_hline(y=0, line=dict(color=INK2, width=1), row="all", col="all")
fig.update_yaxes(tickformat=".0%", title=None)  # eje compartido: los eventos se comparan en la misma escala
fig.update_xaxes(title=None)
style(fig, "Retorno anormal acumulado alrededor de cada evento",
      "gold.event_impact · días hábiles relativos al evento (línea punteada = día del evento)", height=560).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Historial de corridas

# COMMAND ----------

hist = (dq.groupBy("run_ts").agg(F.sum("rows_affected").alias("acciones"), F.countDistinct("rule").alias("reglas"))
          .orderBy("run_ts").toPandas())
if len(hist) > 1:
    fig = go.Figure(go.Bar(x=hist.run_ts, y=hist.acciones, marker_color=CAT[0],
                           hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:,} acciones<extra></extra>"))
    fig.update_yaxes(title="acciones de calidad")
    style(fig, "Acciones de calidad por corrida", "Un cambio brusco indica que la fuente cambió", height=320).show()
display(hist)
