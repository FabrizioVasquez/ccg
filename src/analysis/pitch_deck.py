"""Presentación Value Pitch (estilo visual del evento Value Finders) → docs/pitch_value_finders_cl02.pptx
Uso: .venv/bin/python src/analysis/pitch_deck.py   (requiere python-pptx y los gráficos de docs/img)"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

NAVY, RED, BLUE, LIGHT, WHITE, GREY, DARK = (RGBColor(0x14, 0x1B, 0x2D), RGBColor(0xE5, 0x48, 0x2D), RGBColor(0x2F, 0x6B, 0xDB),
                                             RGBColor(0xEE, 0xF0, 0xF4), RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x6B, 0x72, 0x80),
                                             RGBColor(0x1F, 0x29, 0x37))
FONT = "Inter"
IMG = "docs/img/"
prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def rect(s, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, line=None):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid(); r.fill.fore_color.rgb = fill
    if line is None:
        r.line.fill.background()
    else:
        r.line.color.rgb = line; r.line.width = Pt(1.25)
    r.shadow.inherit = False
    return r


def text(s, x, y, w, h, runs, size=14, color=DARK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.1):
    """runs: str | list de párrafos; cada párrafo str o lista de (texto, {bold,color,size})."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.02)
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align; para.line_spacing = spacing
        for t, fmt in ([(p, {})] if isinstance(p, str) else p):
            r = para.add_run(); r.text = t; f = r.font
            f.name = FONT; f.size = Pt(fmt.get("size", size)); f.bold = fmt.get("bold", bold)
            f.color.rgb = fmt.get("color", color)
    return tb


def deco(s, dark=False):
    """Marca del evento: etiqueta superior y cuadritos rojo/azul (sin logos)."""
    text(s, 0.45, 0.3, 4, 0.35, [[("{ ", {"color": RED, "bold": True}), ("VALUE FINDERS", {"bold": True, "color": WHITE if dark else NAVY}),
                                  (" }", {"color": BLUE if not dark else RGBColor(0x7F, 0xA6, 0xF0), "bold": True})]], size=12)
    rect(s, 12.45, 0.3, 0.42, 0.42, RED); rect(s, 12.12, 0.72, 0.33, 0.33, BLUE)


def base(title=None, kicker=None, dark=False, notes=""):
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill; bg.solid(); bg.fore_color.rgb = NAVY if dark else LIGHT
    if not dark:   # banda diagonal suave como en el PDF
        tri = rect(s, 7.8, 0, 5.53, 7.5, RGBColor(0xE3, 0xE6, 0xEC), MSO_SHAPE.RIGHT_TRIANGLE); tri.rotation = 180
    deco(s, dark)
    if kicker:
        text(s, 0.45, 0.85, 9, 0.4, kicker, size=13, color=RED, bold=True)
    if title:
        text(s, 0.45, 1.15, 11.4, 0.7, title, size=25, color=WHITE if dark else NAVY, bold=True)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def card(s, x, y, w, h, title, body, fill=RED, tsize=15, bsize=11.5, tc=WHITE):
    rect(s, x, y, w, h, fill)
    text(s, x + 0.18, y + 0.15, w - 0.36, 0.5, title, size=tsize, color=tc, bold=True)
    s.shapes.add_connector(1, Inches(x + 0.18), Inches(y + 0.72), Inches(x + w - 0.18), Inches(y + 0.72)).line.color.rgb = tc
    text(s, x + 0.18, y + 0.82, w - 0.36, h - 0.9, body, size=bsize, color=tc)


def kpi(s, x, y, w, h, big, small, fill=NAVY, bc=WHITE, ss=10.5):
    rect(s, x, y, w, h, fill)
    text(s, x + 0.15, y + 0.08, w - 0.3, h * 0.55, big, size=30, color=bc, bold=True, anchor=MSO_ANCHOR.BOTTOM)
    text(s, x + 0.15, y + h * 0.55, w - 0.3, h * 0.43, small, size=ss, color=bc)


def pic(s, path, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    s.shapes.add_picture(path, Inches(x), Inches(y), **kw)


def table(s, x, y, w, rows, colw, size=11, header_fill=NAVY, rh=0.36, bold_rows=()):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(rh * len(rows))).table
    for j, cw in enumerate(colw):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = ""; c.margin_left = c.margin_right = Inches(0.06)
            c.fill.solid(); c.fill.fore_color.rgb = header_fill if i == 0 else (WHITE if i % 2 else RGBColor(0xF6, 0xF7, 0xF9))
            p = c.text_frame.paragraphs[0]; r = p.add_run(); r.text = str(v)
            r.font.name = FONT; r.font.size = Pt(size); r.font.bold = (i == 0) or (i in bold_rows)
            r.font.color.rgb = WHITE if i == 0 else DARK
    return t


def qtag(s, n, q):
    """Etiqueta de pregunta del Decision Dashboard: { 01 ¿...? }"""
    text(s, 0.45, 0.85, 11, 0.45, [[("{ ", {"color": RED, "bold": True}), (f"{n:02d} · ", {"color": BLUE, "bold": True}),
                                    (q, {"color": RED, "bold": True}), (" }", {"color": RED, "bold": True})]], size=14)


# ---------------- 1. Portada ----------------
s = base(dark=True, notes="Danilo abre (0:00–0:40). Presentar al cliente y la pregunta.")
text(s, 0.6, 1.2, 8, 2.1, [[("{ ", {"color": RED}), ("VALUE", {"color": WHITE})], [("FINDERS", {"color": WHITE}), (" }", {"color": BLUE})]],
     size=54, bold=True, spacing=0.95)
text(s, 0.6, 3.55, 8.2, 1.3, "Para CL_02 la decisión no es qué acción comprar,\nsino cuánto riesgo tomar.", size=26, color=WHITE, bold=True)
text(s, 0.6, 4.95, 8, 0.5, "Recomendación de inversión con evidencia · Wealth Management", size=15, color=RED, bold=True)
text(s, 0.6, 6.55, 8, 0.4, "Equipo: Danilo · Cesar · Raf · Fabrizio", size=12, color=WHITE)
text(s, 9.3, 6.55, 3.6, 0.4, "Lima, 31 de octubre de 2026", size=12, color=WHITE, align=PP_ALIGN.RIGHT)
rect(s, 9.4, 1.8, 3.3, 3.6, RED); rect(s, 8.9, 4.9, 1.0, 1.0, BLUE)
text(s, 9.6, 2.0, 2.9, 3.2, [[("20%", {"size": 60, "bold": True})], "en un núcleo defensivo", " ",
                             [("95,7%", {"size": 34, "bold": True})], "de escenarios cumplen su límite de −10% a 36 meses"],
     size=14, color=WHITE)

# ---------------- 2. Pregunta y cliente ----------------
s = base("La pregunta y el cliente que elegimos", "El reto", notes="Danilo. Por qué CL_02: es donde los datos cambian la decisión (valor de la información).")
rect(s, 0.45, 2.05, 5.2, 2.0, BLUE)
text(s, 0.65, 2.2, 4.8, 1.8, "¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?",
     size=16, color=WHITE, bold=True)
text(s, 0.45, 4.3, 5.2, 2.8, [[("Criterio para elegir: valor de la información. ", {"bold": True, "color": NAVY}),
                              ("Atendemos al cliente donde decidir con datos, en vez de “repartir en partes iguales”, ahorra más dinero.", {})],
                             " ", [("CL_02 tiene 2 de los 3 shocks del twist: ", {"bold": True, "color": NAVY}), ("retira 30% en 6 meses y el COP puede caer 8%.", {})]],
     size=13)
for i, (t, b, f) in enumerate([
        ("Cliente 01 · Crecimiento", "USD · tolera −22%\n\n33,8% de carteras cumplen\nequiponderada rompe: 29%\n\n→ el análisis cambia poco", RED),
        ("Cliente 02 · Patrimonio estable", "COP · tolera −10% · 36 meses\n\n0,01% de carteras cumplen\nequiponderada rompe: 92%\nse pasa 85% de su tolerancia\n\n→ los datos cambian la decisión", BLUE),
        ("Cliente 03 · Regional", "PEN · tolera −15%\n\n11,2% de carteras cumplen\nequiponderada rompe: 69%\n\n→ candidato #2 (sus mejores carteras se concentran en EE. UU.)", NAVY)]):
    card(s, 6.0 + i * 2.43, 2.05, 2.3, 4.6, t, b, f, tsize=13.5, bsize=11)
rect(s, 8.38, 1.85, 2.4, 0.16, RED)
text(s, 8.4, 6.75, 2.4, 0.4, "ELEGIDO", size=12, color=BLUE, bold=True, align=PP_ALIGN.CENTER)

# ---------------- 3. Datos confiables ----------------
s = base("Antes de recomendar: ¿podemos confiar en los datos?", "Find the truth",
         notes="Cesar (0:40–1:30). Pipeline medallón; 99,99% aprovechable; intradía contradice al diario → solo estrés.")
for i, (b, sm, f) in enumerate([("541 363", "registros crudos de 7 fuentes", NAVY), ("99,99%", "aprovechables tras la limpieza (cada corrección registrada)", BLUE),
                                 ("0,06", "correlación diario vs intradía: dos historias distintas → intradía solo para estrés y pre-entrenamiento", RED)]):
    kpi(s, 0.45 + i * 4.2, 2.1, 4.0, 1.75, b, sm, f)
table(s, 0.45, 4.15, 12.4, [
    ["Problema encontrado", "Qué hicimos", "Dónde queda"],
    ["IDs con alias, fechas mixtas, N/A, sufijos K/M/B", "Reglas estándar de homologación (regex, ISO-8601, nulos)", "silver · _dq_fixes por fila"],
    ["Un precio ×100 y duplicados", "Corrección ÷100 y una fila por llave", "silver.dq_log"],
    ["Filas sin precio de cierre", "No se imputan: cuarentena", "silver.*_quarantine"],
    ["Trimestre mal rotulado y revenue anómalo", "Se mapea por secuencia y se marca fuera de ratios", "silver.fundamentals"],
    ["Activos en USD, clientes en COP y PEN", "Riesgo en la moneda del cliente con el FX de 02_macro", "gold · riesgo en moneda base"]],
      [4.6, 4.6, 3.2], size=11)

# ---------------- 4. Q1 Qué ocurre ----------------
s = base("Ningún activo, por sí solo, respeta el límite de CL_02", notes="Raf (1:30–2:15). Solo 2 de 8 ganaron; el mejor cae 15%; repartir en partes iguales cae 17–19%: casi el doble de lo tolerado.")
qtag(s, 1, "¿Qué está ocurriendo?")
pic(s, IMG + "pitch/01_que_ocurre.png", 0.45, 2.0, w=7.6)
for i, (b, sm, f) in enumerate([("2 de 8", "activos ganaron en el año (A05 +35%, A04 +24%)", BLUE),
                                 ("0 de 8", "cumplen solos el −10%: el mejor (A05) cae −15%", RED),
                                 ("−17% a −19%", "caída de la cartera equiponderada en COP: casi el doble de lo que tolera", NAVY)]):
    kpi(s, 8.4, 2.0 + i * 1.62, 4.45, 1.48, b, sm, f)
text(s, 0.45, 6.75, 12, 0.4, "Fuente: precios diarios 2025-08-04 → 2026-08-14 convertidos a COP con el FX diario · gold.etapa2_* / etapa3_*", size=10, color=GREY)

# ---------------- 5. Q2 Señales ----------------
s = base("La señal: el retorno no se repite, el riesgo sí", notes="Fabrizio (2:15). Elegir 'ganadoras' falla: el ranking de retorno no persiste (ρ≈0). La volatilidad persiste (ρ 0,93–0,98) → decidir cuánto exponer.")
qtag(s, 2, "¿Qué datos o señales lo explican?")
pic(s, "outputs/etapa3/03_persistencia.png", 0.45, 2.0, w=7.2)
table(s, 8.0, 2.0, 4.85, [["Señal", "Evidencia", "Uso"],
                          ["Volatilidad", "ρ train→test 0,93–0,98 en 7 cortes", "sí, decide"],
                          ["Max drawdown", "ρ −0,24 a 0,60", "objetivo"],
                          ["Retorno", "ρ ≈ 0", "no decide"],
                          ["Optimizar en train", "cumple 0 de 7 fuera de muestra", "descartado"],
                          ["FX / tasas", "R² ≤ 1%: mueve DD 1–2 pp", "moneda base"],
                          ["Eventos", "4/5 en dirección, 1/5 significativo", "contexto"],
                          ["Volatilidad diaria", "sin rachas (ARCH p ≥ 0,08)", "LSTM no aporta"]],
      [1.45, 2.3, 1.1], size=10)
text(s, 0.45, 5.75, 7.3, 1.3, [[("Lectura: ", {"bold": True, "color": RED}),
                                ("lo que ganó el año pasado no predice lo que gana después; lo que se movió mucho sigue moviéndose mucho. "
                                 "Por eso la palanca no es elegir acciones, es decidir cuánto exponer.", {})]], size=13)

# ---------------- 6. Q3 Qué significa ----------------
s = base("Con el consejo ingenuo, CL_02 casi siempre rompe su promesa", notes="Raf/Fabrizio. 2000 escenarios a 36 meses. Mediana de caída −28% vs −5%.")
qtag(s, 3, "¿Qué significa para el cliente elegido?")
pic(s, IMG + "pitch/03_distribucion_caida_36m.png", 0.45, 2.0, w=7.4)
for i, (b, sm, f) in enumerate([("99,9%", "de escenarios a 36 meses en que la equiponderada rompe el −10% (propuesta: 4,3%)", RED),
                                 ("−28% vs −5%", "caída típica: equiponderada vs propuesta", NAVY),
                                 ("S/ 224 mil", "caída evitada típica por cada S/ 1 M (S/ 356 mil en el 10% de peores casos)", BLUE)]):
    kpi(s, 8.2, 2.0 + i * 1.62, 4.65, 1.48, b, sm, f)
text(s, 0.45, 6.75, 7.5, 0.6, "Además retira 30% en el mes 6: si está 100% en acciones, tendría que vender en una caída. Riesgo medido en COP (su moneda); montos en S/ sobre S/ 1 000 000.",
     size=11, color=GREY)

# ---------------- 7. Q4 Qué hacer ----------------
s = base("20% en un núcleo defensivo, 80% en liquidez en COP", notes="Fabrizio (2:15–3:45). Bloques, regla de rebalanceo, 95,7% a 36 meses, walk-forward 7/7.")
qtag(s, 4, "¿Qué debería hacer?")
for i, (pct, t, b, f) in enumerate([("20%", "Núcleo defensivo · S/ 200 000", "A08 Utilities US 33% · A01 Consumo CO 27%\nA05 Salud US 22% · A04 Financiero PE 19%\n(peso = inversa de la volatilidad)", RED),
                                     ("30%", "Reserva para el retiro · S/ 300 000", "Liquidez en COP para pagar el 30% del mes 6\nsin vender acciones en mal momento", BLUE),
                                     ("50%", "Liquidez adicional · S/ 500 000", "Depósitos / fondo de liquidez en COP\n(su tasa es la principal fuente de rentabilidad)", NAVY)]):
    y = 2.0 + i * 1.5
    rect(s, 0.45, y, 1.45, 1.35, f); text(s, 0.45, y, 1.45, 1.35, pct, size=30, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    rect(s, 1.9, y, 4.6, 1.35, WHITE)
    text(s, 2.05, y + 0.1, 4.4, 0.4, t, size=13.5, color=f, bold=True); text(s, 2.05, y + 0.5, 4.4, 0.85, b, size=10.5)
text(s, 0.45, 6.55, 6.1, 0.7, [[("Regla de gestión: ", {"bold": True, "color": RED}), ("rebalancear cada trimestre y al pagar el retiro para volver a 20%.", {})]], size=12)
pic(s, IMG + "pitch/02_curva_exposicion_36m.png", 6.8, 1.95, w=6.05)
for i, (b, sm, f) in enumerate([("95,7%", "P(caída ≤ 10%) a 36 m\n(equiponderada 0,1%)", RED), ("7 de 7", "cortes walk-forward cumplen\n(100% acciones: 0 de 7)", BLUE),
                                 ("−11,0%", "CVaR 95%: caída media en\nel peor 5% de escenarios", NAVY)]):
    kpi(s, 6.8 + i * 2.05, 5.5, 1.95, 1.75, b, sm, f, ss=9.5)

# ---------------- 8. Rentabilidad ----------------
s = base("Rentabilidad por trimestre, año y a 36 meses", "¿Qué debería hacer? · lo que el cliente gana",
         notes="Fabrizio. Base conservadora: deriva 0 y liquidez 0%. La rentabilidad real vendrá de la tasa de la liquidez (80%). Backtest real: +1,3% con caída −2,3%.")
table(s, 0.45, 2.0, 7.1, [["Horizonte", "Base (p50)", "Rango 5%–95%", "Optimista (p50)", "Equiponderada"],
                          ["1 trimestre", "−0,1%", "−2,1% / +2,1%", "+0,2%", "−0,4% [−13%; +14%]"],
                          ["1 año", "−0,3%", "−4,3% / +4,1%", "+1,0%", "−1,1% [−25%; +29%]"],
                          ["2 años", "−0,6%", "−6,2% / +5,4%", "+1,9%", "−1,7% [−32%; +44%]"],
                          ["36 meses", "−0,9%", "−7,7% / +6,5%", "+2,9%", "−3,6% [−38%; +56%]"]],
      [1.3, 1.15, 1.6, 1.35, 1.7], size=11, bold_rows=(4,))
text(s, 0.45, 3.95, 7.1, 0.5, "Base = no suponemos que el mercado sube y la liquidez rinde 0%. Optimista = se repite la tendencia del año (núcleo +6,3%/año).", size=10, color=GREY)
table(s, 0.45, 4.5, 7.1, [["Tasa de la liquidez en COP (supuesto)", "36 meses (p50)", "Anual", "P(cumplir)"],
                          ["0%", "−0,9%", "−0,3%", "95,7%"], ["2%", "+3,9%", "+1,3%", "99,7%"],
                          ["4%", "+8,9% ≈ S/ 89 mil", "+2,9%", "100%"], ["6%", "+14,0%", "+4,5%", "100%"]],
      [3.0, 1.75, 1.0, 1.35], size=11, header_fill=RED)
text(s, 0.45, 6.4, 7.1, 0.8, [[("Cada punto de tasa en la liquidez suma ≈ 0,8 pp al año ", {"bold": True, "color": NAVY}),
                               ("y además reduce el riesgo. Backtest real del año: propuesta +1,3% en COP con caída máxima −2,3% (núcleo 100%: +5,9% pero −11,1%).", {})]], size=11)
pic(s, IMG + "etapa4_reporte/01_montecarlo_abanico.png", 7.8, 2.0, w=5.1)
text(s, 7.8, 4.75, 5.1, 2.4, [[("Monte Carlo, en simple: ", {"bold": True, "color": RED}),
                               ("armamos 2000 futuros de 36 meses pegando bloques de 10 días reales al azar (conserva rachas y co-movimientos), "
                                "aplicamos la estrategia con el retiro del mes 6 y el rebalanceo, y contamos en cuántos se cumple la promesa.", {})],
                              " ", [("Banda clara: ", {"bold": True}), ("9 de cada 10 futuros. ", {}), ("Línea: ", {"bold": True}), ("el caso típico.", {})]], size=11)

# ---------------- 9. Q5 Riesgos ----------------
s = base("Qué la cambiaría: shocks, supuestos y disparadores", notes="Raf (3:45–4:30). Twist dentro del límite; supuestos explícitos; semáforo de monitoreo.")
qtag(s, 5, "¿Qué riesgo, supuesto o cambio podría modificar la recomendación?")
table(s, 0.45, 2.0, 6.3, [["Shock del twist (17-ago-26)", "Impacto con la propuesta"],
                          ["TW_01 · tasa +65 pb (≈ estrés feb-26)", "−1,1% (S/ −10 723)"],
                          ["TW_01 · peor semana intradía 2020-25", "−6,1% (S/ −61 498) · dentro del límite"],
                          ["TW_02 · retiro 30% en 6 meses", "pagado con la reserva: 0 ventas forzadas"],
                          ["TW_03 · COP −8%", "+2,2% en COP (el núcleo está en USD)"],
                          ["Antes con 28% y TW_01 + TW_03", "cumplía solo 59% → corregido a 20%"]],
      [3.3, 3.0], size=11)
table(s, 7.0, 2.0, 5.85, [["Supuesto / cambio", "Si cambia…"],
                          ["Liquidez rinde 0%", "con tasa > 0 la recomendación mejora"],
                          ["1 año de datos sintéticos, colas ~normales", "colas más gruesas → bajar exposición"],
                          ["“Alta volatilidad” = > 30% anual", "otro umbral → la regla se recalcula sola"],
                          ["Tolerancia de −10% y 36 meses", "más tolerancia o menos plazo → más exposición (6 m: 50%)"],
                          ["Mercado alcista fuerte", "costo de oportunidad: gana menos que 100% acciones"]],
      [2.9, 2.95], size=10.5, header_fill=RED)
card(s, 0.45, 5.0, 12.4, 2.05, "Semáforo de monitoreo propuesto (umbrales a acordar con el cliente)",
     "Verde: caída < 5% → mantener 20%   ·   Ámbar: 5–8% → no rebalancear al alza y revisar   ·   Rojo: > 8% → reducir exposición antes de romper el −10%\n"
     "El Job recalcula volatilidad, curva de exposición y escenarios con cada dato nuevo; la LSTM se reentrena y se reevalúa con el mismo criterio fijado de antemano.",
     NAVY, tsize=15, bsize=12)

# ---------------- 10. IA LSTM ----------------
s = base("IA con criterio: una LSTM para anticipar el riesgo", "Machine learning · etapa 4",
         notes="Fabrizio. Hipótesis y criterio fijados antes de entrenar. Mejora EWMA 24%, pero la histórica le gana y no cambia la decisión → H2 rechazada; la IA validó la regla simple.")
pic(s, IMG + "etapa4_lstm/00_arquitectura_lstm.png", 0.45, 2.0, w=7.6)
table(s, 0.45, 5.15, 7.6, [["Modelo (test fuera de muestra, 952 pronósticos)", "QLIKE ↓", "vs EWMA"],
                           ["Volatilidad histórica (promedio)", "0,053", "+34%"], ["LSTM pre-entrenada", "0,061", "+24%"],
                           ["LSTM solo diario", "0,062", "+22%"], ["EWMA 0,94 (RiskMetrics)", "0,079", "—"]],
      [4.6, 1.4, 1.6], size=10.5, rh=0.33)
card(s, 8.35, 2.0, 4.5, 2.4, "Hipótesis H2 (fijada antes)", "La LSTM pronostica la volatilidad de los próximos 21 días ≥ 10% mejor que EWMA y cambia la decisión de CL_02.", BLUE, bsize=12)
card(s, 8.35, 4.6, 4.5, 2.5, "Veredicto: H2 rechazada", "Supera a EWMA (+24%), pero el promedio histórico le gana y el núcleo y el 20% no cambian. "
     "Se mantiene la regla simple: igual de buena, más explicable. La IA validó la decisión, no la adornó.", RED, bsize=12)

# ---------------- 11. Rigor LSTM ----------------
s = base("Cómo entrenamos la LSTM sin mirar el futuro", "Machine learning · validación",
         notes="Datos: diario 2025-08-04→2026-08-14 (oficial). Intradía 2020-01→2025-08 solo para pre-entrenar. Walk-forward 5 cortes feb–jun 2026, validación = 15% más reciente, hueco de 21 días. MSE en log-vol, QLIKE para decidir, hasta 80 épocas con early stopping 12.")
pic(s, IMG + "etapa4_lstm/05_linea_tiempo_particiones.png", 0.45, 1.95, w=6.6)
pic(s, IMG + "etapa4_lstm/04_brecha_generalizacion.png", 7.25, 1.95, w=5.6)
table(s, 7.25, 4.2, 5.6, [["Elemento", "Valor"], ["Pérdida (entrenar)", "MSE sobre log(vol 21d)"], ["Métrica (decidir)", "QLIKE: castiga subestimar el riesgo"],
                          ["Épocas", "≤ 80 (+25 pre-entrenamiento), early stopping 12"], ["Anti-sobreajuste", "dropout 20%, weight decay, 3 semillas, red de ~2 000 parámetros"],
                          ["Brecha", "test ≈ 1,4× train; aún mejor que EWMA (0,034 vs 0,041)"]],
      [1.7, 3.9], size=10, rh=0.42)
text(s, 0.45, 6.55, 6.6, 0.7, [[("Pre-entrenada: ", {"bold": True, "color": RED}),
                                ("aprende primero la dinámica del riesgo con 5,5 años de intradía (que sí tiene rachas) y luego se ajusta con el diario oficial.", {})]], size=11)

# ---------------- 12. Arquitectura ----------------
s = base("Arquitectura en Databricks: de CSV a decisión", "Solución analítica funcional",
         notes="Cesar. Medallón con Unity Catalog; Job orquestado declarado en el Asset Bundle; MLflow para trazabilidad del modelo; consumo en dashboard y simulador.")
pic(s, IMG + "pitch/04_arquitectura.png", 0.55, 1.95, h=5.35)

# ---------------- 13. Trazabilidad ----------------
s = base("Reproducible y trazable de punta a punta", "Databricks Jobs · Asset Bundles · MLflow · Unity Catalog",
         notes="Cesar/Fabrizio. Mostrar el Job ccg_pipeline_cl02 y el experimento de MLflow si hay tiempo.")
for i, (t, b, f) in enumerate([
        ("Databricks Jobs", "Job ccg_pipeline_cl02 (serverless), 9 tareas con dependencias:\nbronze → silver → validación → gold → calidad → señal → propuesta → Monte Carlo y LSTM.\nLa validación bloquea gold si silver falla.", NAVY),
        ("Asset Bundle (DAB)", "databricks.yml + resources/ccg_pipeline_job.yml: el Job es código en git.\n`databricks bundle deploy -t dev` lo crea igual en cualquier workspace; `bundle run` lo ejecuta.", BLUE),
        ("MLflow", "Experimento por etapa: hiperparámetros, pérdida train/validación por época (run hijo por corte), QLIKE/RMSE, gráficos, particiones y el modelo con firma y ejemplo de entrada.", RED),
        ("Unity Catalog", "credicorp_dq: bronze/silver/gold, comentarios por tabla, linaje automático, gold.etapa4_lstm_* (métricas, predicciones, sobreajuste, particiones, decisión).", RGBColor(0x2E, 0x7D, 0x5B))]):
    card(s, 0.45 + i * 3.15, 2.0, 3.0, 3.85, t, b, f, tsize=15, bsize=11)
text(s, 0.45, 6.05, 12.4, 1.1, [[("Nota honesta: ", {"bold": True, "color": RED}),
                                 ("en Databricks Free Edition el almacenamiento de modelos de Unity Catalog está bloqueado; el modelo queda versionado dentro del run de MLflow "
                                  "y el registro en credicorp_dq.gold.lstm_vol_cl02 ya está en el código para un workspace corporativo.", {})]], size=11.5)

# ---------------- 14. Cierre ----------------
s = base(dark=True, notes="Danilo cierra (4:30–5:00).")
text(s, 0.6, 1.6, 10.5, 2.6, [[("{ ", {"color": RED}), ("No le decimos a CL_02 qué acción va a ganar,", {"color": WHITE})],
                              [("porque los datos no lo permiten.", {"color": WHITE})],
                              [("Le decimos cuánto riesgo puede tomar sin romper su promesa.", {"color": WHITE}), (" }", {"color": BLUE})]],
     size=30, bold=True, spacing=1.15)
for i, (b, sm, f) in enumerate([("20 / 30 / 50", "núcleo · reserva retiro · liquidez", RED), ("95,7%", "cumple −10% a 36 meses", BLUE),
                                 ("7 de 7", "validación sin mirar el futuro", RED), ("S/ 224 mil", "caída típica evitada por S/ 1 M", BLUE)]):
    kpi(s, 0.6 + i * 3.1, 4.75, 2.9, 1.55, b, sm, f)

prs.save("docs/pitch_value_finders_cl02.pptx")
print("ok", len(prs.slides), "láminas")
