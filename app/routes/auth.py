from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, Organization, Project
from app.schemas import UserCreate, UserLogin, TokenResponse, UserResponse
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    get_current_user,
    get_current_active_user,
    logout_user,
    generate_organization_slug
)
from app.config import settings
from app.database import get_db
from email_validator import validate_email, EmailNotValidError

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        try:
            valid = validate_email(user_data.email)
            email = valid.email
        except EmailNotValidError:
            raise HTTPException(status_code=400, detail="Invalid email address")
        
        existing = await db.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user_data.password)
        
        org = None
        if user_data.organization_name:
            existing_org = await db.execute(
                select(Organization).where(Organization.name == user_data.organization_name)
            )
            org = existing_org.scalar_one_or_none()
            if not org:
                slug = generate_organization_slug(user_data.organization_name)
                org = Organization(
                    name=user_data.organization_name,
                    slug=slug,
                    created_at=datetime.utcnow()
                )
                db.add(org)
                await db.flush()
        
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
        
        project = Project(
            name="My Project",
            slug="my-project",
            organization_id=org.id if org else None,
            owner_id=user.id,
            created_at=datetime.utcnow()
        )
        db.add(project)
        await db.commit()
        
        await db.refresh(user)
        
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
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
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    try:
        print(f"Login attempt for: {login_data.email}")
        
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
        
        if not verify_password(login_data.password, user.hashed_password):
            print(f"Invalid password for: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        print(f"Login successful for: {login_data.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
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
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme)
):
    result = await logout_user(token)
    return result


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )
    
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id_str is None or token_type != "refresh":
            raise credentials_exception
        
        user_id = int(user_id_str)
    except JWTError:
        raise credentials_exception
    except ValueError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    new_access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        organization_id=current_user.organization_id,
        created_at=current_user.created_at,
        email_notifications=current_user.email_notifications
    )