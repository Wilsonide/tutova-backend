from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine_options = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

# Queue-pool sizing is useful for PostgreSQL/Neon. SQLite in-memory engines
# use a different pool implementation and do not accept these arguments.
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_options.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    )

engine = create_async_engine(settings.DATABASE_URL, **engine_options)


AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session

        finally:
            await session.close()


async def close_database():
    await engine.dispose()
