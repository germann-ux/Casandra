# casandra/expositor/api.py
from __future__ import annotations

from datetime import date

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from .error_handlers import register_error_handlers
from .middleware import JobIdMiddleware

from ..Celador.guardia import celar
from ..Celador.validaciones import (
    requeridos,
    validar_rango,
    entidad_id as validar_entidad_id,
)
from ..dominio.nombres import tool_name


app = FastAPI()
app.add_middleware(JobIdMiddleware)
register_error_handlers(app)


# --- Canonical tool identity (single source of truth) ---
TOOL_ID = "demo_rank"
TOOL_VER = "1.0.0"
DEMO_RANK_TOOL = tool_name(TOOL_ID, TOOL_VER)


# Tool (sin FastAPI adentro)
@celar(DEMO_RANK_TOOL, schema_version="1.0.0", tool_version=TOOL_VER)
def demo_rank(
    *, entidad_id: str, from_: date, to_: date, strict_time: bool = False
) -> dict:
    requeridos(
        {"entidad_id": entidad_id, "from": from_, "to": to_},
        ["entidad_id", "from", "to"],
    )
    entidad_id = validar_entidad_id(entidad_id)

    # Ancla temporal ficticia v0; luego vendrá de /dataset/metadata
    min_d, max_d = date(2024, 1, 1), date(2025, 8, 13)

    ef1, ef2, adjusted = validar_rango(from_, to_, min_d, max_d, strict_time)

    return {
        "status": "ok",
        "tool": DEMO_RANK_TOOL,
        "summary": {
            "headline": f"Ventana efectiva {ef1}..{ef2}",
            "highlights": [],
        },
        "data": {
            "inline": {
                "columns": [],
                "rows": [],
                "limit_notice": {"applied": False, "max_rows": 50},
            }
        },
        "evidence": [],
        "meta": {
            "date_range_effective": {"from": str(ef1), "to": str(ef2)},
            "range_adjusted": adjusted,
        },
    }


@app.get("/demo/rank")
def demo_rank_http(
    entidad_id: str = Query(...),
    from_: date = Query(..., alias="from"),
    to_: date = Query(..., alias="to"),
    strict_time: bool = Query(False),
):
    sobre, http = demo_rank(
        entidad_id=entidad_id, from_=from_, to_=to_, strict_time=strict_time
    )
    return JSONResponse(content=sobre, status_code=http)
