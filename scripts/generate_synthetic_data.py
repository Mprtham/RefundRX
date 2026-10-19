"""Background synthetic FP57 claims dataset.

Generates plausible BACKGROUND VOLUME for realism (500 patients, 1-5 claims
each, split roughly half in-window / half out-of-window). It does NOT generate
the ten DeepEval scenarios — those are hand-constructed fixtures in
tests/evals/fixtures.py, authored against policy_rules so their expected
answers are exact.

Run:  python -m scripts.generate_synthetic_data
"""
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from shared.policy import PRESCRIPTION_CHARGE, fp57_window_end

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference"
OUT = ROOT / "data"

N_PATIENTS = 500
# IDs 99999xxxxx are reserved for hand-built fixtures and demo presets.
RESERVED_PREFIX = "99999"

fake = Faker("en_GB")
Faker.seed(42)
rng = np.random.default_rng(42)  # reproducible dataset

drugs = pd.read_csv(REF / "drugs.csv")
pharmacies = pd.read_csv(REF / "pharmacies.csv")
# PPC and HC3 are not in this file at all (out of scope)
exemptions = pd.read_csv(REF / "exemption_categories.csv")


def new_patient_id(taken: set[str]) -> str:
    while True:
        pid = f"999{rng.integers(0, 10**7):07d}"  # NHS Digital 999 test range
        if pid not in taken and not pid.startswith(RESERVED_PREFIX):
            taken.add(pid)
            return pid


def make_patient(taken: set[str]) -> dict:
    return {
        "patient_id": new_patient_id(taken),
        "name": fake.name(),
        "dob": fake.date_of_birth(minimum_age=18, maximum_age=90),
        "postcode_outward": rng.choice(pharmacies["postcode_outward"].unique()),
    }


def make_claim(patient_id: str, in_window: bool, today: date) -> dict | None:
    drug = drugs.sample(1, weights=drugs["weight"], random_state=rng).iloc[0]
    exemption = exemptions.sample(1, weights=exemptions["weight"], random_state=rng).iloc[0]
    charge_paid_date = today - timedelta(days=int(rng.integers(0, 366)))
    window_end = fp57_window_end(charge_paid_date)

    if in_window:
        # Window end may be in the future for recent charges — cap at today.
        latest = min(window_end, today)
        span = (latest - charge_paid_date).days
        claim_submitted_date = charge_paid_date + timedelta(days=int(rng.integers(0, span + 1)))
    else:
        candidate = window_end + timedelta(days=int(rng.integers(1, 60)))
        if candidate > today:
            # Not yet observable as out-of-window; skip rather than emit a
            # future-dated claim.
            return None
        claim_submitted_date = candidate

    return {
        "claim_id": str(uuid.UUID(int=int(rng.integers(0, 2**63)) << 64 | int(rng.integers(0, 2**63)))),
        "fp57_form_ref": f"FP57-{uuid.UUID(int=int(rng.integers(0, 2**63))).hex[-10:].upper()}",
        "patient_id": patient_id,
        "fp57_receipt_issued": True,      # base case; no-receipt is a hand-built fixture
        "charge_payment_verified": True,  # base case; never-paid is a hand-built fixture
        "charge_paid_date": charge_paid_date,
        "claim_submitted_date": claim_submitted_date,
        "exemption_category": exemption["category"],
        "amount_paid": str(PRESCRIPTION_CHARGE),
        "drug_name": drug["drug_name"],
        "bnf_code": drug["bnf_code"],
        "pharmacy": pharmacies.sample(1, random_state=rng).iloc[0]["pharmacy_name"],  # context only
        "in_window": in_window,
    }


def make_balanced_claim(patient_id: str, in_window: bool, today: date) -> dict | None:
    """Out-of-window draws on recent charges are skipped (never future-dated);
    redraw a few times so the skip doesn't skew the dataset toward in-window."""
    for _ in range(4):
        claim = make_claim(patient_id, in_window, today)
        if claim is not None:
            return claim
    return None


def validate(patients: pd.DataFrame, claims: pd.DataFrame, today: date) -> None:
    assert patients["patient_id"].str.match(r"^999\d{7}$").all(), "non-999 patient id"
    assert claims["patient_id"].isin(patients["patient_id"]).all(), "orphan claim"
    assert (pd.to_datetime(claims["claim_submitted_date"]).dt.date <= today).all(), "future-dated claim"
    assert claims["fp57_form_ref"].is_unique, "fp57_form_ref collision"

    ref_pairs = set(zip(drugs["drug_name"], drugs["bnf_code"]))
    assert set(zip(claims["drug_name"], claims["bnf_code"])) <= ref_pairs, "drug/bnf pair not in reference"

    # The flag must agree with the shared window function.
    ends = [fp57_window_end(d) for d in pd.to_datetime(claims["charge_paid_date"]).dt.date]
    actual = [s <= e for s, e in zip(pd.to_datetime(claims["claim_submitted_date"]).dt.date, ends)]
    assert list(claims["in_window"]) == actual, "in_window flag disagrees with fp57_window_end"

    share = claims["in_window"].mean()
    print(f"patients={len(patients)} claims={len(claims)} in-window share={share:.2f}")
    print("exemption mix:", claims["exemption_category"].value_counts(normalize=True).round(2).to_dict())
    assert 0.40 <= share <= 0.60, f"in/out window split skewed: {share:.2f}"


def main() -> None:
    today = date.today()
    taken: set[str] = set()
    patients = [make_patient(taken) for _ in range(N_PATIENTS)]
    claims = [
        c
        for p in patients
        for _ in range(int(rng.integers(1, 6)))  # inclusive 1..5
        for c in [make_balanced_claim(p["patient_id"], in_window=bool(rng.random() < 0.5), today=today)]
        if c is not None
    ]
    patients_df, claims_df = pd.DataFrame(patients), pd.DataFrame(claims)
    validate(patients_df, claims_df, today)

    OUT.mkdir(exist_ok=True)
    patients_df.to_csv(OUT / "synthetic_patients.csv", index=False)
    claims_df.to_csv(OUT / "synthetic_claims.csv", index=False)


if __name__ == "__main__":
    main()
