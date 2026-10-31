# Explicación del análisis (para entenderlo y defenderlo ante el jurado)

Guía en lenguaje simple de lo que hicimos y por qué. Detalle técnico en `docs/validacion_datos.md` y `docs/encuadre_problema.md`; cifras reproducibles con `python src/senales.py`.

## 1. Qué pregunta estamos respondiendo

> ¿Qué cartera recomendamos **hoy** a CL_02 (un cliente en pesos colombianos que quiere preservar su patrimonio y no tolera caer más de 10%), y con qué evidencia?

"Hoy" es el último dato disponible: **14 de agosto de 2026**. Todo lo que mostramos va de **ago-2025 a ago-2026**, unos 271 días hábiles.

## 2. Primer paso: ¿podemos confiar en los datos?

Antes de analizar revisamos la calidad. Encontramos dos tipos de problema.

**Errores chicos que se corrigen con reglas simples.** Por ejemplo:

- duplicados;
- IDs mal escritos (`VF-A1` en vez de `VF_A01`);
- fechas en dos formatos distintos;
- volúmenes con sufijo "K";
- un precio con un error de ×100: VF_A06 aparece cerrando en 3589 cuando cotiza alrededor de 35.

**Un problema de fondo.** Hay dos archivos de precios:

- **Diario:** un año, de ago-2025 a ago-2026.
- **Cada 10 minutos ("expanded"):** de 2020 a 2026.

Lo lógico sería que el cierre de cada día coincida en los dos archivos. **No coincide.** Arrancan iguales el 1 de ago-2025 y después se separan, con una diferencia típica de 12%. Además, los eventos (noticias) se notan en el diario y casi no en el otro.

**Decisión que tomamos:** usar el **diario** para el análisis actual, porque es el que refleja los eventos. El expanded queda solo como historia de referencia. Es una decisión que tenemos que poder defender, y una de las preguntas para el jurado.

## 3. Qué medimos en cada activo

Son 8 acciones (VF_A01 a VF_A08), todas cotizadas en USD. Para cada una calculamos:

| Métrica | Qué significa | Por qué importa para CL_02 |
|---|---|---|
| **Retorno** | Cuánto subió o bajó en el periodo | El cliente quiere crecer, aunque sea poco |
| **Volatilidad** | Cuánto se mueve el precio día a día, en términos anuales. 15% es tranquilo, 45% es muy movido | Su restricción es máx. 25% en activos de alta volatilidad |
| **Caída máxima (drawdown)** | La peor caída desde un máximo hasta un mínimo. Si algo sube a 100 y luego baja a 80, cayó 20% | **Es la restricción clave: no puede pasar de 10%** |
| **Beta** | Cuánto se mueve el activo cuando se mueve el mercado. Beta 1 = igual que el mercado; 0.4 = se mueve menos de la mitad | Una beta baja protege cuando el mercado cae |
| **Correlación** | Si dos activos suben y bajan juntos. 1 = siempre juntos; 0 = independientes | Si son independientes, combinarlos reduce la caída total |

**Resultado del año:**

- Solo **A05 (Aurora Health, +32%)** y **A04 (Lima Financial, +20%)** subieron. Los otros 6 cayeron.
- **Ningún activo cayó menos de 10% en su peor momento.** El mejor fue A05, con una caída máxima de 13.5%.

Ese segundo punto es el centro del caso: **CL_02 no puede comprar ningún activo solo.**

## 4. Las 5 señales

1. **Defensivos con buenos fundamentales.** A01 (consumo, Colombia) y A08 (utilities, EE.UU.) bajaron de precio, pero sus empresas mejoran: más EBITDA (la ganancia operativa), más utilidad y menos deuda. Además son los que menos se mueven (volatilidad de 15% a 20%, beta de 0.3 a 0.4). Cuando el precio cae y el negocio mejora, puede ser una oportunidad o una trampa: es una señal a defender, no una certeza.
2. **Comportamiento en estrés.** El archivo macro marca un periodo de *Stress* del 9 al 20 de feb de 2026. Esos días, A01 subió y A05 casi no se movió, mientras A02 (tecnología) cayó 2.7% diario. Es evidencia de cuáles activos protegen cuando el mercado va mal.
3. **Eventos.** Las peores caídas tienen explicación. A02 sufrió una falla de proveedor de nube (-15% en 20 días) y después un ajuste de valoración del sector tecnológico. A07 sufrió un golpe de demanda (-15%). Son riesgos de una empresa puntual, y por eso diversificar ayuda.
4. **Correlaciones bajas.** Los activos casi no se mueven juntos (de -0.01 a 0.26), así que una cartera combinada cae mucho menos que cada activo por separado.
5. **Tipo de cambio.** El dólar subió 2.6% frente al peso colombiano en el año. Un cliente en pesos que tiene activos en dólares gana ese 2.6% adicional: A05 pasa de +32% en USD a +35% en COP. Pero si el peso se aprecia, ese efecto se revierte.

## 5. Cómo probamos las carteras

**Método:** generamos **60 000 combinaciones de pesos al azar**, del tipo "34% A05, 22% A04, 14% A01...". Para cada una simulamos qué habría pasado en el año, convertido a pesos colombianos, y revisamos dos condiciones:

1. ¿Tiene máximo 25% en activos de alta volatilidad? Definimos alta volatilidad como más de 30% anual: A02, A03, A06 y A07.
2. ¿Su caída máxima fue de 10% o menos?

**Resultado para CL_02:**

- 9 381 carteras cumplen la condición 1.
- **Solo 58 cumplen las dos.**
- La cartera equiponderada (12.5% en cada activo) cae 17%: **no cumple**.

**La cartera de referencia** (la de menor caída entre las 58):

| A05 | A04 | A01 | A06 | A08 | Retorno (COP) | Caída máx. |
|---|---|---|---|---|---|---|
| 34% | 22% | 14% | 13% | 13% | **+11.5%** | **-9.5%** |

**Por qué no elegimos la de mayor retorno (+21%):** pone 57% en un solo activo y su caída queda justo en 10%, sin margen. Para un cliente que quiere preservar, no es defendible.

## 6. Por qué CL_02 y no otro cliente

| Cliente | Carteras viables | Lectura |
|---|---|---|
| CL_01 Crecimiento | ~20 800 | Fácil de cumplir; termina en una apuesta a A05 y A04 |
| **CL_02 Preservación** | **58** | **Difícil: aquí el análisis marca la diferencia** |
| CL_03 Regional | ~8 500 | Viable, pero el sol peruano se apreció y juega en contra |

El mensaje para el jurado: **"para este cliente, el valor no está en elegir una acción, sino en construir la combinación correcta"**.

## 7. Debilidades (nos las van a preguntar)

| Debilidad | Cómo responder |
|---|---|
| **Elegimos los pesos mirando el mismo año que medimos.** Es como estudiar con las respuestas del examen. | En el bloque 3 elegimos pesos con los primeros 8 meses y probamos en los últimos 4 |
| **Solo 58 de 60 000 cumplen: la solución es frágil** | Lo decimos abiertamente y lo mostramos como el principal riesgo de la recomendación |
| **Un año de datos para un horizonte de 36 meses** | La historia larga muestra caídas de 50% a 80% en todos los activos. Con solo acciones, el 10% no se garantiza a largo plazo |
| **El umbral de "alta volatilidad" (30%) lo pusimos nosotros** | Es un supuesto explícito; hay que probar la sensibilidad a 25% y 35% |
| **El tipo de cambio ayudó** | Probamos un escenario en que el peso se aprecia |

## 8. Preguntas para el jurado

**Sobre los datos (las más importantes):**

1. Los precios diarios y los de 10 minutos coinciden el 1 de ago-2025 y después divergen. ¿Cuál es la fuente oficial? ¿O son escenarios distintos a propósito?
2. VF_A06 cierra en 3589 el 23 de marzo de 2026 cuando cotiza alrededor de 35. ¿Es un error de carga que hay que detectar, o un evento?
3. Los ingresos de ISS_06 en jun-2025 (1 845.7) son 35% más bajos que los de los trimestres vecinos. ¿Es un error intencional?
4. ¿Los fundamentales tienen fecha de publicación? Sin ella, usar un trimestre antes de que se conozca sería usar información futura.

**Sobre el cliente y las reglas:**

5. ¿Qué umbral consideran "alta volatilidad" para la restricción de CL_02?
6. La caída máxima de 10%, ¿se mide en pesos colombianos o en dólares?
7. ¿Podemos recomendar mantener una parte en efectivo, o solo podemos usar los 8 activos?
8. ¿Hay que elegir un cliente o recomendar para los tres?

**Sobre el caso:**

9. El PDF dice que "una misma compañía puede presentarse como alternativa en distintos mercados e instrumentos", pero en los datos cada empresa tiene un solo activo. ¿Hay algo que no estemos viendo?
10. ¿"Hoy" es el 14 de agosto de 2026, el último dato disponible?

Si hay poco tiempo, priorizar la **1, la 5 y la 7**. Son las que más pueden cambiar la recomendación.
