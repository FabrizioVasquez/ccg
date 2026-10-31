# Etapa 2 — Find the signal: resumen

> **Foco:** CL_02 “Patrimonio Estable” (COP, horizonte 36m, tolerancia Media-Baja, **drawdown máx. 10%**, máx. 25% en activos de alta volatilidad).
> **Señal:** con este universo, **ninguna cartera 100% invertida en acciones respeta de forma robusta el límite de 10% de CL_02**. La diversificación ingenua lo rompe casi al doble. La decisión de valor no es solo *qué* comprar, sino **cuánto exponer**.

**Materializado en Databricks:** catálogo `credicorp_dq` (alcance temporal: **un solo dominio**). Lee de `credicorp_dq.silver.*` y escribe `credicorp_dq.gold.etapa2_*` con el notebook [`notebooks/etapa2_find_the_signal.py`](../notebooks/etapa2_find_the_signal.py). Réplica local: `src/analysis/etapa2_signal.py`. Fecha de “hoy” en los datos: **2026-08-14**.

¿Nuevo en el tema? Lee primero la [guía para junior](etapa2_guia_junior.md). Las pruebas de robustez, el plan de limpieza e imputación y el impacto del twist están en el [reporte de ciencia de datos](etapa2_reporte_cientifico_datos.md).

---

## 1. Base de confianza (lo que aprendimos limpiando)

| Hallazgo | Impacto | Tratamiento |
|---|---|---|
| **El diario y el expanded no coinciden** en el periodo común. Parten del mismo precio el 01-ago-2025 y luego se separan (correlación de retornos ≈ 0; diferencia media de USD 7,9). | Dos versiones de la verdad | Se usa **el diario** como fuente. Reacciona en la dirección del evento en **4 de 5** eventos; el intradía, en 2 de 5 (cifra de Databricks). *Matiz del reporte de ciencia de datos: solo 1 de 5 (A02) es estadísticamente significativo; el criterio es de dirección, no de significancia.* El expanded queda solo como historia previa a ago-2025. |
| Alias de IDs (`VF-A1`, `VFA03`, `VF_A6`, `VF-A6`, `VF-A4`, `ISS04`) | Activos partidos en varios IDs | Se homologan al ID canónico (política g-01) |
| 2 fechas en formato `MM/DD/YYYY` y 7 filas duplicadas | Rompen la PK (asset_id, date) | Se pasan a ISO y se deduplican (g-02, g-04) |
| `close = 3589` (VF_A06, 2026-03-23), fuera del rango [low, high] | Un retorno falso de +10.000% | Silver lo corrige como error de escala ×100 → 35,89 |
| `us_inflation_yoy` con 258 nulos (es un dato mensual) | Huecos en el macro | Forward-fill |
| **`Q4-2024` de ISS_02 corresponde en realidad a 2025-06-30** (por su posición en la serie) | El mapeo del doc de arquitectura (→ 2024-12-31) duplicaba un trimestre y perdía otro | Se infiere el trimestre por secuencia. Corrige `data_mesh_architecture.md` |
| Revenue de ISS_06 en 2025-06-30 = 1.845,7 (las demás cifras rondan 2.800); además venía como texto con coma | El margen salta de 15% a 24% | Se convierte a número y se marca como outlier (no se usa en ratios) |
| Los CSV vienen en **UTF-8 con BOM**, no en latin-1 | Leerlos como latin-1 corrompe los acentos | Se leen con `utf-8-sig`. Corrige `data_mesh_architecture.md` |

Resultado: 8 activos × 271 días hábiles, alineados 1:1 con el macro; 8 emisores × 8 trimestres de fundamentales.

---

## 2. Hipótesis descartada (pensamiento crítico)

**“El riesgo cambiario consume el drawdown de los clientes en COP y PEN”: descartada.**
En el periodo, el USD/COP se movió +2,6% con 5,5% de volatilidad anual y el USD/PEN −1,2% con 2,8%. El FX cambia el drawdown de cada activo en 1–2 puntos; no es lo que decide.

---

## 3. Por qué CL_02 (criterio: el cliente donde los datos más cambian la decisión)

Se simularon 200.000 carteras long-only aleatorias (Dirichlet), en la moneda base de cada cliente y con compra y mantenimiento durante el año:

| Cliente | Moneda | Límite DD | % de carteras que cumplen su restricción | % que además cumplen el drawdown | DD de la cartera equiponderada |
|---|---|---|---|---|---|
| CL_01 Crecimiento | USD | 22% | 69,8% | **33,7%** | −21,7% (cumple, al límite) |
| CL_02 Patrimonio Estable | COP | 10% | 13,2% | **0,01%** (≈20 de 200k) | **−19,0% (casi 2× su límite)** |
| CL_03 Diversificación Regional | PEN | 15% | 93,8% | **11,2%** | −23,2% |

- **CL_01:** casi cualquier cartera razonable funciona, así que el análisis cambia poco la decisión.
- **CL_02:** es el cliente con más en juego (busca preservar su patrimonio) y donde un error es más caro: la recomendación “diversifica en partes iguales” le habría hecho perder el doble de lo que tolera.
- **CL_03:** tiene una tensión interesante, que queda como señal secundaria. Las carteras con mejor retorno se concentran en EE. UU. (VF_A05), lo que choca con su objetivo de diversificación regional.

---

## 4. La señal: CL_02 necesita decidir la exposición, no solo la selección

**Todos los activos superan individualmente el 10% de drawdown** en COP. El menor es VF_A05 con −14,6%, seguido de VF_A04 con −18,6%.

**Prueba fuera de muestra:** se eligió la cartera con menor drawdown usando datos hasta el 2026-04-10 y se observó qué pasó después.

| | Drawdown entrenamiento (ago-25 → abr-26) | Drawdown prueba (abr-26 → ago-26) |
|---|---|---|
| Mejor cartera elegida en entrenamiento | −7,9% ✅ | **−11,5% ❌** |
| Cartera equiponderada | −16,3% ❌ | −12,4% ❌ |

Solo el **9,6%** de las carteras que respetan la restricción de volatilidad se mantienen dentro del 10% en el periodo de prueba, y no hay forma de saber de antemano cuáles serán.
**Conclusión:** con 100% en acciones, cumplir el límite de CL_02 depende de la suerte, no de la gestión. La palanca robusta es **dimensionar la exposición** (parte invertida + colchón de liquidez) para que el drawdown esperado quede bajo 10%.

### Evidencia que respalda qué activos forman el núcleo defensivo
| Activo | Por qué | Fundamentales (último trimestre vs. hace 1 año) |
|---|---|---|
| VF_A05 Aurora Health (EE. UU.) | Menor DD (−14,6%), +35% en el año, −2% en el episodio de Stress | Utilidad neta +50%; deuda neta/EBITDA LTM baja de 0,37x a 0,31x |
| VF_A08 Atlas Utilities (EE. UU.) | Menor volatilidad (16%) y correlación ~0 con VF_A01 | Caja neta positiva (deuda neta/EBITDA LTM −0,24x) |
| VF_A04 Lima Financial (Perú) | +24% en el año, DD −18,6% | Revenue +10%, apalancamiento estable (~0,3x LTM) |
| VF_A01 Andes Consumer (Colombia) | Volatilidad 20%, +2,2% en el Stress | Margen EBITDA 33%, el más alto |

Quedan **fuera** o limitados al 25% de alta volatilidad: VF_A02 (−24,5% en el Stress de feb-26 y un evento operacional High), VF_A07 (evento de demanda High, −22% en 3 meses), VF_A06 (el más apalancado del universo, aunque bajo en términos absolutos: 0,68x LTM) y VF_A03.

> **Corrección (31-oct):** en la versión anterior de este documento, el apalancamiento se calculó con el EBITDA de un solo trimestre, lo que lo sobrestimaba unas 4 veces. Las cifras de arriba usan EBITDA LTM (últimos 12 meses), igual que `gold.fundamentals_ratios`. Detalle en el [reporte de ciencia de datos](etapa2_reporte_cientifico_datos.md).

---

## 5. Hipótesis y unidad de análisis (insumo para la etapa 3)

**Hipótesis H1:** para CL_02, una cartera con un **núcleo defensivo** (A05, A08, A04, A01), alta volatilidad ≤ 25% y una **exposición total X% < 100%** (el resto en liquidez) mantiene el drawdown en COP ≤ 10% **fuera de muestra**, con un retorno superior al de la cartera equiponderada.

| Elemento | Definición |
|---|---|
| **Unidad de análisis** | Cartera de CL_02 × día, NAV en COP |
| **Variables de decisión** | Pesos por activo + % de exposición total (el resto en liquidez) |
| **Métrica principal** | Max drawdown en COP ≤ 10%, fuera de muestra |
| **Métricas secundarias** | Retorno en COP, % en alta volatilidad ≤ 25%, comportamiento en el régimen Stress |
| **Línea base a vencer** | Cartera equiponderada al 100% (DD −19%) |
| **Validación** | Entrenamiento hasta 2026-04-10, prueba posterior (walk-forward si alcanza el tiempo) |

**Supuestos explícitos (a defender ante el jurado):**
1. **Liquidez:** no está en el universo de activos. Se asume rendimiento 0 en COP, lo que es conservador. El perfil “liquidez Media” la justifica.
2. **Alta volatilidad:** se define como volatilidad anual > 30% (A02, A03, A06, A07). El perfil del cliente no la define.
3. **Compra y mantenimiento** sin costos de transacción.
4. **Datos sintéticos de un solo año.** Las conclusiones valen para este universo y periodo.

---

## 6. Qué cambiaría la recomendación
- Un nuevo episodio de **Stress**, como el de feb-26, donde VF_A02 cayó 24,5%: exigiría bajar aún más la exposición.
- Un deterioro de los fundamentales de VF_A05, el activo con más peso en el núcleo.
- Que el cliente acepte un drawdown mayor o redefina qué es “alta volatilidad”.

## 7. Siguiente paso (etapa 3 — Find the value)
1. ~~Materializar en Databricks~~ ✅ hecho en `credicorp_dq.gold.etapa2_*`. Alcance temporal: un solo dominio (`credicorp_dq`); la separación en dominios de data mesh queda pospuesta.
2. Optimizar los pesos del núcleo y la exposición X% en entrenamiento, y validar en prueba.
3. Cuantificar el valor: drawdown evitado en COP frente a la cartera equiponderada, sobre un patrimonio de referencia.
