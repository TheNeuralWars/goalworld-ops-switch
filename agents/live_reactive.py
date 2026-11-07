"""WS-driven GoalWorld agents — Switch room is the bus (no paid LLM).

Protocol tokens (short, non-reentrant):
  [human] ...              → only gw-gatekeeper acts
  [handoff:probe] ...      → only gw-ops-scout acts
  [brief] ...              → only gw-scribe acts (no retarget)

Replies are posted with HTTP /message (room log) unless a handoff token is required.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from agents.gatekeeper import Gatekeeper
from agents.live_bridge import StormGuard, extract_handoff_token, extract_human_stimulus
from agents.scout import OpsScout
from agents.scribe import Scribe
from ops.approvals import ApprovalStore
from ops.readonly import ReadonlyOps
from policy.engine import PolicyEngine
from protocol.client import SwitchClient, load_env_file, redact
from protocol.ws import AgentWSSession


def _payload(frame: dict) -> dict:
    data = frame.get("data") or {}
    return data.get("payload") or {}


async def http_post_message(api: str, agent_id: str, api_key: str, room_id: str, content: str):
    async with httpx.AsyncClient(base_url=api, timeout=30.0) as client:
        r = await client.post(
            f"/agents/{agent_id}/message",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"room_id": room_id, "content": content[:3500]},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"post_message {r.status_code}: {r.text[:300]}")
        return r.json()


async def targeted(
    api: str, agent_id: str, api_key: str, connection_id: str, body: str, targets: list[str]
):
    async with httpx.AsyncClient(base_url=api, timeout=30.0) as client:
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


async def run_reactive(api: str = "http://127.0.0.1:18000", max_seconds: float = 55.0) -> dict:
    env = load_env_file("/workspace/flip-the-switch/switch-upstream/.env")
    token = env["AGENT_REGISTRATION_TOKEN"]
    root = ROOT
    policy = PolicyEngine.from_yaml(root / "policy" / "rules.yaml")
    readonly = ReadonlyOps(root)
    store_path = root / "evidence" / "approvals-reactive.jsonl"
    store_path.write_text("")
    store = ApprovalStore(store_path)
    scribe = Scribe(root / "evidence")
    scribe.log("system", "reactive WS demo v2 start (anti-loop)", mode="reactive_v2")
    scout = OpsScout(policy, readonly)
    gate = Gatekeeper(policy, store)

    secrets = root / ".secrets"
    secrets.mkdir(exist_ok=True)

    with SwitchClient(api, registration_token=token) as client:
        agents = {}
        for name, desc in [
            ("gw-ops-scout", "Read-only GoalWorld ops scout"),
            ("gw-gatekeeper", "GoalWorld policy gatekeeper"),
            ("gw-scribe", "GoalWorld ops scribe"),
        ]:
            data = client.register_agent(name, desc, overwrite=True, addressing="")
            agents[name] = data
            print(f"registered {name} {redact(data['id'])}")
        room = client.create_room(
            agents["gw-ops-scout"]["id"],
            agents["gw-ops-scout"]["api_key"],
            "goalworld-ops-reactive",
            description="WS-driven GoalWorld Ops v2",
            agent_names=list(agents),
        )
        room_id = room["id"]
        print("room_id", room_id)
        (secrets / "agents-reactive.json").write_text(
            json.dumps({"room_id": room_id, "agents": {k: v["id"] for k, v in agents.items()}}, indent=2)
        )

    stop = asyncio.Event()
    evidence: list[dict] = []
    seen: set[str] = set()
    sessions: dict[str, AgentWSSession] = {}
    lock = asyncio.Lock()
    storm_guard = StormGuard()

    def remember(frame: dict) -> str | None:
        mid = (_payload(frame).get("message_id") or "") + ":" + str(frame.get("id") or "")
        if mid == ":" or mid in seen:
            return None
        seen.add(mid)
        return mid

    async def handle_gatekeeper(frame: dict):
        stim = extract_human_stimulus(frame)
        if not stim or not remember(frame) or not storm_guard.allow():
            return
        text, origin = stim
        reply = gate.handle(text)
        is_decide_cmd = text.lower().startswith(("approve ", "reject "))
        decision = policy.classify(text) if not is_decide_cmd else None
        action = (
            decision.action
            if decision
            else ("approve" if "approved" in reply.lower() else "reject" if "rejected" in reply.lower() else "decide")
        )
        async with lock:
            evidence.append(
                {"agent": "gw-gatekeeper", "in": text, "out": reply[:400], "action": action, "origin": origin}
            )
        scribe.log("gw-gatekeeper", reply, live_reactive=True, lane="live_reactive", room_id=room_id)
        # Room-visible receipt (not addressed storm)
        await http_post_message(
            api, agents["gw-gatekeeper"]["id"], agents["gw-gatekeeper"]["api_key"], room_id, f"[LIVE] {reply}"
        )
        if decision and decision.action == "allow_auto":
            handoff = f"[handoff:probe] {text}"
            await targeted(
                api,
                agents["gw-gatekeeper"]["id"],
                agents["gw-gatekeeper"]["api_key"],
                sessions["gw-gatekeeper"].connection_id,
                handoff,
                ["gw-ops-scout"],
            )
        elif decision and decision.action == "require_approval":
            await targeted(
                api,
                agents["gw-gatekeeper"]["id"],
                agents["gw-gatekeeper"]["api_key"],
                sessions["gw-gatekeeper"].connection_id,
                f"[brief] approval card posted for `{decision.intent}` — task: {text}",
                ["gw-scribe"],
            )
        elif decision and decision.action == "deny":
            await targeted(
                api,
                agents["gw-gatekeeper"]["id"],
                agents["gw-gatekeeper"]["api_key"],
                sessions["gw-gatekeeper"].connection_id,
                f"[brief] DENIED `{decision.intent}` ({decision.reason}) — task: {text}",
                ["gw-scribe"],
            )

    async def handle_scout(frame: dict):
        text = extract_handoff_token(
            frame, "[handoff:probe]", allowed_senders=frozenset({"gw-gatekeeper"})
        )
        if not text or not remember(frame) or not storm_guard.allow():
            return
        intent, summary, reply = scout.probe_with_summary(text)
        async with lock:
            evidence.append({"agent": "gw-ops-scout", "in": text, "intent": intent, "summary": summary, "out": reply[:500]})
        scribe.log("gw-ops-scout", reply, live_reactive=True, lane="live_reactive", room_id=room_id)
        await http_post_message(
            api, agents["gw-ops-scout"]["id"], agents["gw-ops-scout"]["api_key"], room_id, f"[LIVE] {reply}"
        )
        await targeted(
            api,
            agents["gw-ops-scout"]["id"],
            agents["gw-ops-scout"]["api_key"],
            sessions["gw-ops-scout"].connection_id,
            f"[brief] Read-only probe `{intent}` for `{text}` → {summary}",
            ["gw-scribe"],
        )

    async def handle_scribe(frame: dict):
        text = extract_handoff_token(
            frame, "[brief]", allowed_senders=frozenset({"gw-gatekeeper", "gw-ops-scout"})
        )
        if not text or not remember(frame) or not storm_guard.allow():
            return
        brief = scribe.brief("Reactive Ops Brief", text, lane="live_reactive", room_id=room_id)
        async with lock:
            evidence.append({"agent": "gw-scribe", "in": text[:200], "out": brief[:300]})
        # Terminal node in DAG — do NOT retarget anyone
        await http_post_message(
            api, agents["gw-scribe"]["id"], agents["gw-scribe"]["api_key"], room_id, f"[LIVE] {brief[:1500]}"
        )

    handlers = {
        "gw-gatekeeper": handle_gatekeeper,
        "gw-ops-scout": handle_scout,
        "gw-scribe": handle_scribe,
    }
    for name in handlers:
        sessions[name] = AgentWSSession(
            api,
            agents[name]["id"],
            agents[name]["api_key"],
            room_id=room_id,
            scope="single",
            filter_="all",
        )

    async def worker(name: str):
        return await sessions[name].run(handlers[name], stop_event=stop, max_seconds=max_seconds)

    async def stimulator():
        await asyncio.sleep(3)
        steps = [
            "check site status for goalworld.fun",
            "draft submission text for the hackathon",
            "deploy production to caddy now",
            "submit to hackathon final submit",
        ]
        for text in steps:
            print("STIM", text)
            await targeted(
                api,
                agents["gw-ops-scout"]["id"],
                agents["gw-ops-scout"]["api_key"],
                sessions["gw-ops-scout"].connection_id,
                f"[human] {text}",
                ["gw-gatekeeper"],
            )
            await asyncio.sleep(5)
        pending = store.pending()
        if pending:
            aid = pending[0].approval_id
            print("STIM approve", aid)
            await targeted(
                api,
                agents["gw-ops-scout"]["id"],
                agents["gw-ops-scout"]["api_key"],
                sessions["gw-ops-scout"].connection_id,
                f"[human] approve {aid}",
                ["gw-gatekeeper"],
            )
            await asyncio.sleep(4)
        await asyncio.sleep(3)
        stop.set()

    results = await asyncio.gather(*(worker(n) for n in handlers), stimulator(), return_exceptions=True)
    stats = {n: results[i] for i, n in enumerate(handlers)}
    out = {
        "room_id": room_id,
        "mode": "reactive_ws_v2",
        "stats": stats,
        "evidence_turns": evidence,
        "pending_approvals_left": [a.approval_id for a in store.pending()],
        "honesty": (
            "Agents listen on Switch WebSocket and act only on protocol tokens "
            "([human]/[handoff:probe]/[brief]). Deterministic handlers; no paid LLM. "
            "`python -m agents.runner --mode live` remains a SCRIPTED poster (not room-driven)."
        ),
    }
    (root / "evidence" / "reactive_live.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({"room_id": room_id, "turns": len(evidence), "mode": out["mode"]}, indent=2))
    for e in evidence:
        print(f"- {e['agent']}: {e.get('action', '')} in={e['in'][:70]!r}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:18000")
    ap.add_argument("--seconds", type=float, default=55.0)
    args = ap.parse_args()
    asyncio.run(run_reactive(args.api, args.seconds))


if __name__ == "__main__":
    main()
