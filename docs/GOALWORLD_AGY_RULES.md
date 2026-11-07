# GoalWorld — shared rules for Antigravity (agy) · v2026-11-04b
Source of truth: /workspace/shared-memory/mirror/ (VPS: /data/shared-memory/). Load on demand:
MEMORY_BOOTSTRAP.md → STATE_LIVE.md → PROFILE.md → RULES.md → QUALITY_BAR.md → ROLES.md / CREDITS.md.

## Objectives
GoalWorld = canon (Fractured Code book/universe) + code (GoalChain/webapps) + cinema studio (AI film).
Every artifact must be coherent with canon, honest, and shippable.

## Hard limits (RULES.md)
- Zero spend. No purchases/upgrades/paid plans.
- Nothing goes out without Nico approving that exact message: no emails, posts, DMs, forms, submissions.
- Never delete files, branches, posts, mails — archive/rename with backup.
- Never invent data, figures, quotes, results, partners, users. No source → say "not verified".
- No pre-order / KDP / "available now" / launch claims unless verified live. No fake metrics or testimonials.
- On-chain / treasury / tokens / mainnet: only with Nico approval.
- Preview ≠ prod. Never deploy goalworld.fun prod, touch Caddy, or running services unless the task is approved.
- Public demos/content changes need October/Nico review first (QUALITY_BAR gate).
- Never copy secrets into files, logs or outputs.
- AI video always labelled "Made with AI".
- RULES §20: read QUALITY_BAR.md before marking a deliverable ready. No minimal deliverables.

## QUALITY_BAR (canonical — from VPS /data/shared-memory/QUALITY_BAR.md)

# QUALITY_BAR — GoalWorld / Hermes (desde 2026-11-03)

Nico (via October): **nada de entregas mínimas “solo por entregar”.** Complejidad, ambición, buen gusto. October revisa antes de demos/submits públicos.

## Definición de “listo”
Un deliverable NO está listo si solo “funciona”. Está listo cuando:
1. **Ambición:** resuelve el problema de verdad (edge cases, failure modes, blast-radius/security donde aplique), no un stub demoware.
2. **Complejidad útil:** arquitectura clara, capas separadas, tests que fallarían si se rompe el contrato; no un solo archivo monolítico de 20 líneas fingiendo producto.
3. **Buen gusto:** UI legible/cinemática alineada a Fractured Code / GoalWorld (tipografía, contraste, jerarquía, copy corto EN/ES según audiencia); README/docs que un jurado entiende en 30s.
4. **Evidencia:** `npm test`/equivalente verde + smoke curl + (si UI) screenshot o vídeo; evidencia en `artifacts/.../evidence/`.
5. **Honestidad:** mock vs live explícito; sin inventar métricas/URLs.

## Anti-patrones (rechazo automático en review)
- HTML/CSS de una línea “funciona”
- Agent de <50 LOC sin policy/canon reales
- “Done” sin smoke público o sin checklist de jurado
- Empujar a submit el mismo día del scaffold sin polish
- Pedir OK de Nico por preferencias cosméticas (decidir vos; October revisa bar)

## Gate de review (October ↔ Hermes)
1. Hermes entrega pack + evidencia + `STATUS.md` con `REVIEW: pending`.
2. October revisa (código + UX + docs). Si flojo → `REVIEW: changes_requested` + lista concreta; Hermes itera.
3. Solo con `REVIEW: approved` → demo URL pública / submit form / post.

## Modelos
Contest / jurado / arquitectura: preferir Expert (`/high` o Argon) vía model-picker. Cotidiano: Standard/Quick.


## Review output format
Verdict PASS / PASS-WITH-FIXES / FAIL, then numbered findings with file:line, severity P0–P3, concrete fix.
Review mode: do not edit/commit/push/deploy unless explicitly asked.
Reuse before research: read existing briefs first.
