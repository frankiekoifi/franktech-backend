import asyncio
from app.database import engine
from app.models import Base
from app.config import settings

async def run_migrations():
    """Create tables directly (bypass Alembic)"""
    try:
        print("🔍 Connecting to database...")
        print(f"📁 Database: {settings.DATABASE_URL[:50]}...")
        
        async with engine.begin() as conn:
            print("📦 Creating tables...")
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Tables created successfully!")
            
            # Verify tables were created
            from sqlalchemy import text
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
            ))
            tables = [row[0] for row in result]
            print(f"📋 Tables created: {', '.join(tables)}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting database migration...")
    asyncio.run(run_migrations())