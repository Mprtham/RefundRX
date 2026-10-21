"""Drives the Streamlit UI's scenario presets against a real, seeded local API with no auth."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "ui" / "streamlit_app.py")
EXPECTED = {
    "Eligible claim": ("APPROVED", None),
    "No FP57 receipt": ("REJECTED", "NO_FP57_RECEIPT"),
    "Outside the window (95 days)": ("REJECTED", "OUTSIDE_CLAIM_WINDOW"),
    "Unknown patient": ("REJECTED", "UNKNOWN_PATIENT"),
    "Charge never paid": ("REJECTED", "CHARGE_NOT_PAID"),
    "Information-only question": ("NO_CLAIM_MADE", None),
    "Duplicate claim": ("REJECTED", "DUPLICATE_CLAIM"),
}


@pytest.fixture(scope="module")
def api_url(tmp_path_factory):
    if not (ROOT / "data" / "synthetic_claims.csv").exists():
        pytest.skip("needs data/ from scripts.generate_synthetic_data")
    db = tmp_path_factory.mktemp("ui") / "ui.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db.as_posix()}", "RAG_BACKEND": "keyword",
           "GROQ_API_KEY": "", "PLANNER_BACKEND": "auto", "API_BASIC_AUTH_USER": "", "API_BASIC_AUTH_PASSWORD": "",
           "RATE_LIMIT_PER_MINUTE": "1000"}
    subprocess.run([sys.executable, "-m", "scripts.seed_db", "--reset"], cwd=ROOT, env=env, check=True,
                   capture_output=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                httpx.get(f"{url}/health", timeout=1).raise_for_status()
                break
            except httpx.HTTPError:
                if proc.poll() is not None:
                    pytest.fail("local API exited on startup")
                time.sleep(0.5)
        else:
            pytest.fail("local API did not start")
        old = {k: os.environ.get(k) for k in ("API_URL", "API_BASIC_AUTH_USER", "API_BASIC_AUTH_PASSWORD", "APP_PASSWORD")}
        os.environ.update(API_URL=url, API_BASIC_AUTH_USER="", API_BASIC_AUTH_PASSWORD="", APP_PASSWORD="")
        yield url
        for k, v in old.items():
            if v is None:
                os.environ.pop(k)
            else:
                os.environ[k] = v
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def pick(at: AppTest, preset: str) -> AppTest:
    return at.radio(key="preset").set_value(preset).run()


def run_agent(at: AppTest) -> dict:
    at.button(key="FormSubmitter:claim-Run agent").click().run()
    status, body = at.session_state["last"]
    assert status == 200, body
    return body


def form(at: AppTest) -> dict:
    t = {w.label: w.value for w in at.text_input}
    return {"pid": t.get("Patient ID (999 test range)"), "ref": t.get("FP57 form reference"),
            "paid": next((d.value for d in at.date_input if d.label == "Charge paid"), None),
            "toggles": [w.value for w in at.toggle]}


def test_every_preset_returns_its_decision(api_url):
    at = app()
    for preset, (decision, reason) in EXPECTED.items():
        at = pick(at, preset)
        body = run_agent(at)
        assert body["decision"] == decision, (preset, body["reason_code"])
        if reason:
            assert body["reason_code"] == reason, preset
        if preset == "Eligible claim":
            assert body["refund_amount"] == "9.90"


def test_each_preset_gets_a_fresh_reference_and_rerunning_hits_duplicate(api_url):
    at = app()
    refs = []
    for preset in ["No FP57 receipt", "Eligible claim", "Unknown patient", "Charge never paid", "Eligible claim"]:
        at = pick(at, preset)
        refs.append(form(at)["ref"])
    assert len(set(refs)) == len(refs) and all(r.startswith("FP57-DEMO-") and len(r) == 16 for r in refs)
    assert form(at)["pid"] and form(at)["toggles"] == [True, True]

    assert run_agent(at)["decision"] == "APPROVED"
    again = run_agent(at)  # same preset, same reference: the duplicate check fires on purpose
    assert (again["decision"], again["reason_code"]) == ("REJECTED", "DUPLICATE_CLAIM")


def test_duplicate_preset_reuses_last_approved_reference(api_url):
    at = pick(app(), "Duplicate claim")
    assert any("No approved claim yet." in str(h.proto) for h in at.get("html"))

    at = pick(at, "Eligible claim")
    approved_ref = form(at)["ref"]
    assert run_agent(at)["decision"] == "APPROVED"
    at = pick(at, "Duplicate claim")
    assert form(at)["ref"] == approved_ref
    assert not any("No approved claim yet." in str(h.proto) for h in at.get("html"))


def test_picking_a_preset_scrolls_to_the_claim_form(api_url):
    def scroll_frames(at):
        return [e for e in at.sidebar if "claim-form" in str(getattr(e, "proto", ""))]

    at = app()
    assert not scroll_frames(at)
    at = pick(at, "No FP57 receipt")
    first = scroll_frames(at)
    assert len(first) == 1 and "prefers-reduced-motion" in str(first[0].proto)
    at = pick(at, "Unknown patient")
    assert str(scroll_frames(at)[0].proto) != str(first[0].proto)  # new nonce: the frame remounts
