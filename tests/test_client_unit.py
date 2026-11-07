import json
from pathlib import Path
import sys
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import protocol.client as client_mod
from protocol.client import redact, load_env_file, SwitchClient, SwitchError


def test_redact():
    assert "…" in redact("abcdefghijklmnop")
    assert redact("ab") == "***"


def test_load_env_ignores_comments(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# x\nFOO=bar\n")
    assert load_env_file(p)["FOO"] == "bar"


def test_register_agent_uses_post_agents_and_forbids_register_known():
    """Critical protection: custom agents MUST register via POST /agents, never register-known."""
    assert SwitchClient.REGISTER_ENDPOINT == "/agents"
    src = Path(client_mod.__file__).read_text()
    code_lines = [
        ln.strip()
        for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    for ln in code_lines:
        assert "/register-known" not in ln and "register_known" not in ln

    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.path == "/agents":
            return httpx.Response(200, json={"id": "agent-123", "api_key": "key-xyz"})
        if request.url.path.endswith("/ops/update_agent_detail"):
            return httpx.Response(403, text="Forbidden for bootstrap owner")
        return httpx.Response(404)

    c = SwitchClient("http://127.0.0.1:18000", registration_token="test-registration-token")
    c._http = httpx.Client(base_url="http://127.0.0.1:18000", transport=httpx.MockTransport(handler))
    try:
        res = c.register_agent("gw-ops-scout", "scout desc", addressing="anyone")
        assert res["id"] == "agent-123"
        assert res["_addressing_update"] == {"ok": False, "status": 403}
        assert len(recorded) == 2
        reg_req = recorded[0]
        assert reg_req.method == "POST"
        assert reg_req.url.path == "/agents"
        assert "register-known" not in str(reg_req.url)
        assert reg_req.headers.get("Authorization") == "Bearer test-registration-token"
        payload = json.loads(reg_req.content.decode())
        assert payload["name"] == "gw-ops-scout"
        assert payload["connector_type"] == "goalworld-python"
        assert payload["integration_profile"]["message_exchange"] is True
    finally:
        c.close()


def test_create_room_always_sends_non_empty_description():
    recorded: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"result": {"id": "room-1"}})

    c = SwitchClient("http://127.0.0.1:18000", registration_token="test-registration-token")
    c._http = httpx.Client(base_url="http://127.0.0.1:18000", transport=httpx.MockTransport(handler))
    try:
        out = c.create_room("agent-1", "key-1", "gw-test-room")
        assert out["id"] == "room-1"
        assert recorded[0]["description"] == "GoalWorld room gw-test-room"
    finally:
        c.close()


def test_health_live():
    c = SwitchClient("http://127.0.0.1:18000")
    try:
        h = c.health()
        assert h.get("status") == "ok"
    finally:
        c.close()
