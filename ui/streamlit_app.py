"""RefundRx demo UI. Talks to the FastAPI service over HTTP; holds no decision logic."""
import os
from datetime import date, timedelta
from html import escape
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components

import theme

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
API_AUTH = (
    (os.environ["API_BASIC_AUTH_USER"], os.environ["API_BASIC_AUTH_PASSWORD"])
    if os.getenv("API_BASIC_AUTH_USER") and os.getenv("API_BASIC_AUTH_PASSWORD") else None
)
APP_PASSWORD = os.getenv("APP_PASSWORD")
GITHUB_URL = "https://github.com/Mprtham/RefundRX"
DESIGN_DOC_URL = f"{GITHUB_URL}#architecture"
TAMPER_DEMO = (Path(__file__).parent / "tamper_demo.html").read_text(encoding="utf-8")

st.set_page_config(page_title="RefundRx", page_icon=":material/receipt_long:", layout="wide")
theme.apply()

TOOL_LABELS = {
    "check_fp57_receipt": "checked FP57 receipt",
    "retrieve_policy_clause": "retrieved policy clause",
    "check_exemption_category": "checked exemption category",
    "check_claim_window": "checked claim window",
    "check_duplicate": "checked for duplicate refund",
    "calculate_refund": "verified patient & payment, calculated refund",
}
PILLS = {
    "APPROVED": ("APPROVED", "rr-pill-approved"),
    "REJECTED": ("REJECTED", "rr-pill-rejected"),
    "NO_CLAIM_MADE": ("NO CLAIM MADE", "rr-pill-none"),
}


# --- small HTML helpers (styling lives in theme.py) --------------------------
def mono(text) -> str:
    return f"<span class='rr-mono'>{escape(str(text))}</span>"


def short_hash(h: str | None, n: int = 12) -> str:
    return mono(f"{h[:n]}…") if h else "<span class='rr-muted'>none</span>"


def pill(decision: str) -> str:
    label, cls = PILLS.get(decision, (decision, "rr-pill-none"))
    return f"<span class='rr-pill {cls}'>{escape(label)}</span>"


def notice(title: str, text: str) -> None:
    st.html(f"<div class='rr-notice'><b>{escape(title)}</b>{escape(text)}</div>")


# --- access gate (basic auth for the public demo) ---------------------------
def gate() -> None:
    if not APP_PASSWORD or st.session_state.get("authed"):
        return
    with st.container(border=True, width=420):
        st.html("<div class='rr-wordmark'>RefundRx</div><p class='rr-sub'>Enter the demo password to continue.</p>")
        pw = st.text_input("Demo password", type="password")
        if st.button("Enter", type="primary"):
            st.session_state.authed = pw == APP_PASSWORD
            if not st.session_state.authed:
                notice("Incorrect password.", "")
            st.rerun()
    st.stop()


def api(method: str, path: str, **kw) -> httpx.Response:
    return httpx.request(method, f"{API_URL}{path}", auth=API_AUTH, timeout=90, **kw)


def wake_api() -> None:
    if st.session_state.get("api_awake"):
        return
    with st.spinner("Waking the API. Render's free tier can take up to a minute on first load."):
        try:
            api("GET", "/health").raise_for_status()
            st.session_state.api_awake = True
            st.session_state.known_patient = api("GET", "/demo/known-patient").json().get("patient_id")
        except httpx.HTTPError as e:
            notice("API unreachable.", f"{API_URL}: {e}")
            st.stop()


gate()

# --- header ------------------------------------------------------------------
st.html(f"""
<div class='rr-header'>
  <span class='rr-wordmark'>RefundRx</span>
  <nav class='rr-nav'><a href='{GITHUB_URL}' target='_blank'>GitHub</a><a href='{DESIGN_DOC_URL}' target='_blank'>Design doc</a></nav>
</div>
<p class='rr-lede'>An agent that decides NHSBSA FP57 prescription-charge refund claims against hard policy rules.<br>
<span>Every plan, tool call and decision is logged and hash-chained, so you can audit how it decided.</span></p>
""")

# --- story: why, problem, what (copy shared with site/index.html) ------------
st.html("""
<section class='rr-story'>
  <div class='rr-story-row'>
    <div class='rr-eyebrow'>Why I built this</div>
    <div class='rr-prose'>
      <h2>I wanted to build an agent that shows its working.</h2>
      <p>I work in pharmaceutical technology in the UK. Most AI demos I see are chatbots that sound sure of themselves and cannot say how they got to an answer. In a regulated setting that is the whole problem, so I built the opposite: a small agent whose every step is written down and can be checked afterwards.</p>
      <p>RefundRx is a portfolio project, not a product. It runs on synthetic data, and it is built to production patterns: versioned policy, tested scenarios, and an audit trail you can verify.</p>
    </div>
  </div>
  <div class='rr-story-row'>
    <div class='rr-eyebrow'>The problem I saw</div>
    <div class='rr-prose'>
      <h2>Pharmacies do not refund medicines. One refund does exist.</h2>
      <p>Once a medicine has been dispensed in the UK it cannot go back on the shelf, so there is no general pharmacy refund. The refund that does exist is the NHSBSA prescription-charge refund, claimed on form FP57, for people who paid a charge they were exempt from.</p>
      <p>Each claim turns on hard rules: an FP57 receipt issued at the point of payment, a claim made within three months less a day, a valid exemption category, and one refund per form. A model that guesses is the wrong tool. A model that has to show its plan and its checks is a better one.</p>
    </div>
  </div>
  <div class='rr-story-row'>
    <div class='rr-eyebrow'>What it does</div>
    <div class='rr-prose'>
      <h2>A planner, a gatherer and a decision-maker.</h2>
      <ol class='rr-steps'>
        <li><span class='rr-n'>01</span><div><h3>Planner</h3><p>A language model writes an ordered plan, but it can only choose from six named checks. A plan that leaves out the receipt check is recorded as a weak plan, not quietly corrected.</p></div></li>
        <li><span class='rr-n'>02</span><div><h3>Gather</h3><p>Runs each step in the plan and writes every tool call, its arguments and its result to a trace. Retrieving the relevant policy text is one of those logged steps.</p></div></li>
        <li><span class='rr-n'>03</span><div><h3>Decision</h3><p>Applies the policy rules stored in the database and enforces the receipt rule whatever the plan said. It writes a hash-chained audit row, and on approval records the claim in the same transaction.</p></div></li>
      </ol>
    </div>
  </div>
</section>
""")

wake_api()

# --- sidebar: scenario presets -----------------------------------------------
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

with st.sidebar:
    st.html("<p class='rr-label'>Scenario presets</p>")
    preset = st.radio("Scenario preset", list(PRESETS), index=0, label_visibility="collapsed")
    st.html("<p class='rr-sub'>Synthetic data only. Pick a scenario, then run the agent.</p>")
preset = preset or "Eligible claim"

# Kept in session state so resubmitting the same reference exercises the duplicate check.
st.session_state.setdefault("form_ref", f"FP57-DEMO-{os.urandom(3).hex().upper()}")
values = {
    "patient_id": known,
    "charge_paid_date": today - timedelta(days=10), "claim_submitted_date": today,
    "exemption_category": "HC2", "fp57_receipt_issued": True, "charge_payment_verified": True,
    **PRESETS[preset],
}

form_col, result_col = st.columns([5, 6], gap="large")

# --- claim form -------------------------------------------------------------
with form_col:
    st.html(f"<p class='rr-label'>Claim · {escape(preset)}</p>")
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
                paid = st.date_input("Charge paid", values["charge_paid_date"], max_value=today, format="YYYY-MM-DD")
                submitted = st.date_input("Claim submitted", values["claim_submitted_date"], max_value=today,
                                          format="YYYY-MM-DD")
            receipt = st.toggle("FP57 receipt issued at payment", values["fp57_receipt_issued"])
            paid_ok = st.toggle("Charge payment verified", values["charge_payment_verified"])
        go = st.form_submit_button("Run agent", type="primary")

    run_error = None
    if go:
        with st.spinner("Running the agent: planning, gathering evidence, deciding."):
            try:
                if preset == "Information-only question":
                    r = api("POST", "/info", json={"question": question})
                else:
                    r = api("POST", "/claims", json={
                        "patient_id": patient_id, "fp57_form_ref": form_ref, "charge_paid_date": paid.isoformat(),
                        "claim_submitted_date": submitted.isoformat(), "exemption_category": category,
                        "fp57_receipt_issued": receipt, "charge_payment_verified": paid_ok,
                    })
                st.session_state.last = (r.status_code, r.json())
            except httpx.HTTPError as e:
                run_error = f"{API_URL}: {e}"
    if run_error:
        notice("Request failed.", run_error)


# --- result panel --------------------------------------------------------------
def render_result(status: int, body: dict) -> str:
    if status != 200:
        detail = body.get("detail") if isinstance(body, dict) else None
        fields = ", ".join(".".join(str(p) for p in d.get("loc", [])[1:]) for d in detail
                           if isinstance(d, dict)) if isinstance(detail, list) else ""
        return (f"<div class='rr-panel'><div class='rr-decision'>{mono(f'HTTP {status}')}</div>"
                f"<div class='rr-notice'><b>Rejected at the API boundary.</b>The Planner never ran, so there is "
                f"no plan and no trace.{' Invalid: ' + escape(fields) + '.' if fields else ''}</div></div>")

    refund = f"<span class='rr-refund'>£{escape(body['refund_amount'])}</span>" if body.get("refund_amount") else ""
    reasons = "".join(f"<li>{escape(r)}</li>" for r in body.get("reasons") or [])
    out = [
        "<div class='rr-panel'>",
        f"<div class='rr-decision'>{pill(body['decision'])}{mono(body['reason_code'])}{refund}</div>",
        f"<ul class='rr-reasons'>{reasons}</ul>" if reasons else "",
    ]

    plan = body["plan"]
    out.append(f"<div class='rr-section'><p class='rr-label'>Plan · {len(plan)} steps · {mono(body['model_version'])}</p>")
    if plan:
        out.append("<ol class='rr-plan'>" + "".join(f"<li>{mono(s)}</li>" for s in plan) + "</ol>")
    else:
        out.append(f"<p class='rr-step-detail'>{escape(body.get('planner_error') or 'No plan.')}</p>")
    out.append("</div>")

    if body["trace"]:
        steps = []
        for t in body["trace"]:
            passed = t["result"].get("passed")
            tag = {True: "PASS", False: "FAIL", None: "REF"}[passed]
            steps.append(
                f"<li class='rr-step{' rr-step-fail' if passed is False else ''}'>"
                f"<div class='rr-step-head'>{mono(t['tool'])}<span class='rr-muted'>{escape(TOOL_LABELS.get(t['tool'], ''))}</span>"
                f"<span class='rr-result{' rr-result-fail' if passed is False else ''}'>{tag}</span></div>"
                f"<div class='rr-step-detail'>{escape(str(t['result'].get('detail', '')))}</div></li>"
            )
        out.append("<div class='rr-section'><p class='rr-label'>Trace</p><ol class='rr-trace'>"
                   + "".join(steps) + "</ol></div>")

    if c := body.get("citation"):
        out.append(
            "<div class='rr-section'><p class='rr-label'>Policy citation</p><div class='rr-citation'>"
            f"<h4>{escape(c['heading'])}</h4><p>{escape(c['text'])}</p>"
            f"<p class='rr-muted'>Citation only; {mono('policy_rules')} decides. Retriever: {mono(c['backend'])}</p>"
            "</div></div>"
        )

    out.append(
        "<div class='rr-section rr-meta'>"
        f"<span>audit_id {mono(body.get('audit_id') if body.get('audit_id') is not None else 'none')}</span>"
        f"<span>hash {short_hash(body.get('current_hash'), 16)}</span>"
        f"<span>trace {mono(body['trace_id'][:8])}</span></div>"
    )
    out.append("</div>")
    return "".join(out)


with result_col:
    st.html("<p class='rr-label'>Result</p>")
    if "last" in st.session_state:
        st.html(render_result(*st.session_state.last))
    else:
        st.html("<div class='rr-empty'><strong>No decision yet.</strong>"
                "Pick a scenario in the sidebar and run the agent.<br>"
                "The decision, plan, trace and policy citation appear here.</div>")

# --- how I bridged the gap: tamper-evidence demo -------------------------------
st.html("""
<section class='rr-story rr-story-bridge'>
  <div class='rr-story-row'>
    <div class='rr-eyebrow'>How I bridged the gap</div>
    <div class='rr-prose'>
      <h2>Policy lives in the database, and the log can be checked.</h2>
      <p>The rules are rows in Postgres, not sentences in a prompt, so they can be versioned and tested. Each decision is stored with its plan, its trace and the hash of the row before it. A verifier walks the chain and recomputes every hash.</p>
      <p>Try it. Change a decision below and the verifier notices. Then see what someone with database access could do about that.</p>
    </div>
  </div>
</section>
""")
components.html(TAMPER_DEMO, height=480, scrolling=True)
st.html("<p class='rr-fineprint'>Simplified: the real audit rows hash the plan and the trace as well as the decision.</p>")

# --- audit log ------------------------------------------------------------------
st.html("<p class='rr-h2'>Audit log</p><p class='rr-sub'>Latest decisions, newest first. "
        "Each row's hash covers the previous row's hash.</p>")
try:
    rows = api("GET", "/audit/recent", params={"limit": 10}).json()
except (httpx.HTTPError, ValueError) as e:
    rows = None
    notice("Could not load the audit log.", str(e))
if isinstance(rows, list) and rows:
    body_rows = "".join(
        "<tr>"
        f"<td>{mono(r['audit_id'])}</td>"
        f"<td>{mono(r['created_at'][:19].replace('T', ' '))}</td>"
        f"<td>{pill(r['decision'])}</td>"
        f"<td>{mono(r['model_version'])}</td>"
        f"<td>{short_hash(r['prev_hash'])}</td>"
        f"<td>{short_hash(r['current_hash'])}</td>"
        "</tr>"
        for r in rows
    )
    st.html("<div class='rr-table-wrap'><table class='rr-table'><thead><tr><th>audit_id</th><th>created_at</th>"
            "<th>decision</th><th>model_version</th><th>prev_hash</th><th>current_hash</th></tr></thead>"
            f"<tbody>{body_rows}</tbody></table></div>")
elif rows is not None:
    st.html("<div class='rr-empty'>No audit entries yet. Run a claim to write the first one.</div>")

# --- audit integrity -------------------------------------------------------------
btn_col, verify_col = st.columns([1, 4], vertical_alignment="center")
with btn_col:
    verify = st.button("Verify Audit Integrity", type="primary")
with verify_col:
    if verify:
        try:
            v = api("GET", "/audit/verify").json()
            st.html(f"<div class='rr-verify'><b>{'Chain intact.' if v['ok'] else 'Chain broken.'}</b>"
                    f"<span>{escape(v['message'])}</span>"
                    "<span class='rr-muted'>integrity-checked, not externally anchored</span></div>")
        except httpx.HTTPError as e:
            notice("Verification failed.", str(e))
    else:
        st.html("<div class='rr-verify rr-muted'>integrity-checked, not externally anchored</div>")

st.html("<div class='rr-footer'>Built by <b>Prathamesh Mishra</b> | FDE Portfolio Project"
        "<p>Demonstration system using synthetic data only. Not validated for clinical, regulatory or GxP use. "
        "No real patient data is processed. Out of scope: PPC and HC3 refunds.</p></div>")
