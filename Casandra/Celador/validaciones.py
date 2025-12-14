# casandra/celador/validaciones.py
import re
from datetime import date
from .errores import ValidacionError, RangoFueraDeCorte

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def requeridos(payload: dict, campos: list[str]) -> None:
    faltan = [c for c in campos if payload.get(c) in (None, "", [])]
    if faltan:
        raise ValidacionError(f"Faltan campos requeridos: {', '.join(faltan)}")


def iso_date(s: str) -> date:
    if not isinstance(s, str) or not ISO_DATE_RE.match(s):
        raise ValidacionError(f"Fecha inválida (ISO-YYYY-MM-DD esperado): {s!r}")
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def validar_rango(
    from_s: str, to_s: str, min_date: date, max_date: date, strict_time: bool
) -> tuple[date, date, bool]:
    d1, d2 = iso_date(from_s), iso_date(to_s)
    if d1 > d2:
        raise ValidacionError("from > to")
    adj = False
    ef1, ef2 = d1, d2
    if not strict_time:
        if ef1 < min_date:
            ef1, adj = min_date, True
        if ef2 > max_date:
            ef2, adj = max_date, True
        return ef1, ef2, adj
    # strict: lanzar error si se sale de rango
    if d1 < min_date or d2 > max_date:
        raise RangoFueraDeCorte("Rango fuera del watermark temporal del dataset")
    return d1, d2, False


ENTIDAD_ID_RE = re.compile(
    r"^[A-Z]{3}\.(?:EST|MUN)\.[A-Z0-9_]+$"
)  # ejemplo: GTO.MUN.LEON


def entidad_id(val: str) -> str:
    if not isinstance(val, str) or not ENTIDAD_ID_RE.match(val):
        raise ValidacionError(f"entidad_id inválido: {val!r}")
    return val
