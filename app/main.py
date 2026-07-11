from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routes import errors, auth
from app.database import engine, Base
from app.config import settings
from app.routes import errors, auth, api_keys

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created/verified")
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