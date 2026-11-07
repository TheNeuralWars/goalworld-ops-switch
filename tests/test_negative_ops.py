from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.gatekeeper import Gatekeeper
from ops.approvals import ApprovalStore
from policy.engine import PolicyEngine

ROOT = Path(__file__).resolve().parents[1]


def test_reject_unknown_approval(tmp_path):
    store = ApprovalStore(tmp_path / "a.jsonl")
    gate = Gatekeeper(PolicyEngine.from_yaml(ROOT / "policy" / "rules.yaml"), store)
    msg = gate.handle("approve deadbeef")
    assert "no pending" in msg.lower()


def test_cannot_double_approve(tmp_path):
    store = ApprovalStore(tmp_path / "a.jsonl")
    gate = Gatekeeper(PolicyEngine.from_yaml(ROOT / "policy" / "rules.yaml"), store)
    card = gate.handle("draft submission text for the hackathon")
    assert "APPROVAL REQUIRED" in card
    aid = store.pending()[0].approval_id
    assert "approved" in gate.handle(f"approve {aid}").lower()
    again = gate.handle(f"approve {aid}")
    assert "no pending" in again.lower()


def _make_frame(body: str, *, addressed: bool = True, sender: str = "@switch-agent-1:localhost", sender_name: str = "gw-ops-scout", mid: str = "m1", fid: int = 1) -> dict:
    return {
        "event": "message",
        "id": fid,
        "data": {
            "type": "message",
            "payload": {
                "addressed": addressed,
                "sender": sender,
                "sender_name": sender_name,
                "message_id": mid,
                "body": body,
            },
        },
    }


def test_anti_storm_rejects_agent_echoes_and_self_stimuli():
    from agents.live_bridge import extract_human_stimulus, is_agent_echo

    # Valid targeted [human] relay from gw-ops-scout
    stim = extract_human_stimulus(_make_frame("@gw-gatekeeper [human] check site status for goalworld.fun"))
    assert stim == ("check site status for goalworld.fun", "live-bridge")

    # Agent room echoes must NEVER be accepted as human input
    assert is_agent_echo("[LIVE] @gw-gatekeeper: **DENIED** `deploy_production`")
    assert extract_human_stimulus(_make_frame("[LIVE] @gw-gatekeeper: `site_status` is auto-safe.")) is None
    assert extract_human_stimulus(_make_frame("@gw-scribe: brief saved → evidence/last_brief.md")) is None

    # Gatekeeper and Scribe cannot inject [human] stimuli even if addressed
    assert extract_human_stimulus(
        _make_frame("[human] check site status", sender_name="gw-gatekeeper")
    ) is None
    assert extract_human_stimulus(
        _make_frame("[human] check site status", sender_name="gw-scribe")
    ) is None


def test_handoff_tokens_enforce_prefix_and_sender_dag():
    from agents.live_bridge import extract_handoff_token

    # Valid gatekeeper -> scout handoff
    probe = extract_handoff_token(
        _make_frame("@gw-ops-scout [handoff:probe] check site status", sender_name="gw-gatekeeper"),
        "[handoff:probe]",
        allowed_senders=frozenset({"gw-gatekeeper"}),
    )
    assert probe == "check site status"

    # Substring spoofing (token not at prefix) must be rejected
    spoof = extract_handoff_token(
        _make_frame("what does [handoff:probe] check site status mean?", sender_name="gw-gatekeeper"),
        "[handoff:probe]",
        allowed_senders=frozenset({"gw-gatekeeper"}),
    )
    assert spoof is None

    # Unauthorized sender (e.g. gw-scribe trying to trigger gw-ops-scout) must be rejected
    bad_sender = extract_handoff_token(
        _make_frame("[handoff:probe] check site status", sender_name="gw-scribe"),
        "[handoff:probe]",
        allowed_senders=frozenset({"gw-gatekeeper"}),
    )
    assert bad_sender is None


def test_mattermost_human_fallback_accepted_without_addressed_flag():
    from agents.live_bridge import extract_human_stimulus

    # Non-owner Mattermost user post arrives over WS filter=all with addressed=False
    mm_frame = _make_frame(
        "@gw-gatekeeper check site status for goalworld.fun",
        addressed=False,
        sender="@nico:localhost",
        sender_name="nico",
    )
    assert extract_human_stimulus(mm_frame) == ("check site status for goalworld.fun", "mattermost-human")

    # Unaddressed human chatter not mentioning @gw-gatekeeper or [human] is ignored
    chatter = _make_frame(
        "random coffee chat in channel",
        addressed=False,
        sender="@nico:localhost",
        sender_name="nico",
    )
    assert extract_human_stimulus(chatter) is None


def test_storm_guard_rate_limiter_trips():
    from agents.live_bridge import StormGuard

    sg = StormGuard(max_turns=3, window_seconds=10.0)
    assert sg.allow(now=100.0) is True
    assert sg.allow(now=101.0) is True
    assert sg.allow(now=102.0) is True
    assert sg.allow(now=103.0) is False
    assert sg.tripped_count == 1
    # After window expires, turns are allowed again
    assert sg.allow(now=112.0) is True
