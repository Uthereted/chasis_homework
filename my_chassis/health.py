"""Background dependency checks and cached FastAPI readiness responses."""
import asyncio
from contextlib import asynccontextmanager, suppress
import inspect
import logging
import os
from datetime import datetime, timezone
import time

from fastapi import APIRouter, HTTPException


class ResourceMonitor:
    """Sample OS-visible resources periodically; HTTP only reads the snapshot."""
    def __init__(self, *, interval=5, max_age=15, disk_path=None):
        self.interval = interval
        self.max_age = max_age
        self.disk_path = disk_path or os.getenv('HEALTH_DISK_PATH', '/')
        self.data = None
        self.checked_at = 0
        self.task = None

    def collect(self):
        import psutil
        # The short blocking CPU sample runs in a worker thread, not in HTTP.
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.disk_path)
        return {
            'sampled_at': datetime.now(timezone.utc).isoformat(),
            'cpu_percent': cpu,
            'memory': {'total_bytes': memory.total, 'available_bytes': memory.available,
                       'used_percent': memory.percent},
            'disk': {'path': self.disk_path, 'total_bytes': disk.total,
                     'free_bytes': disk.free, 'used_percent': disk.percent},
        }

    async def refresh(self):
        try:
            self.data = await asyncio.to_thread(self.collect)
            self.checked_at = time.monotonic()
        except Exception:
            self.data = None
            logging.getLogger(__name__).warning('Resource sampling unavailable', exc_info=True)

    async def run(self):
        while True:
            await asyncio.sleep(self.interval)
            await self.refresh()

    def snapshot(self):
        if (self.task is None or self.task.done() or self.data is None
                or time.monotonic() - self.checked_at >= self.max_age):
            raise HTTPException(503, 'Resource snapshot unavailable')
        return self.data

    @asynccontextmanager
    async def lifespan(self):
        self.data = None
        self.checked_at = 0
        await self.refresh()
        self.task = asyncio.create_task(self.run())
        try:
            yield
        finally:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.data = None


class HealthMonitor:
    def __init__(self, checks, *, interval=1, max_age=4, timeout=2):
        self.checks = checks
        self.interval = interval
        self.max_age = max_age
        self.timeout = timeout
        self.states = {}
        self.checked_at = 0
        self.task = None

    @property
    def available(self):
        return (self.task is not None and not self.task.done()
                and time.monotonic() - self.checked_at < self.max_age
                and bool(self.states) and len(self.states) == len(self.checks)
                and all(self.states.values()))

    async def _check(self, check):
        result = check()
        return bool(await result) if inspect.isawaitable(result) else bool(result)

    async def run(self):
        while True:
            states = {}
            for name, check in self.checks.items():
                try:
                    states[name] = await asyncio.wait_for(self._check(check), self.timeout)
                except Exception:
                    states[name] = False
            self.states = states
            self.checked_at = time.monotonic()
            await asyncio.sleep(self.interval)

    @asynccontextmanager
    async def lifespan(self):
        self.states = {}
        self.checked_at = 0
        self.task = asyncio.create_task(self.run())
        try:
            yield
        finally:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.states = {}


async def mongodb_ready(client):
    return (await asyncio.to_thread(client.admin.command, 'ping'))['ok'] == 1


def create_health_router(service_name: str, *, is_ready=None, resources=None) -> APIRouter:
    """Read cached readiness; dependency probes never run in this endpoint."""
    router = APIRouter(tags=['Health'])

    @router.get('/health')
    async def health() -> dict:
        if is_ready is not None and not is_ready():
            raise HTTPException(503, 'Service dependencies unavailable')
        result = {'status': 'ok', 'service': service_name}
        if resources is not None:
            result['resources'] = resources()
        return result

    return router
