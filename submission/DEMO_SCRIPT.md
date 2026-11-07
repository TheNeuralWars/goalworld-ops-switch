# Demo script (≈90s)

1. Show `curl http://127.0.0.1:18000/health` → ok  
2. Open Mattermost/Gateway briefly (optional)  
3. Run `python -m agents.runner --mode live` — agents register, room posts  
4. Open http://127.0.0.1:18765/ — transcript with scout site check  
5. Show approval card for draft submission → `approve <id>` → dry-run receipt  
6. Show DENY for "deploy production" / "final submit"  
7. Close: Switch is the room; policy is the blast radius control
