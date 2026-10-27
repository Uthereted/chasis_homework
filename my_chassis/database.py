"""FastAPI database dependencies without owning service models or commits."""

def create_db_dependency(session_factory):
    """Yield one session per request and close it even when a route fails."""
    async def get_db():
        async with session_factory() as db:
            yield db
    return get_db


def create_database(url, *, echo=False, expire_on_commit=False):
    """Create a service-owned engine, session factory and declarative base."""
    from sqlalchemy.orm import sessionmaker, declarative_base
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    options = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_async_engine(url, connect_args=options, echo=echo)
    sessions = sessionmaker(bind=engine, class_=AsyncSession, autocommit=False,
                            autoflush=False, expire_on_commit=expire_on_commit)
    return engine, sessions, declarative_base()
