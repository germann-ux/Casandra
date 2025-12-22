# Casandra v0 — Documento Unificado de Arquitectura e Integración

> **Objetivo**: unificar la **arquitectura interna** (componentes, carpetas, responsabilidades) y la **integración externa** (contratos, endpoints, sobres, reglas temporales y errores) sin incoherencias. Este documento es la referencia única de v0.

---

## 1) Propósito y Alcance (v0)

Casandra es un sistema de **análisis criminal** para Guanajuato. Ingiere, cura, almacena y analiza datos públicos; expone resultados claros, trazables y **auditables** a un LLM mediante contratos estables.

**Alcance v0**:
- ETL mínimo: CSV/ZIP → curado → Parquet/DuckDB.
- Consultor (solo lectura) al Depósito.
- Orquestador que valida/ejecuta pipelines de herramientas.
- Celador para validaciones, auditoría y manejo de errores.
- Expositor (API) con **dos modos**: *Plan API* (LLM-facing) y *Job API* (compatibilidad simple).
- Catálogo de herramientas versionadas (semver).

---

## 2) Terminología

- **LLM**: agente que razona a alto nivel y arma un **plan** de herramientas.
- **Intérprete**: valida y ejecuta el plan paso a paso (service bus lógico).
- **Tool**: unidad atómica especializada (e.g., `rank_por_delito`).
- **Envelope / Sobre**: formato uniforme de salida de cada tool (éxito o error).
- **Dataset watermark**: `min_date`, `max_date` y `dataset_version` (anclaje temporal).
- **Depósito**: Parquet/DuckDB de solo lectura para consultas del Consultor.

---

## 3) Vista de dominios y responsabilidades

```
LLM ⇄ Expositor → Orquestador → (Herramientas / Análisis / Consultor) → Empaquetador → Mensajero → LLM
                   │
                   └──────────────► Celador (validaciones, auditoría, errores)

ETL: Cargador → Curador → Depósito
Transversal: Auxiliares (config, reloj, log, utilidades)
```

**Componentes** (resumen):
- **Expositor**: API pública. Traduce HTTP a modelos internos. No contiene lógica de negocio.
- **Orquestador**: ejecuta pipelines de tools; delega a Consultor/Análisis; empaqueta resultados.
- **Consultor**: repositorio de lectura contra Parquet/DuckDB.
- **ETL**: Cargador/Curador/Depósito.
- **Celador**: validaciones, tipología de errores, auditoría (job_id).
- **Auxiliares**: config centralizada, **reloj único**, logging, utilidades.
- **Empaquetador/Mensajero**: presentación (json/markdown/tabular/gráfico) a partir del Sobre.

**Estructura de carpetas** (propuesta):

```
casandra/
├── expositor/         # API (FastAPI)
│   ├── api.py
│   └── schemas.py
├── orquestador/
│   ├── core.py
│   └── estados.py
├── consultor/
│   └── repo.py
├── etl/
│   ├── cargador.py
│   ├── curador.py
│   └── deposito.py
├── analisis/
│   ├── metricas/
│   │   ├── core.py
│   │   └── basicas.py
│   ├── patrones/
│   │   ├── core.py
│   │   └── anomalias.py
│   └── heuristica/
│       └── reglas.py
├── herramientas/
│   └── basicas.py
├── auxiliares/
│   ├── config.py
│   ├── reloj.py
│   ├── log.py
│   └── utils.py
├── celador/
│   ├── errores.py
│   ├── validaciones.py
│   └── auditoria.py
├── contratos.py
└── main.py
```

---

## 4) Integración externa (API)

### 4.1 Endpoints

**Plan API (LLM-facing, detallada)**  
- `GET /tools/catalog` → catálogo de herramientas y entidades (IDs canónicos).  
- `GET /dataset/metadata` → `{ dataset_version, min_date, max_date, updated_at }`.  
- `POST /plan/execute` → ejecuta pipeline (plan) y devuelve **Sobres** (último o todos).

**Job API (v0 simple / compatibilidad)**  
- `POST /v1/job` → acepta `JobRequest` simple y devuelve `JobResult`.  
  - Internamente, el Expositor adapta `JobRequest` → **Plan** y **Sobre**, y lo traduce de vuelta a `JobResult`.

> **Nota de coherencia**: Ambos modos conviven. La *Plan API* es la referencia canónica; la *Job API* es un *adapter* para clientes simples o transitorios.

### 4.2 Catálogo de Tools (resumen)

- `enfoque_entidad@1.0.0` — fija entidad (`entidad_id`).
- `filtro_fecha@1.0.0` — intervalo absoluto (`from`/`to` ISO día).
- `filtro_tipo@1.0.0` — por tipo(s) de delito.
- `filtro_metodo@1.0.0` — por método/violencia.
- `filtro_frecuencia@1.0.0` — frecuencia mínima (`por`, `min_eventos`/`min_tasa`).
- `rank_por_delito@1.1.0` — ranking por delito y nivel (`hijos|actual`), `medida` = `conteo|tasa_per_100k`, `top_k`.
- `top_entidades_por_total@1.0.0` — top por total.
- `detectar_patrones@1.0.0` — co-ocurrencias/tiempo/lugar con `score/support/lift`.
- `listar_evidencia@1.0.0` — IDs/filas que sustentan conclusiones.

### 4.3 Plan (entrada a `/plan/execute`)

**Texto simple (aceptado por Intérprete):**
```
[6,9]
entidad_id: GTO.MUN.LEON
delito: homicidio_doloso
nivel: hijos
medida: tasa_per_100k
top_k: 10
from: 2025-07-15
to:   2025-08-13
```

**JSON normalizado:**
```json
{
  "plan": [
    {"tool_id": 6, "tool_version": "1.1.0",
     "args": {"entidad_id":"GTO.MUN.LEON","delito":"homicidio_doloso","nivel":"hijos",
              "medida":"tasa_per_100k","top_k":10,"from":"2025-07-15","to":"2025-08-13"}},
    {"tool_id": 9, "tool_version": "1.0.0", "args": {}}
  ],
  "meta": {"catalog_version":"2025.08.19","dataset_version":"gx-2025.08.15","strict_time":false}
}
```

### 4.4 Sobre (Envelope) — salida estándar de tools

**Éxito (extracto):**
```json
{
  "status": "ok",
  "tool": "rank_por_delito@1.1.0",
  "summary": {
    "headline": "Top homicidio_doloso (tasa_per_100k) — Hijos de GTO.MUN.LEON",
    "highlights": ["Top-1: GTO.MUN.LEON", "Ventana 2025-07-15..2025-08-13"]
  },
  "data": {
    "inline": {
      "columns": [
        {"name":"entidad_id","type":"string"},
        {"name":"label","type":"string"},
        {"name":"conteo","type":"int"},
        {"name":"tasa_per_100k","type":"float"}
      ],
      "rows": [["GTO.MUN.LEON","León",132,8.1]],
      "limit_notice": {"applied": true, "max_rows": 50}
    },
    "artifacts": {
      "tables": {
        "rank_full": "artifact://tables/2025-08-19/rank_homicidio_leon.parquet"
      }
    }
  },
  "evidence": [{"table":"incidents", "ids":[120301,120322,120415]}],
  "meta": {
    "schema_version": "1.0.0",
    "tool_version": "1.1.0",
    "dataset_version": "gx-2025.08.15",
    "anchor_date": "2025-08-13",
    "date_range_effective": {"from":"2025-07-15","to":"2025-08-13"},
    "range_adjusted": false,
    "timing_ms": 4120,
    "query_hash": "sha256:..."
  }
}
```

**Error (extracto):**
```json
{
  "status": "error",
  "tool": "filtro_fecha@1.0.0",
  "error": {
    "code": "INVALID_DATE_RANGE",
    "details": "from > to después de recorte a dataset_max_date",
    "hints": ["Asegure 'from' <= 'to'", "Consulte /dataset/metadata para el watermark temporal"]
  },
  "meta": { "schema_version": "1.0.0", "tool_version": "1.0.0" }
}
```

### 4.5 Job API (compat) — contratos y *adapter*

**JobRequest** (entrada):
- `intent`: `"consulta" | "analisis" | "metricas" | "patrones"`
- `query`: opcional
- `tools`: lista de `{ name, args }` (opcional)
- `params`: `{ municipio, fecha_inicio, fecha_fin, delito }` (v0)
- `output`: `"json" | "markdown" | "tabular" | "grafico"`

**JobResult** (salida):
- `ok`: boolean
- `payload`: datos empaquetados (tablas, muestras, gráficos codificados)
- `warnings`: lista de mensajes
- `provenance`: `{ dataset, dataset_version, data_available_until, filters_applied }`

**Reglas del *adapter***:
- Traduce `municipio` → `entidad_id` (catálogo de entidades).
- Traduce `fecha_inicio|fecha_fin` → `from|to`.
- Aplica *Plan API* internamente y convierte el **Sobre** resultante en `JobResult`:
  - `status:"ok"` → `ok=true`, `payload` derivado de `data.inline/artifacts/summary`.
  - `status:"error"` → `ok=false`, error mapeado a `warnings` (y HTTP 400/422 si aplica).
- `data_available_until` = `max_date` del metadata.


---

## 5) Reglas temporales (anclaje y recorte)

- Fuente única de tiempo: `max_date` del dataset (`/dataset/metadata`).
- Fechas **relativas** → se resuelven contra `max_date`.
- Tools **solo** aceptan **fechas absolutas** `from`/`to` (día ISO).
- `strict_time=false` (por defecto): recorta a `[min_date, max_date]` y registra ajuste.
- `strict_time=true`: rangos fuera → error inmediato.
- Toda respuesta incluye `date_range_effective` y si hubo `range_adjusted`.

---

## 6) Errores y validaciones

**Códigos críticos (abortan)**: `INVALID_PAYLOAD`, `INVALID_FILTER`, `DATA_QUALITY_ISSUE`, `COMPUTE_ERROR`, `RESOURCE_LIMIT`.  
**No críticos**: `EMPTY_RESULT` puede devolver `rows:[]` como resultado válido.  
**Formato único externo**: siempre el **Sobre de error**.  
**Interno**: excepciones del Celador (`ValidacionError`, `DatosFaltantesError`, `HerramientaError`, etc.) se **mapean** 1:1 a códigos del Sobre.

**Tabla de mapeo (ejemplos):**

| Excepción interna                 | Código Sobre           | HTTP |
|----------------------------------|------------------------|------|
| `ValidacionError`                | `INVALID_PAYLOAD`      | 422  |
| `DatosFaltantesError`            | `DATA_QUALITY_ISSUE`   | 409  |
| `HerramientaError`               | `COMPUTE_ERROR`        | 500  |
| `RangoFueraDeCorte` (derivada)   | `INVALID_DATE_RANGE`   | 422  |

---

## 7) Observabilidad, auditoría y salud

- `job_id` por solicitud (trazabilidad punta a punta).
- `query_hash` (hash del plan normalizado + versión de catálogo) para reproducibilidad.
- Audit log: plan normalizado, latencias por paso, row counts, `dataset_version`, rangos efectivos, errores.
- Health: `/health/live`, `/health/ready`.
- Provenance **obligatorio** en toda respuesta (JobResult y/o Sobre).

---

## 8) Conformidad de nombres y convenciones

**Clave canónica externa (Plan API):**
- `entidad_id`, `from`, `to`, `delito`, `nivel`, `medida`, `top_k`…

**Compatibilidad (Job API):**
- Acepta `municipio`, `fecha_inicio`, `fecha_fin`, `delito` y los mapea a los canónicos.

**Tabla de mapeo (parámetros):**

| Job API (entrada) | Plan API (interno) |
|-------------------|--------------------|
| `municipio`       | `entidad_id`       |
| `fecha_inicio`    | `from`             |
| `fecha_fin`       | `to`               |
| `delito`          | `delito`           |

**Tabla de mapeo (dataset info):**

| Campo canónico     | Alias de compatibilidad |
|--------------------|-------------------------|
| `min_date`         | *(sin alias)*           |
| `max_date`         | `data_available_until`  |
| `dataset_version`  | `dataset_version`       |

---

## 9) Datos y Depósito

- Parquet/DuckDB en `./data` (rápido, reproducible, sin servidor).
- Esquema mínimo: `fecha (YYYY-MM-DD)`, `municipio`/`entidad_id`, `delito`, `eventos:int`.
- Catálogos/particiones si aplica.
- `/dataset/metadata` es la **fuente de verdad**; `/dataset/info` puede exponerse como **alias** para compatibilidad (devuelve el superconjunto con ambos nombres: `max_date` y `data_available_until`).

---

## 10) Pruebas y despliegue

**Unitarias**: herramientas (funciones puras), validaciones del Celador, Consultor (mini-datasets).  
**Integración**: ETL completo (CSV→Parquet), `/v1/job` y `/plan/execute` con fixtures.  
**Determinismo**: inyectar `RelojFijo`.  
**Despliegue (desarrollo)**: FastAPI + Uvicorn; `.env`/YAML para rutas/dataset.

---

## 11) Seguridad (v0 → v1)

- v0: entorno de desarrollo.  
- v1: token/bearer por endpoint; rate limits; sanitización de archivos; artefactos firmados/expiran si hay servidor de objetos; mTLS a futuro.

---
### Anexo A — Ejemplos de pipelines (informativos)
- **Top homicidio 30 días anclados**: `[enfoque_entidad] → [filtro_fecha] → [rank_por_delito] → [listar_evidencia]`.
- **Patrones de robos sin violencia**: `[enfoque_entidad] → [filtro_tipo] → [filtro_metodo] → [detectar_patrones]`.

### Anexo B — Secuencia típica (consulta/analítica)

```
1) LLM → POST /plan/execute (o /v1/job)
2) Expositor → valida forma → Orquestador.ejecutar
3) Celador.validaciones(req)
4) Consultor obtiene DataFrame desde Depósito
5) Orquestador aplica pipeline de herramientas
6) (Opcional) análisis métricas/patrones
7) Empaquetador → Sobre/JobResult
8) Auditoría → job_id, query_hash, rangos efectivos
9) Mensajero devuelve respuesta
```
---
## Anexo C — Arquitectura de Tools Verificables y Catálogo Versionado (v0.1)

Este anexo formaliza el modelo de herramientas de Casandra como contratos verificables de primera clase.
Define cómo se describen, versionan, validan y componen las Tools, así como el funcionamiento del catálogo
versionado utilizado por el Orquestador y el Celador antes de cualquier ejecución.

Este anexo complementa el Documento Unificado de Arquitectura e Integración v0 y establece las bases
para la evolución hacia v1 sin romper compatibilidad.

**Propósito**: formalizar las herramientas (Tools) como contratos verificables de primera clase, habilitando validación automática de planes, reproducibilidad fuerte y evolución controlada del sistema sin romper compatibilidad.

Este anexo complementa el documento unificado de arquitectura de Casandra v0 y define las bases para la transición hacia v1.

---

## C.1 Motivación de diseño

Casandra opera bajo el principio de **razonamiento delegado**:  
el LLM propone planes, pero no accede directamente a los datos ni decide los límites operativos.  
Estas decisiones se imponen mediante contratos, validaciones y catálogos versionados.

Para sostener este principio a escala, las herramientas dejan de ser simples funciones y se convierten en **artefactos contractuales verificables**.

Los objetivos de este diseño son:

- Detectar errores antes de ejecutar cómputos costosos.
- Garantizar reproducibilidad y auditabilidad de resultados.
- Permitir evolución del sistema sin romper planes existentes.
- Proveer reglas claras y explícitas tanto para humanos como para agentes LLM.

---

## C.2 ToolSpec — Esquema base de Tool

Toda herramienta en Casandra se define mediante un **ToolSpec**, un contrato formal que describe su identidad, entrada, salida y restricciones.

### C.2.1 Estructura general

Cada ToolSpec incluye:

- Identidad de la herramienta.
- Declaración explícita de dependencias.
- Esquema estricto de argumentos.
- Contrato de salida sobre el Sobre (Envelope).
- Declaración de determinismo.

---

## C.3 Identidad de la herramienta

Cada ToolSpec debe definir:

- **tool_id**  
  Identificador numérico interno y estable.

- **name**  
  Nombre canónico de la herramienta (ej. `rank_por_delito`).

- **version**  
  Versión semántica (semver).

- **summary**  
  Descripción breve y precisa del propósito de la herramienta.

- **kind**  
  Categoría funcional (`filter`, `analysis`, `metricas`, `patrones`, etc.).

La identidad completa de una herramienta está dada por `name@version`.

---

## C.4 Requisitos declarativos (`requires`)

Cada herramienta declara explícitamente sus dependencias lógicas:

- **dataset**: requiere acceso al Depósito.
- **entity**: requiere `entidad_id`.
- **date_range**: requiere `from` y `to`.
- **evidence_capable**: puede generar evidencia trazable.

Estos requisitos permiten:

- Validar el orden lógico del pipeline.
- Detectar planes inválidos antes de ejecución.
- Automatizar reglas de composición entre herramientas.

---

## C.5 Esquema de argumentos (`args_schema`)

Cada ToolSpec define un esquema estricto de entrada, basado en JSON Schema.

Principios del esquema:

- Tipos explícitos.
- Campos obligatorios declarados.
- Enumeraciones cerradas cuando aplica.
- Rangos numéricos definidos.
- `additionalProperties` deshabilitado por defecto.

Esto elimina ambigüedad semántica y reduce errores del LLM a fallos estructurales corregibles.

---

## C.6 Contrato de salida (`output_contract`)

El contrato de salida define qué bloques del Sobre garantiza la herramienta.

Se declaran explícitamente:

- Versión del esquema del Sobre soportado.
- Presencia garantizada de `summary`, `data.inline`, etc.
- Bloques opcionales (`artifacts`, `evidence`).
- Límites de filas por defecto.

Ninguna herramienta puede violar el esquema del Sobre definido por la arquitectura central.

---

## C.7 Determinismo

Cada herramienta declara su nivel de determinismo.

Una herramienta es determinista si, dados:

- el mismo `dataset_version`
- los mismos argumentos normalizados

produce siempre el mismo resultado.

Esta declaración habilita reproducibilidad, auditoría y comparación entre ejecuciones.

---

## C.8 Validación automática de planes

Antes de ejecutar cualquier pipeline, Casandra realiza validación automática en dos fases.

### C.8.1 Validación estática

No accede a datos.

Incluye:

- Verificación de existencia de tool y versión.
- Validación de argumentos contra `args_schema`.
- Compatibilidad con `catalog_version`.
- Orden lógico del pipeline según `requires`.
- Normalización canónica del plan para cálculo de `query_hash`.

---

### C.8.2 Validación contextual

Accede únicamente a metadata.

Incluye:

- Resolución de fechas contra `min_date` y `max_date`.
- Aplicación de reglas de `strict_time`.
- Validación de entidades y taxonomías.
- Estimación básica de consumo de recursos.

Si cualquier validación falla, se retorna un **Sobre de error** y el pipeline no se ejecuta.

---

## C.9 Catálogo Versionado Verificable (CatalogSpec)

El catálogo de herramientas es un artefacto inmutable y versionado.

Contiene:

- `catalog_version`
- versión del esquema
- timestamp de generación
- checksum criptográfico
- lista completa de ToolSpec
- catálogos de entidades y taxonomías asociadas

Cualquier modificación genera un nuevo catálogo con checksum distinto.

---

## C.10 Reglas de versionado y compatibilidad

Casandra adopta versionado semántico estricto:

- **PATCH**: correcciones internas sin cambios contractuales.
- **MINOR**: extensión compatible (campos opcionales).
- **MAJOR**: cambios incompatibles.

Las versiones activas no se eliminan sin transición explícita.

---

## C.11 Beneficios arquitectónicos

Este diseño aporta:

- Validación determinista del razonamiento.
- Errores tempranos, explícitos y auditables.
- Evolución segura del sistema.
- Base sólida para control de acceso, rate limiting y seguridad en v1.

Casandra no confía en que el LLM razone bien.  
Casandra **verifica** que razone dentro de lo permitido.

---

## 13) Limitaciones de v0 y Extensiones Propuestas (hacia v1)

Del análisis de casos de uso más complejos (ej. ranking de municipios por anomalías + gravedad), se identifican huecos claros:

### 13.1 Nuevos Tools requeridos
- **detectar_anomalias@1.0.0**  
  - Args sugeridos: `entidad_id`, `nivel`, `from`, `to`, `z_threshold`, `window`.  
  - Output: lista de anomalías detectadas por entidad con `z_score`, `event_ids`, `severity` (si aplica).  

### 13.2 Extensión de schemas de incidentes y Sobre
- Incluir campo `severity` (0–1 o 0–100 normalizado) en incidentes/artifacts cuando se trate de patrones o anomalías.  
- Añadir bloque `metrics` en el Sobre para exponer métricas agregadas estándar (ejemplo: `total_anomalias`, `gravedad_promedio`).

### 13.3 Reducción y agregación
- Extender `top_entidades_por_total` o crear un nuevo tool `agrupar_por_entidad@1.0.0` que acepte:  
  - `aggregate_by`: métrica a usar (`total_anomalias`, `gravedad_promedio`, etc.).  
  - `metrics`: lista de métricas adicionales a devolver.  
- Esto permite hacer ranking no solo por conteo de incidentes, sino por resultados de análisis.

### 13.4 Contratos de salida enriquecidos
Ejemplo de bloque extendido del Sobre (extracto):

```json
"metrics": {
  "total_anomalias": 48,
  "gravedad_promedio": 0.62
}
```