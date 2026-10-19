"""RefundRx demo UI. Talks to the FastAPI service over HTTP; holds no decision logic."""
import os
from datetime import date, timedelta

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
API_AUTH = (
    (os.environ["API_BASIC_AUTH_USER"], os.environ["API_BASIC_AUTH_PASSWORD"])
    if os.getenv("API_BASIC_AUTH_USER") and os.getenv("API_BASIC_AUTH_PASSWORD") else None
)
APP_PASSWORD = os.getenv("APP_PASSWORD")

st.set_page_config(page_title="RefundRx", page_icon=":material/receipt_long:", layout="wide")

# Small, targeted CSS on top of the config.toml theme: timeline rail + tighter header.
st.html("""
<style>
  .block-container { padding-top: 2.2rem; }
  .st-key-timeline [data-testid="stVerticalBlock"] > div { border-left: 2px solid #30363D; padding-left: 14px; }
</style>
""")

TOOL_LABELS = {
    "check_fp57_receipt": "checked FP57 receipt",
    "retrieve_policy_clause": "retrieved policy clause",
    "check_exemption_category": "checked exemption category",
    "check_claim_window": "checked claim window",
    "check_duplicate": "checked for duplicate refund",
    "calculate_refund": "verified patient & payment, calculated refund",
}


# --- access gate (basic auth for the public demo) ---------------------------
def gate() -> None:
    if not APP_PASSWORD or st.session_state.get("authed"):
        return
    with st.container(border=True, width=420):
        st.subheader("RefundRx demo")
        pw = st.text_input("Demo password", type="password")
        if st.button("Enter", type="primary"):
            st.session_state.authed = pw == APP_PASSWORD
            if not st.session_state.authed:
                st.error("Incorrect password.")
            st.rerun()
    st.stop()


def api(method: str, path: str, **kw) -> httpx.Response:
    return httpx.request(method, f"{API_URL}{path}", auth=API_AUTH, timeout=90, **kw)


def wake_api() -> None:
    if st.session_state.get("api_awake"):
        return
    with st.spinner("Waking up — Render free tier can take up to a minute on first load…"):
        try:
            api("GET", "/health").raise_for_status()
            st.session_state.api_awake = True
            st.session_state.known_patient = api("GET", "/demo/known-patient").json().get("patient_id")
        except httpx.HTTPError as e:
            st.error(f"API unreachable at {API_URL}: {e}")
            st.stop()


gate()

# --- sidebar: the FDE narrative ---------------------------------------------
with st.sidebar:
    st.title(":material/receipt_long: RefundRx")
    st.caption("Agentic FP57 prescription-charge refund decisions, with an audit trail you can verify.")
    st.markdown("""
**What** — An agent that decides NHSBSA FP57 refund claims for patients who paid a
prescription charge but held an exemption (age, maternity, medical, HC2).

**Why** — The one UK "pharmacy refund" that is real. Pharmacies never refund dispensed
medicines; FP57 is the only route.

**Need** — Each claim turns on hard rules: an FP57 issued *at payment*, a 3-months-less-a-day
window, a valid exemption, and one refund per form.

**Gap** — LLM agents are rarely evaluated on *how* they decide, and their decisions are
rarely auditable.

**Bridge** — Planner → Gather → Decision in LangGraph. The plan is generated, every tool
call is logged, `policy_rules` is the sole authority, and RAG text is citation only.
Every decision is hash-chained.

**Impact** — Ten DeepEval scenarios score plan quality, plan adherence and tool
correctness, not just the final answer.
""")
    st.divider()
    st.caption("Out of scope: PPC refunds, HC3 partial help.")
    st.caption("Demonstration system using synthetic data only. Not validated for clinical, regulatory, "
               "or GxP use. No real patient data is processed. Not indemnified for real decisions.")

wake_api()

# --- claim form -------------------------------------------------------------
today = date.today()
known = st.session_state.get("known_patient") or "9999900001"
PRESETS = {
    "Eligible claim": dict(),
    "No FP57 receipt": dict(fp57_receipt_issued=False),
    "Outside the window (95 days)": dict(charge_paid_date=today - timedelta(days=95)),
    "Unknown patient": dict(patient_id="9999900404"),
    "Charge never paid": dict(charge_payment_verified=False),
    "Information-only question": dict(),
}

st.header("Submit a claim")
preset = st.segmented_control("Scenario preset", list(PRESETS), default="Eligible claim")
preset = preset or "Eligible claim"
# Kept in session state so resubmitting the same reference exercises the duplicate check.
st.session_state.setdefault("form_ref", f"FP57-DEMO-{os.urandom(3).hex().upper()}")
values = {
    "patient_id": known,
    "charge_paid_date": today - timedelta(days=10), "claim_submitted_date": today,
    "exemption_category": "HC2", "fp57_receipt_issued": True, "charge_payment_verified": True,
    **PRESETS[preset],
}

with st.form("claim"):
    if preset == "Information-only question":
        question = st.text_input("Question", "What is the time limit for claiming an FP57 refund?")
    else:
        c1, c2 = st.columns(2)
        with c1:
            patient_id = st.text_input("Patient ID (999 test range)", values["patient_id"])
            form_ref = st.text_input("FP57 form reference", key="form_ref",
                                     help="Resubmit the same reference to see the duplicate check.")
            category = st.selectbox("Exemption category", ["HC2", "MATERNITY", "AGE", "MEDICAL"],
                                    index=["HC2", "MATERNITY", "AGE", "MEDICAL"].index(values["exemption_category"]))
        with c2:
            paid = st.date_input("Charge paid", values["charge_paid_date"], max_value=today)
            submitted = st.date_input("Claim submitted", values["claim_submitted_date"], max_value=today)
            receipt = st.toggle("FP57 receipt issued at payment", values["fp57_receipt_issued"])
            paid_ok = st.toggle("Charge payment verified", values["charge_payment_verified"])
    go = st.form_submit_button("Run agent", type="primary", icon=":material/play_arrow:")

if go:
    if preset == "Information-only question":
        r = api("POST", "/info", json={"question": question})
    else:
        r = api("POST", "/claims", json={
            "patient_id": patient_id, "fp57_form_ref": form_ref, "charge_paid_date": paid.isoformat(),
            "claim_submitted_date": submitted.isoformat(), "exemption_category": category,
            "fp57_receipt_issued": receipt, "charge_payment_verified": paid_ok,
        })
    st.session_state.last = (r.status_code, r.json())

# --- result: ClaimResponse JSON beside a readable trace timeline -------------
if "last" in st.session_state:
    status, body = st.session_state.last
    left, right = st.columns([1, 1])
    with left:
        st.subheader("ClaimResponse")
        st.json(body, expanded=2)
    with right:
        st.subheader("Trace timeline")
        if status != 200:
            st.error(f"HTTP {status} — rejected at the API boundary before the Planner ran. No plan, no trace.")
        else:
            with st.container(key="timeline"):
                plan = body["plan"]
                st.markdown(f":blue[**Planner**] generated plan ({len(plan)} steps) · `{body['model_version']}`")
                st.caption(" → ".join(plan) if plan else (body.get("planner_error") or "no plan"))
                for t in body["trace"]:
                    passed = t["result"].get("passed")
                    icon = {True: ":green[:material/check_circle:]", False: ":red[:material/cancel:]",
                            None: ":blue[:material/menu_book:]"}[passed]
                    st.markdown(f"{icon} **Gather** {TOOL_LABELS[t['tool']]}")
                    st.caption(t["result"].get("detail", ""))
                colour = {"APPROVED": "green", "REJECTED": "red"}.get(body["decision"], "blue")
                st.markdown(f":{colour}[**Decision: {body['decision']}**] · `{body['reason_code']}`"
                            + (f" · refund £{body['refund_amount']}" if body.get("refund_amount") else ""))
                if body.get("audit_id"):
                    st.caption(f"audit_id {body['audit_id']} · hash {body['current_hash'][:16]}…")
            if body.get("citation"):
                with st.container(border=True):
                    st.markdown(f":material/format_quote: **Policy citation** — {body['citation']['heading']}")
                    st.caption(body["citation"]["text"])
                    st.caption(f"Citation only; `policy_rules` decides. Retriever: {body['citation']['backend']}")

# --- audit integrity ---------------------------------------------------------
st.divider()
st.subheader("Audit log")
st.caption("Integrity-checked, not externally anchored: detects casual edits, not an attacker with database access.")
if st.button("Verify Audit Integrity", icon=":material/verified_user:"):
    v = api("GET", "/audit/verify").json()
    (st.success if v["ok"] else st.error)(v["message"])

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #8B949E; font-size: 0.9em;'>"
    "Built by <b>Prathamesh Mishra</b> | FDE Portfolio Project"
    "</div>",
    unsafe_allow_html=True
)
