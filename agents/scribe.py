from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class Scribe:
    name = "gw-scribe"
    description = "Writes ops briefs and receipts to evidence/ and room."

    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.transcript = self.evidence_dir / "transcript.jsonl"

    def log(self, role: str, content: str, **meta) -> dict:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
            **meta,
        }
        with self.transcript.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def brief(self, title: str, body: str, *, lane: str = "live", room_id: str | None = None) -> str:
        path = self.evidence_dir / "last_brief.md"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        room_line = f"- **Switch Room:** `{room_id}`\n" if room_id else ""
        text = (
            f"# {title}\n\n"
            f"- **Timestamp:** `{ts}`\n"
            f"- **Lane:** `{lane}`\n"
            f"{room_line}"
            f"- **Engine:** Deterministic policy + read-only probes (no LLM, zero external side effects)\n\n"
            f"## Summary\n\n"
            f"{body.strip()}\n"
        )
        path.write_text(text)
        self.log(self.name, text, kind="brief", lane=lane, **({"room_id": room_id} if room_id else {}))
        return f"@{self.name}: brief saved → evidence/last_brief.md\n{body[:800]}"
