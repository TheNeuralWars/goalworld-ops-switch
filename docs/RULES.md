# RULES — reglas permanentes (Grok Bot · Antigravity · Hermes)

Vigentes desde 2026-10-17 (Europe/Rome). Valen para TODOS los perfiles de Hermes, para cualquier ejecución de agy y para Grok Bot. Si una regla choca con un SOUL, gana la más restrictiva.

1. **Cero gasto.** La tarjeta solo sirve para verificar identidad. Nada de compras, upgrades, planes de pago ni "pequeños unlocks" sin OK explícito de Nico.
2. **Nada sale sin aprobación.** Ningún email, post, DM, reply, formulario ni envío a concursos sin que Nico apruebe ese mensaje concreto (destinatario + texto). Excepción ya aprobada: las rutinas de X de @nicopez que corren como rutinas de Grok Bot (08:30, 15:30, 21:00; replies espaciados 45–60 s, por debajo de umbrales de spam). Que Hermes las asuma necesita un OK explícito de Nico.
3. **Nada se borra.** Ni archivos, ni ramas, ni posts, ni correos. Se archiva o se renombra con backup.
4. **Nada se inventa.** Ni datos, ni cifras, ni citas, ni resultados. Si no hay fuente, se dice "no verificado".
5. **On-chain / tesorería / tokens / mainnet** (MiCA/CONSOB/ADM): siempre con aprobación de Nico.
6. **Modelo de Hermes (Nico 2026-10-25):** default **siempre MiMo v2.6 Pro** (`xiaomi/mimo-v2.6-pro`, provider `nous`) para cotidiano y rutinas. **Kimi K3.1 Pro** solo si MiMo no puede resolver o la tarea es verdaderamente desafiante (dev difícil, debugging profundo, auditorías, planificación, agentes autónomos largos). No cambiar el default de Hermes a Kimi; Grok Bot elige el modelo **por encargo** (`modelo:` en inbox/BRIEF) al mandar trabajo al VPS. Métrica: coste por tarea terminada, no solo $/token. **Advanced Delegation (2026-10-27):** `model_map` con rutas `free` / `work`(MiMo default) / `hard`(Kimi); SOUL AUTO-ORCHESTRATE parte tareas complejas en subagentes solo.
7. **Razonamiento de libro y estrategia:** con **Argon vía agy** (`gemini-4-argon-high`; fallback solo `gemini-4-argon-medium`, nunca Flash/Claude para prosa del libro). Ver `antigravity/README.md`.
8. **Vídeo IA en X siempre etiquetado** ("Hecho con IA" / Made with AI activado).
9. **Deploys de producción:** salen automáticamente después de QA, siempre con rollback listo (`scripts/deploy_goalworld_site.sh --dry-run` / `rollback`). El cambio de contenido de la web saneada (strategy/web) sigue pendiente de OK de Nico (ítem 3 del §6).
10. **No despertar a Nico entre 23:00 y 08:00 (Europe/Rome).** Lo urgente se deja en STATE.md / TIMELINE.md y se le avisa a las 08:00.
11. **Respuestas a Nico:** en español, cortas.
12. **Nunca copiar secretos** (API keys, tokens OAuth, contraseñas, cookies, `.env`, `auth.json`, `creds/`) en este directorio ni en el TIMELINE. `bin/tl` rechaza entradas que parecen secretos.
13. **Datos personales:** `artifacts/ai-credits/profile.md` contiene datos personales de Nico (codice fiscale, dirección, teléfono). Solo para rellenar solicitudes aprobadas; nunca publicarlo ni copiarlo a repos (el repo de Hermes es público).
14. **Memoria compartida:** toda acción relevante deja una línea en `TIMELINE.md` con `bin/tl` (append-only; nunca editar líneas antiguas). El estado vivo va en `STATE.md`.
15. No escribir en los plugins de memoria de Hermes (Hindsight, LCM, Graphiti, Omega) sin un plan acordado con Nico (regla previa del bridge, se mantiene).
16. No tocar Caddy, deploys ni servicios en marcha salvo como parte de una tarea aprobada.
17. **Sync (2026-10-25).** Antes de editar docs core (STATE/CREDITS/RULES/HANDOFF/ROLES/ACCESS) desde el lado que puede estar desfasado (el box), hacer `tl.sh pull-safe` o `sync-now.sh`; después `tl.sh push` (+sm-commit). CREDITS y STATE se actualizan en el VPS como original. Ambos lados registran en TIMELINE (`bin/tl` / `tl.sh`).
18. **Roles y acceso.** Los roles están en `ROLES.md`. Hermes accede al box solo por los métodos y rutas de `ACCESS.md` (túnel `bin/box-ssh`); nunca lee ni copia vault, claves privadas ni `.env` del box.
19. **Memoria de persona y sesión:** hechos duraderos de Nico en `PROFILE.md`; protocolo en `MEMORY_PROTOCOL.md`; resúmenes de día en `sessions/`. No duplicar eso en plugins de memoria de Hermes.
20. **Reutilizar antes de investigar (2026-10-25).** Antes de research/navegador/subagente caro: seguir `REUSE.md` (reutilizar / refrescar / investigar; máx. 2 reintentos con checkpoint; nunca reiniciar encargos completados; un owner por tarea; cargar solo secciones relevantes). Encargos con `templates/BRIEF.md`, relevo en `HANDOFF.md`.
