# Casandra — Documento de Arquitectura (v0)

## 1) Propósito
Casandra es un sistema de **análisis criminal** para Guanajuato. Su objetivo es **ingestar, curar, almacenar, consultar y analizar** datos públicos; y exponer resultados claros y trazables a un LLM mediante un **contrato estable**.

## 2) Alcance (v0)
- **ETL mínimo** (CSV → curado → Parquet/DuckDB).
- **Consultor** de solo lectura al Depósito.
- **Orquestador** que valida, resuelve datos y ejecuta pipelines de herramientas.
- **Auxiliares** (config, reloj, logging, utilidades).
- **Celador** (validación de inputs, manejo de errores y auditoría simple).
- **Expositor** con un endpoint `/v1/job` para hablar con el LLM.

## 3) Principios de diseño
- **Contratos primero** (Pydantic): todo entra y sale con tipos claros.
- **Funciones puras** en herramientas: fácil de testear y reproducir.
- **Separación de dominios** (ETL, Orquestación, Análisis, Exposición).
- **Provenance obligatorio**: cada resultado sabe de dónde viene.
- **Fuente de tiempo única** (Reloj): evita “ahoras” inconsistentes.
- **Corte de datos explícito**: si la petición excede el corte, se recorta y se advierte.

## 4) Mapa de dominios
```
LLM ⇄ Expositor → Orquestador → (Herramientas / Análisis / Consultor) → Empaquetador → Mensajero → LLM
                   │
                   └──────────────► Celador (validaciones, auditoría, errores)

ETL: Cargador → Curador → Depósito
Transversal: Auxiliares (config, reloj, log, utilidades)
```

## 5) Estructura de carpetas (propuesta)
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

## 6) Contratos clave

### 6.1 JobRequest (entrada)
- `intent`: `"consulta" | "analisis" | "metricas" | "patrones"`
- `query`: string opcional (texto natural del LLM)
- `tools`: lista de `{ name, args }` para pipeline determinista
- `params`: `{ municipio, fecha_inicio, fecha_fin, delito }` (v0)
- `output`: `"json" | "markdown" | "tabular" | "grafico"`

### 6.2 JobResult (salida)
- `ok`: boolean
- `payload`: datos empaquetados (tablas, muestras, gráficos codificados)
- `warnings`: lista de mensajes (p. ej., ventana recortada al corte de datos)
- `provenance`: `{ dataset, dataset_version, data_available_until, filters_applied }`

> **Regla de oro**: toda respuesta incluye `provenance`. Sin eso, no hay confianza.

## 7) Flujo de ejecución (runtime)

**Secuencia típica (consulta/analítica):**
```
1) LLM → POST /v1/job (Expositor)
2) Expositor → valida forma → Orquestador.ejecutar_job
3) Celador.validaciones(req)
4) Consultor obtiene DataFrame desde Depósito (solo lectura)
5) Orquestador aplica pipeline de herramientas (si las hay)
6) (Opcional) Análisis.Métricas / Patrones
7) Empaquetador formatea (json/markdown/tabular/grafico)
8) Celador.auditoria registra resultado
9) Mensajero devuelve JobResult al LLM
```

**Secuencia ETL:**
```
Cargador (lee CSV/ZIP/API) → Curador (normaliza y valida esquema)
→ Depósito (escribe Parquet; catálogos/particiones si aplica)
→ (Opcional) actualiza metadata: data_available_until, versión de dataset
```

## 8) Componentes (responsabilidades)

- **Expositor**: API pública para el LLM. Traduce HTTP → `JobRequest`. No contiene lógica de negocio.
- **Orquestador**: cerebro de ejecución. Valida, resuelve datos, ejecuta herramientas, delega análisis y empaqueta resultados.
- **Consultor**: “repositorio” de lectura contra el Depósito. Expone consultas parametrizadas comunes.
- **ETL (Cargador/Curador/Depósito)**: pipeline de ingesta y normalización hacia un formato analizable (Parquet/DuckDB).
- **Auxiliares**: configuración centralizada, reloj, logging y utilidades (p. ej., recorte de ventanas).
- **Celador**: validaciones de entradas, tipología de errores, auditoría (logs, job_id, checks mínimos).

## 9) Manejo de errores y validaciones

- **Tipos**: `ValidacionError`, `DatosFaltantesError`, `HerramientaError`, `CasandraError`.
- **Política**:
  - Validación falla → `JobResult(ok=False)` con `warnings=[detalle]`.
  - Datos faltantes (ventana imposible) → `ok=False` + mensaje accionable.
  - Herramienta no registrada → `ok=False` + nombre de herramienta.
- **Auditoría**:
  - `job_id` por solicitud.
  - Log de inicio, errores y resultado (dataset, versión, warnings).

## 10) Datos y Depósito

- **v0**: Parquet + DuckDB en disco (rápido, reproducible, sin servidor).
- **Esquema mínimo**: `fecha (YYYY-MM-DD)`, `municipio`, `delito`, `eventos:int`.
- **Metadata de dataset**: `dataset_nombre`, `dataset_version`, `data_available_until`.
- **Estrategia de corte**:
  - Si `fecha_fin` > `data_available_until` → recortar y avisar en `warnings`.

## 11) Endpoints iniciales
- `POST /v1/job` → ejecuta un `JobRequest` y devuelve `JobResult`.
- `GET  /health` → vida simple del servicio.
- `GET  /dataset/info` → devuelve `dataset`, `versión` y `corte`.

## 12) Seguridad (v0 → v1)
- v0: red local/desarrollo.
- v1: token de servicio/API key para `POST /v1/job`.  
- Más adelante: mTLS o firma de mensajes si el LLM vive fuera de confianza.

## 13) Observabilidad
- **Logs** con niveles (`orquestador`, `consultor`, `etl`, `celador`).
- **IDs de job** trazables de punta a punta.
- Roadmap: contadores de métricas (promedio de filas, latencia, errores) para Prometheus.

## 14) Pruebas
- **Unitarias**:
  - Herramientas (funciones puras).
  - Validaciones del Celador.
  - Consultor: lectura filtrada con mini-datasets de prueba.
- **Integración**:
  - ETL de extremo a extremo (CSV → Parquet).
  - `/v1/job` con fixtures de Parquet.
- **Determinismo**: inyectar `RelojFijo` cuando se use tiempo.

## 15) Despliegue (desarrollo)
- **FastAPI** con Uvicorn.
- Parquet/DuckDB en `./data`.
- `.env`/YAML opcional para configurar rutas y dataset.

## 16) Convenciones
- **Nombres de parámetros** (estándar): `fecha_inicio`, `fecha_fin`, `municipio`, `delito`.
- **Fechas ISO**: `YYYY-MM-DD`.
- **Columnas base**: `fecha`, `municipio`, `delito`, `eventos`.
- **Salida JSON**: incluir siempre `provenance` y `warnings` (aunque vacíos).

<!-- ## 17) Roadmap inmediato
- Añadir **Métricas v0** (total, promedio semanal, comparación contra periodo anterior).
- **Patrones/anomalías** básicos (z-score o STL).
- **Empaquetador** con gráfico en base64 y resumen markdown.
- **/dataset/info** y `data_available_until` dinámico desde catálogo. -->

---

### Anexo A — Contratos (resumen técnico)
```python
# contratos.py (resumen)
class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = {}

class JobRequest(BaseModel):
    intent: Literal["consulta","analisis","metricas","patrones"]
    query: Optional[str] = None
    tools: List[ToolCall] = []
    params: Dict[str, Any] = {}
    output: Literal["json","markdown","tabular","grafico"] = "json"

class Provenance(BaseModel):
    dataset: str
    dataset_version: str
    data_available_until: Optional[str] = None
    filters_applied: Dict[str, Any] = {}

class JobResult(BaseModel):
    ok: bool
    payload: Dict[str, Any]
    warnings: List[str] = []
    provenance: Provenance
```
### Anexo B — Diagrama ASCII de secuencia
```
LLM
 │  POST /v1/job (JobRequest)
▼
Expositor ── valida forma ──► Orquestador ──► Celador.validaciones
                                 │
                                 │ consulta
                                 ▼
                           Consultor(repo) ──► Depósito (Parquet/DuckDB)
                                 │
                                 └─► aplicar tools ──► (Análisis opcional)
                                                       │
                                                       ▼
                                               Empaquetador
                                                     │
                                                     ▼
                                                Mensajero
                                                     │
                                                     ▼
                                                 LLM (JobResult)
```
