"""Diagramas para la sustentación de la LSTM: arquitectura y línea de tiempo de datos/particiones.
Uso: .venv/bin/python src/analysis/etapa4_lstm_diagramas.py → docs/img/etapa4_lstm/"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import pandas as pd

OUT = "docs/img/etapa4_lstm/"
plt.rcParams.update({"font.size": 10, "figure.dpi": 130})

# ---------- 1. Arquitectura ----------
fig, ax = plt.subplots(figsize=(13, 4.6)); ax.set_xlim(0, 13); ax.set_ylim(0, 4.6); ax.axis("off")
def box(x, y, w, h, title, body, c):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.12", fc=c, ec="#333", lw=1.2))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top", fontsize=10.5, weight="bold")
    ax.text(x + w / 2, y + h - 0.75, body, ha="center", va="top", fontsize=8.6, linespacing=1.45)
def arrow(x1, x2, y=2.2):
    ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#333"))
box(0.1, 0.5, 2.9, 3.5, "1. Entrada", "Últimos 21 días hábiles\nde UN activo (en COP)\n\npor día, 13 datos:\n• retorno r y |r|\n• vol 5d, 21d, 63d\n• activo (8 columnas 0/1)\n\nforma: 21 × 13", "#DCE9F5")
arrow(3.05, 3.55)
box(3.6, 0.5, 2.9, 3.5, "2. Capa LSTM", "16 neuronas con memoria\n\nlee los 21 días en orden\ny decide qué recordar\n(compuertas: olvido,\nentrada y salida)\n\n≈ 2 000 parámetros", "#FBE3D6")
arrow(6.55, 7.05)
box(7.1, 0.5, 2.3, 3.5, "3. Dropout 20%", "apaga al azar 20%\nde las neuronas al\nentrenar\n\n→ evita que\nmemorice", "#EEE")
arrow(9.45, 9.95)
box(10.0, 0.5, 2.9, 3.5, "4. Salida", "1 número:\nlog(volatilidad anual\nde los próximos\n21 días)\n\nse compara con lo que\nrealmente pasó\n(error: MSE)", "#E3F1E0")
ax.text(6.5, 4.45, "LSTM que pronostica el riesgo del mes siguiente de cada activo", ha="center", fontsize=12, weight="bold")
ax.text(6.5, 0.15, "Entrenamiento: Adam (lr 0,002), lotes de 64, hasta 80 épocas con early stopping (paciencia 12) · ensamble de 3 semillas · "
        "variante pre-entrenada: 25 épocas sobre el intradía 2020-25 y luego ajuste fino con lr 0,0005", ha="center", fontsize=8.2, color="#444")
fig.savefig(OUT + "00_arquitectura_lstm.png", bbox_inches="tight"); plt.close(fig)

# ---------- 2. Línea de tiempo de datos ----------
T = pd.Timestamp
fig, (a0, a1) = plt.subplots(2, 1, figsize=(13, 6.2), gridspec_kw={"height_ratios": [1, 2.6]})
# panel superior: fuentes completas
a0.barh(1, (T("2025-08-01") - T("2020-01-02")).days, left=T("2020-01-02"), color="#B279A2", height=.5)
a0.text(T("2022-10-01"), 0.55, "Intradía 2020-01-02 → 2025-08-01 (1455 días, en USD) · solo pre-entrenamiento", ha="center", va="top", color="#B279A2", fontsize=9, weight="bold")
a0.barh(0, (T("2026-08-14") - T("2025-08-04")).days, left=T("2025-08-04"), color="#4C78A8", height=.5)
a0.text(T("2025-06-01"), 0, "Diario 2025-08-04 → 2026-08-14 (270 días, en COP) · fuente oficial: train, validación y test  ", ha="right", va="center", fontsize=9, color="#4C78A8", weight="bold")
a0.barh(0, (T("2026-08-14") - T("2025-08-04")).days, left=T("2025-08-04"), color="#4C78A8", height=.5)
a0.axvline(T("2026-08-17"), color="#E45756", ls="--"); a0.text(T("2026-08-17"), 1.45, " twist (17-ago-26)", color="#E45756", fontsize=8.5)
a0.set_yticks([0, 1]); a0.set_yticklabels(["Diario", "Intradía"]); a0.set_ylim(-0.6, 1.7)
a0.xaxis.set_major_locator(mdates.YearLocator()); a0.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
a0.set_title("¿De dónde a dónde van los datos?", loc="left", weight="bold")
for s in ["top", "right"]: a0.spines[s].set_visible(False)
# panel inferior: walk-forward
cuts = [("1-feb", "2025-09-29", "2025-12-18", "2026-01-01", "2026-02-02", "2026-02-27", "2026-03-30"),
        ("1-mar", "2025-09-29", "2026-01-12", "2026-01-29", "2026-03-02", "2026-03-31", "2026-04-29"),
        ("1-abr", "2025-09-29", "2026-02-06", "2026-03-02", "2026-04-01", "2026-04-30", "2026-05-29"),
        ("1-may", "2025-09-29", "2026-03-05", "2026-04-01", "2026-05-01", "2026-05-29", "2026-06-29"),
        ("1-jun", "2025-09-29", "2026-03-30", "2026-04-30", "2026-06-01", "2026-07-16", "2026-08-14")]
for i, (n, t0, t1, v1, s0, s1, e1) in enumerate(cuts):
    y = len(cuts) - i
    a1.barh(y, (T(t0) - T("2025-08-04")).days, left=T("2025-08-04"), color="#DDD", height=.55, label="calentamiento (vol mín. 21d + secuencia 21d)" if i == 0 else None)
    a1.barh(y, (T(t1) - T(t0)).days, left=T(t0), color="#4C78A8", height=.55, label="entrenamiento" if i == 0 else None)
    a1.barh(y, (T(v1) - T(t1)).days, left=T(t1), color="#F58518", height=.55, label="validación (early stopping)" if i == 0 else None)
    a1.barh(y, (T(s1) - T(s0)).days, left=T(s0), color="#E45756", height=.55, label="test (origen del pronóstico)" if i == 0 else None)
    a1.barh(y, (T(e1) - T(s1)).days, left=T(s1), color="#E45756", alpha=.3, height=.55, label="días que el test pronostica" if i == 0 else None)
    a1.axvline(T(f"2026-{['02','03','04','05','06'][i]}-01"), ymin=0, ymax=1, color="#999", lw=.6, ls=":")
a1.set_yticks(range(1, 6)); a1.set_yticklabels([f"corte {c[0]}" for c in cuts][::-1])
a1.xaxis.set_major_locator(mdates.MonthLocator()); a1.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))
a1.set_xlim(T("2025-08-01"), T("2026-08-20")); a1.legend(loc="upper left", fontsize=8, ncol=2, framealpha=.95)
a1.set_ylim(.4, 7.3)
a1.set_title("Walk-forward: 5 exámenes, cada uno solo con el pasado (el hueco antes del corte evita que el objetivo de 21 días \"vea\" el test)", loc="left", weight="bold", fontsize=10)
for s in ["top", "right"]: a1.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(OUT + "05_linea_tiempo_particiones.png", bbox_inches="tight"); plt.close(fig)
print("ok")
