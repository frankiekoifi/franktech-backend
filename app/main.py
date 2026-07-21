from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from app.routes import errors, auth, api_keys, github, email, users, organizations, performance
from app.database import engine, Base
from app.config import settings
from sqlalchemy import text

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
    description="""
    ## FrankTech Intelligence API
    
    AI-powered error monitoring that automatically fixes your errors.
    
    ### Features
    - **Error Ingestion** - Capture errors from your apps
    - **AI Analysis** - Automatic root cause and fix suggestions
    - **Session Replay** - Watch what users did before an error
    - **GitHub Integration** - Auto-create PRs with fixes
    - **Performance Monitoring** - Track API response times
    - **Organization Management** - Teams and invites
    
    ### Authentication
    Two authentication methods supported:
    1. **Bearer Token (JWT)** - For dashboard users
    2. **X-API-Key** - For SDK integration
    
    ### Documentation
    - Swagger UI: `/api/docs`
    - ReDoc: `/api/redoc`
    - OpenAPI JSON: `/api/openapi.json`
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "FrankTech Support",
        "email": "support@franktechspace.dev",
        "url": "https://monitor.franktechspace.dev",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {"url": "https://franktech-api.franktechspace.dev", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Local Development"},
    ],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="FrankTech Intelligence API",
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token from login endpoint",
        },
        "APIKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key from dashboard",
        },
    }
    
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"APIKeyAuth": []},
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


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


app.include_router(errors.router)
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(github.router)
app.include_router(email.router)
app.include_router(users.router)
app.include_router(organizations.router)
app.include_router(performance.router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to FrankTech Intelligence API",
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "openapi": "/api/openapi.json",
        "status": "running",
        "ai_enabled": settings.ai_enabled
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}