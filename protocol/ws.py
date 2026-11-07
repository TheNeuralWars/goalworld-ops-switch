"""Switch agent WebSocket session — ping/pong + event delivery.

Source: https://docs.switchagents.ai/switch-rooms/internals/agent-connection.md
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable, Optional

import websockets
from websockets.asyncio.client import connect as ws_connect


OnMessage = Callable[[dict[str, Any]], Awaitable[None] | None]


class AgentWSSession:
    def __init__(
        self,
        base_url: str,
        agent_id: str,
        api_key: str,
        *,
        room_id: str | None = None,
        scope: str = "single",
        filter_: str = "all",
        client_name: str = "goalworld-ops",
        client_version: str = "0.2.0",
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.api_key = api_key
        self.room_id = room_id
        self.scope = scope
        self.filter_ = filter_
        self.client_name = client_name
        self.client_version = client_version
        self.connection_id = str(uuid.uuid4())
        self.cursor = 0
        self.generation: int | None = None
        self._ws = None
        self.ready = asyncio.Event()

    def _ws_url(self) -> str:
        base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        q = [
            f"connection_id={self.connection_id}",
            f"scope={self.scope}",
            f"filter={self.filter_}",
            f"client={self.client_name}",
            f"client_version={self.client_version}",
        ]
        if self.room_id:
            q.append(f"rooms={self.room_id}")
        return f"{base}/agents/{self.agent_id}/connection/ws?" + "&".join(q)

    async def run(
        self,
        on_message: OnMessage,
        *,
        stop_event: asyncio.Event,
        max_seconds: float | None = 90.0,
    ) -> dict[str, Any]:
        """Run until stop_event or max_seconds. Returns session stats."""
        stats = {"pings": 0, "messages": 0, "addressed": 0, "evicted": False, "error": None}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        deadline = asyncio.get_event_loop().time() + max_seconds if max_seconds else None
        try:
            async with ws_connect(self._ws_url(), additional_headers=headers, ping_interval=None) as ws:
                self._ws = ws
                self.ready.set()
                while not stop_event.is_set() and not stats["evicted"]:
                    if deadline and asyncio.get_event_loop().time() > deadline:
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    frame = json.loads(raw)
                    await self._handle_frame(ws, frame, on_message, stats)
        except Exception as e:
            stats["error"] = f"{type(e).__name__}: {e}"
        finally:
            self.ready.clear()
            self._ws = None
        return stats

    async def _handle_frame(self, ws, frame: dict[str, Any], on_message: OnMessage, stats: dict) -> None:
        data = frame.get("data", frame)
        ftype = data.get("type") or frame.get("type") or frame.get("event")

        if ftype == "ping" or frame.get("event") == "ping" or (
            isinstance(frame, dict) and frame.get("type") == "ping" and "data" not in frame
        ):
            await ws.send(json.dumps({"type": "pong", "cursor": self.cursor}))
            stats["pings"] += 1
            return

        if ftype == "connection_state":
            self.generation = data.get("generation")
            if data.get("cursor") is not None:
                self.cursor = int(data["cursor"])
            return

        if ftype == "evicted":
            stats["evicted"] = True
            return

        # Domain envelope: {event, data, id}
        if "id" in frame and "data" in frame:
            try:
                self.cursor = max(self.cursor, int(frame["id"]))
            except (TypeError, ValueError):
                pass
            inner = frame["data"]
            if inner.get("type") == "message" or frame.get("event") == "message":
                stats["messages"] += 1
                payload = inner.get("payload") or {}
                if payload.get("addressed"):
                    stats["addressed"] += 1
                maybe = on_message(frame)
                if asyncio.iscoroutine(maybe):
                    await maybe
