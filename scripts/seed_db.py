"""Create the four tables and load synthetic claims + policy_rules.

Works against SQLite (default) or Neon Postgres (set DATABASE_URL).
Run:  python -m scripts.seed_db [--reset]
"""
import argparse
import asyncio
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.config import get_settings
from db.models import AuditLog, Base, Claim, ClaimApproved, PolicyRule
from db.session import create_all, make_engine, make_sessionmaker

ROOT = Path(__file__).resolve().parent.parent


def policy_rows() -> list[PolicyRule]:
    cats = pd.read_csv(ROOT / "reference" / "exemption_categories.csv")
    return [
        PolicyRule(
            category=r.category,
            window_months=int(r.window_months),
            window_days_offset=int(r.window_days_offset),
            requires_fp57_receipt=str(r.requires_fp57_receipt).lower() == "true",
            effective_from=date.fromisoformat(r.effective_from),
        )
        for r in cats.itertuples()
    ]


def claim_rows() -> list[Claim]:
    df = pd.read_csv(ROOT / "data" / "synthetic_claims.csv")
    return [
        Claim(
            claim_id=uuid.UUID(r.claim_id),
            fp57_form_ref=r.fp57_form_ref,
            patient_id=str(r.patient_id),
            fp57_receipt_issued=bool(r.fp57_receipt_issued),
            charge_payment_verified=bool(r.charge_payment_verified),
            charge_paid_date=date.fromisoformat(r.charge_paid_date),
            claim_submitted_date=date.fromisoformat(r.claim_submitted_date),
            exemption_category=r.exemption_category,
            amount_paid=Decimal(str(r.amount_paid)),
            pharmacy=r.pharmacy,
        )
        for r in df.itertuples()
    ]


async def seed(database_url: str, reset: bool = False, with_claims: bool = True) -> None:
    engine = make_engine(database_url)
    if reset:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await create_all(engine)
    Session = make_sessionmaker(engine)
    async with Session() as s, s.begin():
        if (await s.execute(select(PolicyRule).limit(1))).first() is None:
            s.add_all(policy_rows())
        if with_claims and (await s.execute(select(Claim).limit(1))).first() is None:
            s.add_all(claim_rows())
    await engine.dispose()


async def _counts(database_url: str) -> None:
    engine = make_engine(database_url)
    Session = make_sessionmaker(engine)
    async with Session() as s:
        for model in (PolicyRule, Claim, ClaimApproved, AuditLog):
            n = len((await s.execute(select(model))).scalars().all())
            print(f"{model.__tablename__}: {n}")
    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    args = ap.parse_args()
    url = get_settings().database_url
    asyncio.run(seed(url, reset=args.reset))
    asyncio.run(_counts(url))
