"""Persistent LIVE bridge: human typed text → Switch room → WS-driven agents.

Uses only official Switch agent protocol:
  POST /agents, create_room, send_targeted_message, POST /agents/{id}/message, WebSocket.

No Mattermost browser, no public accounts, no external messages, no paid LLM.
Human input arrives via local HTTP (preview proxies /api/live/* here).

Listen: 127.0.0.1:18766 and ::1:18766
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from aiohttp import web

from agents.gatekeeper import Gatekeeper
from agents.scout import OpsScout
from agents.scribe import Scribe
from ops.approvals import ApprovalStore
from ops.readonly import ReadonlyOps
from policy.engine import PolicyEngine
from protocol.client import SwitchClient, load_env_file, redact
from protocol.ws import AgentWSSession

API = "http://127.0.0.1:18000"
AUDIT = ROOT / "evidence" / "live_audit.jsonl"
TRANSCRIPT_NOTE = ROOT / "evidence" / "LIVE_LANE.md"
KNOWN_AGENTS = frozenset({"gw-ops-scout", "gw-gatekeeper", "gw-scribe"})
MENTION_TOKENS = ("@gw-gatekeeper", "@gw-ops-scout", "@gw-scribe")
ECHO_PREFIXES = (
    "[live]",
    "@gw-gatekeeper:",
    "@gw-ops-scout",
    "@gw-scribe:",
    "[handoff:probe]",
    "[brief]",
)
ECHO_MARKERS = (
    "**denied**",
    "**approval required**",
    "brief saved →",
    "dry-run receipt only",
    "goalworld hard limits:",
)


class StormGuard:
    """Sliding-window rate limiter to guarantee zero feedback storms."""

    def __init__(self, max_turns: int = 18, window_seconds: float = 10.0):
        self.max_turns = max_turns
        self.window_seconds = window_seconds
        self._events: deque[float] = deque()
        self.tripped_count = 0

    def allow(self, now: float | None = None) -> bool:
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.popleft()
        if len(self._events) >= self.max_turns:
            self.tripped_count += 1
            return False
        self._events.append(ts)
        return True


STATE = {
    "ready": False,
    "room_id": None,
    "agents": {},
    "sessions": {},
    "stops": {},
    "seen": set(),
    "turns": [],
    "errors": [],
    "started_at": None,
    "storm_guard": StormGuard(),
}


def audit(event: str, **kw):
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
    with AUDIT.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    STATE["turns"].append(row)
    STATE["turns"] = STATE["turns"][-200:]


def _payload(frame: dict) -> dict:
    return (frame.get("data") or {}).get("payload") or {}


async def http_post_message(agent_id: str, api_key: str, room_id: str, content: str):
    async with httpx.AsyncClient(base_url=API, timeout=30.0) as client:
        r = await client.post(
            f"/agents/{agent_id}/message",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"room_id": room_id, "content": content[:3500]},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"post_message {r.status_code}: {r.text[:300]}")
        return r.json()


async def targeted(agent_id: str, api_key: str, connection_id: str, body: str, targets: list[str]):
    async with httpx.AsyncClient(base_url=API, timeout=30.0) as client:
        r = await client.post(
            f"/agents/{agent_id}/ops/send_targeted_message",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Switch-Connection-Id": connection_id,
            },
            json={"body": body, "target_names": targets},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"targeted {r.status_code}: {r.text[:300]}")
        return r.json()


async def bootstrap():
    env = load_env_file("/workspace/flip-the-switch/switch-upstream/.env")
    token = env["AGENT_REGISTRATION_TOKEN"]
    policy = PolicyEngine.from_yaml(ROOT / "policy" / "rules.yaml")
    readonly = ReadonlyOps(ROOT)
    store = ApprovalStore(ROOT / "evidence" / "approvals-live.jsonl")
    scribe = Scribe(ROOT / "evidence")
    scout = OpsScout(policy, readonly)
    gate = Gatekeeper(policy, store)
    STATE["policy"] = policy
    STATE["scout"] = scout
    STATE["gate"] = gate
    STATE["scribe"] = scribe
    STATE["store"] = store

    with SwitchClient(API, registration_token=token) as client:
        agents = {}
        for name, desc in [
            ("gw-ops-scout", "Read-only GoalWorld ops scout"),
            ("gw-gatekeeper", "GoalWorld policy gatekeeper"),
            ("gw-scribe", "GoalWorld ops scribe"),
        ]:
            data = client.register_agent(name, desc, overwrite=True, addressing="")
            agents[name] = {"id": data["id"], "api_key": data["api_key"]}
            print(f"registered {name} {redact(data['id'])}", flush=True)
        room = client.create_room(
            agents["gw-ops-scout"]["id"],
            agents["gw-ops-scout"]["api_key"],
            "goalworld-ops-live",
            description="LIVE human→Switch→agents bridge",
            agent_names=list(agents),
        )
        room_id = room["id"]
        STATE["room_id"] = room_id
        STATE["agents"] = agents
        (ROOT / ".secrets" / "live_bridge.json").write_text(
            json.dumps({"room_id": room_id, "agents": {k: v["id"] for k, v in agents.items()}}, indent=2)
        )
    TRANSCRIPT_NOTE.write_text(
        "# LIVE lane\n\nHuman typed tasks enter via preview LIVE chat → Switch "
        "`send_targeted_message` with `[human]` → WS agents. "
        "Sandbox UI approvals are a separate dry-run lane.\n"
        f"room_id={room_id}\n"
    )
    scribe.log("system", f"LIVE bridge ready room={room_id}", source="live-bridge", lane="live")
    audit("bootstrap", room_id=room_id)
    return room_id


def remember(frame: dict) -> bool:
    p = _payload(frame)
    mid = f"{p.get('message_id') or ''}:{frame.get('id') or ''}"
    if mid == ":" or mid in STATE["seen"]:
        return False
    STATE["seen"].add(mid)
    if len(STATE["seen"]) > 5000:
        STATE["seen"] = set(list(STATE["seen"])[-2000:])
    return True


def strip_leading_mentions(text: str) -> str:
    """Strip leading @gw-* mentions and separators prepended by Switch or users."""
    s = (text or "").strip()
    changed = True
    while changed and s:
        changed = False
        low = s.lower()
        for tok in MENTION_TOKENS:
            if low.startswith(tok):
                s = s[len(tok) :].lstrip(" \t,:;-")
                changed = True
                break
    return s.strip()


def clean_mentions(text: str) -> str:
    s = strip_leading_mentions(text)
    for tok in MENTION_TOKENS:
        s = s.replace(f"{tok}:", "").replace(tok, "").strip()
    return s


def is_agent_echo(body: str) -> bool:
    """Return True if body looks like an agent room reply or internal handoff echo."""
    raw = (body or "").strip().lower()
    stripped = strip_leading_mentions(body).lower()
    if not raw or not stripped:
        return True
    for prefix in ECHO_PREFIXES:
        if raw.startswith(prefix) or stripped.startswith(prefix):
            return True
    for marker in ECHO_MARKERS:
        if marker in raw:
            return True
    return False


def extract_human_stimulus(frame: dict) -> tuple[str, str] | None:
    """Extract (task_text, origin) for gw-gatekeeper, enforcing strict anti-loop rules.

    Accepts:
    1. Targeted `[human] <task>` relay from `gw-ops-scout` (`origin="live-bridge"`).
       Never accepts `[human]` from `gw-gatekeeper` or `gw-scribe`.
    2. Direct human messages from non-agent participants in the bridged Mattermost
       channel (`origin="mattermost-human"`) when addressed OR explicitly prefixed
       with `[human]` or `@gw-gatekeeper` (handling Switch's 403 bootstrap
       `addressing_policy` limitation where non-owner user messages arrive with
       `addressed=False` over `filter=all`).
    """
    p = _payload(frame)
    body = (p.get("body") or "").strip()
    if not body:
        return None
    sender = str(p.get("sender") or "")
    sender_name = str(p.get("sender_name") or "")
    addressed = bool(p.get("addressed"))
    is_agent = sender.startswith("@switch-agent-") or (sender_name in KNOWN_AGENTS)

    stripped = strip_leading_mentions(body)
    if is_agent:
        if not addressed:
            return None
        if sender_name in ("gw-gatekeeper", "gw-scribe"):
            return None
        if not stripped.startswith("[human]"):
            return None
        task = clean_mentions(stripped[len("[human]") :])
        if not task or is_agent_echo(task):
            return None
        return task, "live-bridge"

    # Native human participant (e.g., bridged Mattermost user on 127.0.0.1:18065)
    has_explicit_tag = stripped.startswith("[human]") or ("@gw-gatekeeper" in body.lower())
    if not (addressed or has_explicit_tag):
        return None
    if stripped.startswith("[human]"):
        stripped = stripped[len("[human]") :].strip()
    task = clean_mentions(stripped)
    if not task or is_agent_echo(task):
        return None
    return task, "mattermost-human"


def extract_handoff_token(
    frame: dict, token: str, *, allowed_senders: frozenset[str] | set[str]
) -> str | None:
    """Extract payload for strict DAG handoff tokens (`[handoff:probe]`, `[brief]`)."""
    p = _payload(frame)
    if not p.get("addressed"):
        return None
    sender_name = str(p.get("sender_name") or "")
    if sender_name and sender_name not in allowed_senders:
        return None
    stripped = strip_leading_mentions(p.get("body") or "")
    if not stripped.startswith(token):
        return None
    payload = clean_mentions(stripped[len(token) :])
    if not payload or payload.lower().startswith("[live]"):
        return None
    return payload


async def handle_gatekeeper(frame: dict):
    stim = extract_human_stimulus(frame)
    if not stim or not remember(frame):
        return
    if not STATE["storm_guard"].allow():
        audit("storm_guard_tripped", agent="gw-gatekeeper")
        return
    text, origin = stim
    gate: Gatekeeper = STATE["gate"]
    policy: PolicyEngine = STATE["policy"]
    reply = gate.handle(text)
    is_decide_cmd = text.lower().startswith(("approve ", "reject "))
    decision = policy.classify(text) if not is_decide_cmd else None
    action = (
        decision.action
        if decision
        else ("approve" if "approved" in reply.lower() else "reject" if "rejected" in reply.lower() else "decide")
    )
    STATE["scribe"].log("gw-gatekeeper", reply, source=origin, lane="live", action=action)
    audit("gatekeeper", in_=text, out=reply[:500], action=action, origin=origin)
    agents = STATE["agents"]
    room_id = STATE["room_id"]
    await http_post_message(
        agents["gw-gatekeeper"]["id"], agents["gw-gatekeeper"]["api_key"], room_id, f"[LIVE] {reply}"
    )
    if decision and decision.action == "allow_auto":
        await targeted(
            agents["gw-gatekeeper"]["id"],
            agents["gw-gatekeeper"]["api_key"],
            STATE["sessions"]["gw-gatekeeper"].connection_id,
            f"[handoff:probe] {text}",
            ["gw-ops-scout"],
        )
    elif decision and decision.action == "require_approval":
        first_line = reply.splitlines()[1] if len(reply.splitlines()) > 1 else reply.splitlines()[0]
        await targeted(
            agents["gw-gatekeeper"]["id"],
            agents["gw-gatekeeper"]["api_key"],
            STATE["sessions"]["gw-gatekeeper"].connection_id,
            f"[brief] LIVE approval gate opened for `{decision.intent}` ({first_line}) — task: {text}",
            ["gw-scribe"],
        )
    elif decision and decision.action == "deny":
        await targeted(
            agents["gw-gatekeeper"]["id"],
            agents["gw-gatekeeper"]["api_key"],
            STATE["sessions"]["gw-gatekeeper"].connection_id,
            f"[brief] LIVE DENIED `{decision.intent}` ({decision.reason}) — task: {text}",
            ["gw-scribe"],
        )
    elif is_decide_cmd:
        await targeted(
            agents["gw-gatekeeper"]["id"],
            agents["gw-gatekeeper"]["api_key"],
            STATE["sessions"]["gw-gatekeeper"].connection_id,
            f"[brief] LIVE gate decision ({action}): {reply}",
            ["gw-scribe"],
        )


async def handle_scout(frame: dict):
    text = extract_handoff_token(
        frame, "[handoff:probe]", allowed_senders=frozenset({"gw-gatekeeper"})
    )
    if not text or not remember(frame):
        return
    if not STATE["storm_guard"].allow():
        audit("storm_guard_tripped", agent="gw-ops-scout")
        return
    intent, summary, reply = STATE["scout"].probe_with_summary(text)
    STATE["scribe"].log("gw-ops-scout", reply, source="live-bridge", lane="live", intent=intent)
    audit("scout", in_=text, intent=intent, summary=summary, out=reply[:800])
    agents = STATE["agents"]
    await http_post_message(
        agents["gw-ops-scout"]["id"], agents["gw-ops-scout"]["api_key"], STATE["room_id"], f"[LIVE] {reply}"
    )
    await targeted(
        agents["gw-ops-scout"]["id"],
        agents["gw-ops-scout"]["api_key"],
        STATE["sessions"]["gw-ops-scout"].connection_id,
        f"[brief] Read-only probe `{intent}` for `{text}` → {summary}",
        ["gw-scribe"],
    )


async def handle_scribe(frame: dict):
    text = extract_handoff_token(
        frame, "[brief]", allowed_senders=frozenset({"gw-gatekeeper", "gw-ops-scout"})
    )
    if not text or not remember(frame):
        return
    if not STATE["storm_guard"].allow():
        audit("storm_guard_tripped", agent="gw-scribe")
        return
    brief = STATE["scribe"].brief("GoalWorld LIVE Ops Brief", text, lane="live", room_id=STATE["room_id"])
    audit("scribe", in_=text[:300], out=brief[:400])
    agents = STATE["agents"]
    # Terminal node in DAG: posts HTTP room receipt only; never calls targeted().
    await http_post_message(
        agents["gw-scribe"]["id"], agents["gw-scribe"]["api_key"], STATE["room_id"], f"[LIVE] {brief[:1500]}"
    )


async def worker_loop(name: str, handler):
    while True:
        agents = STATE["agents"]
        sess = AgentWSSession(
            API,
            agents[name]["id"],
            agents[name]["api_key"],
            room_id=STATE["room_id"],
            scope="single",
            filter_="all",
        )
        stop = asyncio.Event()
        STATE["sessions"][name] = sess
        STATE["stops"][name] = stop
        try:
            stats = await sess.run(handler, stop_event=stop, max_seconds=3600)
            audit("ws_end", agent=name, stats=stats)
        except Exception as e:
            STATE["errors"].append(f"{name}: {e}")
            audit("ws_error", agent=name, error=str(e))
        if not stop.is_set():
            await asyncio.sleep(0.5)


async def refresh_agents():
    """Re-register after 401/409 (keys rotate when another process overwrites) and await WS reconnect."""
    env = load_env_file("/workspace/flip-the-switch/switch-upstream/.env")
    token = env["AGENT_REGISTRATION_TOKEN"]
    with SwitchClient(API, registration_token=token) as client:
        agents = {}
        for name, desc in [
            ("gw-ops-scout", "Read-only GoalWorld ops scout"),
            ("gw-gatekeeper", "GoalWorld policy gatekeeper"),
            ("gw-scribe", "GoalWorld ops scribe"),
        ]:
            data = client.register_agent(name, desc, overwrite=True, addressing="")
            agents[name] = {"id": data["id"], "api_key": data["api_key"]}
        room_id = STATE["room_id"]
        for name in agents:
            try:
                client.op(
                    agents["gw-ops-scout"]["id"],
                    agents["gw-ops-scout"]["api_key"],
                    "invite_agent_to_room",
                    {"room_id": room_id, "agent_name": name},
                )
            except Exception:
                pass
        STATE["agents"] = agents

    old_sessions = {k: v for k, v in STATE["sessions"].items()}
    for stop in list(STATE.get("stops", {}).values()):
        stop.set()

    # Wait for worker_loop tasks to create new sessions and open WebSockets
    for _ in range(40):
        await asyncio.sleep(0.1)
        all_ready = True
        for name in ("gw-gatekeeper", "gw-ops-scout", "gw-scribe"):
            cur = STATE["sessions"].get(name)
            if not cur or cur is old_sessions.get(name) or not cur.ready.is_set():
                all_ready = False
                break
        if all_ready:
            break
    await asyncio.sleep(0.35)
    audit("credentials_refreshed")
    print("credentials refreshed and WS sessions reconnected", flush=True)


async def deliver_human_stimulus(stimulus_body: str) -> None:
    """Deliver `[human] ...` via gw-ops-scout targeted message with automatic self-healing."""

    async def _deliver():
        agents = STATE["agents"]
        scout = STATE["sessions"]["gw-ops-scout"]
        if not scout.ready.is_set():
            await asyncio.wait_for(scout.ready.wait(), timeout=5.0)
        await targeted(
            agents["gw-ops-scout"]["id"],
            agents["gw-ops-scout"]["api_key"],
            scout.connection_id,
            stimulus_body,
            ["gw-gatekeeper"],
        )

    try:
        await asyncio.wait_for(_deliver(), timeout=15.0)
    except Exception as e:
        err = str(e)
        audit("human_send_error", error=err)
        if any(tok in err.lower() for tok in ("401", "invalid credentials", "not open", "409")):
            await refresh_agents()
            await asyncio.wait_for(_deliver(), timeout=15.0)
        else:
            raise


async def on_health(request: web.Request):
    ws_connected = {
        name: bool(sess and sess.ready.is_set())
        for name, sess in STATE.get("sessions", {}).items()
    }
    return web.json_response(
        {
            "ok": STATE["ready"],
            "lane": "live",
            "room_id": STATE["room_id"],
            "agents": {k: v["id"] for k, v in STATE["agents"].items()},
            "ws_connected": ws_connected,
            "turns": len(STATE["turns"]),
            "storm_guard_trips": STATE["storm_guard"].tripped_count,
            "errors": STATE["errors"][-5:],
        }
    )


async def on_status(request: web.Request):
    last_brief_path = ROOT / "evidence" / "last_brief.md"
    last_brief = last_brief_path.read_text() if last_brief_path.exists() else ""
    ws_sessions = {
        name: {
            "connected": bool(sess and sess.ready.is_set()),
            "connection_id": redact(sess.connection_id, 4) if sess else "",
            "cursor": sess.cursor if sess else 0,
        }
        for name, sess in STATE.get("sessions", {}).items()
    }
    return web.json_response(
        {
            "ok": STATE["ready"],
            "lane": "live",
            "room_id": STATE["room_id"],
            "sessions": ws_sessions,
            "protocol_dag": "[human] → gw-gatekeeper → [handoff:probe] → gw-ops-scout → [brief] → gw-scribe",
            "mattermost_bridge": {
                "loopback_url": "http://127.0.0.1:18065",
                "bridged": True,
                "primary_input": "preview_live_http_bridge",
                "native_input_support": "WS filter=all accepts @gw-gatekeeper / [human] from non-agent room participants",
            },
            "last_brief": last_brief[:2000],
            "recent": STATE["turns"][-30:],
            "pending_approvals": [
                {"approval_id": a.approval_id, "intent": a.intent, "summary": a.summary, "lane": "live"}
                for a in STATE["store"].pending()
            ]
            if STATE.get("store")
            else [],
        }
    )


async def on_send(request: web.Request):
    if not STATE["ready"]:
        return web.json_response({"ok": False, "error": "bridge not ready"}, status=503)
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "error": "text required"}, status=400)
    STATE["scribe"].log("human", text, source="live-bridge", lane="live")
    audit("human_in", text=text)

    try:
        await deliver_human_stimulus(f"[human] {text}")
    except Exception as e2:
        audit("human_send_retry_error", error=str(e2))
        return web.json_response({"ok": False, "error": str(e2), "lane": "live"}, status=500)

    await asyncio.sleep(2.5)
    return web.json_response(
        {
            "ok": True,
            "lane": "live",
            "room_id": STATE["room_id"],
            "accepted": text,
            "note": "Delivered into Switch room; WS agents process asynchronously. Poll /status or transcript (lane=live).",
            "executed_external_side_effect": False,
        }
    )


async def on_decide_fixed(request: web.Request):
    if not STATE["ready"]:
        return web.json_response({"ok": False, "error": "bridge not ready"}, status=503)
    data = await request.json()
    approval_id = (data.get("approval_id") or "").strip().lower()
    decision = (data.get("decision") or "").strip().lower()
    if decision not in ("approve", "reject") or not approval_id:
        return web.json_response({"ok": False, "error": "approval_id + approve|reject"}, status=400)
    text = f"[human] {decision} {approval_id}"
    STATE["scribe"].log("human", f"{decision} {approval_id}", source="live-bridge", lane="live")
    audit("human_decide", approval_id=approval_id, decision=decision)
    try:
        await deliver_human_stimulus(text)
    except Exception as e:
        audit("human_decide_error", error=str(e))
        return web.json_response({"ok": False, "error": str(e), "lane": "live"}, status=500)
    await asyncio.sleep(2.0)
    return web.json_response(
        {
            "ok": True,
            "lane": "live",
            "message": f"sent {decision} {approval_id} into LIVE room",
            "executed_external_side_effect": False,
            "receipt": "LIVE lane approval is still DRY-RUN for external effects",
        }
    )


async def main_async():
    await bootstrap()
    handlers = {
        "gw-gatekeeper": handle_gatekeeper,
        "gw-ops-scout": handle_scout,
        "gw-scribe": handle_scribe,
    }
    STATE["ready"] = True
    STATE["started_at"] = time.time()

    app = web.Application()
    app.router.add_get("/health", on_health)
    app.router.add_get("/status", on_status)
    app.router.add_post("/send", on_send)
    app.router.add_post("/decide", on_decide_fixed)

    # Dual bind localhost
    runners = []
    for host in ("127.0.0.1", "::1"):
        runner = web.AppRunner(app)
        await runner.setup()
        try:
            site = web.TCPSite(runner, host, 18766)
            await site.start()
            print(f"live_bridge http://{host}:18766/", flush=True)
            runners.append(runner)
        except OSError as e:
            print(f"live_bridge bind fail {host}: {e}", flush=True)
    if not runners:
        raise SystemExit("live_bridge bind failed")

    await asyncio.gather(*(worker_loop(n, h) for n, h in handlers.items()))


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
