# Encuadre del problema: cliente CL_02 (preservación patrimonial)

Bloque 2, *Find the signal*. Cifras reproducibles con `python src/senales.py` sobre la serie diaria limpia (ago-2025 a ago-2026). Las reglas de limpieza están en `docs/validacion_datos.md`.

## 1. El cliente

| Campo | CL_02 Patrimonio Estable |
|---|---|
| Moneda base | COP |
| Horizonte | 36 meses |
| Tolerancia al riesgo | Media-Baja |
| Caída máxima tolerada | **10%** |
| Necesidad de liquidez | Media |
| Prioridad | Preservación + crecimiento moderado |
| Restricción | **Máx. 25% en activos de alta volatilidad** |

Supuesto nuestro: "alta volatilidad" = volatilidad anual > 30%. Con eso, son de alta volatilidad VF_A02, VF_A03, VF_A06 y VF_A07.

## 2. El problema aterrizado

> ¿Qué cartera recomendamos hoy a un cliente en pesos colombianos que quiere preservar su patrimonio y crecer moderado, sin caer más de 10%, y qué evidencia la sostiene?

**Por qué CL_02:** es el cliente donde la restricción de riesgo es la que manda, así que el análisis aporta más.

- **Ningún activo por sí solo cumple la caída máxima de 10%.** La menor caída del año es 13.5% (VF_A05).
- **Diversificar sin criterio tampoco cumple:** la cartera equiponderada rinde -3.7% en COP y cae 17.2%.
- **De 60 000 carteras probadas, 9 381 cumplen el tope de 25% en alta volatilidad, pero solo 58 cumplen además la caída máxima de 10%.**

El valor está en construir la cartera, no en elegir un activo.

## 3. Qué está ocurriendo (mercado, en USD)

| Activo | Sector, país | Retorno año | Volatilidad | Caída máx. | Lectura |
|---|---|---|---|---|---|
| VF_A05 Aurora Health | Health Care, EE.UU. | **+31.9%** | 24% | -13.5% | Precio y fundamentales al alza (utilidad +50%, menos deuda) |
| VF_A04 Lima Financial | Financials, Perú | **+20.5%** | 28% | -17.4% | Sube en el año, pero -4.4% en 3 meses y margen EBITDA de 33.7% a 30.4% |
| VF_A08 Atlas Utilities | Utilities, EE.UU. | -14.2% | **15%** | -22.2% | Precio a la baja, fundamentales mejoran (utilidad +79%, caja neta) |
| VF_A01 Andes Consumer | Consumer Staples, Colombia | -10.0% | 20% | -27.4% | Precio a la baja, fundamentales mejoran (EBITDA +15%); sube en días de estrés |
| VF_A02 Pacifica Digital | Technology, Perú | -13.8% | 45% | -55.4% | Dos eventos negativos; 53% bajo su máximo |
| VF_A07 Sierra Materials | Materials, Chile | -26.7% | 38% | -36.2% | Evento de demanda: -15% en 20 días |
| VF_A03 Cordillera Energy | Energy, Colombia | -26.5% | 35% | -42.5% | Evento positivo que no se sostuvo |
| VF_A06 Norte Industrials | Industrials, México | -22.4% | 34% | -37.1% | Plano en 3 meses |

## 4. Señales que explican lo que ocurre

1. **Calidad defensiva:** A01 y A08 tienen la menor volatilidad (20% y 15%) y la menor sensibilidad al mercado (beta 0.42 y 0.34). Sus fundamentales mejoran aunque el precio cae.
2. **Comportamiento en estrés (9 al 20 de feb de 2026):** A01 subió (+0.27% diario promedio) y A05 apenas bajó (-0.15%). A02 cayó -2.69% diario y A04 y A06 cerca de -1.1%.
3. **Eventos:** explican las peores caídas (A02 y A07, ambos de severidad alta). Son riesgo idiosincrático que una cartera diversificada absorbe.
4. **Correlaciones bajas (0 a 0.26):** combinar activos reduce mucho la caída de la cartera.
5. **Tipo de cambio:** el USD/COP subió 2.56% en el año. Los activos en USD rindieron más para un cliente en pesos: A05 pasa de +31.9% a +35.3% y A04 de +20.5% a +23.6%.

## 5. Qué significa para CL_02

Carteras que cumplen todo (en COP, último año):

| Cartera | Retorno | Caída máx. | Pesos |
|---|---|---|---|
| Menor caída | +11.5% | -9.5% | A05 34%, A04 22%, A01 14%, A06 13%, A08 13% |
| Mayor retorno | +21.1% | -10.0% | A05 57%, A04 21%, A06 17% |

**Hipótesis de decisión:** cartera de núcleo defensivo (A05, A01, A08) más A04, con un máximo de 25% en alta volatilidad, buscando la menor caída y no el mayor retorno. La de mayor retorno queda descartada porque concentra 57% en un activo y queda justo en el límite de 10%.

## 6. Riesgos y supuestos (pregunta 5 del dashboard)

- **Muestra ajustada:** las carteras se eligieron con el mismo año que se mide. Hay que validar fuera de muestra.
- **Solución frágil:** solo 58 de 60 000 carteras cumplen. Un cambio chico en los datos puede romper el límite de 10%.
- **Concentración en A05:** 34% del peso en un solo activo.
- **A04 pierde impulso:** margen a la baja y 3 meses negativos.
- **El tipo de cambio puede revertirse:** si el peso se aprecia, se pierde el 2.6% a favor.
- **Horizonte de 36 meses contra 1 año de datos:** la historia larga (2020 a 2025) muestra caídas de 50% a 80% en todos los activos. Si ese escenario se repite, el límite de 10% no se sostiene sin efectivo o renta fija, que no están en el universo.
- **Umbral de alta volatilidad (30%):** es un supuesto nuestro. Si cambia, cambia la cartera.

## 7. Plan para el bloque 3 (*Find the value*, 75 min)

1. **Databricks, bronze a silver:** cargar los CSV y aplicar las reglas de limpieza de `docs/validacion_datos.md`.
2. **Gold:** métricas por activo en COP (retorno, volatilidad, caída, beta, retorno en estrés), fundamentales (crecimiento, margen, deuda neta/EBITDA) y marca de eventos.
3. **Score defensivo por activo:** combinar riesgo, fundamentales y eventos.
4. **Cartera con restricciones:** minimizar la caída con máx. 25% en alta volatilidad, máx. 10% de caída y un tope por activo (por ejemplo 35%) para evitar concentración.
5. **Prueba fuera de muestra:** elegir pesos con los primeros 8 meses y medir los últimos 4.
6. **Estrés:** repetir el periodo de feb-2026 y un shock de apreciación del COP.

## 8. Borrador de respuestas del dashboard

1. **¿Qué está ocurriendo?** Mercado a la baja: 6 de 8 activos caen en el año, con eventos que golpean a tecnología y materiales.
2. **¿Qué lo explica?** Eventos idiosincráticos de severidad alta, un episodio de estrés en feb-2026 y fundamentales que divergen del precio en los defensivos.
3. **¿Qué significa para CL_02?** Ningún activo solo ni una cartera equiponderada cumple su caída máxima de 10%. Solo una cartera construida con criterio lo logra.
4. **¿Qué debería hacer?** Cartera de núcleo defensivo (A05, A01, A08 y A04), con ≤25% en alta volatilidad y pesos de menor caída.
5. **¿Qué podría cambiarla?** Un peso colombiano que se aprecie, la pérdida de impulso de A04, un nuevo episodio de estrés o un umbral distinto de alta volatilidad.
