# Contexto de negocio — Value Finders (Credicorp Capital, 31-oct-2026)

> Documento vivo. Fuentes: [`brief.md`](brief.md), [`data_mesh_architecture.md`](data_mesh_architecture.md) y los encabezados de `dataset_start/` (no versionado).

## Rama de negocio
**Wealth Management / asesoría patrimonial.** Somos el equipo de Data & Analytics de una compañía de inversiones que asesora a clientes sobre qué hacer con su patrimonio (brief p.9–10). La información de mercado viene de la mesa de inversiones.

## Pregunta central (brief p.11)
> ¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?

## Clientes (de `05_client_profiles`)
| client_id | Perfil | Moneda base | Horizonte | Riesgo | Max drawdown | Liquidez | Restricción |
|---|---|---|---|---|---|---|---|
| CL_01 | Crecimiento Global | USD | 18m | Alta | 22% | Baja | Máx. 45% en un sector |
| CL_02 | Patrimonio Estable | COP | 36m | Media-Baja | 10% | Media | Máx. 25% en activos de alta volatilidad |
| CL_03 | Diversificación Regional | PEN | 24m | Media | 15% | Media | ≥3 países y ≥3 sectores |

**Cliente protagonista:** se elige con los datos al cerrar “Find the truth”. Criterio: el cliente para el que los datos cambian más la decisión.

## Universo invertible (de `04_asset_reference`)
8 activos en USD (VF_A01..VF_A08). 6 son ADR latinoamericanos (CO, PE, MX, CL) y 2 empresas de EE. UU. Cubren 8 sectores distintos.

## Entregables (brief p.16–19)
1. **Solución analítica funcional:** MVP reproducible en Python + SQL sobre Databricks.
2. **Decision Dashboard:** una vista que responda qué ocurre, qué lo explica, qué significa para el cliente, qué hacer y qué podría cambiar la recomendación.
3. **Value Pitch:** 5 min de demo + 2 min de Q&A. Se empieza por el dashboard.

## Criterios del jurado (técnico + negocio)
Problem framing · criterio técnico · comunicación · pensamiento crítico · colaboración.

## Método de trabajo
Explorar → materializar → validar → defender → iterar. Cada ciclo deja algo visible en Databricks.

| Ciclo | Bloque del evento | Qué queda visible en Databricks |
|---|---|---|
| Explorar | Find the truth (35 min) | bronze/silver + quality checks (fallan → pasan) |
| Materializar | Find the signal (55 min) | Hipótesis + unidad de análisis + tabla gold de señal |
| Validar | Find the value (75 min) | Recomendación cuantificada para el cliente |
| Defender | Make it matter (35 min) | Dashboard de una vista + pitch |

**Regla:** no se modela sin una hipótesis explícita y una unidad de análisis definida.

## Decisiones tomadas
- La arquitectura data mesh (2 dominios) se usa como base de confianza y se resume en 1 slide del pitch. El protagonista del pitch es la decisión para el cliente.
- Los datos no se versionan (el repo es público). Se cargan a un Volume de Databricks.
- **Moneda de reporte: sol peruano (PEN, S/)** (31-oct-2026, por recomendación recibida). Todos los montos del análisis, el dashboard y el pitch se expresan en S/. El riesgo (drawdown frente a la tolerancia) se sigue midiendo en la moneda base de cada cliente: CL_02 en COP, CL_03 en PEN y CL_01 en USD.
- Alcance temporal: un solo dominio en Databricks, el catálogo `credicorp_dq`.

## Observaciones por validar (todavía no son hipótesis)
- Todos los activos están en USD, pero CL_02 (COP) y CL_03 (PEN) miden su patrimonio en moneda local. El tipo de cambio podría consumir parte del drawdown tolerado.
- Problemas de calidad declarados en el doc de arquitectura (alias de IDs, fechas mixtas, outliers, 258 nulos en inflación). Ojo: el doc dice que `05_client_profiles` viene en latin-1, pero el archivo es UTF-8 con BOM. Si se lee como latin-1 aparecen caracteres corruptos (“MÃ¡x.”). Se verifican en “Find the truth”.

## Preguntas abiertas
Ver la sección “Datos no especificados” de [`brief.md`](brief.md): asignación vs. activo único, métrica formal de evaluación, etc.
