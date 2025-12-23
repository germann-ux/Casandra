# casandra/dominio/nombres.py

# Capas del sistema
SYSTEM = "system"
EXPOSITOR = "expositor"
ORQUESTADOR = "orquestador"
CONSULTOR = "consultor"
CURADOR = "curador"
DEPOSITO = "deposito"
EMPAQUETADOR = "empaquetador"
ADAPTER_JOB_API = "adapter.job_api"


# Helpers
def tool_name(tool_id: str, version: str) -> str:
    return f"{tool_id}@{version}"
