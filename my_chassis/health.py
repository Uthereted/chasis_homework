"""Background dependency checks and cached FastAPI readiness responses."""
import asyncio
from contextlib import asynccontextmanager, suppress
import inspect
import time

from fastapi import APIRouter, HTTPException


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


def create_health_router(service_name: str, *, is_ready=None) -> APIRouter:
    """Read cached readiness; dependency probes never run in this endpoint."""
    router = APIRouter(tags=['Health'])

    @router.get('/health')
    async def health() -> dict[str, str]:
        if is_ready is not None and not is_ready():
            raise HTTPException(503, 'Service dependencies unavailable')
        return {'status': 'ok', 'service': service_name}

    return router
