from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import secrets
from app.database import get_db
from app.models import APIKey, Project, User
from app.utils.auth import get_current_active_user
from app.schemas import APIKeyCreate, APIKeyResponse
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])

# ============ Schemas ============

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

# ============ Routes ============

@router.post("/", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new API key for a project"""
    try:
        # If no project_id provided, get or create default project
        project_id = key_data.project_id
        
        if not project_id:
            # Get user's first project or create one
            project_result = await db.execute(
                select(Project).where(Project.owner_id == current_user.id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                # Create default project
                project = Project(
                    name="My Project",
                    slug="my-project",
                    owner_id=current_user.id,
                    created_at=datetime.utcnow()
                )
                db.add(project)
                await db.flush()
                await db.refresh(project)
            project_id = project.id
        else:
            # Verify project belongs to user
            project_result = await db.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.owner_id == current_user.id
                )
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found"
                )
        
        # Generate API key
        api_key_value = f"ft_{secrets.token_urlsafe(32)}"
        
        api_key = APIKey(
            key=api_key_value,
            name=key_data.name or "Default Key",
            project_id=project_id,
            created_at=datetime.utcnow(),
            is_active=True
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        return APIKeyResponse(
            id=api_key.id,
            key=api_key.key,
            name=api_key.name,
            project_id=api_key.project_id,
            created_at=api_key.created_at,
            last_used=api_key.last_used,
            is_active=api_key.is_active
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API Key creation error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[APIKeyListResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all API keys for user's projects"""
    try:
        result = await db.execute(
            select(APIKey, Project.name.label("project_name"))
            .join(Project, APIKey.project_id == Project.id)
            .where(Project.owner_id == current_user.id)
            .order_by(APIKey.created_at.desc())
        )
        rows = result.all()
        
        return [
            APIKeyListResponse(
                id=row.APIKey.id,
                key=row.APIKey.key,
                name=row.APIKey.name,
                project_id=row.APIKey.project_id,
                project_name=row.project_name,
                created_at=row.APIKey.created_at,
                last_used=row.APIKey.last_used,
                is_active=row.APIKey.is_active,
                error_count=row.APIKey.error_count
            )
            for row in rows
        ]
    except Exception as e:
        print(f"❌ List API keys error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Revoke an API key"""
    try:
        result = await db.execute(
            select(APIKey).join(Project).where(
                APIKey.id == key_id,
                Project.owner_id == current_user.id
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(
                status_code=404,
                detail="API key not found"
            )
        
        api_key.is_active = False
        await db.commit()
        
        return {"message": "API key revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Revoke API key error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate")
async def validate_api_key(
    api_key: str,
    db: AsyncSession = Depends(get_db)
):
    """Validate an API key (for SDK testing)"""
    try:
        result = await db.execute(
            select(APIKey, Project).join(
                Project, APIKey.project_id == Project.id
            ).where(
                APIKey.key == api_key,
                APIKey.is_active == True
            )
        )
        row = result.first()
        
        if not row:
            raise HTTPException(
                status_code=401,
                detail="Invalid or inactive API key"
            )
        
        api_key_obj, project = row
        
        # Update last_used
        api_key_obj.last_used = datetime.utcnow()
        await db.commit()
        
        return {
            "valid": True,
            "project_id": project.id,
            "project_name": project.name
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Validate API key error: {e}")
        raise HTTPException(status_code=500, detail=str(e))