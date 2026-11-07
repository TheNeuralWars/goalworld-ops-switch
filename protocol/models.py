from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentCreds:
    id: str
    api_key: str
    name: str = ""


@dataclass
class MessageEvent:
    room_id: str
    sequence: int
    addressed: bool
    content: str
    sender: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    approval_id: str
    intent: str
    summary: str
    risk: str
    proposed_action: str
    status: str = "pending"
