#!/usr/bin/env python3
"""Keep one approved Chrome channel and expose only responsive page targets.

Playwright eagerly initializes every existing tab during CDP attach. Chrome's
discarded tabs do not answer page commands and can otherwise stall the attach
of the entire normal browser session.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import sys

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve


STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
ENDPOINT_FILE = STATE_HOME / "chatgpt-rdc-supervisor/channel-endpoint.json"
ACTIVE_PORT_FILE = Path.home() / ".config/google-chrome/DevToolsActivePort"


def notify_ready() -> None:
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.sendto(b"READY=1", address)


class ChannelBridge:
    def __init__(self, chrome) -> None:
        self.chrome = chrome
        self.client = None
        self.next_id = 1_000_000_000
        self.pending: dict[int, tuple[object | None, int | None, asyncio.Future | None]] = {}
        self.forwarded_sessions: set[str] = set()
        self.screen_tasks: set[asyncio.Task] = set()
        self.target_results: dict[str, bool] = {}
        self.target_waiters: dict[str, asyncio.Future] = {}
        self.reader_task: asyncio.Task | None = None

    async def send(self, payload: dict, *, client=None) -> dict | None:
        self.next_id += 1
        command_id = self.next_id
        outgoing = dict(payload)
        outgoing["id"] = command_id
        future = asyncio.get_running_loop().create_future() if client is None else None
        self.pending[command_id] = (client, payload.get("id"), future)
        await self.chrome.send(json.dumps(outgoing))
        if future is not None:
            try:
                return await future
            finally:
                self.pending.pop(command_id, None)
        return None

    async def screen_target(self, event: dict) -> None:
        params = event.get("params", {})
        session_id = params.get("sessionId")
        target_info = params.get("targetInfo", {})
        target_id = target_info.get("targetId")
        target_type = target_info.get("type")
        client = self.client
        if client is None or not session_id:
            return
        responsive = False
        if target_type in {"page", "iframe"}:
            try:
                reply = await asyncio.wait_for(
                    self.send({"method": "Page.getFrameTree", "sessionId": session_id}),
                    timeout=2,
                )
                responsive = "result" in reply
            except (asyncio.TimeoutError, ConnectionError):
                pass
        if responsive and self.client is client:
            self.forwarded_sessions.add(session_id)
            await client.send(json.dumps(event))
        else:
            try:
                await self.send({"method": "Target.detachFromTarget", "params": {"sessionId": session_id}})
            except ConnectionError:
                pass
        if target_id:
            self.target_results[target_id] = responsive
            waiter = self.target_waiters.pop(target_id, None)
            if waiter is not None and not waiter.done():
                waiter.set_result(responsive)

    async def read_chrome(self) -> None:
        async for raw in self.chrome:
            message = json.loads(raw)
            command_id = message.get("id")
            if command_id is not None:
                request = self.pending.pop(command_id, None)
                if request is None:
                    continue
                client, original_id, future = request
                if future is not None:
                    if not future.done():
                        future.set_result(message)
                elif client is self.client:
                    message["id"] = original_id
                    await client.send(json.dumps(message))
                continue

            method = message.get("method")
            if method == "Target.attachedToTarget":
                task = asyncio.create_task(self.screen_target(message))
                self.screen_tasks.add(task)
                task.add_done_callback(self.screen_tasks.discard)
                continue
            if method == "Target.detachedFromTarget":
                session_id = message.get("params", {}).get("sessionId")
                if session_id not in self.forwarded_sessions:
                    continue
                self.forwarded_sessions.discard(session_id)
            elif message.get("sessionId") not in (None, *self.forwarded_sessions):
                continue
            if self.client is not None:
                await self.client.send(json.dumps(message))

    async def handle_client(self, client, token: str) -> None:
        if client.request.path != f"/{token}" or self.client is not None:
            await client.close(code=1008)
            return
        self.client = client
        try:
            async for raw in client:
                message = json.loads(raw)
                if message.get("method") == "Browser.close":
                    await client.send(json.dumps({"id": message.get("id"), "error": {"message": "Closing normal Chrome is disabled"}}))
                    continue
                if message.get("method") == "Target.setAutoAttach" and not message.get("sessionId") and message.get("params", {}).get("autoAttach"):
                    reply = await self.send(message)
                    await asyncio.sleep(0.2)
                    if self.screen_tasks:
                        await asyncio.gather(*list(self.screen_tasks))
                    reply["id"] = message["id"]
                    await client.send(json.dumps(reply))
                    continue
                if message.get("method") == "Target.createTarget":
                    reply = await self.send(message)
                    target_id = reply.get("result", {}).get("targetId")
                    if target_id:
                        if target_id not in self.target_results:
                            waiter = asyncio.get_running_loop().create_future()
                            self.target_waiters[target_id] = waiter
                            try:
                                await asyncio.wait_for(waiter, timeout=5)
                            except asyncio.TimeoutError:
                                pass
                        if not self.target_results.pop(target_id, False):
                            reply = {"error": {"message": "New tab did not become responsive"}}
                    reply["id"] = message["id"]
                    await client.send(json.dumps(reply))
                    continue
                await self.send(message, client=client)
        finally:
            if self.client is client:
                self.client = None
                self.forwarded_sessions.clear()
                try:
                    await asyncio.wait_for(self.send({"method": "Target.setAutoAttach", "params": {"autoAttach": False, "waitForDebuggerOnStart": False, "flatten": True}}), timeout=5)
                except (asyncio.TimeoutError, ConnectionError):
                    pass


async def main() -> None:
    lines = ACTIVE_PORT_FILE.read_text().splitlines()
    port = int(lines[0])
    token = secrets.token_urlsafe(24)
    async with connect(f"ws://127.0.0.1:{port}/devtools/browser", origin=None, max_size=None, open_timeout=60) as chrome:
        bridge = ChannelBridge(chrome)
        bridge.reader_task = asyncio.create_task(bridge.read_chrome())
        async with serve(lambda client: bridge.handle_client(client, token), "127.0.0.1", 0, max_size=None) as server:
            local_port = server.sockets[0].getsockname()[1]
            ENDPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = ENDPOINT_FILE.with_name(f".{ENDPOINT_FILE.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps({"endpoint": f"ws://127.0.0.1:{local_port}/{token}", "pid": os.getpid()}) + "\n")
            temporary.chmod(0o600)
            temporary.replace(ENDPOINT_FILE)
            notify_ready()
            print("channel bridge ready", flush=True)
            try:
                await bridge.reader_task
            finally:
                if bridge.client is not None:
                    await bridge.client.close()
                ENDPOINT_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (OSError, ValueError, ConnectionError) as exc:
        print(f"channel bridge unavailable: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
