# GoalWorld Ops Room — Flip the Switch (Track 01: Best Business Workflow)

**Business workflow:** Human operators + deterministic Python agents run day-to-day **GoalWorld** operations inside a self-hosted **Switch `0.31.0`** room with hard policy & approval gates so no external action fires without explicit human sign-off.

> **Switch is mandatory and central.** Self-hosted Switch `0.31.0` + bundled Mattermost on loopback (`127.0.0.1`). Custom Python agents register via **`POST /agents`** and coordinate over Switch WebSockets (`send_targeted_message` + room event bus). **Deterministic policy & read-only probes — NOT LLM reasoning.**

---

## Honesty & Capability Matrix (Read First)

| Path / Command | What It Actually Does | Switch Room Role | Engine Type |
|---|---|---|---|
| **Preview LIVE Chat** (`demo/server.py` `:18765` → `agents.live_bridge` `:18766`) | **Room-driven human workflow (Primary):** Human task → `send_targeted_message([human])` → WebSocket agents (`gw-gatekeeper` → `gw-ops-scout` → `gw-scribe`) → read-only probes + persisted ops brief (`evidence/last_brief.md`). | **Live coordination bus** (HTTP + WebSocket) | Deterministic Python (No LLM) |
| `python -m agents.live_reactive` | **Room-driven WebSocket runner:** Connects all 3 agents via Switch WebSocket and runs automated stimulus turns across the `[human]` → `[handoff:probe]` → `[brief]` DAG. | **Live coordination bus** (HTTP + WebSocket) | Deterministic Python (No LLM) |
| `python -m agents.runner --mode live` | **Scripted room poster:** Calls local `route()` in-process and posts the resulting transcript into a Switch room using agent API keys. | **Audit / message log only** (room does *not* drive agents) | Deterministic Python (No LLM) |
| **Preview SANDBOX** (`:18765` `/api/simulate`, `/api/decide`) & `runner --mode local` | **Local policy dry-run:** Evaluates `policy/rules.yaml` and sandbox approvals in-process. Does **not** enter the Switch room. | **None** (isolated local sandbox) | Deterministic Python (No LLM) |

- **Deterministic Agents ≠ LLM:** All three agents (`gw-gatekeeper`, `gw-ops-scout`, `gw-scribe`) execute deterministic keyword/precedence policy rules (`policy/rules.yaml`) and real read-only HTTP/Docker/filesystem probes (`ops/readonly.py`). They are **never** marketed as LLM reasoning, and incur **zero API spend**.
- **Dry-Run Side Effects Only:** Even after a human approves a `require_approval` card in the LIVE room or SANDBOX, external side effects (production deploy, email, social post, contest submission, spend) remain strictly `executed_external_side_effect: false`.
- **Review Gate:** See [`REVIEW.md`](./REVIEW.md) and [`STATUS.md`](./STATUS.md) — currently **`REVIEW: approved`**.

---

## Switch Console Eligibility & Protocol Honesty (No Waiver Claimed)

1. **Official Hackathon FAQ (“What do I need to get started?”):**  
   Lists **Switch Console** (desktop app), **Docker** to run Switch locally, and an **AI coding agent** (such as Claude Code, Codex, or OpenCode).  
   Source: https://www.wemakedevs.org/hackathons/switch
2. **Official Switch Agent Protocol Support:**  
   Switch documentation explicitly supports building custom agent clients that register via **`POST /agents`** (with `Bearer <AGENT_REGISTRATION_TOKEN>`) and connect over WebSocket (`/agents/{id}/connection/ws`), noting that `register-known` is reserved for Console-managed agent types.  
   Source: https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md
3. **No Waiver Claimed:**  
   **Protocol support for custom agents does not constitute a contest rule waiver.** We do **not** claim that a Console-less setup waives the FAQ's Switch Console requirement unless confirmed by organizers. [`switch-room.yaml`](./switch-room.yaml) is provided for Switch Console import alongside our custom protocol agents.

---

## Anti-Storm Protocol DAG & Mattermost Loopback (`127.0.0.1:18065`)

```text
Human (Preview LIVE or Mattermost @gw-gatekeeper)
  │
  ├── [human] <task> ────────────► gw-gatekeeper (Policy Engine + Approval Store)
  │                                  ├─ allow_auto ───────► [handoff:probe] <task> ──► gw-ops-scout (Read-Only Probe)
  │                                  │                                                    └─► [brief] <summary> ──► gw-scribe
  │                                  ├─ require_approval ─► [brief] <card receipt> ───────────────────────────────► gw-scribe
  │                                  ├─ deny ─────────────► [brief] <denial receipt> ─────────────────────────────► gw-scribe
  │                                  └─ approve/reject ───► [brief] <dry-run decision> ───────────────────────────► gw-scribe
```

- **Strict Anti-Loop / Anti-Storm Guards:**
  - Directed Acyclic Graph (DAG) token prefixes (`[human]`, `[handoff:probe]`, `[brief]`) with sender allowlists: `gw-scribe` is a terminal sink that posts room receipts via HTTP `/message` and never emits targeted handoffs.
  - Prefix-only token parsing after stripping `@gw-*` mentions prevents substring spoofing (e.g., asking `"what is [handoff:probe]?"` cannot trigger a probe).
  - Deduplication by `message_id:frame_id` plus `StormGuard` sliding-window rate limiter.
  - Self-healing WebSocket worker loop: if agent API keys rotate (`401`) or a WebSocket session is evicted (`409`), `live_bridge` automatically re-registers, reconnects all 3 WebSockets, awaits readiness, and completes delivery.
- **Mattermost-Native Input vs. Preview LIVE Primary Path:**
  - Every room created via `create_room` is automatically bridged to the bundled loopback Mattermost (`http://127.0.0.1:18065`).
  - **Concrete Bootstrap Constraint:** Agents registered via `POST /agents` with `AGENT_REGISTRATION_TOKEN` receive HTTP `403` when calling `update_agent_detail(addressing="anyone")` (owner restriction). As a result, Switch delivers non-owner Mattermost user messages over `filter=all` WebSockets with `payload.addressed = false`.
  - **Dual Support:** `gw-gatekeeper` inspects `filter=all` frames and accepts `@gw-gatekeeper <task>` / `[human] <task>` from non-agent human room participants even when `addressed=false` (while rejecting all `@switch-agent-*` echoes). Because interactive Mattermost user login requires local user credentials/session state that must stay out of repo evidence, **Preview LIVE (`http://127.0.0.1:18765/`)** is the primary zero-secret human interface.

---

## Architecture

| Component | File | Responsibility |
|---|---|---|
| **Switch Protocol Client** | [`protocol/client.py`](./protocol/client.py), [`protocol/ws.py`](./protocol/ws.py) | Custom agent registration (`POST /agents`), room ops, targeted messages, WebSocket ping/pong & cursor tracking |
| **LIVE Bridge Daemon** | [`agents/live_bridge.py`](./agents/live_bridge.py) | Dual-bind (`127.0.0.1:18766` + `::1:18766`) human→Switch bridge, persistent WS workers, self-healing credential refresh |
| **Gatekeeper Agent** | [`agents/gatekeeper.py`](./agents/gatekeeper.py), [`policy/engine.py`](./policy/engine.py) | Deny-first policy classification (`allow_auto` / `require_approval` / `deny`) + idempotent dry-run approval cards |
| **Ops Scout Agent** | [`agents/scout.py`](./agents/scout.py), [`ops/readonly.py`](./ops/readonly.py) | Live read-only probes (`goalworld.fun` HTTP 200 checks, Switch health, Docker `gw-switch-*` containers, deadlines, `STATUS.md`) |
| **Scribe Agent** | [`agents/scribe.py`](./agents/scribe.py) | Structured Markdown ops briefs (`evidence/last_brief.md`) + append-only `evidence/transcript.jsonl` |
| **Preview Console** | [`demo/server.py`](./demo/server.py), [`demo/index.html`](./demo/index.html), [`demo/app.js`](./demo/app.js), [`demo/styles.css`](./demo/styles.css) | Fractured Code–styled dual-lane console (LIVE Switch Room vs. Local Sandbox, lane filters, live WS telemetry, Scribe brief viewer) |
| **Console Template** | [`switch-room.yaml`](./switch-room.yaml) | Switch Console–compatible room & agent template |

---

## Quickstart (Local Box)

```bash
export PATH="$HOME/.local/bin:$PATH"
export DOCKER_HOST=tcp://127.0.0.1:2375
cd /workspace/flip-the-switch/goalworld-ops-switch
source .venv/bin/activate

# 1. Ensure self-hosted Switch 0.31.0 stack is up (idempotent)
./scripts/up-switch.sh

# 2. Run test suite (unit + policy + anti-storm + live Switch + preview + LIVE e2e)
pytest -q --tb=short

# 3. Start room-driven LIVE bridge (:18766) + Preview UI (:18765, dual-bind 127.0.0.1 & ::1)
python -m agents.live_bridge &
python demo/server.py &

# 4. Health checks
curl -sf http://127.0.0.1:18000/health
curl -sf http://127.0.0.1:18765/api/health
```

---

## Official Contest & Hard Limits

- **Contest:** Flip the Switch Hackathon — **Track 01: Best Business Workflow** (https://www.wemakedevs.org/hackathons/switch)
- **Deadline:** **2026-11-07 23:59 IST ≈ 19:29 Europe/Rome**
- **Hard Limits:** Zero spend · No public git push / deploy / form submit until October `REVIEW: approved` · No file deletions · Secrets stay in `.secrets/` and upstream `.env` (gitignored) · Deterministic agents never marketed as LLM.
- **Status:** See [`STATUS.md`](./STATUS.md) — currently **`REVIEW: pending`**.
