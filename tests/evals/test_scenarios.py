"""Deterministic evaluation of the ten scenarios (runs in CI, no LLM needed).

Per scenario: decision, reason code, tool trace (DeepEval ToolCorrectnessMetric,
order-sensitive), plan quality (receipt check first, every required check
planned) and plan adherence (executed tools follow the plan in order), plus
audit-chain integrity after the run. LLM-judged metrics live in
test_llm_judged.py.
"""
import uuid

import pytest
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent.graph import REQUIRED_CHECKS
from db.models import AuditLog
from scripts.verify_audit_chain import verify_chain
from tests.conftest import pre_approve, withdraw_categories
from tests.evals.fixtures import SCENARIOS, Scenario
from tests.evals.judge import NoLLM

AGENT_SCENARIOS = [s for s in SCENARIOS if s.kind != "api_422"]


def plan_quality_ok(plan: list[str], route_has_claim: bool) -> bool:
    if not route_has_claim:
        return plan == ["retrieve_policy_clause"]
    return (
        bool(plan)
        and plan[0] == "check_fp57_receipt"
        and all(c.value in plan for c in REQUIRED_CHECKS)
        and plan.count("retrieve_policy_clause") == 1
        and plan[-1] == "calculate_refund"
    )


def plan_adherence_ok(plan: list[str], executed: list[str]) -> bool:
    # Gather stops at the first failed check, so execution must be a prefix of the plan.
    return executed == plan[: len(executed)]


async def run_scenario(sc: Scenario, make_agent, db):
    if sc.withdrawn_categories:
        await withdraw_categories(db, sc.withdrawn_categories)
    for form in sc.pre_approved_forms:
        await pre_approve(db, form)
    return await make_agent().run(claim=sc.claim, question=sc.question, arg_overrides=sc.arg_overrides)


@pytest.mark.parametrize("sc", AGENT_SCENARIOS, ids=lambda s: s.id)
async def test_scenario(sc: Scenario, make_agent, db):
    resp = await run_scenario(sc, make_agent, db)
    plan = [p.value for p in resp.plan]
    executed = [t.tool.value for t in resp.trace]

    assert resp.decision == sc.expected_decision, resp.reasons
    assert resp.reason_code == sc.expected_reason
    assert executed == sc.expected_tools
    assert plan_quality_ok(plan, sc.claim is not None), f"plan quality: {plan}"
    assert plan_adherence_ok(plan, executed), f"adherence: plan={plan} executed={executed}"

    tc = LLMTestCase(
        input=str(sc.claim or sc.question),
        actual_output=resp.decision,
        tools_called=[ToolCall(name=t.tool.value, input_parameters=t.args, output=t.result) for t in resp.trace],
        expected_tools=[ToolCall(name=n) for n in sc.expected_tools],
    )
    metric = ToolCorrectnessMetric(
        model=NoLLM(), should_consider_ordering=True, should_exact_match=True, async_mode=False
    )
    metric.measure(tc)
    assert metric.score == 1.0, metric.reason

    # The retrieval is an explicit, logged tool call — never a silent fetch.
    if sc.expected_decision != "NO_CLAIM_MADE" and "retrieve_policy_clause" in executed:
        assert resp.citation is not None

    # Every decision is hash-chained; informational answers are not decisions.
    async with db() as s:
        ok, msg = await s.run_sync(verify_chain)
        assert ok, msg
        rows = await s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.trace_id == uuid.UUID(resp.trace_id)))
    assert rows == (0 if sc.kind == "info" else 1)
    if sc.kind == "claim":
        assert resp.audit_id is not None and resp.current_hash


def test_scenario_07_api_boundary_422(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.main import app

    sc = next(s for s in SCENARIOS if s.kind == "api_422")
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    try:
        body = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in sc.claim.items()}
        with TestClient(app) as client:
            r = client.post("/claims", json=body)
            assert r.status_code == 422
            assert r.json()["stage"] == "api_boundary"
            assert any(e["loc"][-1] == "patient_id" for e in r.json()["detail"])
            # No plan, no trace, no audit row: the Planner never ran.
            v = client.get("/audit/verify").json()
            assert v["message"] == "No logs to verify."
    finally:
        get_settings.cache_clear()
