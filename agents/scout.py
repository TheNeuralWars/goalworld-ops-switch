from __future__ import annotations

import json
from typing import Any

from ops.readonly import ReadonlyOps
from policy.engine import PolicyEngine


class OpsScout:
    name = "gw-ops-scout"
    description = "Read-only GoalWorld ops scout: site, stack, deadlines, status."

    def __init__(self, policy: PolicyEngine, readonly: ReadonlyOps):
        self.policy = policy
        self.readonly = readonly

    @staticmethod
    def summarize_result(intent: str, result: dict[str, Any]) -> str:
        if not isinstance(result, dict):
            return f"{intent}: completed"
        if intent == "site_status":
            rows = result.get("results") or []
            ok_cnt = sum(1 for r in rows if r.get("ok") and r.get("status") == 200)
            details = ", ".join(
                f"{str(r.get('url', '')).replace('https://', '')}={r.get('status') or 'ERR'}"
                for r in rows
            )
            return f"Site probe: {ok_cnt}/{len(rows)} HTTP 200 OK ({details})"
        if intent == "health_check":
            sw = result.get("switch") or {}
            site_rows = (result.get("site") or {}).get("results") or []
            ok_cnt = sum(1 for r in site_rows if r.get("ok") and r.get("status") == 200)
            return f"Health check: Switch API status={sw.get('status')} · Site {ok_cnt}/{len(site_rows)} HTTP 200"
        if intent == "stack_status":
            containers = result.get("containers") or []
            return f"Docker stack: ok={result.get('ok')} · {len(containers)} gw-switch container(s) active"
        if intent == "contest_deadline_info":
            return (
                f"{result.get('event', 'Flip the Switch')} ({result.get('track', 'Track 01')}) — "
                f"closes {result.get('deadline_ist')} ({result.get('deadline_rome')})"
            )
        if intent == "read_status":
            prev = (result.get("preview") or "").splitlines()
            gate_line = next((ln.strip() for ln in prev if "REVIEW:" in ln), "exists=" + str(result.get("exists")))
            return f"STATUS.md read-only check: {gate_line}"
        if intent == "summarize_canon":
            return f"{result.get('canon', '')} ({result.get('live_site', '')})"
        if intent == "list_approvals":
            return str(result.get("hint") or "Check gatekeeper for pending approvals")
        return f"{intent}: read-only probe complete"

    def probe_with_summary(self, text: str) -> tuple[str, str, str]:
        decision = self.policy.classify(text)
        if decision.action != "allow_auto":
            msg = (
                f"@{self.name}: that looks like `{decision.intent}` → `{decision.action}` "
                f"({decision.reason}). Handing to @gw-gatekeeper."
            )
            return decision.intent, f"Handed `{decision.intent}` to gatekeeper ({decision.action})", msg
        result = self.readonly.run_intent(decision.intent)
        summary = self.summarize_result(decision.intent, result)
        pretty = json.dumps(result, indent=2)[:3500]
        reply = f"@{self.name} **{decision.intent}** (auto, read-only) — {summary}\n```json\n{pretty}\n```"
        return decision.intent, summary, reply

    def handle(self, text: str) -> str:
        _, _, reply = self.probe_with_summary(text)
        return reply
