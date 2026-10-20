import httpx
from streamlit.testing.v1 import AppTest

from ui import wake


def mock_health(statuses: list[int]):
    """A health() that answers with each status in turn, repeating the last one; records every call."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(statuses[min(len(calls), len(statuses)) - 1])

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api.test")
    return (lambda **kw: client.get("/health", **kw)), calls


def fake_time():
    now = [0.0]
    return {"sleep": lambda s: now.__setitem__(0, now[0] + s), "clock": lambda: now[0]}


def test_two_502s_then_200_succeeds():
    health, calls = mock_health([502, 502, 200])
    assert wake.wait_for_api(health, **fake_time()) is None
    assert len(calls) == 3


def test_401_is_not_retried():
    health, calls = mock_health([401, 200])
    error = wake.wait_for_api(health, **fake_time())
    assert isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 401
    assert len(calls) == 1


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
