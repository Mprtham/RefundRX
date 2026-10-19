"""The ten hand-constructed evaluation scenarios.

Authored directly against policy_rules — never sampled from the background
synthetic dataset. Dates are relative to today so the fixtures never age out.

Golden-answer provenance: most expected answers follow from policy_rules plus
the claim facts. To break that circularity, scenarios marked hand_verified=True
had their expected decision checked by hand against the public NHSBSA FP57
guidance (see `source_note`), not derived from the table.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

KNOWN_PATIENT = "9999900001"    # on file (has claims history in the fixture DB)
UNKNOWN_PATIENT = "9999900404"  # well-formed, never on file
DUPLICATE_FORM = "FP57-FIXTURE-0001"

R, P, E, W, D, C = (
    "check_fp57_receipt", "retrieve_policy_clause", "check_exemption_category",
    "check_claim_window", "check_duplicate", "calculate_refund",
)


def _claim(**over) -> dict:
    today = date.today()
    base = dict(
        patient_id=KNOWN_PATIENT,
        fp57_form_ref="FP57-FIXTURE-NEW",
        charge_paid_date=today - timedelta(days=10),
        claim_submitted_date=today,
        exemption_category="HC2",
        fp57_receipt_issued=True,
        charge_payment_verified=True,
    )
    return {**base, **over}


@dataclass
class Scenario:
    num: int
    name: str
    kind: str  # "claim" | "info" | "api_422"
    expected_decision: str
    expected_reason: str | None
    expected_tools: list[str]
    claim: dict | None = None
    question: str | None = None
    pre_approved_forms: list[str] = field(default_factory=list)
    withdrawn_categories: list[str] = field(default_factory=list)
    arg_overrides: dict = field(default_factory=dict)
    hand_verified: bool = False
    source_note: str = ""

    @property
    def id(self) -> str:
        return f"S{self.num:02d}-{self.name}"


SCENARIOS = [
    Scenario(
        1, "eligible", "claim", "APPROVED", "ELIGIBLE", [R, P, E, W, D, C],
        claim=_claim(),
        hand_verified=True,
        source_note="HC2 holder, FP57 issued at payment, claimed 10 days later: NHSBSA guidance "
                    "permits a refund within 3 months of payment.",
    ),
    Scenario(
        2, "no_receipt", "claim", "REJECTED", "NO_FP57_RECEIPT", [R],
        claim=_claim(fp57_receipt_issued=False),
        hand_verified=True,
        source_note="NHSBSA: an FP57 must be requested when the charge is paid and cannot be issued later.",
    ),
    Scenario(
        3, "outside_window", "claim", "REJECTED", "OUTSIDE_CLAIM_WINDOW", [R, P, E, W],
        claim=_claim(charge_paid_date=date.today() - timedelta(days=95)),
        hand_verified=True,
        source_note="NHSBSA: claims must be made within 3 months of paying; 95 days is beyond any 3-month span.",
    ),
    Scenario(
        4, "wrong_exemption", "claim", "REJECTED", "EXEMPTION_NOT_IN_POLICY", [R, P, E],
        claim=_claim(exemption_category="MEDICAL"),
        # The API accepts MEDICAL, but this fixture's policy_rules has no
        # active MEDICAL rule — "category not in policy_rules".
        withdrawn_categories=["MEDICAL"],
    ),
    Scenario(
        5, "duplicate", "claim", "REJECTED", "DUPLICATE_CLAIM", [R, P, E, W, D],
        claim=_claim(fp57_form_ref=DUPLICATE_FORM),
        pre_approved_forms=[DUPLICATE_FORM],
    ),
    Scenario(
        6, "info_only", "info", "NO_CLAIM_MADE", "INFORMATIONAL", [P],
        question="What is the time limit for claiming an FP57 prescription refund?",
    ),
    Scenario(
        7, "missing_patient_id", "api_422", "HTTP_422", None, [],
        claim={k: v for k, v in _claim().items() if k != "patient_id"},
    ),
    Scenario(
        8, "unknown_patient", "claim", "REJECTED", "UNKNOWN_PATIENT", [R, P, E, W, D, C],
        claim=_claim(patient_id=UNKNOWN_PATIENT),
    ),
    Scenario(
        9, "unpaid_charge", "claim", "REJECTED", "CHARGE_NOT_PAID", [R, P, E, W, D, C],
        claim=_claim(charge_payment_verified=False),
    ),
    Scenario(
        10, "malformed_llm_argument", "claim", "REJECTED", "ARGUMENT_VALIDATION_FAILED", [R, P, E, W],
        claim=_claim(),
        # Simulates the LLM handing check_claim_window a date as a string.
        arg_overrides={W: {"charge_paid_date": "2023-01-01"}},
    ),
]
