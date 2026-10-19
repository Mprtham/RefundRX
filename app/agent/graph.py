"""Three-node LangGraph flow: Planner -> Gather -> Decision.

Stateless across requests: every call builds a fresh state with one trace ID.
No conversation memory, no checkpointer.
"""
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from app.agent.audit import write_decision
from app.agent.planner import PlannerError
from app.agent.tools import REGISTRY, build_args
from app.schemas import ClaimResponse, ToolName

# All of these must have passed before a claim can be APPROVED.
REQUIRED_CHECKS = (
    ToolName.check_fp57_receipt,
    ToolName.check_exemption_category,
    ToolName.check_claim_window,
    ToolName.check_duplicate,
    ToolName.calculate_refund,
)


class AgentState(TypedDict, total=False):
    trace_id: str
    claim: dict | None
    question: str | None
    # Test-only hook that simulates the LLM supplying a malformed tool
    # argument (Scenario 10). Never reachable from the API.
    arg_overrides: dict[str, dict[str, Any]]
    plan: dict | None
    planner_error: str | None
    trace: list[dict]
    response: dict


def _decide(claim: dict, trace: list[dict]) -> tuple[str, str, list[str], str | None]:
    """Returns (decision, reason_code, reasons, refund_amount)."""
    # Hard gate, enforced here regardless of what the Planner planned.
    if not claim["fp57_receipt_issued"]:
        return "REJECTED", "NO_FP57_RECEIPT", [
            "No FP57 receipt was issued at point of payment (hard gate)."
        ], None

    failed = next((t for t in trace if t["result"].get("passed") is False), None)
    if failed is not None:
        return "REJECTED", failed["result"]["reason_code"], [failed["result"]["detail"]], None

    passed = {t["tool"] for t in trace if t["result"].get("passed") is True}
    missing = [c.value for c in REQUIRED_CHECKS if c.value not in passed]
    if missing:
        return "REJECTED", "INCOMPLETE_PLAN", [
            f"Cannot approve: required checks were not executed: {', '.join(missing)}."
        ], None

    refund = next(t["result"]["refund_amount"] for t in trace if t["tool"] == ToolName.calculate_refund.value)
    return "APPROVED", "ELIGIBLE", [t["result"]["detail"] for t in trace if t["result"].get("passed")], refund


def build_graph(*, planner, sessionmaker, retriever):
    async def planner_node(state: AgentState) -> AgentState:
        try:
            plan = await planner.plan(state.get("claim"), state.get("question"))
            return {"plan": plan.model_dump(mode="json"), "planner_error": None}
        except PlannerError as e:
            return {"plan": None, "planner_error": str(e)}

    async def gather_node(state: AgentState) -> AgentState:
        trace: list[dict] = []
        plan = state.get("plan")
        if not plan:
            return {"trace": trace}
        overrides = state.get("arg_overrides") or {}
        ctx = {"retriever": retriever}
        async with sessionmaker() as session:
            for i, name in enumerate(plan["steps"], start=1):
                tool = ToolName(name)  # enum-constrained: unknown names cannot reach here
                arg_model, fn = REGISTRY[tool]
                args = {**build_args(tool, state.get("claim"), state.get("question")), **overrides.get(name, {})}
                try:
                    validated = arg_model.model_validate(args)
                except ValidationError as e:
                    result = {
                        "passed": False,
                        "reason_code": "ARGUMENT_VALIDATION_FAILED",
                        "detail": f"Argument validation failed for {name}; tool not executed.",
                        "errors": [
                            {"loc": list(err["loc"]), "type": err["type"], "msg": err["msg"],
                             "input_type": type(err.get("input")).__name__}
                            for err in e.errors()
                        ],
                    }
                else:
                    result = await fn(session, validated, ctx)
                trace.append({"step": i, "tool": name, "args": to_jsonable_python(args), "result": result})
                if result.get("passed") is False:
                    break  # stop at the first failed check
        return {"trace": trace}

    async def decision_node(state: AgentState) -> AgentState:
        claim, trace = state["claim"], state.get("trace", [])
        decision, code, reasons, refund = _decide(claim, trace)
        if state.get("planner_error") and code == "INCOMPLETE_PLAN":
            code, reasons = "PLANNING_FAILED", [state["planner_error"]]

        plan_json = {"route": (state.get("plan") or {}).get("route"),
                     "steps": (state.get("plan") or {}).get("steps", []),
                     "planner_error": state.get("planner_error")}
        trace_json = {
            "input": to_jsonable_python(claim),
            "steps": trace,
            "outcome": {"reason_code": code, "reasons": reasons, "refund_amount": refund},
        }
        audit_id, current_hash, decision, trace_json = await write_decision(
            sessionmaker,
            trace_id=state["trace_id"],
            plan_json=plan_json,
            trace_json=trace_json,
            decision=decision,
            model_version=planner.model_version,
            claim=to_jsonable_python(claim),
        )
        outcome = trace_json["outcome"]
        return {"response": {
            "decision": decision, "reason_code": outcome["reason_code"], "reasons": outcome["reasons"],
            "refund_amount": outcome["refund_amount"], "audit_id": audit_id, "current_hash": current_hash,
        }}

    def after_gather(state: AgentState) -> str:
        # A request with no claim never reaches Decision: nothing to decide.
        return "decision" if state.get("claim") is not None else END

    g = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("gather", gather_node)
    g.add_node("decision", decision_node)
    g.add_edge(START, "planner")
    g.add_edge("planner", "gather")
    g.add_conditional_edges("gather", after_gather, {"decision": "decision", END: END})
    g.add_edge("decision", END)
    return g.compile()


class RefundAgent:
    def __init__(self, *, planner, sessionmaker, retriever):
        self.planner = planner
        self.graph = build_graph(planner=planner, sessionmaker=sessionmaker, retriever=retriever)

    async def run(self, *, claim: dict | None = None, question: str | None = None,
                  arg_overrides: dict | None = None) -> ClaimResponse:
        state: AgentState = {
            "trace_id": str(uuid.uuid4()),
            "claim": claim,
            "question": question,
            "arg_overrides": arg_overrides or {},
            "trace": [],
        }
        out = await self.graph.ainvoke(state)
        trace = out.get("trace", [])
        citation = next((t["result"]["citation"] for t in trace if "citation" in t["result"]), None)
        plan = out.get("plan") or {}
        common = {
            "trace_id": out["trace_id"],
            "plan": plan.get("steps", []),
            "planner_error": out.get("planner_error"),
            "trace": trace,
            "citation": citation,
            "model_version": self.planner.model_version,
        }
        if claim is None:
            reasons = [citation["text"]] if citation else ["No policy clause could be retrieved."]
            return ClaimResponse(decision="NO_CLAIM_MADE", reason_code="INFORMATIONAL", reasons=reasons, **common)
        return ClaimResponse(**out["response"], **common)
