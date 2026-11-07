from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from policy.engine import PolicyEngine

RULES = Path(__file__).resolve().parents[1] / "policy" / "rules.yaml"


def test_allow_site_status():
    e = PolicyEngine.from_yaml(RULES)
    d = e.classify("please check site status for goalworld.fun")
    assert d.action == "allow_auto"
    assert d.intent == "site_status"


def test_require_approval_draft():
    e = PolicyEngine.from_yaml(RULES)
    d = e.classify("draft submission text for the hackathon")
    assert d.action == "require_approval"
    assert d.intent == "draft_submission"


def test_deny_submit():
    e = PolicyEngine.from_yaml(RULES)
    d = e.classify("submit to hackathon final submit")
    assert d.action == "deny"
    assert d.intent == "contest_submit"


def test_deny_deploy_prod():
    e = PolicyEngine.from_yaml(RULES)
    d = e.classify("deploy production to caddy now")
    assert d.action == "deny"


def test_denial_text_does_not_retrigger_delete():
    """Regression: agent denial prose must not match delete_anything."""
    e = PolicyEngine.from_yaml(RULES)
    d = e.classify("@gw-gatekeeper: **DENIED** `unknown` — no keyword match; default policy.")
    assert d.intent != "delete_anything"


def test_default_deny_unknown():
    e = PolicyEngine.from_yaml(RULES)
    d = e.classify("paint the office purple")
    assert d.action == "deny"


def test_deny_overrides_allow_auto_and_require_approval():
    """Regression: deny-first ordering must win even when allow_auto or approval keywords co-occur."""
    e = PolicyEngine.from_yaml(RULES)
    d1 = e.classify("check site status for goalworld.fun and deploy production now")
    assert d1.action == "deny"
    assert d1.intent == "deploy_production"

    d2 = e.classify("draft submission text and submit to hackathon final submit")
    assert d2.action == "deny"
    assert d2.intent == "contest_submit"

    d3 = e.classify("check site status for goalworld.fun and draft submission text")
    assert d3.action == "require_approval"
    assert d3.intent == "draft_submission"


def test_scribe_and_scout_outputs_do_not_trigger_destructive_intents(tmp_path):
    from agents.scribe import Scribe
    from agents.scout import OpsScout

    e = PolicyEngine.from_yaml(RULES)
    scribe = Scribe(tmp_path)
    brief_out = scribe.brief(
        "GoalWorld LIVE Ops Brief",
        "Read-only probe `site_status` → Site probe: 3/3 HTTP 200 OK",
        lane="live",
        room_id="room-123",
    )
    d = e.classify(brief_out)
    assert d.intent not in ("delete_anything", "spend_money", "deploy_production", "contest_submit")
    summary = OpsScout.summarize_result(
        "site_status",
        {"results": [{"url": "https://goalworld.fun/", "status": 200, "ok": True}]},
    )
    assert "1/1 HTTP 200 OK" in summary
