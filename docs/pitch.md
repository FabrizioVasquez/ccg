# Value Pitch — CL_02 Patrimonio Estable

> **Formato del brief (p. 19):** 8 min por equipo = **5 min de presentación y demo**, 2 min de Q&A del jurado, 1 min de transición. *"Presenten directamente el Decision Dashboard y muestren el MVP cuando ayude a explicar la lógica."* El jurado evalúa también **colaboración** (p. 7): hablan los cuatro.
> **Estructura:** el pitch sigue las **5 preguntas que debe responder la vista principal** (brief p. 18). Cada parte **empieza diciendo su pregunta en voz alta**, y el bloque del dashboard lleva esa pregunta como título.
> **Respuestas para el Q&A:** [`sustentacion.md`](sustentacion.md).
> **Versión vigente:** 20% invertido, horizonte de 36 meses (`gold.etapa3_recomendacion_simulador`). No usar cifras de la versión de 28% a 1 año.

## Mensaje central (si solo recuerdan una frase)

> **Para CL_02, la decisión no es qué acción comprar, sino cuánto invertir.** Con 20% en un núcleo defensivo y el resto en liquidez en COP, cumple su límite de caída de 10% en el 95,7% de los escenarios; repartir en partes iguales lo cumple en el 0,1%.

## Las 5 preguntas y quién responde

| # | Pregunta (brief p. 18) | Quién | Respuesta en una línea |
|---|---|---|---|
| — | Apertura: el cliente y la pregunta del reto | **Danilo** | CL_02 no tolera caer más de 10% y en 6 meses retira el 30% |
| 1 | **¿Qué está ocurriendo?** | **Raf** | El mercado cae: 6 de 8 acciones pierden y ninguna cumple sola el límite de 10% |
| 2 | **¿Qué datos o señales lo explican?** | **Cesar** (datos) y **Fabrizio** (señal) | Datos corregidos y trazados; la señal: el retorno no se repite, la volatilidad sí |
| 3 | **¿Qué significa para el cliente elegido?** | **Danilo** | Con todo en acciones, cumplir su promesa depende de la suerte |
| 4 | **¿Qué debería hacer?** | **Fabrizio** | 20% en un núcleo defensivo, 30% de reserva y 50% de liquidez en COP |
| 5 | **¿Qué riesgo, supuesto o cambio podría modificar la recomendación?** | **Raf** | El twist no la rompe; los supuestos son explícitos |
| — | Cierre | **Danilo** | "Le decimos cuánto riesgo puede tomar sin romper su promesa" |

## Guion (5 minutos)

| Tiempo | Quién | Pregunta | Qué decir | Qué mostrar |
|---|---|---|---|---|
| **0:00–0:25** | **Danilo** | Apertura | "Nuestro cliente es CL_02: un patrimonio en pesos colombianos, horizonte de 3 años, que busca preservar y crecer moderado. Su condición: **no caer más de 10%**. Y en 6 meses retira el 30%. ¿Qué le recomendamos hoy? Lo respondemos en cinco preguntas." | Dashboard: perfil de CL_02 |
| **0:25–1:05** | **Raf** | **1. ¿Qué está ocurriendo?** | "¿Qué está ocurriendo? En el último año solo 2 de las 8 acciones ganaron. **Ninguna, por sí sola, cumple el límite de 10% del cliente**: la mejor cayó 14,6%. Y el consejo típico, repartir en partes iguales, cae 19%: casi el doble de lo que tolera." | Bloque 1: caída máxima por activo con la línea en −10% |
| **1:05–1:50** | **Cesar** | **2. ¿Qué datos lo explican?** | "¿Qué datos lo explican? Primero, había que poder confiar en ellos. Venían con errores: IDs mal escritos, fechas mezcladas, un precio 100 veces mayor y dos fuentes de precios que se contradicen. Construimos un pipeline medallón en Databricks que corrige y deja registrada cada corrección. Aprovechamos el **99,99%** de los registros, y elegimos la fuente diaria porque es la que reacciona a los eventos del mercado." | `gold.dq_scorecard` o `05_reporte_calidad` (10 s) |
| **1:50–2:30** | **Fabrizio** | **2. ¿Qué señales lo explican?** | "¿Y qué señales? Probamos elegir las acciones 'ganadoras' y falla: lo que ganó en un periodo no predice lo que gana en el siguiente. Lo único que se repite es **qué tan volátil es cada acción**. Esa es la señal: no podemos predecir el retorno, pero sí el riesgo." | Bloque 2: persistencia de métricas (volatilidad vs. retorno) |
| **2:30–3:00** | **Danilo** | **3. ¿Qué significa para el cliente?** | "¿Qué significa para CL_02? Que no puede comprar ninguna acción sola. Que el consejo típico le haría perder casi el doble de lo que tolera: unos **S/ 190 000 de cada millón**. Y que con todo en acciones, cumplir su promesa depende de la suerte: lo probamos sin mirar el futuro y **falló en los 7 cortes**. Además, en 6 meses necesita el 30% disponible." | Bloque 3: caída de la equiponderada frente a su límite y walk-forward |
| **3:00–4:00** | **Fabrizio** | **4. ¿Qué debería hacer?** | "¿Qué debería hacer? Decidir **cuánto** invertir, no solo en qué. Recomendamos **20% en un núcleo defensivo** (Atlas Utilities, Andes Consumer, Aurora Health y Lima Financial, ponderados por menor volatilidad), **30% reservado en COP para el retiro** y **50% en liquidez en COP**, rebalanceando cada trimestre. En 2000 escenarios a 36 meses cumple su límite en el **95,7%**. Y sin mirar el futuro, nuestra regla cumple en **7 de 7** cortes." | Bloque 4: asignación en S/ + simulador Monte Carlo (Vista 1) |
| **4:00–4:40** | **Raf** | **5. ¿Qué podría cambiarla?** | "¿Qué riesgo o supuesto podría cambiar esto? Si la tasa sube 65 pb, el impacto queda dentro del límite. Si el peso se deprecia 8%, la reserva en COP protege el retiro. Y somos explícitos con los supuestos: la liquidez rinde 0%, 'alta volatilidad' es más de 30% anual y son datos de un solo año. Si el cliente acepta más caída, la misma regla da otra exposición." | Bloque 5: twist y supuestos |
| **4:40–5:00** | **Danilo** | Cierre | "No le decimos al cliente qué acción va a ganar, porque los datos no lo permiten. **Le decimos cuánto riesgo puede tomar sin romper su promesa.**" | Dashboard completo |

**Tiempos por persona:** Danilo 1:15 · Raf 1:20 · Cesar 0:45 · Fabrizio 1:40.

### Frases de traspaso

| De → a | Frase |
|---|---|
| Danilo → Raf | "Primera pregunta: ¿qué está ocurriendo? Raf." |
| Raf → Cesar | "¿Y qué datos lo explican? Cesar." |
| Cesar → Fabrizio | "Con datos confiables, ¿qué señal encontramos? Fabrizio." |
| Fabrizio → Danilo | "¿Y qué significa esto para CL_02?" |
| Danilo → Fabrizio | "Entonces, ¿qué debería hacer? Fabrizio." |
| Fabrizio → Raf | "¿Y qué podría cambiar esta recomendación? Raf." |
| Raf → Danilo | "Danilo cierra." |

## Q&A (2 min): Danilo reparte las preguntas

Danilo escucha la pregunta y dice "eso lo responde [nombre]". Respuesta corta primero (una frase); detalle solo si repreguntan. Si no sabemos algo, decir qué supuesto usamos y cómo lo probaríamos.

| Tema de la pregunta | Responde | En `sustentacion.md` |
|---|---|---|
| Por qué CL_02, qué significa para el cliente | **Danilo** | §0, §2 |
| Datos, calidad, arquitectura, gobierno, linaje | **Cesar** | §10, §13, §15, §16 |
| Qué pasa en el mercado, riesgo, negocio, retener al cliente | **Raf** | §5, §6, §7 |
| Recomendación, simulación, rentabilidad, metodología, LSTM | **Fabrizio** | §3, §4, §9 |

## Dashboard: un bloque por pregunta

Cada bloque lleva **la pregunta como título**, para que el jurado vea en pantalla cuál se está respondiendo.

| Bloque | Título | Contenido | Tabla |
|---|---|---|---|
| 1 | ¿Qué está ocurriendo? | Caída máxima por activo en COP con la línea en −10%; "la equiponderada cae −19%" | `client_asset_fit` / `asset_risk_metrics` |
| 2 | ¿Qué datos o señales lo explican? | Resumen de calidad (99,99%); persistencia de volatilidad vs. retorno | `dq_scorecard`, `etapa3_metric_persistence` |
| 3 | ¿Qué significa para el cliente elegido? | Caída de la equiponderada frente a su 10% (S/ −189 702); walk-forward: todo en acciones 0/7 | `etapa3_walkforward` |
| 4 | ¿Qué debería hacer? | Asignación 20 / 30 / 50 en S/ y núcleo por activo; P(cumplir) 95,7% vs. 0,1% | `etapa3_recomendacion_simulador`, `etapa3_recomendacion_activos` |
| 5 | ¿Qué podría modificar la recomendación? | Escenarios del twist y lista de supuestos | `etapa3_twist_escenarios`, `etapa3_montecarlo_escenarios` |

## Demo: qué abrir y cuándo

| Momento | Qué abrir | Plan B si no carga |
|---|---|---|
| Inicio | Decision Dashboard (una vista) | Notebook `08_simulador_montecarlo_cl02`, Vista 1 |
| 1:05 (Cesar) | `gold.dq_scorecard` o `05_reporte_calidad` | Decirlo sin mostrar |
| 3:00 (Fabrizio) | Simulador Monte Carlo, Vista 1 | `08_simulador_montecarlo_cl02`, Vista 2 |
| Q&A ("¿cómo lo calculan?") | Notebook `07_etapa3_propuesta_cl02` | `docs/etapa3_propuesta.md` |

Dejar todas las pestañas abiertas y ya ejecutadas antes de presentar: no correr nada en vivo.

## Checklist antes de presentar

- [ ] Cada bloque del dashboard tiene como título su pregunta del brief.
- [ ] Las cifras del dashboard coinciden con las de este guion (versión 20% / 36 meses).
- [x] **Pérdida evitada confirmada a 36 meses:** caída evitada mediana S/ 224 407 y p90 S/ 356 020 por S/ 1 M (`src/analysis/pitch_graficos.py`). Reemplaza S/ 137 725 / S/ 229 404, que venían de la tabla a 1 año.
- [x] Resultado de la LSTM en `sustentacion.md` (Anexo A): H2 rechazada.
- [ ] Presentación: `docs/pitch_value_finders_cl02.pptx` (regenerar con `src/analysis/pitch_deck.py`).
- [ ] Una sola definición de "alta volatilidad" en todo el pitch: más de 30% anual.
- [ ] Ensayar con cronómetro: 5:00 exactos, con traspasos.
- [ ] Pestañas abiertas y ejecutadas.
