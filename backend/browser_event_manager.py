# Browser event manager for real-time status updates via SSE
# Version: 1.0 - Initial implementation for broadcasting browser state changes
# Handles multiple SSE client connections and broadcasts browser open/close events

import asyncio
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BrowserEvent:
    """Represents a browser state change event"""
    event_type: str  # "browser_opened", "browser_closed", "browser_login_created"
    account_id: int
    timestamp: str
    data: Dict[str, Any] = None


class BrowserEventManager:
    """Manages SSE connections and broadcasts browser events to all clients"""

    def __init__(self):
        # List of async queues for connected clients
        self._client_queues: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def add_client(self) -> asyncio.Queue:
        """Register a new SSE client and return its queue"""
        queue = asyncio.Queue()
        async with self._lock:
            self._client_queues.append(queue)
        return queue

    async def remove_client(self, queue: asyncio.Queue):
        """Unregister an SSE client"""
        async with self._lock:
            if queue in self._client_queues:
                self._client_queues.remove(queue)

    async def broadcast(self, event: BrowserEvent):
        """Broadcast an event to all connected clients"""
        async with self._lock:
            dead_queues = []
            for queue in self._client_queues:
                try:
                    # Non-blocking put to avoid slow clients blocking others
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Client queue is full, consider it dead
                    dead_queues.append(queue)

            # Remove dead queues
            for queue in dead_queues:
                self._client_queues.remove(queue)

    async def notify_browser_opened(self, account_id: int):
        """Notify all clients that a browser was opened"""
        event = BrowserEvent(
            event_type="browser_opened",
            account_id=account_id,
            timestamp=datetime.utcnow().isoformat()
        )
        await self.broadcast(event)

    async def notify_browser_closed(self, account_id: int):
        """Notify all clients that a browser was closed"""
        event = BrowserEvent(
            event_type="browser_closed",
            account_id=account_id,
            timestamp=datetime.utcnow().isoformat()
        )
        await self.broadcast(event)

    async def notify_login_browser_created(self, account_id: int):
        """Notify all clients that a new login browser was created"""
        event = BrowserEvent(
            event_type="browser_login_created",
            account_id=account_id,
            timestamp=datetime.utcnow().isoformat()
        )
        await self.broadcast(event)

    async def notify_account_deleted(self, account_id: int):
        """Notify all clients that an account was deleted"""
        event = BrowserEvent(
            event_type="account_deleted",
            account_id=account_id,
            timestamp=datetime.utcnow().isoformat()
        )
        await self.broadcast(event)

    @property
    def client_count(self) -> int:
        """Get number of connected SSE clients"""
        return len(self._client_queues)
