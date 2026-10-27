from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# Declarative base for all ORM models
class Base(DeclarativeBase):
    pass


# Async engine configured from settings; does not connect until first use
engine = create_async_engine(settings.database_url)

# Session factory for creating async database sessions
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


# Dependency that provides an async session and ensures it closes after use
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
