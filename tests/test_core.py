import asyncio
import uuid
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app.agent.planner import PlannerError
from app.schemas import ClaimInput, Plan, ToolName
from db.models import AuditLog, ClaimApproved
from scripts.verify_audit_chain import verify_chain
from shared.audit_hash import compute_audit_hash
from shared.policy import fp57_window_end
from tests.evals.fixtures import KNOWN_PATIENT, _claim
from tests.evals.test_scenarios import plan_adherence_ok, plan_quality_ok


# --- shared/policy.py -------------------------------------------------------

@pytest.mark.parametrize("paid, end", [
    (date(2026, 1, 15), date(2026, 4, 14)),
    (date(2026, 11, 30), date(2027, 2, 27)),   # month-end clamps to Feb 28, less a day
    (date(2028, 11, 30), date(2029, 2, 27)),
    (date(2027, 12, 1), date(2028, 2, 29)),    # leap year
])
def test_window_is_three_months_less_a_day(paid, end):
    assert fp57_window_end(paid) == end


# --- shared/audit_hash.py ---------------------------------------------------

def test_hash_ignores_key_order():
    a = compute_audit_hash("p", {"b": 1, "a": [1, {"y": 2, "x": 1}]}, {"t": 1}, "APPROVED")
    b = compute_audit_hash("p", {"a": [1, {"x": 1, "y": 2}], "b": 1}, {"t": 1}, "APPROVED")
    assert a == b


def test_hash_covers_trace_json():
    base = compute_audit_hash(None, {"p": 1}, {"t": 1}, "APPROVED")
    assert compute_audit_hash(None, {"p": 1}, {"t": 2}, "APPROVED") != base
    assert compute_audit_hash(None, {"p": 1}, {"t": 1}, "REJECTED") != base


# --- API schema -------------------------------------------------------------

@pytest.mark.parametrize("over", [
    {"exemption_category": "PPC"},          # out of scope -> clean 422, never a crash
    {"exemption_category": "HC3"},
    {"patient_id": "1234567890"},           # not in the 999 test range
    {"claim_submitted_date": date.today() + timedelta(days=1)},
])
def test_claim_input_rejects(over):
    with pytest.raises(ValidationError):
        ClaimInput(**_claim(**over))


def test_amount_paid_is_not_caller_supplied():
    assert "amount_paid" not in ClaimInput.model_fields


def test_plan_enum_rejects_unknown_tool():
    with pytest.raises(ValidationError):
        Plan(route="assess_claim", steps=["check_receipt"])


# --- planner failure modes --------------------------------------------------

class SkipsReceiptPlanner:
    model_version = "test-bad-planner"

    async def plan(self, claim, question):
        return Plan(route="assess_claim", steps=[
            ToolName.retrieve_policy_clause, ToolName.check_exemption_category, ToolName.check_claim_window,
            ToolName.check_duplicate, ToolName.calculate_refund,
        ])


class BrokenPlanner:
    model_version = "test-broken-planner"

    async def plan(self, claim, question):
        raise PlannerError("model returned junk")


async def test_hard_gate_holds_when_planner_omits_receipt_check(make_agent):
    resp = await make_agent(SkipsReceiptPlanner()).run(claim=_claim(fp57_receipt_issued=False))
    plan = [p.value for p in resp.plan]
    executed = [t.tool.value for t in resp.trace]
    # Gather did NOT inject the missing step ...
    assert "check_fp57_receipt" not in executed
    # ... the evals flag the plan ...
    assert not plan_quality_ok(plan, True)
    assert plan_adherence_ok(plan, executed)
    # ... and Decision still refuses the claim.
    assert resp.decision == "REJECTED" and resp.reason_code == "NO_FP57_RECEIPT"


async def test_omitted_receipt_check_blocks_approval_even_with_receipt(make_agent):
    resp = await make_agent(SkipsReceiptPlanner()).run(claim=_claim())
    assert resp.decision == "REJECTED" and resp.reason_code == "INCOMPLETE_PLAN"


async def test_planner_failure_is_a_rejection_not_a_crash(make_agent, db):
    resp = await make_agent(BrokenPlanner()).run(claim=_claim())
    assert resp.decision == "REJECTED" and resp.reason_code == "PLANNING_FAILED"
    async with db() as s:
        assert (await s.run_sync(verify_chain))[0]


# --- audit chain ------------------------------------------------------------

async def test_tamper_is_detected(make_agent, db):
    agent = make_agent()
    for i in range(3):
        await agent.run(claim=_claim(fp57_form_ref=f"FP57-T-{i}"))
    async with db() as s, s.begin():
        await s.execute(update(AuditLog).where(AuditLog.audit_id == 2).values(trace_json={"steps": []}))
    async with db() as s:
        ok, msg = await s.run_sync(verify_chain)
    assert not ok and "audit_id 2" in msg


async def test_concurrent_decisions_keep_a_linear_chain(make_agent, db):
    agent = make_agent()
    results = await asyncio.gather(*[
        agent.run(claim=_claim(fp57_form_ref=f"FP57-C-{i}")) for i in range(8)
    ])
    assert all(r.decision == "APPROVED" for r in results)
    async with db() as s:
        ok, msg = await s.run_sync(verify_chain)
        assert ok, msg
        assert await s.scalar(select(func.count()).select_from(AuditLog)) == 8


async def test_concurrent_same_form_approves_exactly_once(make_agent, db):
    agent = make_agent()
    results = await asyncio.gather(*[
        agent.run(claim=_claim(fp57_form_ref="FP57-RACE")) for _ in range(4)
    ])
    assert sorted(r.decision for r in results).count("APPROVED") == 1
    assert all(r.reason_code == "DUPLICATE_CLAIM" for r in results if r.decision == "REJECTED")
    async with db() as s:
        assert await s.scalar(select(func.count()).select_from(ClaimApproved)) == 1
        ok, msg = await s.run_sync(verify_chain)
        assert ok, msg


async def test_approval_links_to_its_audit_row(make_agent, db):
    resp = await make_agent().run(claim=_claim(fp57_form_ref="FP57-LINK"))
    async with db() as s:
        approved = (await s.execute(select(ClaimApproved).where(ClaimApproved.fp57_form_ref == "FP57-LINK"))).scalar_one()
        audit = await s.get(AuditLog, approved.audit_id)
    assert audit.trace_id == uuid.UUID(resp.trace_id) and audit.decision == "APPROVED"
    assert audit.trace_json["input"]["patient_id"] == KNOWN_PATIENT
