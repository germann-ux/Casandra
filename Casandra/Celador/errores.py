# casandra/celador/errores.py
from dataclasses import dataclass
from typing import TypedDict, Literal, Optional


# Excepciones internas (contrato estable con el doc)
class CeladorError(Exception): ...


class ValidacionError(CeladorError): ...


class DatosFaltantesError(CeladorError): ...


class HerramientaError(CeladorError): ...


class RangoFueraDeCorte(ValidacionError): ...


# Mapa 1:1 → códigos del Sobre (doc §6 "Errores y validaciones")
#   ValidacionError        -> INVALID_PAYLOAD (422)
#   DatosFaltantesError    -> DATA_QUALITY_ISSUE (409)
#   HerramientaError       -> COMPUTE_ERROR (500)
#   RangoFueraDeCorte      -> INVALID_DATE_RANGE (422)
ERROR_MAP = {
    ValidacionError: ("INVALID_PAYLOAD", 422),
    DatosFaltantesError: ("DATA_QUALITY_ISSUE", 409),
    HerramientaError: ("COMPUTE_ERROR", 500),
    RangoFueraDeCorte: ("INVALID_DATE_RANGE", 422),
}


class SobreError(TypedDict, total=False):
    status: Literal["error"]
    tool: str
    error: dict
    meta: dict


def a_sobre_error(
    exc: Exception,
    tool_name: str,
    schema_version="1.0.0",
    tool_version="1.0.0",
    hints: Optional[list[str]] = None,
) -> SobreError:
    code, _http = ERROR_MAP.get(type(exc), ("COMPUTE_ERROR", 500))
    return {
        "status": "error",
        "tool": tool_name,
        "error": {"code": code, "details": str(exc), "hints": hints or []},
        "meta": {"schema_version": schema_version, "tool_version": tool_version},
    }
