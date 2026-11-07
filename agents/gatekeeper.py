from __future__ import annotations

import re
from typing import Any

from ops.approvals import ApprovalStore
from policy.engine import PolicyEngine


APPROVE_RE = re.compile(r"\bapprove\s+([a-f0-9]{4,16})\b", re.I)
REJECT_RE = re.compile(r"\breject\s+([a-f0-9]{4,16})\b", re.I)


class Gatekeeper:
    name = "gw-gatekeeper"
    description = "Policy gate: deny/auto/approval cards. Never fires live side effects."

    def __init__(self, policy: PolicyEngine, store: ApprovalStore):
        self.policy = policy
        self.store = store

    def handle(self, text: str, who: str = "human") -> str:
        m = APPROVE_RE.search(text or "")
        if m:
            a = self.store.decide(m.group(1).lower(), "approved", who)
            if not a:
                return f"@{self.name}: no pending approval `{m.group(1)}`."
            return (
                f"@{self.name}: **approved** `{a.approval_id}` ({a.intent}). "
                f"Dry-run receipt only — no live external side effect executed."
            )
        m = REJECT_RE.search(text or "")
        if m:
            a = self.store.decide(m.group(1).lower(), "rejected", who)
            if not a:
                return f"@{self.name}: no pending approval `{m.group(1)}`."
            return f"@{self.name}: **rejected** `{a.approval_id}`."

        decision = self.policy.classify(text)
        if decision.action == "allow_auto":
            return (
                f"@{self.name}: `{decision.intent}` is auto-safe. "
                f"@gw-ops-scout can run it. ({decision.reason})"
            )
        if decision.action == "deny":
            return (
                f"@{self.name}: **DENIED** `{decision.intent}` — {decision.reason}. "
                f"GoalWorld hard limits: no spend / no public submit / no deletes."
            )
        # require_approval
        a = self.store.create(
            intent=decision.intent,
            summary=text.strip()[:240],
            risk="medium" if "deploy" in decision.intent or "submit" in decision.intent else "low",
            proposed_action=f"DRY-RUN only for: {decision.intent}",
        )
        return f"@{self.name}:\n{a.to_card()}"
