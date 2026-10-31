# Guía para entender la Etapa 2 (sin experiencia previa en inversiones)

> Si nunca trabajaste en finanzas ni en datos, empieza aquí. Al final vas a poder explicar **qué encontramos, por qué importa y cómo lo defendemos**.
> Documento técnico de referencia: [`etapa2_resumen.md`](etapa2_resumen.md). Tablas en Databricks: `credicorp_dq.gold.etapa2_*`.

---

## 1. El negocio en un minuto

Credicorp Capital tiene un área de **Wealth Management** (gestión patrimonial). Funciona como un “médico de las finanzas personales”: un cliente con dinero ahorrado (su **patrimonio**) llega y pregunta *“¿qué hago con mi dinero?”*. El asesor no le recomienda lo que más ganó el año pasado, sino **lo que le conviene a esa persona**, según:

- **Cuánto riesgo aguanta:** hay gente que duerme tranquila si su inversión baja 20% y gente que no.
- **Para cuándo necesita el dinero:** su **horizonte**.
- **En qué moneda vive:** un cliente colombiano mide su riqueza en pesos colombianos (COP), no en dólares.
- **Sus reglas personales,** por ejemplo “no quiero más de 25% en cosas muy volátiles”.

Nuestro reto, tal como lo plantea el jurado, es: **¿qué decisión de inversión le recomendamos hoy a un cliente y con qué evidencia la defendemos?**

---

## 2. Glosario (de lo básico a lo técnico)

### 2.1 Mercado e instrumentos
| Término | Qué significa | Ejemplo en nuestros datos |
|---|---|---|
| **Acción** | Un pedacito de propiedad de una empresa. Si a la empresa le va bien, el precio suele subir. | VF_A05 = acción de “Aurora Health” |
| **Emisor** | La empresa que emite la acción. | ISS_05 es el emisor de VF_A05 |
| **ADR** | Una acción de una empresa extranjera que se compra en EE. UU. y en dólares. Así un inversionista compra una empresa colombiana sin ir a la bolsa de Colombia. | 6 de nuestros 8 activos son ADR latinoamericanos |
| **Activo** | Cualquier cosa en la que se puede invertir. Aquí, las 8 acciones. | VF_A01 … VF_A08 |
| **OHLCV** | Los datos de precio de un día: Open (apertura), High (máximo), Low (mínimo), Close (cierre) y Volume (cantidad negociada). | Tabla `market_prices_daily` |
| **Sector** | La industria de la empresa: salud, energía, tecnología… | Cada activo es de un sector distinto |

### 2.2 Medir ganancia y riesgo
| Término | Qué significa | Cómo calcularlo / ejemplo |
|---|---|---|
| **Retorno** | Cuánto ganaste o perdiste, en %. | Compré a 100 y ahora vale 110 → retorno = +10% |
| **Volatilidad** | Cuánto “salta” el precio de un día a otro. Más volatilidad = viaje más movido. | Desviación estándar de los retornos diarios × √252 (los días hábiles de un año). VF_A08 tiene 16% (calmado) y VF_A02 45% (montaña rusa) |
| **Drawdown** | La caída desde el punto más alto hasta el momento actual. Es el “dolor” que siente el cliente al ver su saldo. | Llegaste a tener 100 y hoy tienes 85 → drawdown = −15% |
| **Max drawdown (MDD)** | La **peor** caída de todo el periodo: el peor momento que habría vivido el cliente. | Es **la métrica clave** de este reto, porque los clientes declaran cuánto toleran perder |
| **Tolerancia al drawdown** | La caída máxima que el cliente dice aguantar. Si se pasa, el cliente entra en pánico, vende en el peor momento o pierde la confianza en el asesor. | CL_02 tolera **10%**: con 100 millones, como mucho puede ver 90 |

**Ejemplo de drawdown con números.** Un cliente invierte 100 millones de COP. Su saldo sube a 110, baja a 95 y termina en 105.
- Retorno final: +5%.
- Max drawdown: de 110 a 95 = **−13,6%**.

Aunque terminó ganando, en algún momento vio caer su dinero 13,6%. Si su tolerancia era 10%, **la recomendación falló**, aunque al final haya ganado.

### 2.3 Monedas
| Término | Qué significa | Ejemplo |
|---|---|---|
| **Moneda base** | La moneda en la que el cliente mide su riqueza. | CL_01 en USD, CL_02 en COP (Colombia), CL_03 en PEN (Perú) |
| **FX / tipo de cambio** | Cuántos pesos cuesta un dólar. | USD/COP = 4.000 → 1 dólar = 4.000 pesos |
| **Conversión** | Las acciones cotizan en dólares, así que hay que pasarlas a la moneda del cliente. | Acción a USD 50 × 4.000 = 200.000 COP. Si el dólar sube a 4.200, la misma acción vale 210.000 COP **aunque su precio en dólares no haya cambiado** |

### 2.4 Carteras
| Término | Qué significa |
|---|---|
| **Cartera / portafolio** | El conjunto de inversiones del cliente, con un **peso** (porcentaje) para cada una. Ej.: 40% VF_A05 + 30% VF_A08 + 30% VF_A04 |
| **Diversificar** | No poner todos los huevos en la misma canasta: si una acción cae, otra puede compensar |
| **Correlación** | Qué tanto se mueven juntas dos acciones (de −1 a +1). Cerca de 0 = independientes, y eso ayuda a diversificar. Las nuestras están entre 0 y 0,26 |
| **Equiponderada** | Repartir en partes iguales (8 acciones → 12,5% cada una). Es la diversificación “ingenua” que haría alguien sin análisis. Es nuestra **línea base**: el análisis tiene que superarla |
| **Long-only** | Solo se compra (no se apuesta a la baja). Los pesos van de 0% a 100% y suman 100% |
| **Compra y mantenimiento** | Comprar al inicio y no tocar la cartera. Es lo más simple de simular |
| **Exposición** | Qué parte del dinero está invertida en acciones. El resto queda en **liquidez** (efectivo o depósitos). 60% de exposición = 60% en acciones y 40% en efectivo |
| **Restricción** | Una regla que la cartera debe cumplir sí o sí. Ej.: CL_02 “máx. 25% en activos de alta volatilidad” |

### 2.5 Contexto económico y de empresa
| Término | Qué significa |
|---|---|
| **Régimen de mercado** | El “clima” del mercado: **Normal**, **Stress** (pánico, caídas fuertes; aquí ocurrió del 9 al 20 de feb-2026) y **Recovery** (rebote) |
| **Evento** | Una noticia que mueve el precio: una caída del proveedor de nube, resultados trimestrales, etc. |
| **Fundamentales** | La salud del negocio, según sus estados financieros |
| **Revenue** | Ventas o ingresos |
| **EBITDA** | Ganancia operativa antes de intereses, impuestos y depreciación. Mide “cuánto genera el negocio en sí” |
| **Margen EBITDA** | EBITDA ÷ Revenue. De cada 100 que vende, cuánto le queda operativamente |
| **Utilidad neta** | Lo que queda al final, después de todo |
| **Deuda neta / EBITDA** | (Deuda − Caja) ÷ EBITDA. Cuántos años de ganancia operativa necesita la empresa para pagar su deuda. Se calcula con el EBITDA de los **últimos 12 meses (LTM)**, no con el de un trimestre: si se usa uno solo, el ratio se infla ~4 veces. Bajo = sana (<1,5x); alto = endeudada (>2,5x). Negativo = tiene más caja que deuda. Nuestras 8 empresas están todas por debajo de 0,7x |

### 2.6 Datos y método
| Término | Qué significa |
|---|---|
| **Bronze / Silver / Gold** | Las capas de datos (arquitectura “medallion”). **Bronze** = el dato crudo tal como llegó. **Silver** = limpio, tipado y validado. **Gold** = tablas de negocio listas para decidir |
| **Cuarentena** | Las filas que no pasan las reglas de calidad se apartan, no se borran |
| **Data quality (DQ)** | Reglas que verifican el dato: sin duplicados, fechas en un formato único, IDs consistentes… |
| **ISO 8601** | El formato estándar de fecha `AAAA-MM-DD`. `02/27/2026` no cumple |
| **Outlier** | Un valor anormal. Ej.: un precio de 3.589 cuando siempre está cerca de 35 → falta la coma (error ×100) |
| **Forward-fill** | Rellenar un hueco con el último valor conocido. Útil para la inflación, que se publica mensualmente |
| **BOM** | Un carácter invisible al inicio de algunos CSV. Si no se maneja, el nombre de la primera columna sale “sucio” |
| **Simulación Monte Carlo** | Probar muchísimos escenarios al azar para ver qué pasa “en general”. Probamos **200.000 carteras al azar** |
| **Dirichlet** | La forma matemática de generar pesos al azar que siempre suman 100% |
| **In-sample / Out-of-sample** | **In-sample:** evaluar con los mismos datos con que elegiste (como corregir tu propio examen con las respuestas a la vista). **Out-of-sample:** evaluar con datos que no viste al elegir; es la prueba honesta |
| **Train / Test** | Partir el tiempo en dos: elegir con el pasado (train, ago-25 → abr-26) y comprobar con lo que vino después (test, abr-26 → ago-26) |
| **Backtest** | Simular cómo le habría ido a una estrategia en el pasado |
| **Sesgo retrospectivo / overfitting** | Elegir lo que “hubiera funcionado” mirando hacia atrás, y que luego no funcione hacia adelante. Es el error más común en inversiones |
| **Hipótesis** | Una afirmación que se puede comprobar o refutar con datos |
| **Unidad de análisis** | Qué cosa estamos midiendo. Aquí: **la cartera de CL_02, día a día, valorada en COP** |
| **Data mesh / dominio** | Organizar los datos por áreas de negocio, cada una dueña de los suyos. Por ahora usamos **un solo dominio**: el catálogo `credicorp_dq` |

---

## 3. El análisis, paso a paso

### Paso 1 — ¿Podemos confiar en los datos? (Find the truth)
Antes de analizar, revisamos los datos. Encontramos problemas típicos de la vida real:

- **Un mismo activo con varios nombres** (`VF-A1`, `VF_A01`). Sin corregirlo, la computadora cree que son dos empresas distintas.
- **Fechas en dos formatos, filas duplicadas y un precio con la coma corrida** (3.589 en lugar de 35,89). Ese error solo habría inventado una ganancia de +10.000% en un día.
- **Un trimestre mal etiquetado:** decía “Q4-2024”, pero por su posición en la serie era 2025-06-30.
- **Un dato de ventas sospechoso** (1.845 cuando siempre ronda 2.800). Probablemente es un error de tipeo, así que no lo usamos.
- **El hallazgo más importante: dos fuentes de precios que se contradicen.** El archivo diario y el intradía (cada 10 minutos) arrancan en el mismo precio y después cuentan historias distintas.
  - **¿Cómo decidimos cuál creer?** Usamos los eventos como “prueba de verdad”. Si hubo una caída del proveedor de nube de VF_A02, el precio debería bajar.
  - El diario **acierta la dirección en 4 de 5 eventos** y el intradía solo en 2. Nos quedamos con el diario.
  - Matiz honesto: acertar la *dirección* no es lo mismo que una reacción *estadísticamente significativa*. Solo la caída de A02 (−17,9%) supera claramente el ruido normal.

> 💡 **Lección:** un modelo sofisticado sobre datos sucios produce conclusiones falsas con mucha seguridad. Limpiar no es un trámite: es parte del valor.

La limpieza la hizo el equipo en `credicorp_dq.silver`, y la reconciliación está en `gold.etapa2_source_reconciliation`.

### Paso 2 — Descartar lo que no es (pensamiento crítico)
Nuestra primera sospecha fue que **el tipo de cambio** perjudicaba a los clientes en COP y PEN. Lo medimos: en el año, el dólar frente al peso colombiano se movió apenas +2,6%. Cambia el riesgo en 1 o 2 puntos y **no es la historia principal**. Lo descartamos.

> 💡 Descartar hipótesis con datos también es un resultado. Le muestra al jurado que no nos enamoramos de la primera idea.

### Paso 3 — Elegir a qué cliente ayudar (Find the signal)
El reto pide una recomendación para un cliente. ¿Cuál? Usamos este criterio: **el cliente al que el análisis le cambia más la decisión.**

Generamos **200.000 carteras al azar** y, para cada cliente, medimos qué porcentaje cumple su regla personal y su límite de caída, en su propia moneda:

| Cliente | Límite de caída | Carteras que cumplen | Si reparte en partes iguales… |
|---|---|---|---|
| CL_01 Crecimiento (USD) | 22% | **1 de cada 3** | Cae 21,7%: justo al límite |
| CL_02 Patrimonio Estable (COP) | **10%** | **1 de cada 10.000** | Cae **19%: casi el doble de lo que aguanta** |
| CL_03 Diversificación Regional (PEN) | 15% | 1 de cada 9 | Cae 23,2% |

**Lectura para un junior:**
- **CL_01:** casi cualquier cosa razonable le sirve. El análisis le aporta poco.
- **CL_02:** el consejo “diversifica en partes iguales”, que suena prudente, le habría causado una pérdida del doble de lo que tolera. Es justo el cliente que vino a **preservar** su patrimonio. Aquí el análisis tiene más valor, y por eso **CL_02 es nuestro foco**.

### Paso 4 — La señal: el problema no es *qué* comprar, sino *cuánto*
Miramos cada acción por separado: **las 8 cayeron más de 10% en algún momento del año.** La más tranquila (VF_A05) cayó 14,6%. Ninguna acción sola cabe en el límite de CL_02.

¿Y combinándolas? Hicimos la **prueba honesta (out-of-sample):**
1. Con datos de agosto-2025 a abril-2026 elegimos **la mejor cartera posible** para CL_02. En ese periodo cayó solo 7,9%.
2. Después miramos qué le pasó a **esa misma cartera** de abril a agosto-2026, con datos que no habíamos usado para elegirla.
3. Resultado: cayó **11,5%** y **rompió el límite**.

Solo 1 de cada 10 carteras se salvó en ese periodo, y no había forma de saber de antemano cuáles.

> 💡 **La señal:** si CL_02 tiene el 100% de su dinero en estas acciones, cumplir su límite depende de la suerte, no de la gestión. La palanca que sí controlamos es **cuánto invertir** (la exposición). Una parte va a un núcleo de acciones defensivas y el resto queda en liquidez como colchón.

**Intuición con números.** Si la parte en acciones puede caer hasta 16% y el cliente invierte solo el 60% (el otro 40% en efectivo), su patrimonio total cae como mucho 0,60 × 16% ≈ **9,6%**, dentro de su límite.

### Paso 5 — ¿Qué acciones forman el núcleo?
No las elegimos solo por precio, porque eso sería sesgo retrospectivo. Las respaldamos con **fundamentales**:

| Activo | Por qué entra | Lo que dicen sus números de empresa |
|---|---|---|
| VF_A05 Aurora Health (EE. UU.) | La que menos cayó; casi no se movió en el Stress | Utilidad +50% en un año; deuda bajando |
| VF_A08 Atlas Utilities (EE. UU.) | La menos volátil | Tiene más caja que deuda |
| VF_A04 Lima Financial (Perú) | Buen retorno y caída moderada | Ventas +10%, deuda estable |
| VF_A01 Andes Consumer (Colombia) | Volatilidad baja; subió en el Stress | Margen de 33%, el más alto |

Las demás (VF_A02, A03, A06, A07) son “alta volatilidad”: la regla de CL_02 permite máximo 25% en ellas. VF_A02 cayó 24,5% en el Stress de febrero y VF_A06 es la más apalancada del grupo, aunque con poca deuda en términos absolutos (0,68x).

---

## 4. Lo que queda para la Etapa 3
**Hipótesis H1:** una cartera con este núcleo defensivo, menos de 25% en alta volatilidad y **solo un X% invertido** (el resto en liquidez) mantiene la caída de CL_02 por debajo de 10% **en la prueba honesta**, y le va mejor que repartir en partes iguales.

En la etapa 3 vamos a calcular el **X%** y los pesos exactos, validarlos y traducirlos a dinero: *“con 100 millones de COP, esta recomendación evita perder hasta N millones frente a la alternativa ingenua”*.

### Supuestos que debes saber defender
1. **La liquidez rinde 0%.** Es conservador: en la realidad rendiría algo y el resultado sería mejor.
2. **“Alta volatilidad” = más de 30% anual.** El perfil del cliente no lo define, así que fijamos un umbral explícito.
3. **No hay costos de transacción** (comisiones).
4. **Solo hay un año de datos sintéticos:** las conclusiones valen para este caso.

---

## 5. Preguntas probables del jurado (y cómo responderlas)

| Pregunta | Respuesta corta |
|---|---|
| “¿Por qué CL_02 y no otro?” | Porque es donde el análisis cambia más la decisión: solo 1 de cada 10.000 carteras le sirve y la alternativa ingenua le hace perder el doble de lo que tolera. |
| “¿No están eligiendo con el diario del lunes?” | No: separamos los datos en entrenamiento y prueba. Justamente esa prueba nos mostró que el 100% en acciones no funciona. |
| “¿Por qué no usaron el archivo de 500 mil registros?” | Porque contradice al diario, y el diario es el que reacciona correctamente a 4 de 5 eventos reales del dataset. Usar el intradía habría sido usar datos menos confiables solo porque son más. |
| “¿Por qué no un modelo de machine learning?” | Porque la decisión no lo necesita. Con 8 activos y un año de datos, un modelo complejo se sobreajusta. Elegimos el método más simple que responde la pregunta y lo validamos fuera de muestra. |
| “¿Y si viene otra crisis?” | Es lo que más cambiaría la recomendación. El colchón de liquidez existe justamente para eso, y en la etapa 3 lo probamos contra el episodio de Stress de febrero. |

---

## 6. Dónde ver todo en Databricks
Catálogo **`credicorp_dq`**:
- **`bronze.*`:** datos crudos (equipo).
- **`silver.*`:** datos limpios, cuarentenas y `dq_log` con cada corrección (equipo).
- **`gold.*`:** tablas de negocio (equipo), más las de esta etapa:
  - `gold.etapa2_source_reconciliation`: diario vs. intradía y prueba de eventos.
  - `gold.etapa2_client_feasibility`: por qué CL_02.
  - `gold.etapa2_cl02_oos_backtest`: la prueba honesta.
  - `gold.etapa2_cl02_asset_view`: activo por activo en COP, con fundamentales.
  - `gold.etapa2_findings`: la bitácora de hallazgos.
- **Notebook:** `/Workspace/Users/fabrizio.vx@gmail.com/ccg/etapa2_find_the_signal`.
