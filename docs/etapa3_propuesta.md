# Etapa 3 — Propuesta para CL_02 (resumen defendible)

> **Notebook con gráficos:** `/Workspace/Users/cesaraop.12@gmail.com/hackaton-credicorp/07_etapa3_propuesta_cl02` (fuente: [`notebooks/etapa3_propuesta_cl02.py`](../notebooks/etapa3_propuesta_cl02.py)).
> **Tablas:** `credicorp_dq.gold.etapa3_*`. **Moneda:** el riesgo se mide en COP (moneda base de CL_02) y los montos se reportan en S/ sobre un patrimonio de S/ 1 000 000 (FX 2026-08-14: USD/PEN 3,6802; USD/COP 4.195,52).

## La recomendación
| Bloque | % patrimonio | Monto |
|---|---|---|
| Núcleo defensivo: A08 33% · A01 27% · A05 22% · A04 19% del núcleo | **28%** | S/ 280 000 |
| Reserva para el retiro de 6 meses (TW_02), liquidez en COP | 30% | S/ 300 000 |
| Liquidez adicional en COP | 42% | S/ 420 000 |

**Por qué 28%:** la exposición máxima que cumple el límite de 10% con 95% de confianza es X* = 40%. Como el 30% sale en 6 meses, hoy se invierte 70% × 40% = 28%, para que tras el retiro la exposición siga en 40%.

## 1. Por qué CL_02 y no CL_01 ni CL_03
Criterio: **valor de la información**, es decir, dónde la decisión con datos difiere más del consejo ingenuo ("reparte en partes iguales") y dónde el error cuesta más.

| | CL_01 Crecimiento (USD, 22%) | **CL_02 Patrimonio Estable (COP, 10%)** | CL_03 Regional (PEN, 15%) |
|---|---|---|---|
| Carteras que cumplen (de 200k) | 33,8% | **0,01%** | 11,2% |
| P(la equiponderada rompe el límite) | 29% | **92%** | 69% |
| Exceso esperado, en % de la tolerancia | 7% | **85%** | 35% |
| Lectura | El análisis cambia poco | **Los datos cambian la decisión** | Candidato #2; sus mejores carteras se concentran en EE. UU., en contra de su objetivo regional |

Además, 2 de los 3 shocks del twist apuntan a CL_02 (el retiro del 30% y el COP −8%).

## 2. Métricas defendibles
| Métrica | Uso | Por qué |
|---|---|---|
| **Max drawdown en COP** | Objetivo | Es lo que el cliente declaró tolerar, medido en su moneda |
| **P(DD ≤ 10%)** (bootstrap por bloques, 2000 réplicas) | Elegir la exposición | Un año es un solo camino; la probabilidad captura la incertidumbre |
| **Exceso esperado sobre la tolerancia** | Elegir el cliente | Mide el costo de la heurística ingenua |
| **Volatilidad** | Elegir el núcleo | **Es la única métrica que persiste**: ρ train→test de 0,93–0,98 en 7 cortes, frente a −0,24–0,60 del drawdown y ≈ 0 del retorno |
| **Pérdida evitada en S/** | Comunicar el valor | Traduce el riesgo a dinero |
| ❌ Retorno, Sharpe, betas a tasa/FX | No se usan para decidir | No son predecibles ni significativas con 1 año de datos |

## 3. Validación sin mirar el futuro (walk-forward, 7 cortes dic-25 → jun-26)
| Estrategia | Cumple DD ≤ 10% fuera de muestra |
|---|---|
| **Propuesta (núcleo por volatilidad × X elegido con el pasado)** | **7/7** |
| Equiponderada con la misma exposición X | 6/7 |
| Núcleo al 100% | 0/7 |
| Cartera optimizada en train al 100% | 0/7 |
| Equiponderada al 100% | 0/7 |

**Resultado honesto:** casi todo el valor viene de **decidir cuánto invertir**. Elegir el núcleo por volatilidad agrega un margen menor pero consistente: cae ~0,7 pp menos en 7 de 7 cortes y es lo que hace cumplir en dic-25.

## 4. Valor (2000 escenarios simulados)
| | Propuesta | Equiponderada 100% | Equiponderada con la misma exposición |
|---|---|---|---|
| P(cumple DD ≤ 10%) | **99,9%** | 7,1% | 97,7% |
| Drawdown mediano | −3,6% | −17,6% | −5,2% |
| Retorno mediano a 1 año | +1,7% | −2,8% | — |

**Pérdida evitada frente a la equiponderada:** mediana de **S/ 137 725** y, en el escenario adverso (p90), de **S/ 229 404** por cada S/ 1 000 000.
*Advertencia:* esta cifra se estima con los mismos datos con que se eligió X. La evidencia fuera de muestra es el walk-forward.

## 5. Twist
| Shock | Impacto en el patrimonio con la propuesta |
|---|---|
| TW_01 (tasa +65 pb) ≈ repetición del Stress feb-26 | −1,1% (S/ −10 723) |
| TW_01 ≈ peor semana del intradía 2020-25 (−22% en el núcleo) | −6,1% (S/ −61 498), dentro del límite |
| TW_03 (COP −8%) | +2,2% en COP. La reserva en COP no se mueve, y debe estar en COP porque el retiro es en COP |

## 6. Cuestionamiento de los datos
- Hay **un año sintético**, con retornos ~normales (0 de 8 activos rechazan la normalidad), así que el riesgo real podría ser mayor. Lo mitigamos exigiendo 95% de confianza y aplicando el estrés intradía.
- El **intradía contradice al diario** (correlación ≈ 0,06). Usamos el diario y dejamos el intradía solo como escenario de estrés.
- El drawdown de la equiponderada es muy incierto: −19% histórico, con IC90 de [−31%; −9%]. Por eso decidimos con probabilidades y no con un solo número.
- Hay solo **5 eventos** y 1 significativo. Son contexto, no señal.
- La **liquidez no existe en el universo**: suponemos que rinde 0%, lo que es conservador.

## 7. Qué cambiaría la recomendación
El costo de oportunidad si el mercado sube (coherente con "preservación + crecimiento moderado"), colas más gruesas que las simuladas, que el cliente amplíe su tolerancia (la curva de exposición da el nuevo X) o un umbral de alta volatilidad distinto (la regla se recalcula sola).
