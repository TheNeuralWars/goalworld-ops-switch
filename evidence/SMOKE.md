# Smoke — GoalWorld Ops Switch

Generated: 2026-11-06 17:08 CET (Europe/Rome box clock)

## Switch health
```
{"status":"ok"}
```
## Gateway
HTTP 200
## Mattermost
HTTP 200
## Containers
```
gw-switch-gateway-1 Up 6 minutes
gw-switch-switch-1 Up 6 minutes
gw-switch-mattermost-1 Up 6 minutes (healthy)
gw-switch-postgres-1 Up 6 minutes (healthy)
```

## Preview
GET / → HTTP 200
API snippet: `{"rows": [{"ts": "2026-11-06T16:08:21.275762+00:00", "role": "gw-ops-scout", "content": "GoalWorld Ops Room online. Switch is central. Read-only probes auto-run; side effects need approval. Demo mode `

## Notes
- Secrets redacted; agent keys only in .secrets/ (gitignored)
- Side effects: dry-run only
- REVIEW: pending (October)
