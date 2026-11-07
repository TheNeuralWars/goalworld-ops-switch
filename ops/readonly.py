from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


ROME_LABEL = "Europe/Rome"


class ReadonlyOps:
    """Safe, read-only probes for GoalWorld ops. Never mutates external systems."""

    def __init__(self, project_root: Path | None = None):
        self.root = project_root or Path(__file__).resolve().parents[1]

    def _http_get(self, url: str, timeout: float = 8.0) -> dict[str, Any]:
        try:
            req = Request(url, headers={"User-Agent": "goalworld-ops-switch/0.1"})
            with urlopen(req, timeout=timeout) as r:
                body = r.read(500)
                return {
                    "url": url,
                    "status": getattr(r, "status", None) or r.getcode(),
                    "ok": True,
                    "snippet": body[:120].decode("utf-8", errors="replace"),
                }
        except HTTPError as e:
            return {"url": url, "status": e.code, "ok": False, "error": str(e)}
        except Exception as e:
            return {"url": url, "status": None, "ok": False, "error": str(e)}

    def site_status(self) -> dict[str, Any]:
        urls = [
            "https://goalworld.fun/",
            "https://goalworld.fun/book.html",
            "https://goalworld.fun/cinema.html",
        ]
        return {"checked_at": datetime.now(timezone.utc).isoformat(), "results": [self._http_get(u) for u in urls]}

    def switch_health(self, api: str = "http://127.0.0.1:18000") -> dict[str, Any]:
        return self._http_get(f"{api.rstrip('/')}/health")

    def stack_status(self) -> dict[str, Any]:
        env = os.environ.copy()
        env.setdefault("DOCKER_HOST", "tcp://127.0.0.1:2375")
        env["PATH"] = f"/home/box/.local/bin:{env.get('PATH','')}"
        try:
            out = subprocess.check_output(
                ["docker", "ps", "--filter", "name=gw-switch", "--format", "{{.Names}}\t{{.Status}}"],
                env=env,
                text=True,
                timeout=15,
            )
            lines = [ln for ln in out.splitlines() if ln.strip()]
            return {"ok": True, "containers": lines}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def disk(self) -> dict[str, Any]:
        usage = shutil.disk_usage("/")
        return {
            "total_gb": round(usage.total / 1e9, 1),
            "used_gb": round(usage.used / 1e9, 1),
            "free_gb": round(usage.free / 1e9, 1),
        }

    def project_status(self) -> dict[str, Any]:
        status = self.root / "STATUS.md"
        return {
            "exists": status.exists(),
            "preview": status.read_text()[:500] if status.exists() else None,
        }

    def contest_deadline(self) -> dict[str, Any]:
        return {
            "event": "Flip the Switch",
            "deadline_ist": "2026-11-07 23:59 IST",
            "deadline_rome": "2026-11-07 19:29 Europe/Rome",
            "track": "01 Best Business Workflow",
            "official": "https://www.wemakedevs.org/hackathons/switch",
            "note": "Track03 hackathon issues were all assigned as of prep; focus Track01.",
        }

    def run_intent(self, intent: str) -> dict[str, Any]:
        mapping = {
            "health_check": lambda: {"switch": self.switch_health(), "site": self.site_status()},
            "site_status": self.site_status,
            "stack_status": self.stack_status,
            "list_approvals": lambda: {"hint": "ask gatekeeper for open approvals"},
            "read_status": self.project_status,
            "summarize_canon": lambda: {
                "canon": "GoalWorld = Fractured Code book/universe + GoalChain code + cinema studio",
                "live_site": "https://goalworld.fun/",
            },
            "contest_deadline_info": self.contest_deadline,
        }
        fn = mapping.get(intent)
        if not fn:
            return {"error": f"no readonly handler for {intent}"}
        return fn() if callable(fn) else fn
