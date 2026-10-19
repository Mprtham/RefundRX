"""Canonical audit-log hash. Imported by the Decision node's write path and by
scripts/verify_audit_chain.py — never re-implemented anywhere else.

Canonicalization (sort_keys, no whitespace) makes the hash independent of the
key order Postgres JSONB happens to return on read-back.
"""
import hashlib
import json


def compute_audit_hash(prev_hash: str | None, plan_json: dict, trace_json: dict, decision: str) -> str:
    canonical = json.dumps(
        {"prev": prev_hash, "plan": plan_json, "trace": trace_json, "decision": decision},
        sort_keys=True, separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
