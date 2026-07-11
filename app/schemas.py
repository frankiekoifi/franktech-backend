from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# ============ Error Schemas ============

class ErrorBase(BaseModel):
    type: str
    message: str
    stack_trace: Optional[str] = None
    severity: str = "error"
    url: Optional[str] = None
    line_no: Optional[int] = None
    col_no: Optional[int] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    environment: str = "production"
    release_version: Optional[str] = None
    extra_data: Optional[dict] = {}

class ErrorCreate(ErrorBase):
    pass

class ErrorResponse(ErrorBase):
    id: int
    status: str
    created_at: datetime
    has_ai_analysis: bool
    fixed_at: Optional[datetime] = None

# ============ AI Analysis Schemas ============

class AIAnalysisResponse(BaseModel):
    error_id: int
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    fix_explanation: Optional[str] = None
    confidence: Optional[float] = None
    analyzed_at: Optional[datetime] = None
    status: str

# ============ Auth Schemas ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    organization_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    organization_id: Optional[int] = None
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class APIKeyCreate(BaseModel):
    name: str
    project_id: Optional[int] = None

class APIKeyResponse(BaseModel):
    id: int
    key: str
    name: str
    project_id: int
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool

class APIKeyListResponse(BaseModel):
    id: int
    key: str
    name: str
    project_id: int
    project_name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool
    error_count: int