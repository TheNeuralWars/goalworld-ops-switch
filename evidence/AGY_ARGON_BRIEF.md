# Antigravity Argon task — GoalWorld Ops Switch (Flip the Switch Track01)

You ARE Gemini 4 Argon on Google Antigravity (`--model gemini-4-argon-high`). Do substantive code work. Do NOT write another AGY_SCOPED_NOTE-only deliverable. Do NOT claim to be Nous Portal Argon.

## Hard constraints (non-negotiable)
- Work ONLY under `/workspace/flip-the-switch/goalworld-ops-switch`
- Local prepare only: NO public git push, NO deploy, NO contest form submit, NO external messages, NO Hermes contact
- NO spend / NO PAYG keys / NO paid model APIs
- NO deletions of user data; archive/rename with backup if needed
- Do NOT reconfigure shared Docker daemon (`0.0.0.0:2375`); use `DOCKER_HOST=tcp://127.0.0.1:2375` if needed
- Do NOT kill/restart unrelated workloads; existing `demo/server.py` (:18765) and `agents.live_bridge` may be running — inspect first; only restart if you broke them
- Keep `REVIEW.md` / `STATUS.md` as **pending / changes_requested** — never mark approved
- Secrets stay out of git/evidence: never copy `.secrets/`, `.env`, API keys into logs or evidence
- Deterministic agents: NEVER market them as LLM reasoning

## Context to load first (read these files)
1. `/workspace/shared-memory/mirror/QUALITY_BAR.md`
2. `/workspace/shared-memory/mirror/RULES.md` (esp. zero spend, no invent, §20 reuse)
3. Project: `README.md`, `REVIEW.md`, `STATUS.md`, `PREPARED_NOT_SUBMITTED.md`
4. Code: `protocol/client.py`, `agents/live_bridge.py`, `agents/live_reactive.py`, `policy/`, `demo/`, `tests/`

## Critical protection
`protocol/client.py` `register_agent` MUST keep using **POST /agents** for custom agents.
**FORBIDDEN:** switching to Console-only `register-known`.
Add/strengthen a unit test that fails if registration path regresses to register-known.

## Goal (implement, not just note)
Close genuine quality gaps for Track01 human→agents workflow:

1. **Coherent LIVE path:** human chat (preview LIVE) → live_bridge → Switch room → WS reactive agents → useful read-only ops brief. Harden loop/anti-storm tokens; clear UX copy distinguishing LIVE vs SANDBOX.
2. **Production-quality UX** in `demo/` (Fractured Code / GoalWorld taste): hierarchy, contrast, status chips for LIVE/SANDBOX/bridge health, honest labels, no demoware stubs.
3. **Mattermost-native input IF safely feasible** on loopback Mattermost (`127.0.0.1:18065`) without exposing secrets or breaking stack — otherwise document concrete blocker and keep preview LIVE as primary.
4. **Tests:** robustness/loop + policy regressions; protect POST /agents; keep suite green (expect ~19 tests; LIVE e2e may skip if bridge down).
5. **README honesty:** Console eligibility — official FAQ “What do I need to get started?” lists Switch Console + Docker + AI coding agent (https://www.wemakedevs.org/hackathons/switch). Protocol allows custom agents. **No waiver claimed.** Deterministic agents ≠ LLM.

## Deliverables you must produce in-repo
- Real code/UX/test diffs (not token-only notes)
- `evidence/AGY_ARGON_RUN.md` summarizing: model slug used, account email if known (`theneuralwars@gmail.com` expected), files changed, tests run+result, remaining gaps. Sanitize — no secrets.
- Update `STATUS.md` timestamp + pack note; keep REVIEW pending
- Optionally refresh sanitized evidence under `evidence/` (no raw key material, no `.env`)

## Verification before you finish
```bash
cd /workspace/flip-the-switch/goalworld-ops-switch
source .venv/bin/activate
pytest -q --tb=short
curl -sf http://127.0.0.1:18000/health
curl -sf http://127.0.0.1:18765/api/health
```
Write pytest output to `evidence/pytest.txt` (sanitize).

## Start now
Read context → implement → test → write AGY_ARGON_RUN.md. Prefer depth over breadth. If Mattermost-native is unsafe/blocked, say so and invest in LIVE path + UX + tests instead.
