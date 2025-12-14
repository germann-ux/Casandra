# casandra/expositor/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from ..Celador.auditoria import set_job_id, audit


class JobIdMiddleware(BaseHTTPMiddleware):
    """middleware con job Id"""

    async def dispatch(self, request, call_next):
        jid = set_job_id()  # genera y propaga contextualmente
        audit("request_in", {"path": request.url.path, "method": request.method})
        resp: Response = await call_next(request)
        resp.headers["X-Job-Id"] = jid  # trazabilidad cliente
        audit("response_out", {"status_code": resp.status_code})
        return resp