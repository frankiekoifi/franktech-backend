from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings
import os

# Determine database URL (SQLite or PostgreSQL)
if settings.DATABASE_URL.startswith("postgresql://"):
    # Convert to async format for PostgreSQL
    DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif settings.DATABASE_URL.startswith("sqlite:///"):
    # Convert to async format for SQLite
    DATABASE_URL = settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    # Default to SQLite with async
    DATABASE_URL = "sqlite+aiosqlite:///./franktech.db"

# Create engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG or False,
    future=True
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()

# Dependency to get DB session
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()