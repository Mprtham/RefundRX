"""Hash-chained audit_log append, plus the atomic approval write.

Transaction order (one transaction):
  1. SELECT latest audit_log row ... FOR UPDATE   (lock held only for this write;
     it is taken after the LLM call and all tool execution have finished)
  2. INSERT INTO audit_log (...) RETURNING audit_id
  3. on APPROVED: INSERT INTO claims, then INSERT INTO claims_approved (..., audit_id)
If any insert fails the whole transaction rolls back.
"""
import asyncio
import random
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from db.models import AuditLog, Claim, ClaimApproved
from shared.audit_hash import compute_audit_hash
from shared.policy import PRESCRIPTION_CHARGE

MAX_ATTEMPTS = 12


class AuditWriteError(Exception):
    pass


def _approval_rows(claim: dict, audit_id: int) -> tuple[Claim, ClaimApproved]:
    claim_id = uuid.uuid4()
    row = Claim(
        claim_id=claim_id,
        fp57_form_ref=claim["fp57_form_ref"],
        patient_id=claim["patient_id"],
        fp57_receipt_issued=claim["fp57_receipt_issued"],
        charge_payment_verified=claim["charge_payment_verified"],
        charge_paid_date=date.fromisoformat(str(claim["charge_paid_date"])),
        claim_submitted_date=date.fromisoformat(str(claim["claim_submitted_date"])),
        exemption_category=claim["exemption_category"],
        amount_paid=Decimal(PRESCRIPTION_CHARGE),
        pharmacy=None,
    )
    approved = ClaimApproved(
        claim_id=claim_id,
        fp57_form_ref=claim["fp57_form_ref"],
        approved_date=datetime.now(timezone.utc),
        audit_id=audit_id,
    )
    return row, approved


async def write_decision(
    sessionmaker: async_sessionmaker,
    *,
    trace_id: str,
    plan_json: dict,
    trace_json: dict,
    decision: str,
    model_version: str,
    claim: dict | None,
) -> tuple[int, str, str, dict]:
    """Returns (audit_id, current_hash, final_decision, final_trace_json)."""
    for attempt in range(MAX_ATTEMPTS):
        if attempt:
            await asyncio.sleep(random.uniform(0, 0.02 * attempt))
        try:
            async with sessionmaker() as s, s.begin():
                head = (
                    await s.execute(
                        select(AuditLog).order_by(AuditLog.audit_id.desc()).limit(1).with_for_update()
                    )
                ).scalar_one_or_none()
                prev_hash = head.current_hash if head else None
                current_hash = compute_audit_hash(prev_hash, plan_json, trace_json, decision)
                row = AuditLog(
                    trace_id=uuid.UUID(trace_id),
                    created_at=datetime.now(timezone.utc),
                    plan_json=plan_json,
                    trace_json=trace_json,
                    decision=decision,
                    prev_hash=prev_hash,
                    current_hash=current_hash,
                    model_version=model_version,
                )
                s.add(row)
                await s.flush()  # INSERT ... RETURNING audit_id
                if decision == "APPROVED":
                    claim_row, approved = _approval_rows(claim, row.audit_id)
                    s.add(claim_row)
                    await s.flush()
                    s.add(approved)
                    await s.flush()
            return row.audit_id, current_hash, decision, trace_json
        except IntegrityError as e:
            if decision == "APPROVED" and "fp57_form_ref" in str(e.orig):
                # DB-level backstop fired: the app-level duplicate SELECT missed a
                # concurrent approval. Whole transaction rolled back; record the
                # rejection instead.
                decision = "REJECTED"
                trace_json = {
                    **trace_json,
                    "outcome": {
                        "reason_code": "DUPLICATE_CLAIM",
                        "reasons": ["Duplicate caught by the claims_approved unique-index backstop."],
                        "refund_amount": None,
                    },
                }
            # Otherwise a concurrent append took the same chain head
            # (uq_audit_log_chain_link); retry against the new head.
    raise AuditWriteError("could not append to audit_log after retries")
