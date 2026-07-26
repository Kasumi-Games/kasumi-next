"""A minimal Satori server simulator for sandbox-testing the real bot.

Implements the protocol surface the nonebot-satori adapter actually uses
(verified against nonebot/adapters/satori/adapter.py):

- ``GET /v1/events`` (WebSocket): IDENTIFY (op=3) -> READY (op=4) with one
  online login; PING (op=1) -> PONG (op=2); events pushed as op=0 payloads
  with an incrementing ``sn``.
- ``POST /v1/{api}``: captures every call the bot makes. ``message.create``
  returns a plausible message object; any unimplemented api returns ``{}``
  and is recorded in the gap list so missing surface area is visible, never
  silent.

Control endpoints (not part of Satori; used by the driver):
- ``POST /_sandbox/send``  {user_id, nickname, channel_id, content, guild_id}
- ``GET  /_sandbox/outbox?since=N`` -> captured bot API calls
- ``GET  /_sandbox/gaps`` -> apis the sim did not implement
- ``GET  /_sandbox/status`` -> {connected, ready, events_sent}
"""

import json
import time
import asyncio
from dataclasses import field
from dataclasses import asdict
from dataclasses import dataclass

from aiohttp import WSMsgType
from aiohttp import web

PLATFORM = "sandbox"
SELF_ID = "3889000000"
SELF_NAME = "Kasumi"


@dataclass
class Outbox:
    """Captured bot->server API calls, in order."""

    calls: list = field(default_factory=list)

    def add(self, api: str, body: dict) -> None:
        self.calls.append(
            {"seq": len(self.calls), "api": api, "body": body, "at": time.time()}
        )


class SatoriSim:
    def __init__(self) -> None:
        self.outbox = Outbox()
        self.gaps: list[str] = []
        self.ws: web.WebSocketResponse | None = None
        self.ready = asyncio.Event()
        self.sn = 0
        self.message_id = 1000

    # ------------------------------------------------------------------
    # Protocol pieces
    # ------------------------------------------------------------------

    def login_payload(self) -> dict:
        return {
            "sn": 0,
            "status": 1,
            "adapter": "sandbox-sim",
            "platform": PLATFORM,
            "user": {"id": SELF_ID, "name": SELF_NAME, "is_bot": True},
            "features": [],
        }

    async def events_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=None)
        await ws.prepare(request)
        self.ws = ws

        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            payload = json.loads(msg.data)
            op = payload.get("op")
            if op == 3:  # IDENTIFY
                await ws.send_json(
                    {
                        "op": 4,  # READY
                        "body": {
                            "logins": [self.login_payload()],
                            "proxy_urls": [],
                        },
                    }
                )
                self.ready.set()
            elif op == 1:  # PING
                await ws.send_json({"op": 2, "body": {}})
        self.ws = None
        self.ready.clear()
        return ws

    async def push_message_event(
        self,
        *,
        user_id: str,
        nickname: str,
        content: str,
        channel_id: str,
        guild_id: str | None,
    ) -> int:
        if self.ws is None:
            raise RuntimeError("bot is not connected")
        self.sn += 1
        self.message_id += 1
        channel_type = 0 if guild_id else 1  # TEXT vs DIRECT
        event = {
            "sn": self.sn,
            "type": "message-created",
            "timestamp": int(time.time() * 1000),
            "login": self.login_payload(),
            "channel": {"id": channel_id, "type": channel_type, "name": "沙盒频道"},
            "user": {"id": user_id, "name": nickname, "is_bot": False},
            "message": {
                "id": f"sandbox-msg-{self.message_id}",
                "content": content,
            },
        }
        if guild_id:
            event["guild"] = {"id": guild_id, "name": "沙盒群"}
            event["member"] = {"nick": nickname}
        await self.ws.send_json({"op": 0, "body": event})
        return self.sn

    # ------------------------------------------------------------------
    # HTTP API the bot calls
    # ------------------------------------------------------------------

    async def api(self, request: web.Request) -> web.Response:
        api_name = request.match_info["api"]
        try:
            body = await request.json()
        except Exception:
            body = {}
        self.outbox.add(api_name, body)

        if api_name == "message.create":
            self.message_id += 1
            return web.json_response(
                [
                    {
                        "id": f"bot-msg-{self.message_id}",
                        "content": body.get("content", ""),
                    }
                ]
            )
        if api_name not in self.gaps:
            self.gaps.append(api_name)
        return web.json_response({})

    # ------------------------------------------------------------------
    # Control endpoints for the driver
    # ------------------------------------------------------------------

    async def control_send(self, request: web.Request) -> web.Response:
        body = await request.json()
        try:
            sn = await self.push_message_event(
                user_id=str(body["user_id"]),
                nickname=body.get("nickname", f"玩家{body['user_id']}"),
                content=body["content"],
                channel_id=str(body.get("channel_id", "sandbox-channel")),
                guild_id=body.get("guild_id", "sandbox-guild"),
            )
        except RuntimeError as error:
            return web.json_response({"error": str(error)}, status=503)
        return web.json_response({"sn": sn})

    async def control_outbox(self, request: web.Request) -> web.Response:
        since = int(request.query.get("since", 0))
        return web.json_response(
            {"calls": [c for c in self.outbox.calls if c["seq"] >= since]}
        )

    async def control_gaps(self, request: web.Request) -> web.Response:
        return web.json_response({"gaps": self.gaps})

    async def control_status(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "connected": self.ws is not None,
                "ready": self.ready.is_set(),
                "events_sent": self.sn,
                "calls": len(self.outbox.calls),
            }
        )


def build_app(sim: SatoriSim) -> web.Application:
    app = web.Application(client_max_size=64 * 1024 * 1024)
    app.router.add_get("/v1/events", sim.events_ws)
    app.router.add_post("/v1/{api}", sim.api)
    app.router.add_post("/_sandbox/send", sim.control_send)
    app.router.add_get("/_sandbox/outbox", sim.control_outbox)
    app.router.add_get("/_sandbox/gaps", sim.control_gaps)
    app.router.add_get("/_sandbox/status", sim.control_status)
    return app


def main(port: int = 5140) -> None:
    sim = SatoriSim()
    web.run_app(build_app(sim), host="127.0.0.1", port=port, print=None)


if __name__ == "__main__":
    import sys

    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5140)
