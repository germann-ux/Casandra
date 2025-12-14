# casandra/celador/auditoria.py
from __future__ import annotations
import hashlib, json, os, time, uuid
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

job_id_ctx: ContextVar[str] = ContextVar("job_id", default="")
AUDIT_DIR = Path(os.getenv("CASANDRA_AUDIT_DIR", "./data/audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def new_job_id() -> str:
    try:
        return uuid.uuid4().hex  # py>=3.13; fallback abajo
    except AttributeError:
        return uuid.uuid4().hex


def set_job_id(jid: Optional[str] = None) -> str:
    jid = jid or new_job_id()
    job_id_ctx.set(jid)
    return jid


def get_job_id() -> str:
    jid = job_id_ctx.get()
    return jid or set_job_id()


def query_hash(plan_normalizado: dict, catalog_version: str) -> str:
    blob = json.dumps(
        {"plan": plan_normalizado, "catalog_version": catalog_version}, sort_keys=True
    ).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


@dataclass
class AuditRecord:
    job_id: str
    when_ms: int
    stage: str
    payload: dict[str, Any]


def audit(stage: str, payload: dict[str, Any]) -> None:
    rec = AuditRecord(
        job_id=get_job_id(),
        when_ms=int(time.time() * 1000),
        stage=stage,
        payload=payload,
    )
    out = AUDIT_DIR / f"{rec.job_id}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
