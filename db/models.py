"""SQLAlchemy ORM models — one definition, two backends (SQLite in CI, Neon
Postgres in production). No raw, dialect-specific DDL anywhere."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid, func, literal,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on Postgres, plain JSON on SQLite.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Claim(Base):
    """Input claims. fp57_form_ref deliberately has NO unique constraint: a
    resubmitted form must reach the agent and be rejected as a decision, not
    crash on an IntegrityError."""
    __tablename__ = "claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fp57_form_ref: Mapped[str] = mapped_column(String(64), index=True)
    patient_id: Mapped[str] = mapped_column(String(10), index=True)
    fp57_receipt_issued: Mapped[bool] = mapped_column(Boolean, nullable=False)
    charge_payment_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    charge_paid_date: Mapped[date] = mapped_column(Date, nullable=False)
    claim_submitted_date: Mapped[date] = mapped_column(Date, nullable=False)
    exemption_category: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("9.90"))
    pharmacy: Mapped[str | None] = mapped_column(String(255))


class AuditLog(Base):
    """Hash-chained, append-only. current_hash covers prev_hash, plan_json,
    trace_json and decision (shared/audit_hash.py)."""
    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False, server_default=func.now()
    )
    plan_json: Mapped[dict] = mapped_column(JsonType, nullable=False)
    trace_json: Mapped[dict] = mapped_column(JsonType, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)


# Each row may be the successor of a given head only once, so two concurrent
# appends that read the same head cannot both land. COALESCE covers the genesis
# row too: SELECT ... FOR UPDATE has nothing to lock on an empty table, and a
# plain unique constraint lets multiple NULLs through.
Index("uq_audit_log_chain_link", func.coalesce(AuditLog.prev_hash, literal("GENESIS")), unique=True)


class ClaimApproved(Base):
    """Finalized approvals only. The unique index on fp57_form_ref is a
    last-resort backstop; the primary duplicate check is the app-level SELECT
    in the check_duplicate tool."""
    __tablename__ = "claims_approved"

    claim_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("claims.claim_id"), primary_key=True)
    fp57_form_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    approved_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[int] = mapped_column(Integer, ForeignKey("audit_log.audit_id"), nullable=False)


class PolicyRule(Base):
    """Sole decision authority. Window is structured integers, never a parsed string."""
    __tablename__ = "policy_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    window_months: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    window_days_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    requires_fp57_receipt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    superseded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("policy_rules.rule_id"))
