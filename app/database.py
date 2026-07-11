from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings
import os

# Determine database URL
if settings.DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif settings.DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL = settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    DATABASE_URL = "sqlite+aiosqlite:///./franktech.db"

print(f"📁 Database URL: {DATABASE_URL[:50]}...")

# Create engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG or False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create Base
Base = declarative_base()

# Dependency to get DB session
async def get_db() -> AsyncSession: # type: ignore
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()