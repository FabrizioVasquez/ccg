# ccg: Credicorp Capital - Value Finders

Hackathon presencial de Credicorp Capital (31 oct 2026, 8:00 a 14:00, Lima). Reto de 6 horas con defensa ante un panel.

**Pregunta guía:** ¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?

## Entregables

1. MVP con Python + SQL en Databricks
2. Decision Dashboard de una vista: ¿qué está ocurriendo?, ¿qué datos o señales lo explican?, ¿qué significa para el cliente elegido?, ¿qué debería hacer?, ¿qué riesgo, supuesto o cambio podría modificar la recomendación?
3. Value Pitch: presentación y demo ante el jurado

## Clientes

| Cliente | Perfil | Moneda | Drawdown máx. | Restricción |
|---|---|---|---|---|
| CL_01 | Crecimiento Global | USD | 22% | Máx. 45% en un solo sector |
| CL_02 | Patrimonio Estable | COP | 10% | Máx. 25% en activos de alta volatilidad |
| CL_03 | Diversificación Regional | PEN | 15% | Al menos 3 países y 3 sectores |

## Datos (`dataset_start/`)

> No se versiona (repo público, ver `.gitignore`). Cada quien la copia en local y la fuente compartida es el Volume de Databricks.

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

- [`docs/00_contexto_negocio.md`](docs/00_contexto_negocio.md): rama de negocio (Wealth Management), método por ciclos y decisiones tomadas
- [`docs/etapa3_propuesta.md`](docs/etapa3_propuesta.md): **propuesta final para CL_02** (núcleo 28% + liquidez COP), métricas defendibles, walk-forward y valor en S/
- [`docs/etapa2_resumen.md`](docs/etapa2_resumen.md), [`docs/etapa2_guia_junior.md`](docs/etapa2_guia_junior.md) y [`docs/etapa2_reporte_cientifico_datos.md`](docs/etapa2_reporte_cientifico_datos.md): etapa 2 (foco CL_02, señal, limpieza, robustez y twist)
- [`docs/brief.md`](docs/brief.md): brief oficial completo del evento (23 páginas)
- [`docs/data_mesh_architecture.md`](docs/data_mesh_architecture.md): arquitectura data mesh de 2 dominios
- [`.claude/`](.claude/): skills y agentes del equipo (selección de [ECC](https://github.com/affaan-m/ECC), MIT, más `data-scientist`)
- [`REQUERIMIENTOS.md`](REQUERIMIENTOS.md): requisitos del reto y pendientes
- [`ANALISIS.md`](ANALISIS.md): análisis inicial de los datos y propuesta de ramas

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
