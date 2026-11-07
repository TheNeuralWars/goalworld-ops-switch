#!/usr/bin/env python3
"""Local GoalWorld Ops preview — dual-bind localhost (IPv4+IPv6).

ROOT CAUSE FIX (browser QA): Chrome resolves `localhost` → ::1 first.
Binding only 127.0.0.1 made /api/health (via 127.0.0.1) work while
http://localhost:18765/ returned ERR_CONNECTION_REFUSED.

Listens on 127.0.0.1 AND ::1 only (not 0.0.0.0).
Sandbox APIs stay local dry-run. LIVE path proxies to live_bridge :18766.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEMO = Path(__file__).resolve().parent
TRANSCRIPT = ROOT / "evidence" / "transcript.jsonl"
APPROVALS = ROOT / "evidence" / "approvals-ui.jsonl"
LIVE_BRIDGE = "http://127.0.0.1:18766"
HOSTS = ("127.0.0.1", "::1")
PORT = 18765


def _stack():
    from agents.gatekeeper import Gatekeeper
    from agents.scout import OpsScout
    from agents.scribe import Scribe
    from ops.approvals import ApprovalStore
    from ops.readonly import ReadonlyOps
    from policy.engine import PolicyEngine

    policy = PolicyEngine.from_yaml(ROOT / "policy" / "rules.yaml")
    store = ApprovalStore(APPROVALS)
    scribe = Scribe(TRANSCRIPT.parent)
    return policy, OpsScout(policy, ReadonlyOps(ROOT)), Gatekeeper(policy, store), scribe, store


def _read_json(handler) -> dict:
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    return json.loads(raw.decode() or "{}")


def _send(handler, code: int, payload: dict):
    body = json.dumps(payload).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _proxy_live(method: str, path: str, body: bytes | None = None) -> tuple[int, dict]:
    url = f"{LIVE_BRIDGE}{path}"
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode() or "{}")
        except Exception:
            payload = {"ok": False, "error": str(e)}
        return e.code, payload
    except Exception as e:
        return 503, {
            "ok": False,
            "error": f"live_bridge unreachable: {e}",
            "hint": "start: python -m agents.live_bridge",
            "path": "LIVE",
        }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEMO), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            live_code, live = _proxy_live("GET", "/health")
            return _send(
                self,
                200,
                {
                    "ok": True,
                    "service": "goalworld-ops-preview",
                    "binds": list(HOSTS),
                    "port": PORT,
                    "sandbox_dry_run": True,
                    "dry_run_only": True,
                    "engine": "deterministic_policy_v1",
                    "llm_used": False,
                    "live_bridge": {"reachable": live_code < 500, "status": live},
                },
            )
        if path == "/api/transcript":
            rows = []
            if TRANSCRIPT.exists():
                for line in TRANSCRIPT.read_text().splitlines():
                    if line.strip():
                        rows.append(json.loads(line))
            brief_path = TRANSCRIPT.parent / "last_brief.md"
            last_brief = brief_path.read_text() if brief_path.exists() else ""
            live_cnt = sum(
                1
                for r in rows
                if "live" in str(r.get("lane") or r.get("source") or "").lower()
                or r.get("live") is True
                or r.get("live_reactive") is True
            )
            sandbox_cnt = sum(
                1
                for r in rows
                if str(r.get("lane") or "").lower() == "sandbox"
                or str(r.get("source") or "").lower() == "preview-ui"
            )
            return _send(
                self,
                200,
                {
                    "rows": rows[-200:],
                    "counts": {
                        "total": len(rows),
                        "live": live_cnt,
                        "sandbox": sandbox_cnt,
                    },
                    "last_brief": last_brief[:2500],
                    "sandbox_dry_run_note": "Rows with source=preview-ui are SANDBOX. source=live-bridge / live_reactive are LIVE Switch path.",
                },
            )
        if path == "/api/approvals":
            _, _, _, _, store = _stack()
            pending = [
                {
                    "approval_id": a.approval_id,
                    "intent": a.intent,
                    "summary": a.summary,
                    "risk": a.risk,
                    "proposed_action": a.proposed_action,
                    "status": a.status,
                    "lane": "sandbox",
                }
                for a in store.pending()
            ]
            return _send(self, 200, {"pending": pending, "lane": "sandbox", "dry_run_only": True})
        if path.startswith("/api/live/"):
            code, payload = _proxy_live("GET", path[len("/api/live") :] or "/")
            return _send(self, code if code else 502, payload)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        raw_len = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(raw_len) if raw_len else b"{}"

        if path.startswith("/api/live/"):
            code, payload = _proxy_live("POST", path[len("/api/live") :], raw)
            return _send(self, code if code else 502, payload)

        data = json.loads(raw.decode() or "{}")
        policy, scout, gate, scribe, store = _stack()

        if path == "/api/simulate":
            text = (data.get("text") or "").strip()
            if not text:
                return _send(self, 400, {"ok": False, "error": "text required", "lane": "sandbox"})
            decision = policy.classify(text)
            scribe.log("human", text, source="preview-ui", lane="sandbox", intent=decision.intent, action=decision.action)
            if decision.action == "deny":
                msg = gate.handle(text)
                scribe.log("gw-gatekeeper", msg, source="preview-ui", lane="sandbox")
                return _send(
                    self,
                    200,
                    {
                        "ok": True,
                        "lane": "sandbox",
                        "decision": "deny",
                        "intent": decision.intent,
                        "message": msg,
                        "executed_side_effect": False,
                        "dry_run_only": True,
                    },
                )
            if decision.action == "allow_auto":
                g = gate.handle(text)
                s = scout.handle(text)
                scribe.log("gw-gatekeeper", g, source="preview-ui", lane="sandbox")
                scribe.log("gw-ops-scout", s, source="preview-ui", lane="sandbox")
                return _send(
                    self,
                    200,
                    {
                        "ok": True,
                        "lane": "sandbox",
                        "decision": "allow_auto",
                        "intent": decision.intent,
                        "message": s[:2000],
                        "executed_side_effect": False,
                        "dry_run_only": True,
                    },
                )
            msg = gate.handle(text)
            scribe.log("gw-gatekeeper", msg, source="preview-ui", lane="sandbox")
            return _send(
                self,
                200,
                {
                    "ok": True,
                    "lane": "sandbox",
                    "decision": "require_approval",
                    "intent": decision.intent,
                    "message": msg,
                    "executed_side_effect": False,
                    "dry_run_only": True,
                },
            )

        if path == "/api/decide":
            approval_id = (data.get("approval_id") or "").strip().lower()
            decision = (data.get("decision") or "").strip().lower()
            if decision not in ("approve", "reject") or not approval_id:
                return _send(self, 400, {"ok": False, "error": "approval_id + approve|reject", "lane": "sandbox"})
            before = store.get(approval_id)
            if before and before.status != "pending":
                msg = f"@gw-gatekeeper: already `{before.status}` `{approval_id}` (idempotent)."
                scribe.log("gw-gatekeeper", msg, source="preview-ui", lane="sandbox", idempotent=True)
                return _send(
                    self,
                    200,
                    {
                        "ok": True,
                        "lane": "sandbox",
                        "idempotent": True,
                        "status": before.status,
                        "message": msg,
                        "executed_side_effect": False,
                        "dry_run_only": True,
                    },
                )
            msg = gate.handle(f"{decision} {approval_id}", who="preview-ui")
            scribe.log("human", f"{decision} {approval_id}", source="preview-ui", lane="sandbox")
            scribe.log("gw-gatekeeper", msg, source="preview-ui", lane="sandbox")
            return _send(
                self,
                200,
                {
                    "ok": True,
                    "lane": "sandbox",
                    "idempotent": False,
                    "message": msg,
                    "executed_side_effect": False,
                    "dry_run_only": True,
                    "receipt": "SANDBOX DRY-RUN ONLY — not the LIVE Switch lane",
                },
            )

        return _send(self, 404, {"ok": False, "error": "not found"})

    def log_message(self, fmt, *args):
        line = args[0] if args else ""
        if isinstance(line, str) and "/api/" in line:
            return
        super().log_message(fmt, *args)


def _make_server(host: str) -> ThreadingHTTPServer:
    if ":" in host:
        class V6(ThreadingHTTPServer):
            address_family = socket.AF_INET6

        httpd = V6((host, PORT), Handler)
    else:
        httpd = ThreadingHTTPServer((host, PORT), Handler)
    return httpd


def main():
    APPROVALS.parent.mkdir(parents=True, exist_ok=True)
    servers = []
    for host in HOSTS:
        try:
            httpd = _make_server(host)
            servers.append((host, httpd))
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            print(f"preview bound http://{host}:{PORT}/", flush=True)
        except OSError as e:
            print(f"bind failed {host}:{PORT}: {e}", flush=True)
    if not servers:
        raise SystemExit("no preview binds succeeded")
    print(
        "URLs: http://127.0.0.1:18765/  AND  http://localhost:18765/ (IPv6 ::1)",
        flush=True,
    )
    threading.Event().wait()


if __name__ == "__main__":
    main()
