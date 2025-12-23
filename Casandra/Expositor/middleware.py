# casandra/expositor/middleware.py
from __future__ import annotations

import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..Celador.auditoria import audit, set_job_id


_JOB_ID_RE = re.compile(r"^[a-f0-9]{16,64}$", re.IGNORECASE)  # uuid4 hex = 32 chars


def _extract_job_id(request: Request) -> str | None:
    # Starlette normaliza headers a case-insensitive, pero mantenemos el nombre.
    jid = request.headers.get("X-Job-Id")
    if not jid:
        return None
    jid = jid.strip()
    if not _JOB_ID_RE.match(jid):
        return None
    return jid


class JobIdMiddleware(BaseHTTPMiddleware):
    """Middleware que garantiza job_id contextual + auditoría básica."""

    async def dispatch(self, request: Request, call_next):
        incoming = _extract_job_id(request)
        jid = set_job_id(
            incoming
        )  # si viene válido lo preserva; si no, genera uno nuevo

        audit(
            "request_in",
            {
                "job_id": jid,
                "path": request.url.path,
                "method": request.method,
            },
        )

        try:
            resp: Response = await call_next(request)
        except Exception as e:
            # Auditoría best-effort de excepción; el handler global de FastAPI decidirá el response final.
            audit(
                "request_exception",
                {
                    "job_id": jid,
                    "path": request.url.path,
                    "method": request.method,
                    "error": type(e).__name__,
                    "details": str(e),
                },
            )
            raise

        resp.headers["X-Job-Id"] = jid  # trazabilidad hacia el cliente

        audit(
            "response_out",
            {
                "job_id": jid,
                "status_code": resp.status_code,
            },
        )

        return resp
