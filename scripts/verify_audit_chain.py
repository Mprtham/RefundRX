"""Walk audit_log in audit_id order and verify the hash chain.

Uses the same shared/audit_hash.py:compute_audit_hash() the Decision node
writes with. Integrity-checked, not externally anchored: this detects casual
edits, not an attacker with full database access.

Run:  python -m scripts.verify_audit_chain
"""
import asyncio

from sqlalchemy.orm import Session

from db.models import AuditLog
from shared.audit_hash import compute_audit_hash


def verify_chain(db: Session):
    logs = db.query(AuditLog).order_by(AuditLog.audit_id.asc()).all()
    if not logs:
        return True, "No logs to verify."

    expected_prev = None
    for log in logs:
        if log.prev_hash != expected_prev:
            return False, f"Chain broken at audit_id {log.audit_id}: prev_hash mismatch."
        recomputed = compute_audit_hash(log.prev_hash, log.plan_json, log.trace_json, log.decision)
        if recomputed != log.current_hash:
            return False, f"Tamper detected at audit_id {log.audit_id}: hash mismatch."
        expected_prev = log.current_hash

    return True, f"Integrity verified across {len(logs)} records."


async def _main() -> int:
    from app.config import get_settings
    from db.session import make_engine, make_sessionmaker

    engine = make_engine(get_settings().database_url)
    async with make_sessionmaker(engine)() as s:
        ok, msg = await s.run_sync(verify_chain)
    await engine.dispose()
    print(("OK: " if ok else "FAIL: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
