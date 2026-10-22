"""Shared infrastructure for FastAPI microservices."""
from .health import create_health_router
from .logging import configure_logging

__all__ = ["configure_logging", "create_health_router"]
