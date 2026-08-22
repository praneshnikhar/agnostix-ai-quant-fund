"""WebSocket endpoint with connection manager and heartbeat.

All server→client messages use the typed WSMessage envelope
(schemas.contracts.WSMessage). This is the foundation for the real-time
event contracts; milestone-specific event types are added later.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.schemas.contracts import WSMessage, WSMessageType

logger = get_logger(__name__)
router = APIRouter(tags=["realtime"])


class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts envelopes."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("ws_connected", active=self.active_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("ws_disconnected", active=self.active_count)

    async def broadcast(self, message: WSMessage) -> None:
        """Send an envelope to every connected client."""
        data = message.model_dump_json()
        async with self._lock:
            connections = list(self._connections)
        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001 - drop dead connections
                await self.disconnect(ws)

    async def send_heartbeat(self) -> None:
        await self.broadcast(WSMessage(type=WSMessageType.HEARTBEAT))


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept a client and stream heartbeats + broadcast events."""
    await manager.connect(websocket)
    try:
        while True:
            # Receive loop keeps the connection alive; client messages are
            # currently ignored (no client→server commands in M0).
            await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
    except (TimeoutError, WebSocketDisconnect):
        pass
    except Exception:  # noqa: BLE001
        logger.exception("ws_error")
    finally:
        await manager.disconnect(websocket)


async def heartbeat_loop(interval_seconds: float = 15.0) -> None:
    """Background task broadcasting periodic heartbeats to all clients."""
    while True:
        await asyncio.sleep(interval_seconds)
        if manager.active_count > 0:
            await manager.send_heartbeat()
