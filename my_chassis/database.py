"""FastAPI database dependencies without owning service models or commits."""

def create_db_dependency(session_factory):
    """Yield one session per request and close it even when a route fails."""
    async def get_db():
        async with session_factory() as db:
            yield db
    return get_db
