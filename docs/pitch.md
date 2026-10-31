# Value Pitch — CL_02 Patrimonio Estable

> **Formato del brief (p. 19):** 8 min por equipo = **5 min de presentación y demo**, 2 min de Q&A del jurado, 1 min de transición. *"Presenten directamente el Decision Dashboard y muestren el MVP cuando ayude a explicar la lógica."* El jurado evalúa también **colaboración** (p. 7): hablan los cuatro.
> **Respuestas para el Q&A:** [`sustentacion.md`](sustentacion.md).
> **Versión vigente:** 20% invertido, horizonte de 36 meses (`gold.etapa3_recomendacion_simulador`). No usar cifras de la versión de 28% a 1 año.

## Mensaje central (si solo recuerdan una frase)

> **Para CL_02, la decisión no es qué acción comprar, sino cuánto invertir.** Con 20% en un núcleo defensivo y el resto en liquidez en COP, cumple su límite de caída de 10% en el 95,7% de los escenarios; repartir en partes iguales lo cumple en el 0,1%.

## Reparto y guion (5 minutos)

| Tiempo | Quién | Parte | Qué decir | Qué mostrar |
|---|---|---|---|---|
| **0:00–0:40** | **Danilo** | Apertura: el problema | "Nuestro cliente es CL_02: un patrimonio en pesos colombianos, horizonte de 3 años, que busca preservar y crecer moderado. Su condición: **no caer más de 10%**. Y en 6 meses retira el 30%. ¿Qué le recomendamos hoy, y con qué evidencia?" | Dashboard: perfil de CL_02 |
| **0:40–1:30** | **Cesar** | ¿Podemos confiar en los datos? | "Los datos venían con errores: IDs mal escritos, fechas mezcladas, un precio 100 veces mayor y dos fuentes de precios que se contradicen. Construimos un pipeline medallón en Databricks: bronze guarda el original, silver corrige y deja registrada cada corrección, y lo que no se puede corregir va a cuarentena. Aprovechamos el **99,99%** de los registros." | `gold.dq_scorecard` o `05_reporte_calidad` (10 s) |
| **1:30–2:15** | **Raf** | ¿Qué está ocurriendo? | "Con datos confiables, lo que vimos: solo 2 de 8 activos ganaron en el año, y **ninguno cumple solo el límite de 10%**: el mejor cae 14,6%. El consejo típico, repartir en partes iguales, cae 19%: casi el doble de lo que tolera." | Bloque 1: caída máxima por activo con la línea en −10% |
| **2:15–3:45** | **Fabrizio** | La señal y la recomendación | "Probamos elegir las acciones 'ganadoras' y falla: lo que ganó no predice lo que gana después. Lo único que se repite es la **volatilidad**. La señal es **decidir cuánto exponer**, y lo validamos sin mirar el futuro en 7 cortes: nuestra regla cumple en **7 de 7**; todo en acciones, en 0 de 7. Recomendamos **20% en un núcleo defensivo** (Atlas Utilities, Andes Consumer, Aurora Health y Lima Financial, ponderados por menor volatilidad), **30% reservado en COP para el retiro** y **50% en liquidez en COP**, rebalanceando cada trimestre. En 2000 escenarios a 36 meses cumple su límite en el **95,7%**." | Bloques 2 a 4 + simulador Monte Carlo (Vista 1) |
| **3:45–4:30** | **Raf** | ¿Qué podría cambiarla? | "Si la tasa sube 65 pb, el impacto queda dentro del límite. Si el peso se deprecia 8%, la reserva en COP protege el retiro. Y somos explícitos con los supuestos: la liquidez rinde 0%, 'alta volatilidad' es más de 30% anual y son datos de un solo año." | Bloque 5: twist y supuestos |
| **4:30–5:00** | **Danilo** | Cierre | "No le decimos al cliente qué acción va a ganar, porque los datos no lo permiten. **Le decimos cuánto riesgo puede tomar sin romper su promesa.**" | Dashboard completo |

**Tiempos por persona:** Danilo 1:10 · Cesar 0:50 · Raf 1:30 · Fabrizio 1:30.

### Frases de traspaso

| De → a | Frase |
|---|---|
| Danilo → Cesar | "Antes de recomendar, había que saber si podíamos confiar en los datos. Cesar." |
| Cesar → Raf | "Con datos confiables, ¿qué encontramos? Raf." |
| Raf → Fabrizio | "Si ningún activo cumple solo, ¿qué hacemos? Fabrizio." |
| Fabrizio → Raf | "¿Y qué podría cambiar esta recomendación?" |
| Raf → Danilo | "Danilo cierra." |

## Q&A (2 min): Danilo reparte las preguntas

Danilo escucha la pregunta y dice "eso lo responde [nombre]". Respuesta corta primero (una frase); detalle solo si repreguntan. Si no sabemos algo, decir qué supuesto usamos y cómo lo probaríamos.

| Tema de la pregunta | Responde | En `sustentacion.md` |
|---|---|---|
| Por qué CL_02, encuadre del problema | **Danilo** | §0, §2 |
| Datos, calidad, arquitectura, gobierno, linaje | **Cesar** | §10, §13, §15, §16 |
| Qué pasa en los datos, riesgo, negocio, retener al cliente | **Raf** | §5, §6, §7 |
| Recomendación, simulación, rentabilidad, metodología, LSTM | **Fabrizio** | §3, §4, §9 |

## Demo: qué abrir y cuándo

| Momento | Qué abrir | Plan B si no carga |
|---|---|---|
| Inicio | Decision Dashboard (una vista) | Notebook `08_simulador_montecarlo_cl02`, Vista 1 |
| 0:40 (Cesar) | `gold.dq_scorecard` o `05_reporte_calidad` | Decirlo sin mostrar |
| 2:15 (Fabrizio) | Curva exposición vs. probabilidad y walk-forward | `08_simulador_montecarlo_cl02`, Vista 2 |
| Q&A ("¿cómo lo calculan?") | Notebook `07_etapa3_propuesta_cl02` | `docs/etapa3_propuesta.md` |

Dejar todas las pestañas abiertas y ya ejecutadas antes de presentar: no correr nada en vivo.

## Checklist antes de presentar

- [ ] Las cifras del dashboard coinciden con las de este guion (versión 20% / 36 meses).
- [ ] **Fabrizio confirma la pérdida evitada en S/ de la versión vigente.** `sustentacion.md` usa S/ 137 725 (mediana) y S/ 229 404 (p90), pero en `etapa3_propuesta.md` §4 esas cifras vienen de la tabla a 1 año, no de la simulación a 36 meses. Hasta confirmarla, no decirla en el guion.
- [ ] Completar en `sustentacion.md` el resultado de la LSTM (`gold.etapa4_lstm_decision`).
- [ ] Una sola definición de "alta volatilidad" en todo el pitch: más de 30% anual.
- [ ] Ensayar con cronómetro: 5:00 exactos, con traspasos.
- [ ] Pestañas abiertas y ejecutadas.
