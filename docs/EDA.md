# EDA: calidad y exploración en soles (PEN)

Reproducible con [`notebooks/EDA.ipynb`](../notebooks/EDA.ipynb) (parte A: calidad; parte B: exploración en PEN). Reglas de limpieza alineadas con `databricks/02_silver.py`. Periodo: 2025-08-01 a 2026-08-14 (271 días hábiles, 8 activos).

## Tipo de cambio: qué usamos y por qué

Credicorp usa el sol como moneda funcional desde 2014 y convierte con el **tipo de cambio de cierre publicado por la SBS**: los saldos al cierre del periodo y los flujos al cierre de cada mes ([reexpresión 2009-2013 de Credicorp](https://credicorp.gcs-web.com/node/9756)). El BCRP difunde esa misma serie (compra, venta y promedio).

En el dataset, `usd_pen` de `02_macro_raw.csv` hace de TC de cierre:

| Dato | Regla |
|---|---|
| Precios (saldo de la posición) | `close_pen = close_usd × usd_pen` del mismo día. Si falta el TC, se usa el último publicado (no faltó ningún día). |
| Fundamentales | TC del cierre de trimestre. Solo hay TC desde 2025-08-01, así que solo se convierten 4 trimestres por emisor (2025-09-30 a 2026-06-30). Los ratios no dependen de la moneda. |
| Expanded intradía (2020-2026) | Solo se puede convertir desde 2025-08-01, porque antes no hay TC. Además no coincide con el diario (ver la sección A10 del notebook). |

## 1. Calidad

Diagnóstico completo, con totales y porcentajes (nulos, registros y duplicados por ID, cuánto se salva): parte A del notebook. Se aprovecha el 99,99% (541.319 de 541.363 registros).

| Dataset | Chequeo | Casos |
|---|---|---|
| Precios | Alias de `asset_id` | 3 |
| Precios | Fechas `MM/DD/YYYY` | 4 |
| Precios | Duplicados (date, asset_id) | 7 |
| Precios | Close outlier (VF_A06, 3.589: error de escala ×100 → 35,89) | 1 |
| Precios | Volumen con sufijo K (diario / intradía) | 3 / 45 |
| Precios | Volumen como texto `N/A` (diario / intradía) | 3 / 30 |
| Precios | `currency` / `volume` vacíos | 4 / 3 |
| Macro | `us_inflation_yoy` vacía (mensual) | 258 |
| Fundamentales | Alias, `Q4-2024`, texto con coma, cash vacío, duplicado, revenue outlier | 1 c/u |

El diccionario dice que el diario termina el 2026-07-21; en realidad llega al 2026-08-14.

## 2. Tipo de cambio USD/PEN

- Pasó de 3,7233 a 3,6802 (−1,2%): **el sol se apreció**. Rango de 3,667 a 3,827, con el pico en sep-2025.
- Volatilidad anual del 2,8% y peor día −0,50%. Es muy estable comparado con las acciones (15–45%).
- Todos los activos rinden entre 0,9 y 1,5 pp menos en PEN que en USD. **El FX resta, pero no decide.**

## 3. Activos en PEN

| Activo | Sector / País | Ret. PEN | Ret. USD | Vol. | Max DD | Últ. 60d |
|---|---|---|---|---|---|---|
| VF_A05 | Health Care / EE. UU. | **+30,4%** | +31,9% | 24,4% | −15,0% | +8,6% |
| VF_A04 | Financials / Perú | **+19,1%** | +20,5% | 28,4% | −16,6% | −4,9% |
| VF_A01 | Consumer Staples / Colombia | −11,1% | −10,0% | 20,1% | −29,0% | −16,1% |
| VF_A02 | Technology / Perú | −14,8% | −13,8% | 44,8% | −56,2% | −7,5% |
| VF_A08 | Utilities / EE. UU. | −15,2% | −14,2% | 15,5% | −21,8% | −2,2% |
| VF_A06 | Industrials / México | −23,3% | −22,4% | 33,5% | −38,2% | −2,9% |
| VF_A03 | Energy / Colombia | −27,3% | −26,5% | 35,2% | −44,1% | −12,5% |
| VF_A07 | Materials / Chile | −27,5% | −26,7% | 38,6% | −38,7% | −25,8% |

- Solo 2 de 8 activos ganan. La cartera equiponderada en PEN cierra en −7,2%, con volatilidad del 16,0% y **max DD de −21,3%**: solo cabe en la tolerancia de CL_01 (22%).
- VF_A02 subió cerca de +80% hasta nov-2025 y después lo perdió todo: es el activo con el mayor drawdown (−56%).
- Activos de alta volatilidad (más de 30% anual, supuesto): VF_A02, VF_A03, VF_A06 y VF_A07.

## 4. Distribución de retornos

- Colas casi normales: curtosis en exceso entre −0,5 y 0,2 y asimetría cercana a 0. No hay colas gordas, así que la volatilidad sirve como medida de riesgo.
- Días con caída mayor a 3%: VF_A02 tiene 36, VF_A03 27 y VF_A07 24; VF_A08 no tiene ninguno. El peor día fue −9,0% (VF_A02, 2026-06-10).

## 5. Correlaciones

- Son bajas: de 0,0 a 0,27, con media de 0,12 a 0,21. Diversificar entre estos activos reduce bastante el riesgo.
- Beta contra `market_factor`: VF_A02 (1,47) es el más agresivo; VF_A08 (0,35) y VF_A01 (0,43) son los más defensivos.

## 6. Regímenes de riesgo

10 días de Stress (09–20 feb 2026) y 10 de Recovery (02–13 mar 2026).

| Activo | Stress | Recovery |
|---|---|---|
| VF_A02 | −24,0% | +9,9% |
| VF_A06 | −10,8% | −0,3% |
| VF_A04 | −10,5% | +0,1% |
| VF_A07 | −7,4% | +7,2% |
| VF_A08 | −5,1% | +0,3% |
| VF_A05 | −1,4% | +1,3% |
| VF_A03 | −1,0% | −2,1% |
| VF_A01 | **+2,9%** | +1,7% |

- VF_A01 es el único activo que sube en el estrés y VF_A05 casi no cae: son los refugios.
- VF_A04 cae −10,5% y no se recupera en la ventana de Recovery. Es el riesgo principal del segundo mejor activo.

## 7. Eventos (retorno anormal frente a la cartera equiponderada, en PEN)

| Fecha | Activo | Evento | Antes (−5 a −1 días) | Después (0 a +5 días) |
|---|---|---|---|---|
| 2026-02-10 | VF_A02 | Caída de proveedor de nube (High) | +8,0% | **−15,8%** |
| 2026-04-06 | VF_A03 | Mejora de margen energético | −4,1% | +3,5% |
| 2026-05-18 | VF_A04 | Resultados sobre lo esperado | +7,5% | −2,3% |
| 2026-06-08 | VF_A07 | Debilidad de demanda (High) | −4,7% | **−8,4%** |
| 2026-07-21 | Technology (VF_A02) | Repricing de múltiplos | −8,4% | −3,4% |

- Los eventos de severidad High mueven el precio en la dirección esperada.
- El buen resultado de VF_A04 ya estaba en el precio antes del anuncio (+7,5% previo): una posible señal de anticipación.

## 8. Fundamentales (último trimestre, 2026-06-30)

| Emisor | Crec. revenue a/a | Margen neto | Margen EBITDA | Deuda neta/EBITDA | Revenue trimestral (S/ m) |
|---|---|---|---|---|---|
| ISS_04 (VF_A04) | 10,0% | 20% | 30% | 0,29 | 17.225 |
| ISS_05 (VF_A05) | 9,1% | 20% | 28% | 0,29 | 7.936 |
| ISS_02 (VF_A02) | 10,0% | 14% | 27% | 0,23 | 11.894 |
| ISS_07 (VF_A07) | 8,7% | 13% | 21% | 0,12 | 20.162 |
| ISS_01 (VF_A01) | 6,8% | 22% | 33% | 0,26 | 8.231 |
| ISS_06 (VF_A06) | s/d (outlier hace 1 año) | 8% | 16% | **0,62** | 11.469 |
| ISS_03 (VF_A03) | 4,7% | 7% | 12% | 0,01 | 12.545 |
| ISS_08 (VF_A08) | 3,7% | 8% | 12% | −0,25 (caja neta) | 7.704 |

- Todos los emisores tienen poca deuda. El más apalancado es ISS_06.
- VF_A04 y VF_A05 combinan buen precio con buenos fundamentales. VF_A02 tiene fundamentales sanos y aun así su precio cayó: lo explican los eventos y el repricing del sector, no el negocio.

## Conclusiones para la recomendación

1. Medir en soles no cambia el ranking de activos; el FX resta alrededor de 1 pp a cada uno.
2. Solo VF_A05 y VF_A04 generan valor. VF_A01 y VF_A08 aportan defensa (beta baja y buen comportamiento en el estrés), no rentabilidad.
3. Repartir en partes iguales (DD −21,3%) rompe los límites de CL_02 (10%) y CL_03 (15%). Lo que hay que decidir es cuánto exponer al cliente, además de qué comprar.
