"""The six allowlisted tools. Each has a strict Pydantic argument model, so a
malformed argument (e.g. a date passed as a string) fails validation in the
Gather node *before* the tool executes — it is never silently coerced.

Every tool returns a JSON-safe dict with a `passed` key: True/False for checks,
None for retrieve_policy_clause (informational, cannot fail a claim).
"""
from datetime import date
from typing import Awaitable, Callable

from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ToolName
from db.models import Claim, ClaimApproved, PolicyRule
from shared.policy import (
    DEFAULT_WINDOW_DAYS_OFFSET, DEFAULT_WINDOW_MONTHS, PRESCRIPTION_CHARGE, fp57_window_end,
)


class StrictArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ReceiptArgs(StrictArgs):
    fp57_form_ref: str
    fp57_receipt_issued: bool


class RetrieveArgs(StrictArgs):
    query: str


class ExemptionArgs(StrictArgs):
    exemption_category: str
    charge_paid_date: date


class WindowArgs(StrictArgs):
    exemption_category: str
    charge_paid_date: date
    claim_submitted_date: date


class DuplicateArgs(StrictArgs):
    fp57_form_ref: str


class RefundArgs(StrictArgs):
    patient_id: str
    charge_payment_verified: bool


async def _active_rule(session: AsyncSession, category: str, on: date) -> PolicyRule | None:
    stmt = select(PolicyRule).where(
        and_(
            PolicyRule.category == category,
            PolicyRule.superseded_by.is_(None),
            PolicyRule.effective_from <= on,
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def check_fp57_receipt(session: AsyncSession, a: ReceiptArgs, ctx: dict) -> dict:
    if a.fp57_receipt_issued:
        return {"passed": True, "detail": f"FP57 receipt {a.fp57_form_ref} was issued at point of payment."}
    return {
        "passed": False,
        "reason_code": "NO_FP57_RECEIPT",
        "detail": "No FP57 receipt was issued at point of payment; one cannot be issued retroactively.",
    }


async def retrieve_policy_clause(session: AsyncSession, a: RetrieveArgs, ctx: dict) -> dict:
    retriever = ctx["retriever"]
    chunk, score = retriever.search(a.query, k=1)[0]
    return {
        "passed": None,
        "citation": {"heading": chunk.heading, "text": chunk.text, "score": round(score, 4), "backend": retriever.backend},
        "detail": f"Retrieved policy clause: {chunk.heading}",
    }


async def check_exemption_category(session: AsyncSession, a: ExemptionArgs, ctx: dict) -> dict:
    rule = await _active_rule(session, a.exemption_category, a.charge_paid_date)
    if rule is None:
        return {
            "passed": False,
            "reason_code": "EXEMPTION_NOT_IN_POLICY",
            "detail": f"No active policy_rules entry for category '{a.exemption_category}' on {a.charge_paid_date}.",
        }
    return {
        "passed": True,
        "rule_id": rule.rule_id,
        "window_months": rule.window_months,
        "window_days_offset": rule.window_days_offset,
        "detail": f"Category {rule.category} is valid under policy rule {rule.rule_id}.",
    }


async def check_claim_window(session: AsyncSession, a: WindowArgs, ctx: dict) -> dict:
    rule = await _active_rule(session, a.exemption_category, a.charge_paid_date)
    months = rule.window_months if rule else DEFAULT_WINDOW_MONTHS
    offset = rule.window_days_offset if rule else DEFAULT_WINDOW_DAYS_OFFSET
    window_end = fp57_window_end(a.charge_paid_date, months, offset)
    days = (a.claim_submitted_date - a.charge_paid_date).days
    base = {"window_end": window_end.isoformat(), "days_since_payment": days}
    if a.claim_submitted_date < a.charge_paid_date:
        return {**base, "passed": False, "reason_code": "CLAIM_BEFORE_PAYMENT",
                "detail": "Claim is dated before the charge was paid."}
    if a.claim_submitted_date > window_end:
        return {**base, "passed": False, "reason_code": "OUTSIDE_CLAIM_WINDOW",
                "detail": f"Submitted {days} days after payment; window closed on {window_end}."}
    return {**base, "passed": True, "detail": f"Submitted {days} days after payment, within window ending {window_end}."}


async def check_duplicate(session: AsyncSession, a: DuplicateArgs, ctx: dict) -> dict:
    # Primary duplicate mechanism: an application-level SELECT. The unique
    # index on claims_approved.fp57_form_ref is only a last-resort backstop.
    stmt = select(ClaimApproved.claim_id).where(ClaimApproved.fp57_form_ref == a.fp57_form_ref)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return {"passed": False, "reason_code": "DUPLICATE_CLAIM",
                "detail": f"FP57 {a.fp57_form_ref} already has an approved refund."}
    return {"passed": True, "detail": f"No prior approved refund on FP57 {a.fp57_form_ref}."}


async def calculate_refund(session: AsyncSession, a: RefundArgs, ctx: dict) -> dict:
    on_file = (await session.execute(select(Claim.claim_id).where(Claim.patient_id == a.patient_id).limit(1))).first()
    if on_file is None:
        return {"passed": False, "reason_code": "UNKNOWN_PATIENT",
                "detail": f"Patient {a.patient_id} is not on file."}
    if not a.charge_payment_verified:
        return {"passed": False, "reason_code": "CHARGE_NOT_PAID",
                "detail": "No verified payment for this charge; nothing to refund."}
    return {"passed": True, "refund_amount": str(PRESCRIPTION_CHARGE),
            "detail": f"Refund of £{PRESCRIPTION_CHARGE} (current prescription charge)."}


ToolFn = Callable[[AsyncSession, BaseModel, dict], Awaitable[dict]]

# The allowlist: enum member -> (argument model, implementation). Nothing
# outside this mapping can ever be executed.
REGISTRY: dict[ToolName, tuple[type[StrictArgs], ToolFn]] = {
    ToolName.check_fp57_receipt: (ReceiptArgs, check_fp57_receipt),
    ToolName.retrieve_policy_clause: (RetrieveArgs, retrieve_policy_clause),
    ToolName.check_exemption_category: (ExemptionArgs, check_exemption_category),
    ToolName.check_claim_window: (WindowArgs, check_claim_window),
    ToolName.check_duplicate: (DuplicateArgs, check_duplicate),
    ToolName.calculate_refund: (RefundArgs, calculate_refund),
}


def build_args(tool: ToolName, claim: dict | None, question: str | None) -> dict:
    """Arguments come from the validated request, never from the LLM or from
    retrieved policy text."""
    if tool is ToolName.retrieve_policy_clause:
        if claim is None:
            return {"query": question or ""}
        return {"query": f"{claim['exemption_category']} exemption entitlement to free prescriptions "
                         f"supporting an FP57 refund"}
    if claim is None:
        return {}
    fields = REGISTRY[tool][0].model_fields
    return {k: claim[k] for k in fields if k in claim}
