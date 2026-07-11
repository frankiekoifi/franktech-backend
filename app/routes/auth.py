from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, Organization, Project
from app.schemas import UserCreate, UserLogin, TokenResponse, UserResponse 
from app.utils.auth import create_access_token, verify_password, get_password_hash, get_current_user
from app.config import settings
from app.database import get_db
from email_validator import validate_email, EmailNotValidError

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    try:
        # Validate email
        try:
            valid = validate_email(user_data.email)
            email = valid.email
        except EmailNotValidError:
            raise HTTPException(status_code=400, detail="Invalid email address")
        
        # Check if user exists
        existing = await db.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create organization if provided
        org = None
        if user_data.organization_name:
            existing_org = await db.execute(
                select(Organization).where(Organization.name == user_data.organization_name)
            )
            org = existing_org.scalar_one_or_none()
            if not org:
                slug = user_data.organization_name.lower().replace(" ", "-")
                org = Organization(
                    name=user_data.organization_name,
                    slug=slug,
                    created_at=datetime.utcnow()
                )
                db.add(org)
                await db.flush()
        
        # Create user
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            organization_id=org.id if org else None,
            created_at=datetime.utcnow(),
            is_active=True
        )
        db.add(user)
        await db.flush()
        
        # Create default project
        project = Project(
            name="My Project",
            slug="my-project",
            organization_id=org.id if org else None,
            owner_id=user.id,
            created_at=datetime.utcnow()
        )
        db.add(project)
        await db.commit()
        
        # Refresh user to get relationships
        await db.refresh(user)
        
        # Generate token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                organization_id=user.organization_id,
                created_at=user.created_at
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login user"""
    try:
        print(f"Login attempt for: {login_data.email}")
        
        # Find user
        result = await db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"User not found: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            print(f"Invalid password for: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Generate token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        print(f"Login successful for: {login_data.email}")
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                organization_id=user.organization_id,
                created_at=user.created_at
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        organization_id=current_user.organization_id,
        created_at=current_user.created_at
    )