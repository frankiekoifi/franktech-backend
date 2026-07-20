import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

# Manually load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    with open(ENV_FILE, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./franktech.db")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    USE_GROQ: bool = os.getenv("USE_GROQ", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    store_user_email: bool = True
    groq_model: str = "llama-3.3-70b-versatile"
    openai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: int = 30
    ai_max_retries: int = 1
    FRONTEND_URL: str = "https://monitor.franktechspace.dev"
    
    # GitHub OAuth settings only
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "FrankTech <francisochieng700@gmail.com>")
    
    model_config = ConfigDict(extra="ignore")
    
    @property
    def ai_enabled(self) -> bool:
        if self.USE_GROQ:
            return bool(self.GROQ_API_KEY)
        return bool(self.OPENAI_API_KEY)
    
    @property
    def ai_provider(self) -> str:
        if self.USE_GROQ:
            return "groq"
        return "openai"

settings = Settings()

# Print status
print("=" * 60)
print("🔍 Configuration Status")
print("=" * 60)
print(f"🤖 AI Provider: {settings.ai_provider}")
if settings.USE_GROQ:
    print(f"🔑 GROQ_API_KEY: {'✅ SET' if settings.GROQ_API_KEY else '❌ NOT SET'}")
else:
    print(f"🔑 OPENAI_API_KEY: {'✅ SET' if settings.OPENAI_API_KEY else '❌ NOT SET'}")
print(f"🔐 SECRET_KEY: {'✅ SET' if settings.SECRET_KEY else '❌ NOT SET'}")
print(f"🗄️  DATABASE_URL: {settings.DATABASE_URL}")
if settings.GITHUB_CLIENT_ID:
    print(f"🔑 GITHUB_CLIENT_ID: ✅ SET")
else:
    print(f"🔑 GITHUB_CLIENT_ID: ❌ NOT SET")
print("=" * 60)