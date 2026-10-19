from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ClaimInput(BaseModel):
    patient_id: str = Field(..., pattern=r"^999\d{7}$", description="NHS Digital test range")
    fp57_form_ref: str = Field(..., min_length=1, max_length=64)
    charge_paid_date: date
    claim_submitted_date: date
    exemption_category: Literal["HC2", "MATERNITY", "AGE", "MEDICAL"]
    fp57_receipt_issued: bool
    charge_payment_verified: bool
    # amount_paid is NOT a caller-supplied field: it is the server-side
    # constant shared.policy.PRESCRIPTION_CHARGE, never taken from input.

    @field_validator("claim_submitted_date")
    @classmethod
    def not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("claim_submitted_date cannot be in the future")
        return v


class InfoQuery(BaseModel):
    """A question with no claim attached (Scenario 6)."""
    question: str = Field(..., min_length=3, max_length=500)


class ToolName(str, Enum):
    check_fp57_receipt = "check_fp57_receipt"
    retrieve_policy_clause = "retrieve_policy_clause"
    check_exemption_category = "check_exemption_category"
    check_claim_window = "check_claim_window"
    check_duplicate = "check_duplicate"
    calculate_refund = "calculate_refund"


class Plan(BaseModel):
    """Planner output: a route plus an ordered list of allowlisted tool names only."""
    route: Literal["assess_claim", "informational"]
    steps: list[ToolName] = Field(..., min_length=1, max_length=12)


class TraceStep(BaseModel):
    step: int
    tool: ToolName
    args: dict[str, Any]
    result: dict[str, Any]


Decision = Literal["APPROVED", "REJECTED", "NO_CLAIM_MADE"]


class Citation(BaseModel):
    heading: str
    text: str
    score: float
    backend: str


class ClaimResponse(BaseModel):
    trace_id: str
    decision: Decision
    reason_code: str
    reasons: list[str]
    refund_amount: str | None = None
    plan: list[ToolName]
    planner_error: str | None = None
    trace: list[TraceStep]
    citation: Citation | None = None
    audit_id: int | None = None
    current_hash: str | None = None
    model_version: str
