# Build: GoalWorld Ops Switch — Flip the Switch Track 01

You are implementing a COMPLETE, runnable standalone project at:
`/workspace/flip-the-switch/goalworld-ops-switch/`

Read first (already copied under docs/):
- docs/GOALWORLD_AGY_RULES.md
- docs/QUALITY_BAR.md
- docs/RULES.md

## Contest context (verified live 2026-11-06)
- Hackathon: Flip the Switch (WeMakeDevs × DevTools Academy × Switch)
- Official: https://www.wemakedevs.org/hackathons/switch
- Rules: https://www.wemakedevs.org/hackathons/switch/rules
- Docs: https://docs.switchagents.ai/
- Track: **01 Best Business Workflow** ($2k) — Track03 issues all claimed
- Deadline: Nov 7, 2026 11:59 PM IST = **19:29 Europe/Rome**
- Registered: theneuralwars (WeMakeDevs + Luma)
- Switch is MANDATORY and central
- Free self-host + Mattermost bundled; no company Slack needed
- Deliverables for submit later (DO NOT submit): repo, demo video, README
- October review gate: STATUS.md REVIEW: pending — no public submit

## Live Switch stack ALREADY RUNNING on this box (use it)
- DOCKER_HOST=tcp://127.0.0.1:2375
- docker CLI: /home/box/.local/bin/docker
- Compose project: gw-switch
- API/bridge: http://127.0.0.1:18000  (health → {"status":"ok"})
- Gateway: http://127.0.0.1:13000
- Mattermost: http://127.0.0.1:18065
- Env/secrets: /workspace/flip-the-switch/switch-upstream/.env
- Upstream clone: /workspace/flip-the-switch/switch-upstream/
- Agent registration works: POST /agents with Bearer [REDACTED]
- Probe agent already registered; see .secrets/probe-agent.json (gitignored)
- Protocol docs: https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md
  and agent-connection.md (WebSocket /agents/{id}/connection/ws)

## Product vision (ambitious — QUALITY_BAR)
**GoalWorld Ops Room**: a business workflow where people + AI agents run GoalWorld day-to-day ops inside a Switch room (Mattermost-backed), with hard approval gates so nothing external fires without a human.

Agents (deterministic Python clients speaking real Switch protocol — NO fake stub claiming to be Switch):
1. **gw-ops-scout** — read-only: site health, contest deadlines, timeline pulse, disk, docker stack status. Never mutates.
2. **gw-gatekeeper** — classifies intents; allows auto for read-only; for anything with side effects posts an APPROVAL card and waits for human "approve <id>" / "reject <id>" in-room. Never executes live external side effects in demo mode.
3. **gw-scribe** — writes structured ops briefs / receipts into the room and local evidence/.

Policy (must be real code, not comments):
- Default DENY for: email, social posts, deploys, spends, deletes, contest submit, VPS mutations
- ALLOW auto: health checks, read local STATUS, summarize canon pointers, list open approvals
- REQUIRE approval: draft submissions, proposed deploy plans, external message drafts (still dry-run only)

## Architecture to create
```
goalworld-ops-switch/
  README.md                 # jury-ready EN, 30s clarity
  STATUS.md                 # REVIEW: pending + evidence links
  pyproject.toml / requirements.txt
  .gitignore                # must ignore .secrets, .env, evidence secrets
  switch-room.yaml          # Switch room/agent template for Console + self-host
  protocol/
    client.py               # real Switch HTTP+WS client (register, ops, post_message, connect, pong)
    models.py
  agents/
    scout.py
    gatekeeper.py
    scribe.py
    runner.py               # multi-agent process
  policy/
    rules.yaml
    engine.py
  ops/
    readonly.py             # safe probes (curl goalworld.fun, local docker ps, files under project)
    approvals.py
  demo/
    index.html + app.js + styles.css   # cinematic GoalWorld/Fractured Code dark UI preview of room transcript + approvals
    server.py               # local preview HTTP on 127.0.0.1:18765 reading evidence/transcript.jsonl
  scripts/
    up-switch.sh            # document/start compose (idempotent)
    register-agents.sh
    run-demo.sh             # end-to-end scripted demo against live Switch
    smoke.sh
  tests/
    test_policy.py
    test_client_unit.py
    test_demo_flow.py       # can use live Switch if SWITCH_API=http://127.0.0.1:18000
  submission/
    SUBMISSION.md           # draft text for WeMakeDevs form — DO NOT submit
    CHECKLIST.md
    DEMO_SCRIPT.md
  evidence/                 # created by smoke/demo
  docs/                     # already has RULES/QUALITY_BAR
```

## Hard constraints
- Zero spend. No PAYG keys. Included agy/auth only.
- No public deploy, no contest submit, no external messages/posts, no destructive git, no deletes of origin.
- Do not modify GoalChain production. Standalone project only.
- Do not contact Hermes / send VPS inbox.
- Do not print secrets (AGENT_REGISTRATION_TOKEN, passwords, api_keys) into README/STATUS/evidence public files — redact.
- Honest labeling: LIVE Switch integration vs dry-run side effects.
- Prefer websockets library + httpx/urllib; Python 3.11+.
- Demo must produce evidence/transcript.jsonl + evidence/SMOKE.md with curl proofs.
- Local preview URL: http://127.0.0.1:18765/

## Implementation order
1. Write protocol client + unit tests (mockable)
2. Policy engine + tests
3. Agents + runner
4. Register agents against live Switch; create/join room via ops; run scripted demo conversation
5. Demo UI + smoke
6. README + submission pack + STATUS REVIEW:pending
7. Run pytest + smoke; save evidence

## Success criteria
- `pytest` green
- Live Switch: agents registered, messages posted, approval gate demonstrated
- Preview UI serves transcript
- No secrets in tracked files
- Ambitious enough for October review (not a 50-LOC stub)

Start coding now. Create all files. Run tests. Write evidence.
