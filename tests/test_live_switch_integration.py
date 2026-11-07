"""Live Switch integration — skipped automatically if API down."""
from pathlib import Path
import sys
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol.client import SwitchClient, load_env_file

API = "http://127.0.0.1:18000"


def _switch_up() -> bool:
    try:
        r = httpx.get(f"{API}/health", timeout=2.0)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _switch_up(), reason="Switch API not running")


def test_register_create_room_post_and_list():
    env = load_env_file("/workspace/flip-the-switch/switch-upstream/.env")
    token = env.get("AGENT_REGISTRATION_TOKEN")
    assert token
    with SwitchClient(API, registration_token=token) as c:
        # Use isolated agent name so integration test does not rotate live_bridge daemon keys
        a = c.register_agent("gw-ops-scout-itest", "integration scout", overwrite=True)
        assert a.get("id") and a.get("api_key")
        room = c.create_room(
            a["id"], a["api_key"], "gw-itest-room", description="itest", agent_names=["gw-ops-scout-itest"]
        )
        assert room.get("id")
        posted = c.post_message(a["id"], a["api_key"], room["id"], "itest ping")
        assert posted.get("ok") is True or posted.get("event_id")
        rooms = c.op(a["id"], a["api_key"], "list_rooms", {})
        assert rooms is not None
        try:
            c.op(a["id"], a["api_key"], "archive_room", {"room_id": room["id"]})
        except Exception:
            pass
