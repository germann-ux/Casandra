# casandra/celador/validaciones.py
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

from .errores import RangoFueraDeCorte, ValidacionError


def requeridos(payload: Mapping[str, Any], campos: Iterable[str]) -> None:
    """
    Valida presencia de campos requeridos (no None, no "", no []).
    """
    faltan = [c for c in campos if payload.get(c) in (None, "", [])]
    if faltan:
        raise ValidacionError(f"Faltan campos requeridos: {', '.join(faltan)}")


def as_date(val: Any, *, field: str = "date") -> date:
    """
    Convierte 'val' a date.
    Acepta:
      - datetime.date
      - str ISO "YYYY-MM-DD"
    """
    if isinstance(val, date):
        return val

    if isinstance(val, str):
        try:
            # Valida formato y rangos (mes 1-12, día correcto, etc.)
            return date.fromisoformat(val)
        except ValueError:
            raise ValidacionError(
                f"Fecha inválida en '{field}' (ISO YYYY-MM-DD esperado): {val!r}"
            )

    raise ValidacionError(
        f"Tipo inválido para '{field}': {type(val).__name__} (se esperaba date o str ISO)"
    )


def validar_rango(
    from_val: Any,
    to_val: Any,
    min_date: date,
    max_date: date,
    strict_time: bool,
) -> tuple[date, date, bool]:
    """
    Devuelve (from_effective, to_effective, range_adjusted).
    Reglas:
      - from <= to
      - si strict_time=False: recorta a [min_date, max_date]
      - si strict_time=True: error si se sale del watermark
    """
    d1 = as_date(from_val, field="from")
    d2 = as_date(to_val, field="to")

    if d1 > d2:
        raise ValidacionError("Rango inválido: 'from' > 'to'")

    adjusted = False
    ef1, ef2 = d1, d2

    if not strict_time:
        if ef1 < min_date:
            ef1, adjusted = min_date, True
        if ef2 > max_date:
            ef2, adjusted = max_date, True
        return ef1, ef2, adjusted

    # strict: lanzar error si se sale de rango
    if d1 < min_date or d2 > max_date:
        raise RangoFueraDeCorte(
            "Rango fuera del watermark temporal del dataset (strict_time=true)"
        )

    return d1, d2, False


def entidad_id(val: Any) -> str:
    """
    Valida entidad_id con patrón:
      AAA.(EST|MUN).TOKEN
    Ejemplo: GTO.MUN.LEON
    """
    if not isinstance(val, str):
        raise ValidacionError(f"entidad_id inválido: {val!r}")

    # Evito regex porque aquí es simple y da errores más claros:
    parts = val.split(".")
    if len(parts) != 3:
        raise ValidacionError(
            f"entidad_id inválido: {val!r} (formato AAA.(EST|MUN).ID)"
        )

    a, scope, ident = parts
    if len(a) != 3 or not a.isalpha() or not a.isupper():
        raise ValidacionError(
            f"entidad_id inválido: {val!r} (prefijo AAA en mayúsculas)"
        )

    if scope not in ("EST", "MUN"):
        raise ValidacionError(
            f"entidad_id inválido: {val!r} (scope debe ser EST o MUN)"
        )

    if not ident or any(
        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in ident
    ):
        raise ValidacionError(f"entidad_id inválido: {val!r} (ID solo A-Z, 0-9 y _)")

    return val
