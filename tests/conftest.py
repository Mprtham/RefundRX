import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.agent.graph import RefundAgent
from app.agent.planner import make_planner
from app.config import Settings, get_model_pin
from app.rag.retriever import get_retriever
from db.models import AuditLog, Base, Claim, ClaimApproved, PolicyRule
from db.session import create_all, make_engine, make_sessionmaker
from scripts.seed_db import policy_rows
from shared.audit_hash import compute_audit_hash
from tests.evals.fixtures import KNOWN_PATIENT

# CI defaults: SQLite, offline reference planner, keyword retriever.
# Set EVAL_PLANNER=groq (with GROQ_API_KEY) to evaluate the real LLM planner.
os.environ.setdefault("RAG_BACKEND", "keyword")


@pytest.fixture
async def db(tmp_path):
    # Default: a fresh SQLite file per test. Set TEST_DATABASE_URL to run the
    # same suite against Postgres (tables are dropped and recreated per test).
    url = os.getenv("TEST_DATABASE_URL")
    engine = make_engine(url or f"sqlite+aiosqlite:///{(tmp_path / 'eval.db').as_posix()}")
    if url:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await create_all(engine)
    sm = make_sessionmaker(engine)
    async with sm() as s, s.begin():
        s.add_all(policy_rows())
        s.add(Claim(  # claims history that puts KNOWN_PATIENT "on file"
            claim_id=uuid.uuid4(), fp57_form_ref="FP57-HISTORY-0001", patient_id=KNOWN_PATIENT,
            fp57_receipt_issued=True, charge_payment_verified=True,
            charge_paid_date=date.today() - timedelta(days=200),
            claim_submitted_date=date.today() - timedelta(days=150),
            exemption_category="AGE", amount_paid=Decimal("9.90"), pharmacy="FIXTURE PHARMACY",
        ))
    yield sm
    await engine.dispose()


async def withdraw_categories(sm, categories: list[str]) -> None:
    async with sm() as s, s.begin():
        await s.execute(delete(PolicyRule).where(PolicyRule.category.in_(categories)))


async def pre_approve(sm, form_ref: str) -> None:
    """Insert a prior approval (with its own valid audit row) for a form ref."""
    async with sm() as s, s.begin():
        plan, trace = {"route": "assess_claim", "steps": []}, {"fixture": "prior approval"}
        audit = AuditLog(trace_id=uuid.uuid4(), created_at=datetime.now(timezone.utc), plan_json=plan,
                         trace_json=trace, decision="APPROVED", prev_hash=None,
                         current_hash=compute_audit_hash(None, plan, trace, "APPROVED"),
                         model_version="fixture")
        s.add(audit)
        await s.flush()
        claim_id = uuid.uuid4()
        s.add(Claim(claim_id=claim_id, fp57_form_ref=form_ref, patient_id=KNOWN_PATIENT,
                    fp57_receipt_issued=True, charge_payment_verified=True,
                    charge_paid_date=date.today() - timedelta(days=20),
                    claim_submitted_date=date.today() - timedelta(days=15),
                    exemption_category="HC2", amount_paid=Decimal("9.90")))
        await s.flush()
        s.add(ClaimApproved(claim_id=claim_id, fp57_form_ref=form_ref,
                            approved_date=datetime.now(timezone.utc), audit_id=audit.audit_id))


def eval_settings() -> Settings:
    backend = os.getenv("EVAL_PLANNER", "reference")
    return Settings(planner_backend="groq" if backend == "groq" else "reference",
                    rag_backend=os.environ["RAG_BACKEND"])


@pytest.fixture
def make_agent(db):
    def _make(planner=None):
        s = eval_settings()
        return RefundAgent(planner=planner or make_planner(s, get_model_pin()),
                           sessionmaker=db, retriever=get_retriever(s.rag_backend))
    return _make
