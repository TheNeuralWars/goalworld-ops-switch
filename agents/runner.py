"""Orchestrate GoalWorld agents.

HONESTY:
- `--mode local`: in-process route() only (no Switch).
- `--mode live`: registers agents + posts a SCRIPTED conversation into a Switch room.
  The room is NOT driving agents; the runner calls route() then posts results.
- Room-driven coordination: `python -m agents.live_reactive` (WebSocket listeners).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.gatekeeper import Gatekeeper
from agents.scout import OpsScout
from agents.scribe import Scribe
from ops.approvals import ApprovalStore
from ops.readonly import ReadonlyOps
from policy.engine import PolicyEngine
from protocol.client import SwitchClient, load_env_file, redact


def build_stack(root: Path):
    policy = PolicyEngine.from_yaml(root / "policy" / "rules.yaml")
    readonly = ReadonlyOps(root)
    store = ApprovalStore(root / "evidence" / "approvals.jsonl")
    scribe = Scribe(root / "evidence")
    scout = OpsScout(policy, readonly)
    gate = Gatekeeper(policy, store)
    return policy, scout, gate, scribe, store


def route(text: str, scout: OpsScout, gate: Gatekeeper, scribe: Scribe) -> list[str]:
    """Deterministic multi-agent turn for demo messages."""
    outs: list[str] = []
    decision = gate.policy.classify(text)
    scribe.log("human", text, intent=decision.intent, action=decision.action)

    # approval/reject always to gatekeeper
    low = text.lower()
    if "approve " in low or "reject " in low:
        msg = gate.handle(text)
        outs.append(msg)
        scribe.log("gw-gatekeeper", msg)
        return outs

    if decision.action == "allow_auto":
        g = gate.handle(text)
        outs.append(g)
        scribe.log("gw-gatekeeper", g)
        s = scout.handle(text)
        outs.append(s)
        scribe.log("gw-ops-scout", s)
        b = scribe.brief(f"Ops: {decision.intent}", s)
        outs.append(b)
        return outs

    # deny or require_approval → gatekeeper
    g = gate.handle(text)
    outs.append(g)
    scribe.log("gw-gatekeeper", g)
    if decision.action == "deny":
        b = scribe.brief(f"Denied: {decision.intent}", g)
        outs.append(b)
    return outs


def run_local_demo(root: Path) -> Path:
    _, scout, gate, scribe, store = build_stack(root)
    # reset transcript for clean demo
    if scribe.transcript.exists():
        scribe.transcript.write_text("")
    script = [
        "check site status for goalworld.fun",
        "what is the Flip the Switch deadline?",
        "docker stack status please",
        "draft submission text for the hackathon",
        "deploy production to caddy now",
        "submit to hackathon final submit",
    ]
    # We'll fill approval id dynamically after draft
    for line in script:
        print(f"\n>>> {line}")
        for out in route(line, scout, gate, scribe):
            print(out[:500])
    pending = store.pending()
    if pending:
        aid = pending[0].approval_id
        line = f"approve {aid}"
        print(f"\n>>> {line}")
        for out in route(line, scout, gate, scribe):
            print(out[:500])
    return scribe.transcript



def run_live_switch(root: Path, api: str) -> None:
    env = load_env_file("/workspace/flip-the-switch/switch-upstream/.env")
    token = env.get("AGENT_REGISTRATION_TOKEN")
    if not token:
        raise SystemExit("AGENT_REGISTRATION_TOKEN missing in switch-upstream/.env")

    secrets_dir = root / ".secrets"
    secrets_dir.mkdir(exist_ok=True)

    with SwitchClient(api, registration_token=token) as client:
        health = client.health()
        print("switch health:", health)

        agents_meta = {}
        for name, desc in [
            ("gw-ops-scout", "Read-only GoalWorld ops scout"),
            ("gw-gatekeeper", "GoalWorld policy gatekeeper"),
            ("gw-scribe", "GoalWorld ops scribe"),
        ]:
            data = client.register_agent(name, desc, overwrite=True, addressing="")
            agents_meta[name] = {"id": data["id"], "api_key": data["api_key"]}
            print(f"registered {name} id={data['id']} key={redact(data['api_key'])}")

        (secrets_dir / "agents.json").write_text(json.dumps(agents_meta, indent=2))

        scout_id = agents_meta["gw-ops-scout"]["id"]
        scout_key = agents_meta["gw-ops-scout"]["api_key"]

        room = client.op(
            scout_id,
            scout_key,
            "create_room",
            {
                "name": "goalworld-ops",
                "description": "GoalWorld Ops Room — Flip the Switch Track01",
                "agent_names": ["gw-ops-scout", "gw-gatekeeper", "gw-scribe"],
            },
        )
        room_id = room.get("id") if isinstance(room, dict) else None
        print("room_id=", room_id)

        if not room_id:
            print("WARN: no room_id; falling back to local demo")
            run_local_demo(root)
            return

        _, scout, gate, scribe, store = build_stack(root)
        if scribe.transcript.exists():
            scribe.transcript.write_text("")

        def post(agent_name: str, content: str) -> None:
            meta = agents_meta[agent_name]
            client.post_message(meta["id"], meta["api_key"], room_id, content[:3500])

        kickoff = (
            "GoalWorld Ops Room online. Switch is central. "
            "Read-only probes auto-run; side effects need approval. Demo mode = dry-run only."
        )
        post("gw-ops-scout", kickoff)
        scribe.log("gw-ops-scout", kickoff, room_id=room_id, live=True)

        script = [
            "check site status for goalworld.fun",
            "what is the Flip the Switch deadline?",
            "draft submission text for the hackathon",
            "deploy production to caddy now",
        ]
        for line in script:
            post("gw-ops-scout", f"[human] {line}")
            for out in route(line, scout, gate, scribe):
                if out.startswith("@gw-gatekeeper"):
                    post("gw-gatekeeper", out)
                elif out.startswith("@gw-scribe"):
                    post("gw-scribe", out)
                else:
                    post("gw-ops-scout", out)

        pending = store.pending()
        if pending:
            aid = pending[0].approval_id
            line = f"approve {aid}"
            post("gw-ops-scout", f"[human] {line}")
            for out in route(line, scout, gate, scribe):
                post("gw-gatekeeper", out)

        (root / "evidence" / "live_room.json").write_text(
            json.dumps(
                {
                    "room_id": room_id,
                    "agents": {k: v["id"] for k, v in agents_meta.items()},
                    "integration": "LIVE Switch HTTP agent protocol",
                    "side_effects": "dry-run only",
                },
                indent=2,
            )
        )
        print("LIVE_OK room_id=", room_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "live"], default="local")
    ap.add_argument("--api", default="http://127.0.0.1:18000")
    args = ap.parse_args()
    root = ROOT
    if args.mode == "local":
        path = run_local_demo(root)
        print("transcript:", path)
    else:
        run_live_switch(root, args.api)


if __name__ == "__main__":
    main()
