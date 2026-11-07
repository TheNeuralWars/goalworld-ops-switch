"""Real Switch Rooms agent bridge client (HTTP + WebSocket).

Uses POST /agents (custom agents), not register-known (Console-only types).
Docs: https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx


class SwitchError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def load_env_file(path: str | Path) -> dict[str, str]:
    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def redact(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "***"
    return f"{value[:keep]}…{value[-keep:]}"


class SwitchClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:18000",
        *,
        registration_token: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.registration_token = registration_token
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "SwitchClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        r = self._http.get("/health")
        r.raise_for_status()
        return r.json()

    REGISTER_ENDPOINT = "/agents"

    def register_agent(
        self,
        name: str,
        description: str,
        *,
        connector_type: str = "goalworld-python",
        connection_model: str = "always_on",
        overwrite: bool = True,
        addressing: str = "",
    ) -> dict[str, Any]:
        """Register a custom protocol agent via POST /agents.

        CRITICAL: Must always use POST /agents for custom agents.
        Never use Console-only register-known.
        """
        if not self.registration_token:
            raise SwitchError("registration_token required")
        body = {
            "name": name,
            "description": description,
            "connector_type": connector_type,
            "overwrite": overwrite,
            "integration_profile": {
                "connection_model": connection_model,
                "message_exchange": True,
                "pre_invocation_mediation": [],
                "post_invocation_mediation": [],
                "event_reporting": [],
            },
        }
        r = self._http.post(
            self.REGISTER_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.registration_token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if r.status_code >= 400:
            raise SwitchError(
                f"register failed: {r.status_code}", status=r.status_code, body=r.text
            )
        data = r.json()
        if addressing:
            try:
                self.op(
                    data["id"],
                    data["api_key"],
                    "update_agent_detail",
                    {"agent_id": data["id"], "addressing": addressing},
                )
            except SwitchError as e:
                data["_addressing_update"] = {"ok": False, "status": e.status}
        return data

    def _auth_headers(self, api_key: str, connection_id: str | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if connection_id:
            h["X-Switch-Connection-Id"] = connection_id
        return h

    def list_ops(self, agent_id: str, api_key: str) -> dict[str, Any]:
        r = self._http.get(f"/agents/{agent_id}/ops", headers=self._auth_headers(api_key))
        if r.status_code >= 400:
            raise SwitchError(f"list_ops {r.status_code}", status=r.status_code, body=r.text)
        return r.json()

    def op(
        self,
        agent_id: str,
        api_key: str,
        operation: str,
        arguments: dict[str, Any] | None = None,
        *,
        connection_id: str | None = None,
    ) -> Any:
        r = self._http.post(
            f"/agents/{agent_id}/ops/{operation}",
            headers=self._auth_headers(api_key, connection_id),
            json=arguments or {},
        )
        if r.status_code >= 400:
            raise SwitchError(
                f"op {operation} failed: {r.status_code}",
                status=r.status_code,
                body=r.text,
            )
        data = r.json()
        return data.get("result", data)

    def post_message(
        self,
        agent_id: str,
        api_key: str,
        room_id: str,
        content: str,
        *,
        connection_id: str | None = None,
    ) -> Any:
        """Post via HTTP shortcut (works without an open WS connection)."""
        r = self._http.post(
            f"/agents/{agent_id}/message",
            headers=self._auth_headers(api_key, connection_id),
            json={"room_id": room_id, "content": content},
        )
        if r.status_code >= 400:
            raise SwitchError(
                f"post_message {r.status_code}", status=r.status_code, body=r.text
            )
        return r.json()

    def create_room(
        self,
        agent_id: str,
        api_key: str,
        name: str,
        *,
        description: str = "",
        agent_names: list[str] | None = None,
    ) -> Any:
        args: dict[str, Any] = {
            "name": name,
            "description": description or f"GoalWorld room {name}",
        }
        if agent_names:
            args["agent_names"] = agent_names
        return self.op(agent_id, api_key, "create_room", args)
