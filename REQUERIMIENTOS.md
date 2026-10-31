# Requerimientos del reto: Credicorp Capital - Value Finders

> Fuente: PDF oficial del evento (`Evento Value Finders - Versión final Copia.pdf`, 23 páginas), que está en la raíz del repo. Los tiempos están en [`TIEMPOS.md`](TIEMPOS.md).

## 1. Objetivo del evento

Credicorp Capital quiere ver cómo piensa el equipo frente a información compleja, qué dirección encuentra en los datos y hasta dónde lleva ese hallazgo. Lema del PDF:

> Buscamos una idea que puedas explicar. Una decisión que puedas defender.

Lo que se espera: encontrar una señal relevante y llevarla a una decisión que genere valor.

## 2. Caso y rol

Somos un equipo de Data & Analytics de una compañía de inversiones. El equipo asesora a clientes que deben decidir qué hacer con su patrimonio. Se recibe información de mercado, compañías y contexto económico para llegar a una recomendación sustentada en datos.

Contexto de negocio: Credicorp Capital acompaña decisiones de patrimonio e inversiones. Una misma compañía puede presentarse como alternativa de inversión en distintos mercados e instrumentos, y su desempeño puede responder al contexto de mercado y a variables propias de la compañía. **Los conceptos financieros necesarios estarán incluidos en el material inicial.**

## 3. Pregunta guía

> ¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?

## 4. Perfiles de cliente

| Cliente | Orientación |
|---|---|
| 01 | Orientado al crecimiento |
| 02 | Enfocado en la preservación patrimonial |
| 03 | Busca diversificación regional |

Los perfiles detallados (moneda, horizonte, restricciones) están en `dataset_start/05_client_profiles.csv`.

## 5. Insumos (Data Pack)

Dataset sintético basado en estructuras financieras reales: más de 500 000 registros de mercado, 271 observaciones de contexto macro y 65 registros financieros. El material incluye tablas de referencia, eventos y perfiles de cliente.

| Grupo | Contenido | Archivo |
|---|---|---|
| 01 Market Raw | Precios, volúmenes, mercado, moneda y activos | `01_market_prices_raw.csv`, `01_market_prices_raw_expanded.csv` |
| 02 Macro Raw | Tasa 10Y, inflación, FX y régimen de mercado | `02_macro_raw.csv` |
| 03 Fundamentals Raw | Revenue, EBITDA, utilidad, deuda y caja | `03_fundamentals_raw.csv` |
| 04 Asset Reference | Referencia de activos, emisores, sectores y países | `04_asset_reference.csv` |
| 05 Client Profiles | Perfiles de cliente y sus necesidades | `05_client_profiles.csv` |
| 06 Events | Eventos que pueden explicar movimientos o cambios | `06_events.csv` |

El acceso al Data Pack se entregó al terminar la sesión introductoria (enlace y clave en la página 15 del PDF; la clave no se copia aquí).

## 6. Entregables

La solución debe mostrar el **recorrido de datos a decisión**.

### 6.1 Solución analítica funcional

MVP ejecutable o reproducible, desarrollado con **Python + SQL en Databricks**, que muestre cómo se pasó de la información original a una recomendación. Puede ser un notebook, pipeline, modelo, scoring, recomendador, análisis predictivo, sistema de alertas o una combinación adecuada para la lógica elegida.

### 6.2 Decision Dashboard

Una vista ejecutiva principal (*one main view*) que permita entender la recomendación y responder rápido estas 5 preguntas:

1. ¿Qué está ocurriendo?
2. ¿Qué datos o señales lo explican?
3. ¿Qué significa para el cliente elegido?
4. ¿Qué debería hacer?
5. ¿Qué riesgo, supuesto o cambio podría modificar la recomendación?

### 6.3 Value Pitch

8 minutos por equipo: 5 min de presentación y demo, 2 min de Q&A del jurado y 1 min de transición. Se presenta directamente el Decision Dashboard y se muestra el MVP cuando ayude a explicar la lógica.

## 7. Qué evalúa el jurado

| Criterio | Qué mira |
|---|---|
| Problem framing | Aterrizar el problema y entender el contexto de negocio |
| Criterio técnico | Elegir herramientas y métodos con intención |
| Comunicación | Explicar una decisión de forma clara y defendible |
| Pensamiento crítico | Sostener decisiones y revisar supuestos con criterio |
| Colaboración | Trabajar bien con otras personas durante la experiencia |

El jurado evalúa el **criterio detrás de lo que se entregue** y la capacidad del equipo para explicar cómo funciona la solución.

## 8. Reglas técnicas y herramientas

- Requerido: **Python + SQL + Databricks**. Laptop propia.
- **La solución debe poder reproducirse** y el equipo debe explicar las decisiones técnicas que presenta.
- Permitido: Databricks o herramientas equivalentes, Power BI u otra visualización, notebooks y herramientas cloud, librerías open source y APIs, modelos de machine learning, y herramientas generativas y asistentes de IA.
- La IA está permitida en el análisis, el código, la documentación y la presentación.

## 9. Dinámica

6 horas en total: 4 bloques de trabajo y el pitch. El host marca el cambio de bloque y la cuenta regresiva queda visible en pantalla. Detalle y estado en [`TIEMPOS.md`](TIEMPOS.md).

## 10. Contexto de los Chapters (quién organiza)

El PDF presenta cuatro Chapters de Credicorp Capital, probablemente parte del jurado o del equipo organizador:

- Arquitectura de Datos: datos confiables, accesibles y comprensibles; modelos, patrones, gobierno, calidad y seguridad.
- Gobierno de Datos: confianza en los datos como activo estratégico; calidad, seguridad e interoperabilidad.
- Ingeniería de Datos y Modelamiento: estándares de modelamiento, modelo empresarial común, calidad y trazabilidad.
- Advanced Analytics: soluciones analíticas y de inteligencia de negocios; cultura data-driven.

Implicancia: pesa la calidad y el gobierno de datos. Conviene mostrar la validación hecha (`docs/validacion_datos.md`) y que el pipeline sea trazable.

## Pendientes

- Notas de sala (evaluación, arquitectura y gobernanza, habilidades): no se pegó el contenido.
- Los conceptos financieros del "material inicial" no están en el repo: pedirlos si hacen falta.
