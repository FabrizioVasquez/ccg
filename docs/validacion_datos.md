# Validación de confiabilidad del dataset

Generado con `python src/validacion.py` sobre `dataset_start/` (solo lectura). Los datos son crudos y sucios a propósito: casi todo se corrige con reglas simples, pero hay **un problema de fondo** (diario vs expanded) que hay que resolver antes de modelar.

## Veredicto

| Área | Confiable | Nota |
|---|---|---|
| Tablas pequeñas (referencia, clientes, eventos) | Sí | Sin nulos ni duplicados; claves consistentes |
| Macro | Sí, con relleno | Completa y sin saltos raros; la inflación es mensual |
| Fundamentales | Sí, tras limpiar | 5 defectos puntuales, todos corregibles |
| Precios diarios | Sí, tras limpiar | Un precio con error de ×100 y algunos duplicados |
| Precios expanded | Parcial | Misma limpieza, pero **no reconcilia con el diario** desde ago-2025 |

## Hallazgo crítico: diario y expanded no coinciden

- El 2025-08-01 ambos cierran igual (VF_A01 52.0, VF_A02 85.6, VF_A03 36.3, VF_A04 64.0). Después divergen.
- Correlación de retornos diarios entre las dos series: entre -0.09 y 0.11, o sea, casi cero. Mediana de diferencia relativa del cierre: 12%.
- Ejemplo 2026-01-02, VF_A02: diario 131.6 contra expanded 123.8. 2026-08-14, VF_A04: diario 77.1 contra expanded 54.9.
- Los eventos (`06_events.csv`) se notan en el diario (VF_A02 alrededor del 2026-02-10: salto máx. de 6.3% en ±5 días) y casi no en el expanded (3.0%).
- Lectura probable: son dos simulaciones con el mismo punto de partida. El diario (ago-2025 a ago-2026) lleva los eventos; el expanded aporta la historia larga (2020 a 2025).
- **Decisión sugerida:** historia previa a ago-2025 solo viene del expanded (volatilidad, correlaciones, drawdown histórico). El periodo actual y los eventos, del diario. No mezclarlos en una misma serie. Confirmarlo con los organizadores.

## Defectos por archivo

### `01_market_prices_raw.csv` (diario, 2.175 filas)
- 7 duplicados exactos (misma fecha y activo).
- `asset_id` con variantes: `VF-A1`, `VFA03`, `VF_A6` (3 filas) → normalizar a `VF_A0n`.
- Fechas `MM/DD/YYYY` mezcladas con ISO (4 filas).
- `volume` con sufijo K, ej. `3635.6K` (3 filas); 3 volúmenes nulos; 4 `currency` nulos (todo es USD).
- **VF_A06, 2026-03-23: close = 3589.00** cuando open/high/low rondan 35 y el día siguiente cierra 36.19. Es un error de ×100 (debería ser ~35.89) y genera un retorno de +10.336%. Es la única fila con OHLC incoherente.
- Sin precios ≤ 0 ni fines de semana. Tras deduplicar, los 8 activos tienen las 271 fechas del calendario macro.

### `01_market_prices_raw_expanded.csv` (10 min, 538.836 filas)
- 12 duplicados exactos; 16 `asset_id` con variante (`VF-A6`, `VF-A4`, `VF-A1`).
- 38 fechas en `MM/DD/YYYY HH:MM:SS`; 45 volúmenes con sufijo K.
- Nulos: 24 `close`, 30 `volume`, 35 `currency`.
- Sin OHLC incoherente, sin precios ≤ 0 y retorno máximo en 10 min de 3.2% (no hay outliers). Sesión 09:30 a 15:50, sin fines de semana.
- Cada activo tiene ~67.350 barras de 10 min, 2020-01-02 a 2026-08-14.

### `02_macro_raw.csv` (271 días)
- `us_inflation_yoy` tiene 258 nulos de 271: es un dato mensual (13 valores). Rellenar hacia adelante.
- Sin duplicados, sin huecos, sin saltos diarios >3% en FX ni en yield.
- `risk_regime`: Normal 251 días, Stress 10, Recovery 10.
- Rangos: USD/COP 3.944 a 4.199, USD/PEN 3,67 a 3,83, USD/MXN 18,05 a 18,76, USD/CLP 922 a 1.009.

### `03_fundamentals_raw.csv` (65 filas)
- 1 duplicado exacto (ISS_03, 2025-06-30).
- `ISS04` en vez de `ISS_04` (1 fila, 2025-06-30). Sin corregir, ISS_04 queda con 7 trimestres y aparece un emisor fantasma.
- 1 `period_end` con formato `Q4-2024` en vez de fecha.
- 1 ingreso como texto con coma de miles (`1,845.7`).
- 1 `cash_usd_m` nulo (ISS_07, 2025-09-30).
- Sin negativos, EBITDA nunca supera ingresos, utilidad nunca supera EBITDA.
- **ISS_06, 2025-06-30: ingresos 1,845.7** contra ~2.840 en los trimestres vecinos (-35% y luego +55%). Los "dos saltos" son un solo valor erróneo; tratarlo como nulo o interpolar.
- **ISS_02:** su fila `Q4-2024` duplica la de 2024-12-31, así que le falta un trimestre. Tras limpiar queda con 7.
- Tras limpiar: 7 emisores × 8 trimestres más ISS_02 con 7 (2024-09-30 a 2026-06-30).

### Tablas pequeñas
- `04_asset_reference` (8), `05_client_profiles` (3) y `06_events` (5): limpias.
- Todos los `asset_id` de precios existen en la referencia; mercado y moneda coinciden con la referencia; los 5 eventos tienen `scope` válido y caen dentro del rango de precios.
- Universo: 8 sectores y 5 países (Colombia 2, Perú 2, Estados Unidos 2, México 1, Chile 1). CL_03 (≥3 países y ≥3 sectores) es viable.

## Reglas de limpieza propuestas (silver)

1. Leer con `encoding="utf-8-sig"`.
2. Normalizar `asset_id` e `issuer_id` con regex (`VF[-_]?A0?(\d)` → `VF_A0n`, `ISS_?0?(\d)` → `ISS_0n`).
3. Parsear fechas ISO y `MM/DD/YYYY` (el mes va primero).
4. Quitar duplicados exactos.
5. `volume`: convertir sufijo K a ×1000; dejar nulo lo que falte (no imputar).
6. Precio con salto >50% que revierte al día siguiente: marcar y corregir (÷100 en VF_A06, 2026-03-23).
7. `currency` nula → USD (la referencia lo confirma).
8. Macro: forward-fill de la inflación.
9. Fundamentales: `Q4-2024` → 2024-12-31; coma de miles fuera; `cash` nulo sin imputar sin confirmar.
10. Mantener diario y expanded como dos fuentes separadas en silver.

## Riesgos para el modelo

- **Dos series de precios incompatibles** (arriba): elegir cuál alimenta qué.
- **Solo 8 activos y 3 clientes:** cualquier optimización es chica; las restricciones (45% por sector, 25% en alta volatilidad, ≥3 países y sectores) pesan más que el modelo.
- **Un año de diario:** ~270 observaciones por activo; las métricas de riesgo calculadas solo con el diario son ruidosas.
- **Fundamentales trimestrales:** 8 puntos por emisor y sin fecha de publicación; cuidado con el uso de información futura al hacer el cruce con precios.
- **FX:** todos los activos cotizan en USD, pero CL_02 y CL_03 están en COP y PEN.

## Pendientes

1. Confirmar con los organizadores la relación entre diario y expanded.
2. Confirmar el valor real de ingresos de ISS_06 en 2025-06-30 y el trimestre faltante de ISS_02.
3. Confirmar que 2026-03-23 de VF_A06 es un error de ×100 y no un evento real.
