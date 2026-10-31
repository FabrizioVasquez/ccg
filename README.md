# ccg: Credicorp Capital - Value Finders

Hackathon presencial de Credicorp Capital (31 oct 2026, 8:00 a 14:00, Lima). Reto de 6 horas con defensa ante un panel.

**Pregunta guía:** ¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?

## Entregables

1. MVP con Python + SQL en Databricks
2. Decision Dashboard (responde 5 preguntas, aún por conocer)
3. Value Pitch: presentación y demo ante el jurado

## Clientes

| Cliente | Perfil | Moneda | Drawdown máx. | Restricción |
|---|---|---|---|---|
| CL_01 | Crecimiento Global | USD | 22% | Máx. 45% en un solo sector |
| CL_02 | Patrimonio Estable | COP | 10% | Máx. 25% en activos de alta volatilidad |
| CL_03 | Diversificación Regional | PEN | 15% | Al menos 3 países y 3 sectores |

## Datos (`dataset_start/`)

| Archivo | Contenido |
|---|---|
| `01_market_prices_raw.csv` | OHLCV diario, 8 activos |
| `01_market_prices_raw_expanded.csv` | OHLCV cada 10 min desde 2020 (~539k filas) |
| `02_macro_raw.csv` | Yield, inflación, FX (COP, PEN, MXN, CLP), régimen de riesgo |
| `03_fundamentals_raw.csv` | Fundamentales trimestrales por emisor |
| `04_asset_reference.csv` | Referencia de activos: sector, país, mercado |
| `05_client_profiles.csv` | Perfiles y restricciones de los 3 clientes |
| `06_events.csv` | Eventos por activo o sector |

## Documentación

- [`REQUERIMIENTOS.md`](REQUERIMIENTOS.md): requisitos del reto y pendientes
- [`ANALISIS.md`](ANALISIS.md): análisis inicial de los datos y propuesta de ramas
- Notas completas en Obsidian: `hackathon/Credicorp Capital - Value Finders/`

## Ramas

`main` se mantiene estable. Cada línea de trabajo va en su propia rama `feat/*`:

| Rama | Foco |
|---|---|
| `feat/ingesta-calidad` | Carga a bronze, limpieza y reglas de calidad |
| `feat/modelo-datos` | Capas bronze, silver y gold |
| `feat/features-riesgo` | Retorno, volatilidad, drawdown, correlaciones |
| `feat/fundamentales-eventos` | Ratios y marca de eventos |
| `feat/motor-recomendacion` | Score por perfil y cartera con restricciones |
| `feat/dashboard` | Decision Dashboard |
| `feat/pitch-demo` | Guion, evidencia y demo |

## Stack

Python, SQL, Databricks (Azure es un plus).
