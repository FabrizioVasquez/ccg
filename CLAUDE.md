# CLAUDE.md

Proyecto: hackathon Credicorp Capital - Value Finders. Ver `README.md` para el resumen.

## Contexto

- Pregunta guía: qué decisión de inversión recomendar a cada cliente hoy y con qué evidencia.
- Entregables: MVP en Python + SQL (Databricks), Decision Dashboard, Value Pitch.
- 3 clientes (`dataset_start/05_client_profiles.csv`) con restricciones duras: máx. 45% por sector (CL_01), máx. 25% en alta volatilidad (CL_02), al menos 3 países y 3 sectores (CL_03). Respetarlas en cualquier recomendación.
- Leer `REQUERIMIENTOS.md` (requisitos y pendientes) y `ANALISIS.md` (datos y ramas) antes de trabajar.

## Datos

- `dataset_start/` es la entrada cruda. No editarla en sitio: limpiar en una capa silver.
- Los CSV traen BOM en las cabeceras. Leer con `encoding="utf-8-sig"`.
- Todos los activos cotizan en USD; los clientes CL_02 y CL_03 están en COP y PEN. Convertir con el FX de `02_macro_raw.csv`.
- No inventar columnas ni cifras: validar contra los archivos.

## Trabajo

- `main` estable. Una rama `feat/*` por línea de trabajo (lista en `README.md`).
- Código en `src/`, SQL en `sql/`, notebooks en `notebooks/`, docs en `docs/`.
- Notas del equipo en Obsidian (`hackathon/Credicorp Capital - Value Finders/`). Si cambia algo relevante, actualizar la nota y el `.md` del repo.
- Idioma: español.
