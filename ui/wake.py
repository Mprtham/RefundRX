"""Wakes the API on Render's free tier, which answers 502 while the instance spins up."""
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

import httpx
import streamlit as st

WAKE_INTERVAL_S = 3
WAKE_DEADLINE_S = 90
MAX_RETRY_AFTER_S = 10
HEALTH_TTL_S = 60

# Monotonic time of the last successful health check. Module state, so it is
# shared by every session this Streamlit process serves; failures are not kept.
_last_ok: float | None = None


def retryable(e: httpx.HTTPError) -> bool:
    """5xx, 429, timeouts and connection errors will pass; other 4xx will not fix itself."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        return code >= 500 or code == 429
    return isinstance(e, httpx.TransportError)


def retry_delay(e: httpx.HTTPError) -> float:
    """The server's Retry-After (in seconds, capped) when it sent one, else the usual interval."""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            return min(max(float(e.response.headers["retry-after"]), 0.0), MAX_RETRY_AFTER_S)
        except (KeyError, ValueError):
            pass
    return WAKE_INTERVAL_S


def wait_for_api(
    health: Callable[..., httpx.Response],
    *,
    waiting: Callable[[float], AbstractContextManager] = lambda elapsed: nullcontext(),
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> httpx.HTTPError | None:
    """Polls health() until it succeeds or the deadline passes. Returns the last error, or None."""
    start = clock()
    while True:
        elapsed = clock() - start
        with waiting(elapsed):
            try:
                health(timeout=max(1.0, WAKE_DEADLINE_S - elapsed)).raise_for_status()
                return None
            except httpx.HTTPError as e:
                delay = retry_delay(e)
                if not retryable(e) or clock() - start + delay > WAKE_DEADLINE_S:
                    return e
                sleep(delay)


def wake_api(
    health: Callable[..., httpx.Response],
    notice: Callable[[str, str], None],
    target: str,
    *,
    clock: Callable[[], float] = time.monotonic,
    **wait_kw,
) -> bool:
    """True on the run that first reaches the API. Stops the script with a notice if it never answers.

    A success in the last HEALTH_TTL_S seconds, from any session, stands in for a fresh check.
    """
    global _last_ok
    if st.session_state.get("api_awake"):
        return False
    if _last_ok is None or clock() - _last_ok >= HEALTH_TTL_S:
        error = wait_for_api(
            health,
            waiting=lambda elapsed: st.spinner(
                f"Waking the API ({elapsed:.0f}s elapsed). Render's free tier can take up to a minute on first load."
            ),
            clock=clock,
            **wait_kw,
        )
        if error is not None:
            notice("API unreachable.", f"{target}: {error}")
            st.button("Try again")  # a click reruns the script, which runs this check again
            st.stop()
        _last_ok = clock()
    st.session_state.api_awake = True
    return True
