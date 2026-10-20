"""Wakes the API on Render's free tier, which answers 502 while the instance spins up."""
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

import httpx
import streamlit as st

WAKE_INTERVAL_S = 3
WAKE_DEADLINE_S = 90


def retryable(e: httpx.HTTPError) -> bool:
    """5xx, timeouts and connection errors mean "still waking"; 4xx will not fix itself."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)


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
                if not retryable(e) or clock() - start + WAKE_INTERVAL_S > WAKE_DEADLINE_S:
                    return e
                sleep(WAKE_INTERVAL_S)


def wake_api(
    health: Callable[..., httpx.Response],
    notice: Callable[[str, str], None],
    target: str,
    **wait_kw,
) -> bool:
    """True on the run that first reaches the API. Stops the script with a notice if it never answers."""
    if st.session_state.get("api_awake"):
        return False
    error = wait_for_api(
        health,
        waiting=lambda elapsed: st.spinner(
            f"Waking the API ({elapsed:.0f}s elapsed). Render's free tier can take up to a minute on first load."
        ),
        **wait_kw,
    )
    if error is not None:
        notice("API unreachable.", f"{target}: {error}")
        st.button("Try again")  # a click reruns the script, which runs this check again
        st.stop()
    st.session_state.api_awake = True
    return True
