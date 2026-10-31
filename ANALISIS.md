# Análisis inicial del dataset y propuesta de ramas

Análisis superficial: solo cabeceras y primeras filas de `dataset_start/`. No hay validación profunda de datos.

## Qué hay

| Archivo | Contenido |
|---|---|
| `01_market_prices_raw.csv` | OHLCV diario de 8 activos (`VF_A01` a `VF_A08`), desde ago-2025 (~2.2k filas) |
| `01_market_prices_raw_expanded.csv` | OHLCV cada 10 min desde 2020 (~539k filas, 37 MB) |
| `02_macro_raw.csv` | 271 días: yield a 10 años, inflación, USD/COP, USD/PEN, USD/MXN, USD/CLP, `market_factor`, `risk_regime` |
| `03_fundamentals_raw.csv` | 8 emisores, datos trimestrales: ingresos, EBITDA, utilidad neta, deuda, caja (65 filas) |
| `04_asset_reference.csv` | 8 activos con emisor, sector, país, mercado y moneda |
| `05_client_profiles.csv` | 3 clientes con moneda base, horizonte, tolerancia, drawdown máximo, liquidez, prioridad y restricción |
| `06_events.csv` | 5 eventos, por activo o por sector, con severidad |

Relaciones: `asset_id` une mercado y referencia; `issuer_id` une referencia y fundamentales; `scope` de eventos es un `asset_id` o un sector; `date` une mercado y macro.

## Clientes y restricciones

| Cliente | Perfil | Moneda | Horizonte | Drawdown máx. | Restricción |
|---|---|---|---|---|---|
| CL_01 | Crecimiento Global | USD | 18 m | 22% | Máx. 45% en un solo sector |
| CL_02 | Patrimonio Estable | COP | 36 m | 10% | Máx. 25% en activos de alta volatilidad |
| CL_03 | Diversificación Regional | PEN | 24 m | 15% | Al menos 3 países y 3 sectores |

Las restricciones son reglas duras y se pueden codificar directo en el motor de recomendación.

## Cosas visibles de calidad

- Las cabeceras de casi todos los CSV tienen BOM.
- `date` es solo fecha en el archivo diario, pero trae hora en el expanded.
- `us_inflation_yoy` viene vacío en varios días (probablemente dato mensual).
- Todos los activos cotizan en USD, pero CL_02 y CL_03 están en COP y PEN: hace falta un paso de FX con el macro.
- Por confirmar: que el diario y el expanded coincidan entre sí, y su cobertura de fechas (el diario parte en ago-2025, el expanded en 2020).

## Ramas propuestas

| Rama | Qué hace |
|---|---|
| `feat/ingesta-calidad` | Cargar a bronze, quitar BOM, unificar fechas, forward-fill del macro, comparar diario contra expanded |
| `feat/modelo-datos` | Capas bronze, silver y gold: hecho de precios diarios con dimensiones de activo, cliente, macro y eventos |
| `feat/features-riesgo` | Retorno, volatilidad, drawdown, correlaciones e impacto de eventos, desde el expanded |
| `feat/fundamentales-eventos` | Ratios (deuda/EBITDA, margen) y marca de evento por activo y fecha |
| `feat/motor-recomendacion` | Puntuar activos por perfil y armar una cartera que respete las restricciones, con FX |
| `feat/dashboard` | Decision Dashboard (faltan las 5 preguntas) |
| `feat/pitch-demo` | Guion, evidencia y demo |

Orden crítico: `ingesta-calidad`, `modelo-datos` y `features-riesgo`. Luego `fundamentales-eventos` y `motor-recomendacion` en paralelo. `pitch-demo` corre durante todo el proceso.

## Foco elegido: CL_02 (preservación patrimonial)

Decisión del bloque 2. Detalle en [`docs/encuadre_problema.md`](docs/encuadre_problema.md); cifras con `python src/senales.py`.

- **Por qué CL_02:** su restricción de riesgo es la que manda. Ningún activo solo cumple la caída máxima de 10%, la cartera equiponderada cae 17.2% y solo 58 de 60 000 carteras probadas cumplen todo.
- **Señales:** solo A05 (+31.9%) y A04 (+20.5%) suben en el año. A01 y A08 son defensivos (baja volatilidad y beta) con fundamentales que mejoran. Los eventos explican las peores caídas (A02, A07). Las correlaciones son bajas (0 a 0.26). El USD/COP sube 2.56%, a favor del cliente.
- **Hipótesis de decisión:** núcleo defensivo (A05, A01, A08) más A04, con ≤25% en alta volatilidad y pesos de menor caída. Referencia: +11.5% en COP con caída de -9.5%.
- **Riesgos:** ajuste dentro de la misma muestra, solución frágil, concentración en A05, reversión del tipo de cambio, y 1 año de datos para un horizonte de 36 meses.

## Pendientes

1. Asignar una rama por persona si trabajan varios.
2. Validar la cartera fuera de muestra (bloque 3).
