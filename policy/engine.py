from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Decision:
    intent: str
    action: str  # allow_auto | require_approval | deny
    reason: str
    matched_keyword: str | None = None


class PolicyEngine:
    def __init__(self, rules: dict[str, Any]):
        self.rules = rules
        self.keywords: dict[str, list[str]] = rules.get("keywords") or {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PolicyEngine":
        data = yaml.safe_load(Path(path).read_text())
        return cls(data)

    def classify(self, text: str) -> Decision:
        lowered = (text or "").strip().lower()
        if not lowered:
            return Decision("unknown", "deny", "empty input")

        # Explicit deny phrases first
        for item in self.rules.get("deny") or []:
            intent = item["intent"]
            for kw in self.keywords.get(intent, [intent.replace("_", " ")]):
                if kw.lower() in lowered:
                    return Decision(intent, "deny", f"denied by policy keyword '{kw}'", kw)

        for item in self.rules.get("require_approval") or []:
            intent = item["intent"]
            for kw in self.keywords.get(intent, []):
                if kw.lower() in lowered:
                    return Decision(
                        intent, "require_approval", f"needs human approval ('{kw}')", kw
                    )

        for item in self.rules.get("allow_auto") or []:
            intent = item["intent"]
            for kw in self.keywords.get(intent, []):
                if kw.lower() in lowered:
                    return Decision(intent, "allow_auto", f"safe auto ('{kw}')", kw)

        default = self.rules.get("default", "deny")
        return Decision("unknown", default, "no keyword match; default policy")
