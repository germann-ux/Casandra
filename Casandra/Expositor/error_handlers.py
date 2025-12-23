# casandra/expositor/error_handlers.py
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from ..Celador.auditoria import audit, get_job_id
from ..Celador.errores import (
    CeladorError,
    a_sobre_error,
    error_code_http,
    sobre_compute_error,
)
from ..dominio.nombres import EXPOSITOR, SYSTEM


def register_error_handlers(app) -> None:
    @app.exception_handler(CeladorError)
    async def celador_error_handler(request: Request, exc: CeladorError):
        jid = get_job_id()
        code, http = error_code_http(exc)

        audit(
            "unhandled_celador_error",
            {
                "job_id": jid,
                "component": EXPOSITOR,
                "path": request.url.path,
                "method": request.method,
                "code": code,
                "error": type(exc).__name__,
                "details": str(exc),
            },
        )

        # Aquí el "productor" del sobre es la capa HTTP (Expositor), no una tool específica.
        sobre = a_sobre_error(exc, tool_name=EXPOSITOR, hints=[])
        return JSONResponse(content=sobre, status_code=http, headers={"X-Job-Id": jid})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        jid = get_job_id()

        audit(
            "unhandled_exception",
            {
                "job_id": jid,
                "component": EXPOSITOR,
                "path": request.url.path,
                "method": request.method,
                "error": type(exc).__name__,
                "details": str(exc),
            },
        )

        sobre = sobre_compute_error(
            tool_name=SYSTEM,
            details="Error interno no controlado.",
        )
        return JSONResponse(content=sobre, status_code=500, headers={"X-Job-Id": jid})
