from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Approval:
    approval_id: str
    intent: str
    summary: str
    risk: str
    proposed_action: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    decided_at: float | None = None
    decided_by: str | None = None

    def to_card(self) -> str:
        return (
            f"**APPROVAL REQUIRED** `{self.approval_id}`\n"
            f"- intent: `{self.intent}`\n"
            f"- risk: {self.risk}\n"
            f"- summary: {self.summary}\n"
            f"- proposed (dry-run only): {self.proposed_action}\n"
            f"Reply: `approve {self.approval_id}` or `reject {self.approval_id}`"
        )


class ApprovalStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, Approval] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            a = Approval(**data)
            self._items[a.approval_id] = a

    def _append(self, approval: Approval) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(approval)) + "\n")

    def create(self, intent: str, summary: str, risk: str, proposed_action: str) -> Approval:
        aid = secrets.token_hex(3)
        a = Approval(
            approval_id=aid,
            intent=intent,
            summary=summary,
            risk=risk,
            proposed_action=proposed_action,
        )
        self._items[aid] = a
        self._append(a)
        return a

    def decide(self, approval_id: str, status: str, who: str = "human") -> Approval | None:
        a = self._items.get(approval_id)
        if not a or a.status != "pending":
            return None
        a.status = status
        a.decided_at = time.time()
        a.decided_by = who
        self._append(a)
        return a

    def pending(self) -> list[Approval]:
        return [a for a in self._items.values() if a.status == "pending"]

    def get(self, approval_id: str) -> Approval | None:
        return self._items.get(approval_id)
