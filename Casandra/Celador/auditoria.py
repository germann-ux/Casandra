# casandra/celador/auditoria.py
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


job_id_ctx: ContextVar[str] = ContextVar("job_id", default="")

AUDIT_DIR = Path(os.getenv("CASANDRA_AUDIT_DIR", "./data/audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def new_job_id() -> str:
    # uuid4().hex existe desde siempre; no requiere fallback.
    return uuid.uuid4().hex


def set_job_id(jid: Optional[str] = None) -> str:
    jid = jid or new_job_id()
    job_id_ctx.set(jid)
    return jid


def get_job_id() -> str:
    # Si no hay job_id activo, genera uno automáticamente.
    jid = job_id_ctx.get()
    return jid or set_job_id()


def query_hash(plan_normalizado: dict[str, Any], catalog_version: str) -> str:
    """
    Hash estable del plan (normalizado) + versión del catálogo.
    Útil para correlación y caching.
    """
    blob = json.dumps(
        {"plan": plan_normalizado, "catalog_version": catalog_version},
        sort_keys=True,
        ensure_ascii=False,
        default=str,  # evita reventar si algo no es serializable
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


@dataclass(frozen=True)
class AuditRecord:
    job_id: str
    when_ms: int
    stage: str
    payload: dict[str, Any]


def _audit_file_for_day(ts_ms: int) -> Path:
    # Un archivo por día evita explosión de archivos por job.
    day = time.strftime("%Y-%m-%d", time.localtime(ts_ms / 1000))
    return AUDIT_DIR / f"audit_{day}.jsonl"


def audit(stage: str, payload: dict[str, Any]) -> None:
    """
    Escribe un evento de auditoría en JSONL.
    Regla: auditoría nunca debe tumbar el request (best-effort).
    """
    when_ms = int(time.time() * 1000)
    rec = AuditRecord(
        job_id=get_job_id(),
        when_ms=when_ms,
        stage=stage,
        payload=payload,
    )

    out = _audit_file_for_day(when_ms)
    try:
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rec), ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Best-effort: si falla escribir, no rompemos el flujo principal.
        # (Si quieres, aquí luego metemos fallback a stderr/logger)
        return
