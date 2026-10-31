# Requerimientos del reto: Credicorp Capital - Value Finders

> Fuente: PDF oficial del reto (resumen pegado por el usuario) más un resumen previo de las diapositivas. Los tiempos están en [`TIEMPOS.md`](TIEMPOS.md).

## 1. Caso y rol

Somos el equipo de Data & Analytics de una compañía de inversiones que asesora a clientes sobre su patrimonio. Credicorp Capital acompaña decisiones de patrimonio e inversiones.

## 2. Pregunta guía

> ¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?

## 3. Perfiles de cliente

| Perfil | Orientación |
|---|---|
| 01 | Orientado al crecimiento |
| 02 | Enfocado en la preservación patrimonial |
| 03 | Busca diversificación regional |

## 4. Insumos (Data Pack)

Dataset sintético basado en estructuras financieras reales:

- más de 500 000 registros de mercado
- 271 observaciones de contexto macro
- 65 registros financieros

| Grupo | Contenido | Archivo |
|---|---|---|
| 01 Market Raw | Precios, volúmenes, mercado, moneda y activos | `01_market_prices_raw.csv`, `01_market_prices_raw_expanded.csv` |
| 02 Macro Raw | Tasa 10Y, inflación, FX y régimen de mercado | `02_macro_raw.csv` |
| 03 Fundamentals Raw | Revenue, EBITDA, utilidad, deuda y caja | `03_fundamentals_raw.csv` |
| 04 Asset Reference | Referencia de activos, emisores, sectores y países | `04_asset_reference.csv` |
| 05 Client Profiles | Perfiles de cliente y sus necesidades | `05_client_profiles.csv` |
| 06 Events | Eventos que pueden explicar movimientos o cambios | `06_events.csv` |

## 5. Entregables

1. **Solución analítica funcional:** MVP ejecutable o reproducible con **Python + SQL usando Databricks** (notebook, pipeline, modelo, scoring, etc.).
2. **Decision Dashboard:** vista ejecutiva principal (*one main view*) que responda:
   - qué ocurre
   - las señales
   - el impacto en el cliente
   - la recomendación
   - los riesgos o supuestos
3. **Value Pitch:** presentación y defensa de la decisión frente al jurado.

## 6. Reglas técnicas y herramientas

- Laptop propia.
- Requerido: **Python + SQL + Databricks**.
- Permitido: Databricks, Power BI u otras visualizaciones, notebooks, librerías open source, APIs, modelos de machine learning y **herramientas generativas / asistentes de IA**.

## 7. Dinámica

6 horas en total, en 4 bloques más el pitch (8 min por equipo). Detalle y estado en [`TIEMPOS.md`](TIEMPOS.md).

## Pendientes

- Nota al pie de "Qué recibirán" y descripción de Asset Reference: una persona tapaba parte del texto en las diapositivas; verificar con el material oficial.
- Notas de sala (evaluación, arquitectura y gobernanza, habilidades): no se pegó el contenido.
- Criterios de evaluación del jurado: no figuran en el resumen.
