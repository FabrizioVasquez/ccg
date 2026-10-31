# Requerimientos del reto: Credicorp Capital - Value Finders

> Fuente: resumen de las diapositivas del evento, pegado por el usuario. Es un índice de secciones: el detalle de cada una (columnas de los datos, las 5 preguntas del dashboard, criterios de evaluación) **no está en esta fuente**. No inventar; pedirlo al usuario o revisar el material oficial.

## Notas de la fuente

- Las fotos "9.00.16 AM" y "9.00.16 AM (1)" son la misma diapositiva.
- En dos diapositivas una persona tapaba parte del texto: la descripción de **Asset Reference** y la nota al pie de **Qué recibirán**. Lo deducido iba entre corchetes en la fuente original. Conviene verificar esas dos partes con el material oficial.

## 1. Contexto de negocio

Credicorp Capital acompaña decisiones de patrimonio e inversiones.

## 2. Pregunta guía

> ¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?

## 3. Perfiles de cliente

| Perfil | Orientación |
|---|---|
| 01 | Orientado al crecimiento |
| 02 | Busca preservar su patrimonio |
| 03 | Busca diversificación regional |

## 4. Qué recibirán

Dataset sintético con:

- más de 500 000 registros de mercado
- 271 observaciones de contexto macro
- 65 registros financieros

## 5. Organización de los datos

Seis grupos de datos. Archivos en `dataset_start/`:

| Grupo | Archivo |
|---|---|
| Market Raw | `01_market_prices_raw.csv`, `01_market_prices_raw_expanded.csv` |
| Macro Raw | `02_macro_raw.csv` |
| Fundamentals Raw | `03_fundamentals_raw.csv` |
| Asset Reference | `04_asset_reference.csv` |
| Client Profiles | `05_client_profiles.csv` |
| Events | `06_events.csv` |

(La fuente describe el contenido de cada grupo, pero ese detalle no se pegó. Ver las cabeceras de los CSV cuando tengan datos.)

## 6. Qué deben entregar

1. **MVP** con Python + SQL en Databricks.
2. **Decision Dashboard.**
3. **Value Pitch:** presentación y demo ante el jurado.

## 7. Preguntas que debe responder el dashboard

Resuelto con el brief completo ([`docs/brief.md`](docs/brief.md), p.18). Es una vista principal que responde:

1. ¿Qué está ocurriendo?
2. ¿Qué datos o señales lo explican?
3. ¿Qué significa para el cliente elegido?
4. ¿Qué debería hacer?
5. ¿Qué riesgo, supuesto o cambio podría modificar la recomendación?

## 8. Notas de sala

La fuente incluye notas de sala ordenadas por tema: evaluación, arquitectura y gobernanza, y habilidades. **Pendiente: no se pegó el contenido.**

## Contexto adicional

- Evento: 31 oct 2026, 8:00 a 14:00, Centro Empresarial Cronos, Lima. Reto de 6 horas y defensa ante panel.
- Stack esperado: Python, SQL, Databricks; Azure es un plus.
- Se evalúa: entrar al problema y explorar, explorar datos y construir solución, traducir hallazgos en una decisión de valor, y defender ante el panel.
