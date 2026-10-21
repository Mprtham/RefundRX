import httpx
import pytest
from streamlit.testing.v1 import AppTest

from ui import wake


@pytest.fixture(autouse=True)
def forget_last_success():
    wake._last_ok = None
    yield
    wake._last_ok = None


def mock_health(statuses: list[int | tuple[int, dict]]):
    """A health() that answers with each status (optionally with headers) in turn, repeating the last one."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        answer = statuses[min(len(calls), len(statuses)) - 1]
        code, headers = answer if isinstance(answer, tuple) else (answer, {})
        return httpx.Response(code, headers=headers)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api.test")
    return (lambda **kw: client.get("/health", **kw)), calls


def fake_time(slept: list[float] | None = None):
    now = [0.0]

    def sleep(s):
        if slept is not None:
            slept.append(s)
        now[0] += s

    return {"sleep": sleep, "clock": lambda: now[0]}


def test_two_502s_then_200_succeeds():
    health, calls = mock_health([502, 502, 200])
    assert wake.wait_for_api(health, **fake_time()) is None
    assert len(calls) == 3


def test_401_is_not_retried():
    health, calls = mock_health([401, 200])
    error = wake.wait_for_api(health, **fake_time())
    assert isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 401
    assert len(calls) == 1


def test_429_is_retried_honouring_capped_retry_after():
    slept = []
    health, calls = mock_health([(429, {"Retry-After": "5"}), (429, {"Retry-After": "120"}), 429, 200])
    assert wake.wait_for_api(health, **fake_time(slept)) is None
    assert len(calls) == 4
    assert slept == [5.0, wake.MAX_RETRY_AFTER_S, wake.WAKE_INTERVAL_S]


def test_401_fails_fast_even_after_a_429():
    health, calls = mock_health([429, 401, 200])
    error = wake.wait_for_api(health, **fake_time())
    assert isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 401
    assert len(calls) == 2


def wake_script(health, time_kw):
    import streamlit as st

    from ui import wake

    def notice(title, text):
        st.session_state.notice = (title, text)

    wake.wake_api(health, notice, "http://api.test", **time_kw)
    st.write("awake")


def test_persistent_502_ends_in_unreachable_notice():
    health, calls = mock_health([502])
    at = AppTest.from_function(wake_script, args=(health, fake_time())).run()
    title, text = at.session_state["notice"]
    assert title == "API unreachable." and "502" in text
    assert [b.label for b in at.button] == ["Try again"]
    assert "api_awake" not in at.session_state
    assert not any(m.value == "awake" for m in at.markdown)
    # every 3 s for 90 s: attempts at t = 0, 3, ..., 90
    assert len(calls) == wake.WAKE_DEADLINE_S // wake.WAKE_INTERVAL_S + 1


def test_a_recent_success_is_shared_across_sessions():
    health, calls = mock_health([200])
    time_kw = fake_time()
    for _ in range(3):  # three separate page loads within the TTL
        at = AppTest.from_function(wake_script, args=(health, time_kw)).run()
        assert at.session_state["api_awake"]
    assert len(calls) == 1
    time_kw["sleep"](wake.HEALTH_TTL_S)
    AppTest.from_function(wake_script, args=(health, time_kw)).run()
    assert len(calls) == 2


def test_a_failure_is_not_remembered():
    health, calls = mock_health([401, 200])
    at = AppTest.from_function(wake_script, args=(health, fake_time())).run()
    assert at.session_state["notice"][0] == "API unreachable."
    at = AppTest.from_function(wake_script, args=(health, fake_time())).run()
    assert at.session_state["api_awake"] and len(calls) == 2
