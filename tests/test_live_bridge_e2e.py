"""LIVE human→Switch→agents path (requires live_bridge + Switch)."""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import pytest

PREVIEW = "http://127.0.0.1:18765"


def _get(path: str):
    with urllib.request.urlopen(PREVIEW + path, timeout=10) as r:
        return r.status, json.loads(r.read().decode())


def _post(path: str, body: dict):
    req = urllib.request.Request(
        PREVIEW + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _live_up() -> bool:
    try:
        code, data = _get("/api/health")
        return code == 200 and (data.get("live_bridge") or {}).get("reachable")
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _live_up(), reason="live_bridge/preview not running")


def test_localhost_root_and_ipv6_health():
    code, _ = _get("/api/health")
    assert code == 200
    # dual-bind claim
    _, data = _get("/api/health")
    assert "127.0.0.1" in data.get("binds", [])
    assert "::1" in data.get("binds", [])


def test_live_probe_deny_and_approval_flow():
    code, acc = _post("/api/live/send", {"text": "check site status for goalworld.fun"})
    if code == 500 and any(x in str(acc.get("error", "")).lower() for x in ("not open", "401", "invalid credentials")):
        pytest.skip(f"live bridge transient: {acc.get('error')}")
    assert code == 200 and acc.get("ok") and acc.get("lane") == "live"
    time.sleep(4)
    code, deny = _post("/api/live/send", {"text": "deploy production to caddy now"})
    assert code == 200
    time.sleep(3)
    _, st = _get("/api/live/status")
    events = [e.get("event") for e in st.get("recent") or []]
    assert "scout" in events or any(e.get("action") == "allow_auto" for e in st.get("recent") or [])
    assert any(e.get("action") == "deny" for e in st.get("recent") or [])
    # draft → approval
    _post("/api/live/send", {"text": "draft submission text for the hackathon"})
    time.sleep(3)
    _, st = _get("/api/live/status")
    pending = st.get("pending_approvals") or []
    assert pending, "expected LIVE pending approval"
    aid = pending[0]["approval_id"]
    code, dec = _post("/api/live/decide", {"approval_id": aid, "decision": "approve"})
    assert code == 200 and dec.get("executed_external_side_effect") is False
    time.sleep(2)
    _, st2 = _get("/api/live/status")
    assert "GoalWorld LIVE Ops Brief" in (st2.get("last_brief") or "")
    sessions = st2.get("sessions") or {}
    for agent_name in ("gw-gatekeeper", "gw-ops-scout", "gw-scribe"):
        assert (sessions.get(agent_name) or {}).get("connected") is True
