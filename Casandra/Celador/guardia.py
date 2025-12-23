# casandra/celador/guardia.py
from __future__ import annotations

from functools import wraps
import time
from typing import Any, Callable, TypeVar

from .auditoria import audit, get_job_id
from .errores import (
    CeladorError,
    a_sobre_error,
    error_code_http,
    SobreError,
    sobre_compute_error,
)

T = TypeVar("T", bound=dict)


def _warn_if_noncanonical(tool: str) -> None:
    # Canónico mínimo para tools: "id@version"
    if "@" not in tool:
        audit("tool.name_warning", {"tool": tool, "reason": "missing @version"})


def celar(
    tool_name: str,
    schema_version: str = "1.0.0",
    tool_version: str = "1.0.0",
) -> Callable[[Callable[..., T]], Callable[..., tuple[T | SobreError, int]]]:
    """
    Decorador para funciones Tool:
    - Audita inicio/fin/error
    - Captura errores y los convierte a SobreError
    - Devuelve (sobre_ok | sobre_error, http_status)

    La tool decorada debe devolver el 'sobre ok' (dict) en éxito.
    """

    def deco(fn: Callable[..., T]) -> Callable[..., tuple[T | SobreError, int]]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            _ = get_job_id()  # asegura job_id en contexto
            _warn_if_noncanonical(tool_name)

            t0 = time.perf_counter()
            audit("tool.start", {"tool": tool_name, "args": kwargs})

            try:
                sobre_ok = fn(*args, **kwargs)
                dt = int((time.perf_counter() - t0) * 1000)

                # Inyección suave de meta consistente
                meta = sobre_ok.setdefault("meta", {})
                meta.setdefault("schema_version", schema_version)
                meta.setdefault("tool_version", tool_version)
                meta.setdefault("timing_ms", dt)

                # Asegurar coherencia del productor (si la tool no lo puso)
                sobre_ok.setdefault("tool", tool_name)

                audit("tool.ok", {"tool": tool_name, "timing_ms": dt})
                return sobre_ok, 200

            except CeladorError as e:
                dt = int((time.perf_counter() - t0) * 1000)
                code, http = error_code_http(e)

                audit(
                    "tool.error",
                    {
                        "tool": tool_name,
                        "code": code,
                        "error": type(e).__name__,
                        "details": str(e),
                        "timing_ms": dt,
                    },
                )

                sobre_err = a_sobre_error(e, tool_name, schema_version, tool_version)
                sobre_err.setdefault("tool", tool_name)
                sobre_err_meta = sobre_err.setdefault("meta", {})
                sobre_err_meta.setdefault("timing_ms", dt)

                return sobre_err, http

            except Exception as e:
                dt = int((time.perf_counter() - t0) * 1000)

                audit(
                    "tool.exception",
                    {
                        "tool": tool_name,
                        "error": type(e).__name__,
                        "details": str(e),
                        "timing_ms": dt,
                    },
                )

                sobre_err = sobre_compute_error(
                    tool_name=tool_name,
                    schema_version=schema_version,
                    tool_version=tool_version,
                    details="Error interno no controlado durante la ejecución de la tool.",
                    extra_meta={"timing_ms": dt},
                )
                return sobre_err, 500

        return wrapper

    return deco
