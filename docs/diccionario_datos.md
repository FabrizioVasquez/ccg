# Diccionario de datos: `dataset_start/`

Fuente: lectura directa de los CSV y `docs/validacion_datos.md`. Todos traen BOM (leer con `encoding="utf-8-sig"`), salvo el expanded, que no lo trae. Columnas marcadas "(sin documentar)" no tienen definición oficial; la descripción es lectura de los valores, a confirmar con los organizadores.

## Mapa

| Archivo | Qué es | Filas | Granularidad / clave | Uso |
|---|---|---|---|---|
| `01_market_prices_raw.csv` | OHLCV diario | 2.175 | `date` + `asset_id` | Periodo actual (ago-2025 a ago-2026) y eventos |
| `01_market_prices_raw_expanded.csv` | OHLCV cada 10 min | 538.836 | `date` (con hora) + `asset_id` | Historia larga (2020 a 2026): volatilidad, correlación, drawdown |
| `02_macro_raw.csv` | Macro y FX diario | 271 | `date` | Conversión a COP/PEN, régimen de riesgo |
| `03_fundamentals_raw.csv` | Estados financieros trimestrales | 65 | `issuer_id` + `period_end` | Calidad del emisor |
| `04_asset_reference.csv` | Catálogo de activos | 8 | `asset_id` | Sector y país (restricciones de clientes) |
| `05_client_profiles.csv` | Perfiles de cliente | 3 | `client_id` | Objetivos y restricciones |
| `06_events.csv` | Eventos relevantes | 5 | `event_date` + `scope` | Explicar caídas/saltos |

## Relaciones

```
05_client_profiles  (independiente; se cruza por reglas, no por clave)
04_asset_reference.asset_id  ──  01_market_prices_raw(.expanded).asset_id
04_asset_reference.issuer_id ──  03_fundamentals_raw.issuer_id
06_events.scope = asset_id (VF_A0n)  o  sector (ej. Technology → 04.sector)
02_macro_raw.date ── 01_market_prices_raw.date  (mismo calendario de 271 días)
```

## 01_market_prices_raw.csv (diario)

| Columna | Tipo | Descripción |
|---|---|---|
| `date` | fecha | Día hábil. ISO, con 4 filas `MM/DD/YYYY` |
| `asset_id` | texto | `VF_A01` a `VF_A08`. Hay variantes sucias (`VF-A1`, `VFA03`, `VF_A6`) |
| `market` | texto | Bolsa: `NYSE`, `NYSE ADR`, `NASDAQ` |
| `currency` | texto | Siempre USD; 4 nulos |
| `open`, `high`, `low`, `close` | decimal | Precios en USD |
| `volume` | entero | Acciones negociadas. 3 con sufijo K (`3635.6K`), 3 nulos |

Calidad: 7 duplicados; VF_A06 2026-03-23 `close` = 3589 (error ×100).

## 01_market_prices_raw_expanded.csv (10 min)

Mismas columnas que el diario. `date` incluye hora (`2020-01-02 09:30:00`), sesión 09:30 a 15:50, ~67.350 barras por activo, 2020-01-02 a 2026-08-14.

Calidad: 12 duplicados, 16 `asset_id` con variante, 38 fechas `MM/DD/YYYY HH:MM:SS`, 45 volúmenes con K, nulos en `close` (24), `volume` (30) y `currency` (35).

**No reconcilia con el diario desde ago-2025** (correlación de retornos ~0). Son dos simulaciones con el mismo punto de partida. No mezclar en una serie. Ver `docs/validacion_datos.md`.

## 02_macro_raw.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `date` | fecha | Día hábil (271) |
| `us_10y_yield` | decimal | Rendimiento del bono del Tesoro de EE.UU. a 10 años, en % (ej. 4.353) |
| `us_inflation_yoy` | decimal | Inflación anual de EE.UU., en %. Dato mensual: 258 nulos, forward-fill |
| `usd_cop` | decimal | Pesos colombianos por 1 USD (3.944 a 4.199) |
| `usd_pen` | decimal | Soles por 1 USD (3,67 a 3,83) |
| `usd_mxn` | decimal | Pesos mexicanos por 1 USD (18,05 a 18,76) |
| `usd_clp` | decimal | Pesos chilenos por 1 USD (922 a 1.009) |
| `market_factor` | decimal | Factor de mercado diario, valores del orden de ±0.01 a ±0.02 (sin documentar; parece un retorno diario del mercado) |
| `risk_regime` | texto | `Normal` (251 días), `Stress` (10), `Recovery` (10) (sin documentar la regla) |

Para pasar valores de USD a COP o PEN: multiplicar por `usd_cop` o `usd_pen` del día. `usd_mxn` y `usd_clp` aplican a activos de México y Chile.

## 03_fundamentals_raw.csv

| Columna | Tipo | Descripción |
|---|---|---|
| `issuer_id` | texto | `ISS_01` a `ISS_08`; une con `04.issuer_id`. 1 fila sucia `ISS04` |
| `period_end` | fecha | Cierre del trimestre (2024-09-30 a 2026-06-30). 1 fila con `Q4-2024` |
| `revenue_usd_m` | decimal | Ingresos, millones de USD. 1 valor con coma de miles |
| `ebitda_usd_m` | decimal | EBITDA (utilidad antes de intereses, impuestos, depreciación y amortización), millones de USD |
| `net_income_usd_m` | decimal | Utilidad neta, millones de USD |
| `debt_usd_m` | decimal | Deuda total, millones de USD |
| `cash_usd_m` | decimal | Caja, millones de USD. 1 nulo (ISS_07, 2025-09-30) |

Calidad: 1 duplicado (ISS_03); ISS_06 2025-06-30 con ingresos atípicos (1.845,7 contra ~2.840 en vecinos).

Métricas derivables (no vienen en el archivo): margen EBITDA = ebitda/revenue; margen neto = net_income/revenue; deuda neta = debt − cash; deuda neta/EBITDA.

## 04_asset_reference.csv

| Columna | Descripción |
|---|---|
| `asset_id` | `VF_A01` a `VF_A08` |
| `issuer_id` | Emisor: `ISS_01` a `ISS_08` |
| `name` | Nombre ficticio |
| `sector` | Sector |
| `country` | País |
| `market` | Bolsa |
| `currency` | Moneda de cotización (todo USD) |

| asset_id | issuer | name | sector | country | market |
|---|---|---|---|---|---|
| VF_A01 | ISS_01 | Andes Consumer | Consumer Staples | Colombia | NYSE ADR |
| VF_A02 | ISS_02 | Pacifica Digital | Technology | Peru | NASDAQ |
| VF_A03 | ISS_03 | Cordillera Energy | Energy | Colombia | NYSE ADR |
| VF_A04 | ISS_04 | Lima Financial | Financials | Peru | NYSE ADR |
| VF_A05 | ISS_05 | Aurora Health | Health Care | United States | NYSE |
| VF_A06 | ISS_06 | Norte Industrials | Industrials | Mexico | NYSE ADR |
| VF_A07 | ISS_07 | Sierra Materials | Materials | Chile | NYSE ADR |
| VF_A08 | ISS_08 | Atlas Utilities | Utilities | United States | NYSE |

8 sectores distintos y 5 países: la restricción de CL_01 (45% por sector) exige al menos 3 activos de sectores distintos. Cada sector tiene un solo activo.

## 05_client_profiles.csv

| Columna | Descripción |
|---|---|
| `client_id` | `CL_01` a `CL_03` |
| `profile_name` | Nombre del perfil |
| `base_currency` | Moneda en que se mide el resultado: USD, COP, PEN |
| `horizon_months` | Plazo previsto de la inversión (18, 36, 24) |
| `risk_tolerance` | Alta, Media-Baja, Media |
| `max_drawdown_tolerance_pct` | Caída máxima pico a valle aceptada (22, 10, 15) |
| `liquidity_need` | Baja, Media, Media |
| `priority` | Objetivo principal |
| `constraint` | Restricción dura, en texto libre (hay que convertirla a regla en código) |

## 06_events.csv

| Columna | Descripción |
|---|---|
| `event_date` | Fecha del evento (2026-02-10 a 2026-07-21) |
| `scope` | A qué afecta: un `asset_id` o un sector (`Technology`) |
| `event_type` | `Operational`, `Commodity`, `Earnings`, `Demand`, `Sector` |
| `headline` | Titular en texto |
| `severity` | `High` o `Medium` |

| Fecha | Scope | Tipo | Titular | Severidad |
|---|---|---|---|---|
| 2026-02-10 | VF_A02 | Operational | Interrupción de proveedor crítico de nube | High |
| 2026-04-06 | VF_A03 | Commodity | Mejora abrupta en margen de referencia energético | Medium |
| 2026-05-18 | VF_A04 | Earnings | Resultados superan expectativas | Medium |
| 2026-06-08 | VF_A07 | Demand | Debilidad inesperada en demanda externa | High |
| 2026-07-21 | Technology | Sector | Repricing de múltiplos en compañías de crecimiento | Medium |

Solo se ven en el diario. El último evento tiene scope de sector, no de activo: mapearlo con `04.sector`.
