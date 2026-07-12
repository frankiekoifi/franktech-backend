from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routes import errors, auth, api_keys, github
from app.database import engine, Base
from app.config import settings
from sqlalchemy import text

# Import all models
from app.models import User, Organization, Project, Error, AIAnalysis, APIKey

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔍 Checking database connection...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Database tables created/verified")
            
            try:
                result = await conn.execute(text("SELECT COUNT(*) FROM users"))
                count = result.scalar()
                print(f"👥 Users in database: {count}")
            except Exception as e:
                print(f"⚠️ Users table check: {e}")
    except Exception as e:
        print(f"❌ Database connection error: {e}")
    
    yield
    
    await engine.dispose()
    print("✅ Database connections closed")

app = FastAPI(
    title="FrankTech Intelligence API",
    description="AI-powered error monitoring that auto-fixes errors",
    version="1.0.0",
    lifespan=lifespan
)

#  CORS middleware - Allow all Render domains
app.add_middleware(
    CORSMiddleware,
     allow_origins=[
        "https://monitor.franktechspace.dev",
        "https://franktech-api.franktechspace.dev",

        "https://franktech-dashboard.onrender.com",
        "https://franktech-backend.onrender.com",

        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Include routers
app.include_router(errors.router)
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(github.router)

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