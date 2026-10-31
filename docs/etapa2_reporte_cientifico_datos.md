# Etapa 2: revisión de ciencia de datos (hallazgos, limpieza, robustez de CL_02 y twist)

> Complementa [`etapa2_resumen.md`](etapa2_resumen.md); no lo reemplaza.
> **Todas las cifras** salen de [`src/analysis/etapa2_ds_review.py`](../src/analysis/etapa2_ds_review.py) (semilla 7; tarda unos 35 s): `.venv/bin/python src/analysis/etapa2_ds_review.py`.
> **Moneda de reporte: PEN (S/). El riesgo se mide en la moneda base del cliente** (CL_02 en COP). Patrimonio de referencia: **S/ 1 000 000**, convertido con el FX del 2026-08-14: USD/PEN 3,6802; USD/COP 4.195,52; **cruce 1.140,02 COP por S/** (S/ 1 000 000 = USD 271.724 = COP 1.140 millones).

---

## 1. Resumen ejecutivo

1. **CL_02 es la elección correcta, y la conclusión es robusta.** En las 60 combinaciones probadas (5 semillas × 4 valores de α × 3 umbrales de alta volatilidad), CL_02 siempre es el cliente con menos carteras factibles (entre 0% y 0,03%). Con bootstrap por bloques, la cartera ingenua (equiponderada al 100%) **incumple su límite de 10% en el 95% de los escenarios**, con un exceso esperado de 8,0 pp, es decir, el 80% de su tolerancia. Para CL_03 esas cifras son 74% y 37%, y para CL_01, 27% y 6%.
2. **En estos datos, elegir pesos “ganadores” no generaliza; dimensionar la exposición sí.** Los retornos se comportan como ruido gaussiano independiente: no hay colas gruesas, autocorrelación, efecto día de la semana ni agrupamiento de volatilidad. Además, la estructura de correlaciones de train no predice la de test (correlación 0,04). Por eso la cartera de menor drawdown en train **falla en test en los 7 cortes del walk-forward**, y las 27 carteras “factibles” de la muestra solo cumplen en el 28% de las trayectorias bootstrap. El núcleo (A01/A04/A05/A08) invertido al 100% también incumple: −10,7% en la muestra e incumplimiento en el 64% de los escenarios bootstrap. **Con una exposición ≤ 50% cumple con probabilidad ≥ 90% (93%); con 45%, el 96%.**
3. **Con los datos no se puede medir la sensibilidad a tasas, así que TW_01 se evalúa con escenarios, no con betas.** En todo el año, la tasa de 10 años solo bajó 25 pb y su mayor movimiento semanal fue de 3,8 pb. El shock de +65 pb es 17 veces mayor. Ninguna beta es significativa (R² semanal ≤ 5,3%), y el IC95 del impacto de +65 pb en el núcleo va de −2,7% a +53,8%: no informa nada. A08 (utilities) no muestra sensibilidad, pero eso es ausencia de evidencia, no protección.
4. **El twist endurece la recomendación.** Por TW_02, el 30% del retiro (S/ 300 000) debe apartarse en liquidez en COP. Para que el saldo restante siga con ≥ 90% de probabilidad de cumplir el 10%, **lo invertido hoy debe ser ≤ 35% del patrimonio** (70% × 50%). TW_03 (COP −8%) **sube** el valor en COP de lo invertido en USD (+2,8% con una mezcla 35/65), pero crea un nuevo pico y, con él, riesgo de reversión. Además, es un movimiento de 11 desviaciones estándar respecto a lo observado: el FX deja de ser irrelevante.
5. **Hay tres correcciones de datos que afectan la defensa ante el jurado.** (a) Los ratios deuda neta/EBITDA del resumen usan EBITDA trimestral, no anual, y sobrestiman unas 4 veces: A06 no tiene 2,5x sino **0,68x LTM**. (b) El revenue anómalo de ISS_06 sigue en silver y contamina `gold.fundamentals_ratios`: margen de 23,7% y revenue_qoq de −35% y +55%. (c) El intradía 2020-2025 no sirve como historia (correlación media entre activos de 0,80 frente a 0,16 en el diario), pero sí como prueba de estrés: en ese mundo el núcleo cae más de 10% en el **82% de las ventanas de un año**.

**En S/:** frente a la equiponderada al 100%, el núcleo al 50% evita una pérdida máxima mediana de **S/ 100 612** y, en el escenario adverso (p10), de **S/ 164 657** (drawdown medido en COP y convertido al cruce de referencia).

---

## 2. Hallazgos adicionales

Unidad: retornos logarítmicos diarios en USD de 8 activos, 270 días (2025-08-04 a 2026-08-14), salvo que se indique otra cosa. Errores estándar HAC (Newey-West, 5 rezagos diarios o 2 semanales).

### Tabla de evidencia

| # | Pregunta | Resultado (tamaño del efecto ± incertidumbre) | ¿Significativo? | Implicación |
|---|---|---|---|---|
| H1 | ¿Sube la volatilidad en Stress? | Ratio de volatilidad Stress/Normal entre 0,78 (A06) y 1,19 (A05). Prueba F con p ≥ 0,36 y Levene con p ≥ 0,34. Solo hay **10 días de Stress** | No (poca potencia) | No se puede afirmar que el régimen Stress cambie la volatilidad |
| H2 | ¿Suben las correlaciones en Stress? | Correlación media entre pares: Normal 0,158, **Stress 0,035**, Recovery 0,160. La ventana Stress está en el percentil 17 de las 261 ventanas de 10 días (p5-p95: −0,007 a 0,309) | No (y va en sentido contrario) | **El Stress de feb-26 fue idiosincrático** (A02 −24,2%, A04 −10,7%, A06 −11,0% en USD), no un evento sistémico. Matiz: dentro del núcleo, A04-A05 sube de 0,22 a 0,61, y A08 pasa a correlación negativa con el resto (−0,30 a −0,55); con n=10 esto es indicativo, no concluyente |
| H3 | ¿Es estable la volatilidad entre train y test? | Ratio test/train entre 0,87 y 1,23. Ninguno pasa Bonferroni (p < 0,006); A02 tiene p = 0,044 y A03 p = 0,055 | No | La volatilidad es razonablemente estable |
| H4 | ¿Es estable la estructura de correlaciones? | Correlación entre las 28 correlaciones de train y las de test: **0,04**; diferencia absoluta media 0,088 | — | **Las correlaciones por par son ruido alrededor de ~0,15.** Optimizar pesos con ellas es sobreajustar |
| H5 | Beta frente a la tasa de 10 años (diaria) | Entre −0,14% y +0,31% por pb; t máximo 1,84 (A05); **R² ≤ 1,3%**. Controlando por market_factor, t máximo 1,47 | No | Ver H6 |
| H6 | Beta frente a la tasa (semanal) | A08: 0,22%/pb (EE 0,34; R² 1,0%). A05: 0,77%/pb (EE 0,59; R² 5,3%). Signos mayormente **positivos**, contrarios a la teoría | No | La tasa casi no varió (desv. diaria 0,58 pb; total del año −25 pb; máximo en 5 días 3,8 pb). **No hay variación con la cual identificar la sensibilidad** |
| H7 | Beta frente a USD/COP | Entre −0,74 (A02, t −1,79) y +0,42 (A07); **R² ≤ 1%**. Correlación de USD/COP con market_factor: −0,008 | No | Confirma que “el FX no era la señal” en la historia. Tampoco hay cobertura natural medible |
| H8 | Market factor | Betas entre 0,34 (A08, EE 0,07) y 1,46 (A02, EE 0,20), **todas significativas**; R² entre 8% y 24% (media 16%). Correlación con el retorno equiponderado: 0,76 | Sí | A08 y A01 son los de menor beta: defensivos de verdad frente al mercado |
| H9 | Market factor por régimen | Normal −1,8 pb/día, Stress −59,5, Recovery +30,1 (Kruskal p = 0,027) | Sí (marginal) | El régimen está bien etiquetado, pero solo ocurrió un episodio (2026-02-09 a 02-20) |
| H10 | ¿Colas gruesas? | Curtosis en exceso entre −0,44 y +0,12; Jarque-Bera p ≥ 0,34. Días con más de 3σ: 3 en total frente a ~5,8 esperados con normalidad | No | Datos sintéticos **gaussianos**; el riesgo de cola real estaría **subestimado** |
| H11 | ¿Autocorrelación o agrupamiento de volatilidad? | AC(1) entre −0,10 y +0,04 (IC95 bajo H0: ±0,119); Ljung-Box(10) en retornos p ≥ 0,32 y en cuadrados p ≥ 0,19 | No | Ni momentum ni GARCH. El bootstrap por bloques es apropiado |
| H12 | Estacionalidad | Día de la semana: Kruskal p ≥ 0,087 (ninguno pasa Bonferroni). Mensual: **no se puede probar con un solo año** | No | — |
| H13 | Eventos (CAR [0,+5] con modelo de mercado) | A02 Operational −16,7% (t −2,67). A07 Demand −7,7% (t −1,42). A03 Commodity +3,8% (t 0,79). Tech Sector −3,6% (t −0,57). **A04 Earnings −0,5% (t −0,14, signo contrario)** | 1 de 5 | En dirección, 4/5 se mantiene; en significancia, solo 1/5 |
| H14 | ¿Aporta historia el intradía 2020-2025? | Correlación con el diario en el periodo común entre −0,01 y 0,13 por activo. Correlación media entre activos: **0,80 en el intradía frente a 0,16 en el diario** (similitud de estructura 0,41). DD máximo 2020-25 entre −51% y −82% por activo | — | **Es otro proceso generador**: no se empalma. Sirve como escenario de estrés: el núcleo equiponderado tiene un DD de un año con mediana −17,8%, p10 −35,7% y peor caso −46,7%; supera −10% en el 82% de las ventanas |
| H15 | Inflación de EE. UU. | Va de 2,82 a 3,00 en el año, casi constante | — | Sin poder explicativo |
| H16 | Calendario | 271 días = todos los días lunes a viernes; incluye feriados de EE. UU. (p. ej., 2025-11-27) | — | Confirma que los datos son sintéticos |

**Lectura para negocio:** fuera del factor de mercado, los datos no contienen patrones explotables, como estacionalidad, momentum o sensibilidad a tasas o al FX. Eso es una buena noticia para la tesis: si no hay patrones, lo único que se puede gestionar con robustez es **cuánto riesgo se toma (exposición)** y **qué tan volátil y cíclico es cada activo (beta, volatilidad)**, no la apuesta a qué activo “ganará”.

---

## 3. Plan de limpieza e imputación

Las cifras de filas salen de la sección 2 del script, contrastadas con `credicorp_dq.silver.dq_log`.

### 3.1 Tabla por tabla

| Tabla | Problema detectado | Filas | Tratamiento | Justificación | Riesgo del tratamiento | ¿Silver lo hace? |
|---|---|---|---|---|---|---|
| 01 diario | Alias de asset_id | 3 | Corregir (mapa a ID canónico) | Mapeo 1 a 1 evidente | Bajo | Sí (3) |
| 01 diario | Fecha MM/DD/YYYY | 4 | Corregir (parseo a ISO) | Sin ambigüedad: día > 12 o secuencia | Bajo | Sí (4) |
| 01 diario | currency nulo | 4 | Imputar desde el maestro 04 | Todos los activos cotizan en USD | Bajo | Sí (4) |
| 01 diario | Volumen “3635.6K” | 3 | Corregir (×1e3 / ×1e6) | Formato | Bajo (no se usa en la decisión) | Sí (3) |
| 01 diario | Duplicados (asset, fecha) | 7 | Descartar | Los 7 son **exactos** | Nulo | Sí (7) |
| 01 diario | close = 3589 (A06, 2026-03-23), fuera de [34,56; 35,92] | 1 | Corregir ÷100 → 35,89 | Error de escala: 35,89 cae dentro del rango del día | Bajo. **Diferencia local:** `clean.py` usa (o+h+l)/3 = 35,03. El DD en COP de A06 es idéntico (−33,59%) con ambos métodos: **inmaterial**, pero conviene alinear el script local con silver | Sí (÷100) |
| 01 expanded (intradía) | Precio en el periodo común no coincide con el diario | 2025-08 a 2026-08 | **Descartar como fuente de precios** | Correlación de retornos con el diario ≈ 0 (H14); reacciona a 2/5 eventos frente a 4/5 | Perder 5 años de historia; se mitiga usándolo como escenario de estrés (H14, §5) | Sí (se usa el diario) |
| 01 expanded | Historia 2020-2025 como serie empalmada | ~1.400 días | **Descartar el empalme**; conservar solo como escenario de estrés | Correlación media 0,80 frente a 0,16: otro mundo. Empalmar mezclaría dos procesos | Si el intradía fuera “el real”, nuestro riesgo estaría subestimado (ver §6) | No aplica |
| 01 expanded | close nulo | 24 | Cuarentena (no imputar) | En barras de 10 min no aporta nada; el cierre diario usa la última barra válida | Bajo | Sí (24) |
| 01 expanded | **volume nulo** | **30** | Dejar nulo (no imputar) | No se usa el volumen en la decisión | Nulo | **No figura en dq_log (vacío de documentación)** |
| 01 expanded | Alias / fechas / currency / K-M / duplicados | 16 / 38 / 35 / 45 / 12 | Corregir / descartar duplicados | Igual que en el diario | Bajo | Sí |
| 02 macro | us_inflation_yoy nulo (dato mensual) | 258 | **Imputar con forward-fill** | Es un dato mensual: el valor vigente es el último publicado. Ffill no mira al futuro | Bajo; además la variable no tiene poder explicativo (H15) | Sí (258) |
| 02 macro | Otras columnas | 0 nulos | — | — | — | — |
| 03 fundamentals | Duplicado exacto (ISS_03 2025-06-30) | 1 | Descartar | Exacto | Nulo | Sí |
| 03 fundamentals | Alias ISS04 | 1 | Corregir | — | Bajo | Sí |
| 03 fundamentals | “Q4-2024” en ISS_02 | 1 | Corregir a 2025-06-30 por secuencia (imputed_period) | Su posición en la serie lo ubica ahí | Medio-bajo (supuesto de orden), por eso queda marcado | Sí |
| 03 fundamentals | Revenue “1,845.7” como texto | 1 | Convertir a número | Formato | Bajo | Sí |
| 03 fundamentals | **Revenue ISS_06 2025-06-30 = 1.845,7**: −35,3% frente al promedio de sus vecinos (2.841,6 / 2.861,2) | 1 | **Cuarentena o marca `revenue_outlier`, excluido de ratios.** No imputar en silver | Muy probable error de dígito (2.845,7 encajaría), pero no es verificable | Si se deja tal cual, el margen EBITDA salta a 23,7% (con 2.845,7 sería 15,4%) y revenue_qoq a −35% / +55% | **No: silver lo deja sin marca y contamina `gold.fundamentals_ratios`** |
| 03 fundamentals | **cash_usd_m nulo de ISS_07 2025-09-30** | 1 | **No imputar** en silver; si un ratio lo necesita, interpolación lineal marcada (335,6) | No es el último trimestre, así que no afecta la lectura actual de ISS_07 | Bajo | Silver: NULL (correcto). **Diferencia local:** `clean.py` hace ffill (328,0). Hay que alinear |
| 03 fundamentals | Ratio deuda neta/EBITDA calculado con EBITDA trimestral | 8 emisores | **Corregir el análisis** (no los datos): usar EBITDA LTM | Un ratio de apalancamiento se mide contra el EBITDA anual | Ver §6 | `gold.fundamentals_ratios` ya usa LTM (correcto); **el resumen de etapa 2 no** |
| 04 asset_reference | — | 0 | — | — | — | — |
| 05 client_profiles | “Alta volatilidad” no definida | — | Supuesto: vol anual > 30% en COP, con sensibilidad 25/35% (§4) | El perfil no la define | Ver §4: no cambia la elección | — |
| 06 events | Scope “Technology” es un sector | 1 | Mapear a VF_A02 (único activo tech) | El maestro lo determina | Bajo | Sí (0 en cuarentena) |
| 07 twist | `field` (p. ej., `CL_02_liquidity`) no es una columna | 3 | **No imputar a las tablas**: se tratan como parámetros de escenario | Son información prospectiva (2026-08-17), posterior al último dato (2026-08-14) | Mezclarla con la historia sería fuga de información (look-ahead) | No aplica |

### 3.2 Síntesis: qué descartamos, qué imputamos y qué no imputamos

| | Qué | Por qué |
|---|---|---|
| **Descartamos** | El intradía como fuente de precios y como historia empalmada; 7 duplicados exactos del diario; 12 del intradía; 1 de fundamentals | Dos versiones de la verdad (correlación ≈ 0); estructura de correlación incompatible (0,80 frente a 0,16) |
| **Imputamos** | Inflación (258, forward-fill); currency (4 + 35, desde el maestro); periodo de ISS_02 (por secuencia, marcado); close de A06 (÷100, corrección de escala) | Reglas deterministas con fuente clara |
| **No imputamos, a propósito** | close nulo del intradía (24, cuarentena); volume nulo del intradía (30); cash de ISS_07 (1); revenue de ISS_06 (se marca, no se “arregla”) | No se usan en la decisión, o imputar inventaría un dato contable no verificable |
| **Pendiente en silver o gold** (no lo tocamos: Databricks es solo lectura en esta revisión) | Marcar el revenue de ISS_06 como outlier y excluirlo de los ratios de gold; documentar los 30 volume nulos del intradía; alinear `clean.py` local (A06 ÷100, sin ffill de cash) | Consistencia entre silver, gold y la réplica local |

---

## 4. Por qué CL_02: criterio formal, robustez e incertidumbre

### 4.1 Criterio formal: valor de la información

Elegimos al cliente donde **(a)** la decisión basada en datos se aleja más de la heurística ingenua (diversificar en partes iguales al 100%) y **(b)** equivocarse cuesta más. Lo medimos así:

- **Escasez:** % de carteras aleatorias que cumplen la restricción y el drawdown. Cuanto menor, más difícil es acertar sin análisis.
- **Probabilidad de que la heurística falle:** P(DD de la equiponderada > tolerancia).
- **Severidad:** exceso esperado sobre la tolerancia, E[max(0, |DD| − tol)], en pp y como fracción de la tolerancia.

Método: bootstrap circular por bloques de 20 días (300 réplicas; activos y FX se remuestrean juntos), con 20.000 carteras Dirichlet (α = 0,6) por réplica.

| Métrica | CL_01 (USD, 22%) | **CL_02 (COP, 10%)** | CL_03 (PEN, 15%) |
|---|---|---|---|
| % factible en la muestra | 33,7% | **0,01%** | 11,6% |
| % factible bootstrap: mediana [IC90] | 41,9% [6,0%; 68,7%] | **0,76% [0,0%; 7,3%]** | 17,2% [0,01%; 55,7%] |
| P(no existe ninguna cartera factible) | 0% | **24%** | 3,3% |
| DD de la equiponderada (muestra) | −21,7% | **−19,0%** | −23,2% |
| P(la equiponderada incumple) | 27% | **95%** | 74% |
| Exceso esperado de la equiponderada | 1,3 pp (6% de la tolerancia) | **8,0 pp (80%)** | 5,5 pp (37%) |

CL_02 domina en las tres dimensiones. El 0,01% de la muestra es, además, una estimación **pesimista**: el IC90 bootstrap llega a 7,3%. Aun así, sigue siendo el menor de los tres clientes por un orden de magnitud.

### 4.2 Pruebas de robustez

| Prueba | Resultado | ¿Cambia la elección? |
|---|---|---|
| **Semilla** (7, 11, 23, 42, 99) y **α de Dirichlet** (0,3; 0,6; 1; 2), 50k carteras | % factible de CL_02 entre 0% y 0,032%; CL_01 entre 18% y 50%; CL_03 entre 3,4% y 11,4% | No: CL_02 es el menor en **60/60** combinaciones |
| **Umbral de alta volatilidad** (vol en COP) | 25% → {A02, A03, **A04**, A06, A07}: **0% factible en todas** (mejor DD entre −10,2% y −11,1%). 30% → 0% a 0,016%. 35% → {A02, A03, A07}: 0,002% a 0,032%. A03 (35,5%) queda justo en el borde | No. Con 25%, A04 sale del núcleo permitido y CL_02 se vuelve **más** difícil |
| **Walk-forward**, 7 cortes (2025-12-01 a 2026-06-01) | Cartera de menor DD en train: DD de train entre −3,0% y −8,1% → **DD de test entre −10,9% y −15,3% (0/7 cumplen)**. Solo el 7%-13% de las carteras válidas cumple en test | Refuerza la tesis: la selección no generaliza |
| **Núcleo elegido sin mirar el futuro** (los 4 de menor DD en train) | Con cortes desde feb-26, coincide 4/4 con A01/A04/A05/A08. Con cortes de dic-25 y ene-26 elige **A02 en lugar de A08** (antes de su caída de −24%) | Parcial: **el núcleo depende de haber visto el episodio Stress** (ver §6) |
| **Exposición del núcleo** (bootstrap) | P(DD ≤ 10%) según exposición: 100% → 0,36; 80% → 0,60; 70% → 0,74; 60% → 0,83; **50% → 0,93**; **45% → 0,96**; 40% → 0,99 | Define la palanca: **≤ 50% para tener ≥ 90%** |
| Regla ingenua de exposición en walk-forward (X = 80%) | Cumple 5/7; las fallas son marginales (−10,1% y −10,7%) | 80% es demasiado. La muestra sugería 92% como máximo, el bootstrap 50%: **la muestra es optimista** |
| Equiponderada con exposición reducida (bootstrap) | P(cumplir): 50% → 0,70; 40% → 0,86; 35% → 0,93 | El núcleo permite un 15 pp más de exposición que la equiponderada con la misma confianza |

### 4.3 Qué cambiaría la elección

- Que **CL_02 acepte un DD ≥ 19%**, el de la equiponderada en la muestra: la heurística ingenua bastaría y el valor del análisis caería al nivel de CL_01.
- Que el **intradía** resulte ser la historia correcta: con correlaciones de 0,80 casi nadie cumple. CL_03 (15%) también pasaría a ser crítico y el foco se volvería “exposición para todos”.
- Que la liquidez **no** fuera un activo admisible para CL_02. En ese caso no habría ninguna solución robusta y la recomendación sería “no invertir” o cambiar el universo.
- Con los datos actuales, ningún parámetro razonable de simulación (semilla, α, umbral) cambia la elección.

---

## 5. Impacto del twist en CL_02 (efectivo el 2026-08-17)

Supuestos: la liquidez rinde 0; compra y mantenimiento; drawdown medido en COP; montos en S/ al cruce de referencia (1.140,02 COP/S/).

### TW_01: tasa de 10 años +65 pb en una semana

- **Las betas no sirven aquí.** El shock es 17 veces el mayor movimiento semanal observado. Betas semanales del núcleo: A01 0,44%/pb (EE 0,31), A04 0,15 (0,48), A05 0,77 (0,59), **A08 0,22 (0,34)**, con R² entre 0,2% y 5,3%. Extrapoladas, implican **+25,5%** para el núcleo con un IC95 de −2,7% a +53,8%: un resultado sin sentido económico. **No reportamos betas como impacto.**
- **A08 (utilities):** en estos datos no se ve sensibilidad a tasas (signo positivo, no significativo). La teoría financiera dice que las utilities se comportan como “bonos” y sufren cuando las tasas suben. Conclusión honesta: **no se puede contar con A08 como refugio ante una subida de tasas**.
- **Escenarios con datos** (impacto en el núcleo al 100% / en la equiponderada al 100%):

| Escenario | Núcleo 100% | Equiponderada 100% | Núcleo al 35% (derivado: 0,35 × núcleo) |
|---|---|---|---|
| Se repite el Stress de feb-26 (en COP) | −4,2% | −7,8% | −1,5% |
| Peor semana del diario por activo (en COP, no simultánea) | −9,2% | −11,7% | −3,2% |
| Peor semana del intradía 2020-25 por activo (en USD) | −22,7% | −26,5% | −7,9% |

  Con el núcleo al 35%, el peor escenario consume el 79% del presupuesto de drawdown. Al 50% se rompería en el escenario intradía (≈ −11,4%).

### TW_02: CL_02 necesitará el 30% del portafolio en 6 meses

- La liquidez pasa a ser una **restricción dura**: el 30% (**S/ 300 000**, unos COP 342 millones) debe estar en efectivo o renta fija de corto plazo **desde hoy**, porque el núcleo puede estar en pérdida al momento del retiro. Retorno del núcleo a 6 meses (bootstrap): **P(pérdida) 31%**, p10 −7,2%, p5 −9,3%. Para la equiponderada: P(pérdida) 59% y p5 −15,8%.
- Si el retiro dependiera de vender el núcleo en el escenario p10, se materializaría una pérdida de **S/ 21 562** solo por la venta.
- **Efecto oculto:** el retiro sale de la liquidez y **eleva la exposición del saldo restante**. Invertir hoy el 49% se convierte en un **70%** después del retiro (P(cumplir) 0,74); el 60% se convierte en 86% (0,53), y el 70% en 100% (0,36).
- **Regla:** invertido hoy ≤ 70% × X*, donde X* es la exposición post-retiro que cumple con ≥ 90%. Con X* = 50%, **invertido hoy ≤ 35%** y liquidez ≥ 65% (30% reservado + 35% de colchón). Con 95% de confianza (X* = 45%): invertido ≤ 32%.
- Esto es mucho más estricto que el “≤ 70%” que se deduce directamente del enunciado del twist.

### TW_03: el COP se deprecia 8% frente al USD

- Es un movimiento de **11 desviaciones estándar** del cambio de 5 días observado (la mayor depreciación en 5 días de la muestra fue 2,2%; la volatilidad anual, 5,5%). Para el **riesgo**, el FX deja de ser irrelevante.
- **Efecto inmediato en COP** (moneda de riesgo de CL_02): los activos en USD **suben** 8% en COP y la liquidez en COP no se mueve.

| Configuración | En COP | Caída desde el nuevo pico si el COP revierte | En S/ (USD/PEN constante) |
|---|---|---|---|
| Equiponderada 100% | +8,0% | −7,4% | 0,0% |
| Núcleo 49% + liquidez en COP | +3,9% | −3,8% | −3,8% (S/ −37 778) |
| Núcleo 49% + liquidez en USD | +8,0% | −7,4% | 0,0% |
| Núcleo 49% + 30% en COP (retiro) + 21% en USD | +5,6% | −5,3% | −2,2% (S/ −22 222) |
| **Núcleo 35% + 65% en COP** | **+2,8%** | — | **−4,8% (S/ −48 148)** |

- **Lectura en PEN:** si USD/PEN se mantiene constante, el cruce pasa de 1.140 a 1.231 COP por S/, así que el COP también se deprecia 8% frente al PEN. Un saldo en COP pierde 7,4% medido en S/, y lo invertido en USD no cambia en S/. **Esto es traducción contable, no pérdida del cliente:** su pasivo (el retiro) y su tolerancia están en COP, y en COP el portafolio **gana**. El retiro de 30% equivale a S/ 277 778 después del shock (antes, S/ 300 000).
- **¿La liquidez debe estar en USD o en COP?** La reserva del retiro (30%) debe estar **en COP**, porque calza con la moneda del pasivo. En USD tendría un IC95 de ±7,7% en 6 meses, es decir, **±S/ 23 062**, y además expondría al cliente a que el COP revierta justo antes del retiro. El colchón de largo plazo podría estar en USD (cobertura del poder de compra), pero en los datos **no hay cobertura natural medible** (correlación entre USD/COP y el núcleo: 0,03). Además, cuanto más USD, más se expone el cliente a la reversión: con todo en USD, una reversión completa consume el 74% del presupuesto de 10%.

### Escenario combinado (TW_01 como repetición del Stress + TW_03 + reserva de TW_02)

| Cartera | En COP | En S/ |
|---|---|---|
| Equiponderada 100% | 0,0% (la depreciación compensa la caída de −7,4%) | −7,4% (S/ −73 887) |
| Núcleo 100% | +3,9% | −3,8% (S/ −37 556) |
| **Núcleo 35% + 65% en COP** | **+1,4%** (sin FX: −1,3%) | −6,1% (S/ −61 293) |

En COP, la moneda que manda, la recomendación queda muy lejos del límite. La depreciación **disfraza** las caídas de la equiponderada: por eso hay que medir el drawdown desde el nuevo pico.

---

## 6. Riesgos, supuestos y limitaciones

- **Moneda de reporte: PEN. El riesgo se mide en la moneda base del cliente.** Los montos en S/ usan el FX fijo del 2026-08-14 (USD/PEN 3,6802; USD/COP 4.195,52; cruce 1.140,02). Convertir los drawdowns en COP a S/ con un tipo fijo es una traducción de magnitud, no una medición del riesgo en PEN.
- **Un solo año de datos sintéticos y gaussianos.** No hay colas gruesas ni agrupamiento de volatilidad, y el calendario incluye feriados. Los mercados reales tienen colas más gruesas, así que las probabilidades de cumplimiento estimadas son **optimistas**.
- **Un único episodio Stress de 10 días.** Cualquier afirmación sobre regímenes tiene muy poca potencia estadística.
- **Sesgo de retrospectiva en el núcleo:** A08 entra en el núcleo solo cuando el train incluye la caída de A02 (feb-26). Con información hasta enero, el criterio “menor DD” habría elegido A02.
- **Tasas:** la sensibilidad no está identificada (la tasa no se movió). TW_01 se evalúa con escenarios y con la teoría, no con estimaciones.
- **El intradía** se descarta como historia, pero si fuera el “mundo real”, la exposición de CL_02 debería ser bastante menor: el núcleo cae más de 10% en el 82% de los años.
- **Liquidez a rendimiento 0** (conservador en retorno; la liquidez en COP real rendiría tasa local). Compra y mantenimiento sin costos.
- **Bootstrap por bloques de 20 días:** preserva la dependencia de corto plazo, pero no genera regímenes que no estén en la muestra. El IC90 de la factibilidad es amplio (0% a 7,3%).
- Supuesto de **USD/PEN constante** en TW_03, porque el twist no menciona el PEN; la correlación de USD/PEN con USD/COP en la muestra no se usó para extrapolar un shock 11 veces mayor que lo observado.

---

## 7. Implicaciones para la etapa 3 (hipótesis actualizada)

**H1′ (actualiza H1):** para CL_02, una cartera con un **núcleo defensivo** (A01, A04, A05, A08; el peso de A08 no se justifica como cobertura de tasas) con **exposición en renta variable ≤ 35% del patrimonio hoy**, una **reserva del 30% en liquidez en COP** para el retiro de 6 meses y un colchón adicional en liquidez mantiene el drawdown en COP ≤ 10% con probabilidad ≥ 90% (bootstrap) **y** en el walk-forward, incluso en los escenarios del twist.

| Elemento | Cambio frente a la etapa 2 |
|---|---|
| Variable de decisión principal | **Exposición X** (antes: pesos + X). Los pesos dentro del núcleo importan poco porque las correlaciones son ruido (H4): usar pesos iguales o por inversa de volatilidad, no optimizados |
| Métrica principal | P(DD ≤ 10% en COP), con bootstrap por bloques **y** walk-forward, no solo un drawdown puntual de test |
| Restricción nueva | Liquidez en COP ≥ 30% (TW_02); exposición post-retiro ≤ X* |
| Escenarios obligatorios | Repetición del Stress, peor semana del intradía (TW_01), COP ±8% con reversión (TW_03) |
| Línea base | Equiponderada al 100%: DD −19,0% (S/ −189 702 sobre S/ 1 000 000) |
| Valor a reportar (en S/) | Pérdida máxima evitada frente a la línea base: núcleo al 50%, mediana S/ 100 612 y p10 S/ 164 657; núcleo al 35%, mediana S/ 117 425 y p10 S/ 190 929. Costo: menor retorno esperado (por cuantificar en la etapa 3) |
| Correcciones para el dashboard y el pitch | Apalancamiento en LTM (A06: 0,68x, no 2,5x); “4/5 eventos” solo en dirección (1/5 significativo); marcar el revenue de ISS_06 en gold |
