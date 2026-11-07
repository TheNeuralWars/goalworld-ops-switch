"""Preview API: deny non-bypass, approve dry-run, idempotent decide."""
from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Isolate approval store for tests
import demo.server as srv


@pytest.fixture()
def preview_server(tmp_path, monkeypatch):
    approvals = tmp_path / "approvals-ui.jsonl"
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("")
    monkeypatch.setattr(srv, "APPROVALS", approvals)
    monkeypatch.setattr(srv, "TRANSCRIPT", transcript)
    # Scribe writes to ROOT/evidence — also redirect by patching Scribe in _stack via APPROVALS only;
    # transcript path used by GET; simulate logs via Scribe(ROOT/evidence) — patch evidence via env
    httpd = srv.ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield port, approvals, transcript
    httpd.shutdown()


def _req(port, method, path, body=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    raw = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=raw, headers=headers)
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    return resp.status, data


def test_health(preview_server):
    port, _, _ = preview_server
    code, data = _req(port, "GET", "/api/health")
    assert code == 200 and data["ok"] and (data.get("sandbox_dry_run") is True or data.get("dry_run_only") is True)


def test_deny_cannot_be_approved_via_simulate(preview_server):
    port, _, _ = preview_server
    code, data = _req(port, "POST", "/api/simulate", {"text": "deploy production to caddy now"})
    assert code == 200
    assert data["decision"] == "deny"
    assert data["executed_side_effect"] is False
    assert "DENIED" in data["message"]


def test_require_approval_then_approve_dry_run_and_idempotent(preview_server):
    port, approvals, _ = preview_server
    code, data = _req(port, "POST", "/api/simulate", {"text": "draft submission text for the hackathon"})
    assert code == 200
    assert data["decision"] == "require_approval"
    assert data["executed_side_effect"] is False
    code, pending = _req(port, "GET", "/api/approvals")
    assert pending["pending"]
    aid = pending["pending"][0]["approval_id"]
    code, dec = _req(port, "POST", "/api/decide", {"approval_id": aid, "decision": "approve"})
    assert code == 200
    assert dec["executed_side_effect"] is False
    assert "approved" in dec["message"].lower() or "dry-run" in (dec.get("receipt") or "").lower()
    # duplicate
    code, dec2 = _req(port, "POST", "/api/decide", {"approval_id": aid, "decision": "approve"})
    assert code == 200
    assert dec2.get("idempotent") is True
    assert dec2["executed_side_effect"] is False


def test_final_submit_denied(preview_server):
    port, _, _ = preview_server
    _, data = _req(port, "POST", "/api/simulate", {"text": "submit to hackathon final submit"})
    assert data["decision"] == "deny"
    assert data["executed_side_effect"] is False
