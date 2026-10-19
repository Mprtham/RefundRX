"""LLM-judged DeepEval metrics over the agent scenarios.

Not run in CI (needs a Groq key and costs free-tier quota). Run locally:
    GROQ_API_KEY=... DEEPEVAL_JUDGE=1 EVAL_PLANNER=groq pytest -m llm_judged

Thresholds are the KPI targets. n=9 agent scenarios: indicative only, not
statistically powered.
"""
import os

import pytest
from deepeval.metrics import FaithfulnessMetric, GEval, PlanAdherenceMetric, PlanQualityMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall

from tests.evals.fixtures import SCENARIOS
from tests.evals.test_scenarios import run_scenario

pytestmark = [
    pytest.mark.llm_judged,
    pytest.mark.skipif(
        not (os.getenv("GROQ_API_KEY") and os.getenv("DEEPEVAL_JUDGE") == "1"),
        reason="LLM-judged evals need GROQ_API_KEY and DEEPEVAL_JUDGE=1",
    ),
]

AGENT_SCENARIOS = [s for s in SCENARIOS if s.kind != "api_422"]


def expected_output(sc) -> str:
    if sc.expected_decision == "APPROVED":
        return "APPROVED: the claim is eligible and the refund is £9.90."
    if sc.expected_decision == "NO_CLAIM_MADE":
        return "No claim was made; the agent answers the question from FP57 policy without a decision."
    return f"REJECTED ({sc.expected_reason}); no refund is paid."


def build_case(sc, resp) -> LLMTestCase:
    actual = f"{resp.decision} ({resp.reason_code}). " + " ".join(resp.reasons)
    if resp.refund_amount:
        actual += f" Refund: £{resp.refund_amount}."
    context = [resp.citation.text] if resp.citation else []
    context += [t.result.get("detail", "") for t in resp.trace]
    tc = LLMTestCase(
        input=f"FP57 refund request: {sc.claim}" if sc.claim else sc.question,
        actual_output=actual,
        expected_output=expected_output(sc),
        retrieval_context=context or ["(no context retrieved)"],
        tools_called=[ToolCall(name=t.tool.value, input_parameters=t.args, output=t.result) for t in resp.trace],
    )
    # Plan metrics read the agent trace: the Planner's generated plan plus the
    # logged tool calls — exactly what is written to audit_log.
    tc._trace_dict = {
        "name": "RefundRx",
        "input": tc.input,
        "output": actual,
        "children": [
            {"name": "planner", "type": "agent", "output": {"plan": [p.value for p in resp.plan]}},
            *[{"name": t.tool.value, "type": "tool", "input": t.args, "output": t.result} for t in resp.trace],
        ],
    }
    return tc


@pytest.fixture(scope="module")
def judge():
    from tests.evals.judge import GroqJudge
    return GroqJudge()


@pytest.mark.parametrize("sc", AGENT_SCENARIOS, ids=lambda s: s.id)
async def test_llm_judged(sc, make_agent, db, judge):
    resp = await run_scenario(sc, make_agent, db)
    tc = build_case(sc, resp)
    metrics = [
        GEval(
            name="Answer correctness",
            criteria="Does the actual output reach the same eligibility conclusion (approved / rejected / "
                     "no claim) and the same refund amount as the expected output?",
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
            model=judge, threshold=0.9, async_mode=False,
        ),
        FaithfulnessMetric(model=judge, threshold=0.95, async_mode=False),
    ]
    if sc.claim is not None:
        metrics += [
            PlanQualityMetric(model=judge, threshold=0.85, async_mode=False),
            PlanAdherenceMetric(model=judge, threshold=0.85, async_mode=False),
        ]
    failures = []
    for m in metrics:
        m.measure(tc)
        print(f"{sc.id} {m.__class__.__name__ if not isinstance(m, GEval) else m.name}: {m.score:.2f}")
        if not m.is_successful():
            failures.append(f"{getattr(m, 'name', type(m).__name__)}={m.score:.2f}: {m.reason}")
    assert not failures, "\n".join(failures)
