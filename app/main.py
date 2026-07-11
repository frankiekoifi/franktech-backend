from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routes import errors, auth, api_keys
from app.database import engine, Base
from app.config import settings
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist
    print("🔍 Checking database connection...")
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created/verified")
        
        # Check if users table exists and has data
        try:
            result = await conn.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
            print(f"👥 Users in database: {count}")
        except Exception as e:
            print(f"⚠️ Users table check: {e}")
    
    yield
    
    # Shutdown: Close connections
    await engine.dispose()
    print("✅ Database connections closed")

app = FastAPI(
    title="FrankTech Intelligence API",
    description="AI-powered error monitoring that auto-fixes errors",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(errors.router)
app.include_router(auth.router)
app.include_router(api_keys.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to FrankTech Intelligence API",
        "docs": "/docs",
        "status": "running",
        "ai_enabled": settings.ai_enabled
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}