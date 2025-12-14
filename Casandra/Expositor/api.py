# Expositor/api.py
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
# si usas mayúsculas: from Casandra.Expositor.middleware import JobIdMiddleware
from .middleware import JobIdMiddleware

# si usas mayúsculas: from Casandra.Celador.guardia import celar
from ..Celador.guardia import celar
from ..Celador.validaciones import validar_rango, requeridos
from datetime import date

app = FastAPI()
app.add_middleware(JobIdMiddleware)


@celar("demo_rank@1.0.0", schema_version="1.0.0", tool_version="1.0.0")
def demo_rank(
    *, entidad_id: str, from_: str, to_: str, strict_time: bool = False
) -> dict:
    requeridos(locals(), ["entidad_id", "from_", "to_"])
    # ancla temporal ficticia v0; conectaremos a /dataset/metadata luego
    min_d, max_d = date(2024, 1, 1), date(2025, 8, 13)
    ef1, ef2, adjusted = validar_rango(from_, to_, min_d, max_d, strict_time)
    # devolver un Sobre OK mínimo
    return {
        "status": "ok",
        "tool": "demo_rank@1.0.0",
        "summary": {"headline": f"Ventana efectiva {ef1}..{ef2}", "highlights": []},
        "data": {
            "inline": {
                "columns": [],
                "rows": [],
                "limit_notice": {"applied": False, "max_rows": 50},
            }
        },
        "evidence": [],
        "meta": {
            "schema_version": "1.0.0",
            "tool_version": "1.0.0",
            "date_range_effective": {"from": str(ef1), "to": str(ef2)},
            "range_adjusted": adjusted,
        },
    }


@app.get("/demo/rank")
def demo_rank_http(
    entidad_id: str = Query(...),
    from_: str = Query(..., alias="from"),
    to_: str = Query(..., alias="to"),
    strict_time: bool = Query(False),
):
    sobre, http = demo_rank(
        entidad_id=entidad_id, from_=from_, to_=to_, strict_time=strict_time
    )
    return JSONResponse(content=sobre, status_code=http)