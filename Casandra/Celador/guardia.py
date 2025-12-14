# casandra/celador/guardia.py
from functools import wraps
import time
from typing import Callable, Any
from .auditoria import audit, get_job_id
from .errores import CeladorError, a_sobre_error, SobreError


def celar(tool_name: str, schema_version="1.0.0", tool_version="1.0.0") -> Callable:
    """
    Decorador para funciones de Tool: valida audit, captura errores y
    devuelve tuple (sobre_ok | sobre_error, http_status).
    La función decorada debe devolver ya el 'sobre ok' (dict) en éxito.
    """

    def deco(fn: Callable[..., dict]):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            jid = get_job_id()
            t0 = time.perf_counter()
            audit("tool_start", {"tool": tool_name, "args": kwargs})
            try:
                sobre_ok = fn(*args, **kwargs)
                dt = int((time.perf_counter() - t0) * 1000)
                audit("tool_ok", {"tool": tool_name, "timing_ms": dt})
                # El sobre_ok debería incluir 'meta.timing_ms' y 'meta.query_hash' aguas si no
                return sobre_ok, 200
            except CeladorError as e:
                dt = int((time.perf_counter() - t0) * 1000)
                audit(
                    "tool_error",
                    {
                        "tool": tool_name,
                        "error": type(e).__name__,
                        "details": str(e),
                        "timing_ms": dt,
                    },
                )
                sobre_err = a_sobre_error(e, tool_name, schema_version, tool_version)
                return sobre_err, _http_from_sobre(sobre_err)
            except Exception as e:
                dt = int((time.perf_counter() - t0) * 1000)
                audit(
                    "tool_exception",
                    {
                        "tool": tool_name,
                        "error": type(e).__name__,
                        "details": str(e),
                        "timing_ms": dt,
                    },
                )
                sobre_err = a_sobre_error(e, tool_name, schema_version, tool_version)
                return sobre_err, 500

        return wrapper

    return deco


# def _http_from_sobre(sobre_error: dict) -> int:
#     code = sobre_error.get("error", {}).get("code", "")
#     return {
#         "INVALID_PAYLOAD": 422,
#         "DATA_QUALITY_ISSUE": 409,
#         "COMPUTE_ERROR": 500,
#         "INVALID_DATE_RANGE": 422,
#     }.get(code, 500)


def _http_from_sobre(sobre_error: SobreError) -> int:
    code = sobre_error.get("error", {}).get("code", "")
    return {
        "INVALID_PAYLOAD": 422,
        "DATA_QUALITY_ISSUE": 409,
        "COMPUTE_ERROR": 500,
        "INVALID_DATE_RANGE": 422,
    }.get(code, 500)
