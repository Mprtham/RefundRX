import logging
import math
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select

from app.agent.graph import RefundAgent
from app.agent.planner import make_planner
from app.config import get_model_pin, get_settings
from app.rag.retriever import get_retriever
from app.schemas import ClaimInput, ClaimResponse, InfoQuery
from db.models import AuditLog, Claim, PolicyRule
from db.session import create_all, make_engine, make_sessionmaker
from scripts.seed_db import policy_rows
from scripts.verify_audit_chain import verify_chain

log = logging.getLogger("refundrx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings.database_url)
    await create_all(engine)
    sessionmaker = make_sessionmaker(engine)
    async with sessionmaker() as s, s.begin():
        if (await s.execute(select(PolicyRule).limit(1))).first() is None:
            s.add_all(policy_rows())
    app.state.sessionmaker = sessionmaker
    # Re-embed policy text on every startup instead of trusting persisted state.
    app.state.agent = RefundAgent(
        planner=make_planner(settings, get_model_pin()),
        sessionmaker=sessionmaker,
        retriever=get_retriever(settings.rag_backend),
    )
    yield
    await engine.dispose()


app = FastAPI(title="RefundRx", version="1.0.0", lifespan=lifespan)

# --- basic auth (enabled when both credentials are set) ---------------------
_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    s = get_settings()
    if not (s.api_basic_auth_user and s.api_basic_auth_password):
        return
    ok = creds is not None and secrets.compare_digest(creds.username, s.api_basic_auth_user) \
        and secrets.compare_digest(creds.password, s.api_basic_auth_password)
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})


# --- in-memory sliding-window rate limit (per process) ---------------------
# Every limited request counts toward one global bucket. The UI names the visitor
# in VISITOR_HEADER; that header is trusted only when basic auth is configured
# (so the caller holds the API credentials) and then also gets its own, smaller
# bucket, so one visitor cannot spend everyone's allowance. X-Forwarded-For is
# ignored: on Render it carries the UI server's address, and it is spoofable.
VISITOR_HEADER = "x-refundrx-visitor"
WINDOW_S = 60
_hits: dict[str, deque] = defaultdict(deque)


def _wait(key: str, limit: int, now: float) -> int | None:
    """Seconds until key's bucket has room, or None if it has room now."""
    q = _hits[key]
    while q and now - q[0] >= WINDOW_S:
        q.popleft()
    if not q:
        del _hits[key]
        return None
    return max(1, math.ceil(WINDOW_S - (now - q[0]))) if len(q) >= limit else None


def rate_limit(request: Request, _: None = Depends(require_auth)) -> None:
    s = get_settings()
    now = time.monotonic()
    buckets = {"global": s.rate_limit_global_per_minute}
    visitor = request.headers.get(VISITOR_HEADER)
    if visitor and s.api_basic_auth_user and s.api_basic_auth_password:
        buckets[f"visitor:{visitor[:64]}"] = s.rate_limit_per_minute
    buckets = {k: n for k, n in buckets.items() if n > 0}
    waits = [w for k, n in buckets.items() if (w := _wait(k, n, now)) is not None]
    if waits:
        wait = max(waits)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Rate limit exceeded; retry in {wait}s.",
                            headers={"Retry-After": str(wait)})
    for k in buckets:
        _hits[k].append(now)


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    # Scenario 7: rejected at the API boundary, before the Planner runs.
    log.info("422 at API boundary on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors()), "stage": "api_boundary"})


@app.api_route("/health", methods=["GET", "HEAD"])  # never rate limited: Render and keep-alive poll it
async def health():
    return {"status": "ok"}


@app.post("/claims", response_model=ClaimResponse, dependencies=[Depends(require_auth), Depends(rate_limit)])
async def submit_claim(claim: ClaimInput, request: Request) -> ClaimResponse:
    return await request.app.state.agent.run(claim=claim.model_dump())


@app.post("/info", response_model=ClaimResponse, dependencies=[Depends(require_auth), Depends(rate_limit)])
async def info(query: InfoQuery, request: Request) -> ClaimResponse:
    return await request.app.state.agent.run(question=query.question)


@app.get("/demo/known-patient", dependencies=[Depends(require_auth)])
async def demo_known_patient(request: Request):
    """A synthetic patient that is on file, for the UI's preset scenarios."""
    async with request.app.state.sessionmaker() as s:
        pid = await s.scalar(select(Claim.patient_id).order_by(Claim.patient_id).limit(1))
    return {"patient_id": pid}


@app.get("/audit/verify", dependencies=[Depends(require_auth)])
async def audit_verify(request: Request):
    async with request.app.state.sessionmaker() as s:
        ok, message = await s.run_sync(verify_chain)
    return {"ok": ok, "message": message, "note": "Integrity-checked, not externally anchored."}


@app.get("/audit/recent", dependencies=[Depends(require_auth)])
async def audit_recent(request: Request, limit: int = 10):
    async with request.app.state.sessionmaker() as s:
        rows = (await s.execute(
            select(AuditLog).order_by(AuditLog.audit_id.desc()).limit(min(limit, 50))
        )).scalars().all()
    return [
        {"audit_id": r.audit_id, "trace_id": str(r.trace_id), "created_at": r.created_at.isoformat(),
         "decision": r.decision, "model_version": r.model_version,
         "prev_hash": r.prev_hash, "current_hash": r.current_hash}
        for r in rows
    ]
