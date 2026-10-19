"""Retrieval sanity check on a small hand-labelled gold set.

The Qdrant backend downloads bge-small-en-v1.5 (~130 MB), so it is opt-in:
    RUN_QDRANT_TESTS=1 pytest tests/test_retrieval.py
GOLD was used to tune the lexical weight (0.3) and scores 10/10, so it is a
regression check, not an accuracy claim. HELD_OUT was never tuned on and is the
honest number: 6/8 at the time of writing.
"""
import os
import re

import pytest

from app.rag.retriever import get_retriever, load_chunks

GOLD = {
    "How long do I have to claim an FP57 refund?": "Time limit",
    "What is the time limit for claiming an FP57 prescription refund?": "Time limit",
    "Is there a deadline for prescription refunds?": "Time limit",
    "Can I get an FP57 after I paid?": "FP57 must",
    "Can my pharmacy refund medicine I don't need?": "Pharmacies",
    "I have a PPC, can I get money back?": "Out of scope",
    "Which exemption certificates count?": "Exemption categories|Evidence",
    "How much will I get back?": "Refund amount",
    "I already got a refund on this form": "One refund",
    "What is an FP57?": "FP57 refund receipt",
}

HELD_OUT = {
    "When is it too late to get my prescription money back?": "Time limit",
    "The pharmacist forgot to give me a refund form, what now?": "FP57 must",
    "I'm pregnant, can I claim back what I paid?": "Exemption categories|Evidence",
    "Do I need to show my certificate?": "Evidence",
    "Can I return unused tablets for cash?": "Pharmacies",
    "Is HC3 partial help covered?": "Out of scope",
    "How many refunds can one receipt give?": "One refund",
    "What does it cost per item?": "Refund amount",
}


def _hits(r, gold: dict) -> int:
    return sum(bool(re.match(g, r.search(q)[0][0].heading)) for q, g in gold.items())


def test_chunks_drop_provenance_comment():
    chunks = load_chunks()
    assert len(chunks) == 9
    assert not any("<!--" in c.text for c in chunks)


@pytest.mark.skipif(os.getenv("RUN_QDRANT_TESTS") != "1", reason="downloads the embedding model")
def test_hybrid_retrieval_gold_set():
    r = get_retriever("qdrant")
    assert _hits(r, GOLD) == len(GOLD)
    assert _hits(r, HELD_OUT) >= 6
