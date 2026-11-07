# Flip the Switch — submission draft (DO NOT SUBMIT until October REVIEW: approved)

**Project name:** GoalWorld Ops Room  
**Track:** 01 — Best Business Workflow  
**Team:** TheNeuralWars / theneuralwars (solo or up to 4)  
**Deadline:** 2026-11-07 23:59 IST ≈ **19:29 Europe/Rome**

## One-liner
A Switch-native GoalWorld operations room where scout, gatekeeper, and scribe agents run real business ops with hard approval gates — Mattermost-backed, self-hosted, zero spend.

## What we built
- Self-hosted Switch 0.31.0 (Docker) + bundled Mattermost
- Three custom Python agents speaking the **real** Switch agent protocol (HTTP + WebSocket)
- Policy engine: allow-auto / require-approval / deny aligned to GoalWorld RULES
- Local cinematic preview of the room transcript
- Reproducible scripts: up, register, demo, smoke

## Why Switch is central
Without Switch there is no shared room identity, agent addressing, or chat bridge. The workflow cannot run on agents alone.

## Repo / demo (fill at submit time)
- Repo: _(create public fork/repo after October approve — currently local `/workspace/flip-the-switch/goalworld-ops-switch`)_
- Demo video: _(record after REVIEW: approved)_
- Preview (local): http://127.0.0.1:18765/
- Switch API (local): http://127.0.0.1:18000/health

## Honesty
Live Switch integration verified. External side effects remain **dry-run** behind approval gates. No contest submit performed in prep.

## Links
- https://www.wemakedevs.org/hackathons/switch
- https://docs.switchagents.ai/
- https://github.com/sandbox-quantum/switch
- https://goalworld.fun/

## LIVE human workflow (prep)
Humans type in the local preview LIVE panel. Text is injected into a self-hosted Switch room via the official agent protocol (`send_targeted_message`). Deterministic agents on WebSocket perform policy, read-only probes, and briefs. Sandbox approve/deny is a separate dry-run lane.

## Switch Console note
Hackathon materials list Switch Console as part of getting started. This prep uses documented self-host + custom protocol agents. We do **not** claim Console is optional for eligibility without organizer confirmation.
