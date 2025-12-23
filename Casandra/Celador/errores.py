# casandra/celador/errores.py
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict, Type


# Excepciones internas (contrato estable con el doc)
class CeladorError(Exception):
    """Base de errores controlados por Celador."""


class ValidacionError(CeladorError):
    """Payload inválido o no cumple reglas."""


class DatosFaltantesError(CeladorError):
    """Problemas de calidad/ausencia en dataset requerido."""


class HerramientaError(CeladorError):
    """Falló una tool (cálculo/ejecución) de forma controlada."""


class RangoFueraDeCorte(ValidacionError):
    """Rango temporal fuera del watermark del dataset (strict_time)."""


# Mapa → (código_sobre, http_status)
ERROR_MAP: dict[Type[Exception], tuple[str, int]] = {
    ValidacionError: ("INVALID_PAYLOAD", 422),
    DatosFaltantesError: ("DATA_QUALITY_ISSUE", 409),
    HerramientaError: ("COMPUTE_ERROR", 500),
    RangoFueraDeCorte: ("INVALID_DATE_RANGE", 422),
}


class SobreErrorDetails(TypedDict):
    code: str
    details: str
    hints: list[str]


class SobreError(TypedDict):
    status: Literal["error"]
    tool: str
    error: SobreErrorDetails
    meta: dict[str, Any]


def error_code_http(exc: Exception) -> tuple[str, int]:
    """
    Devuelve (code, http) usando el mapa, respetando herencia.
    Si no hay match, cae a COMPUTE_ERROR/500.
    """
    for exc_type, (code, http) in ERROR_MAP.items():
        if isinstance(exc, exc_type):
            return code, http
    return "COMPUTE_ERROR", 500


def a_sobre_error(
    exc: Exception,
    tool_name: str,
    schema_version: str = "1.0.0",
    tool_version: str = "1.0.0",
    hints: Optional[list[str]] = None,
) -> SobreError:
    code, _http = error_code_http(exc)
    return {
        "status": "error",
        "tool": tool_name,
        "error": {
            "code": code,
            "details": str(exc),
            "hints": hints or [],
        },
        "meta": {
            "schema_version": schema_version,
            "tool_version": tool_version,
        },
    }


def sobre_compute_error(
    *,
    tool_name: str,
    schema_version: str = "1.0.0",
    tool_version: str = "1.0.0",
    details: str = "Error interno no controlado.",
    hints: Optional[list[str]] = None,
    extra_meta: Optional[dict[str, Any]] = None,
) -> SobreError:
    """
    Constructor tipado de SobreError para fallos no controlados (500).
    Mantiene el shape estable y evita dicts sueltos por el código.
    """
    meta: dict[str, Any] = {
        "schema_version": schema_version,
        "tool_version": tool_version,
    }
    if extra_meta:
        meta.update(extra_meta)

    return {
        "status": "error",
        "tool": tool_name,
        "error": {"code": "COMPUTE_ERROR", "details": details, "hints": hints or []},
        "meta": meta,
    }
