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
