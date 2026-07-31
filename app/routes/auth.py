from fastapi import APIRouter, HTTPException, Depends, status, Request
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets
from app.models import User, Organization, Project
from app.schemas import UserCreate, UserLogin, TokenResponse, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    get_current_user,
    get_current_active_user,
    logout_user,
    generate_organization_slug,
    _is_sha256_hash
)
from app.config import settings
from app.database import get_db
from email_validator import validate_email, EmailNotValidError
from app.middleware.rate_limit import limiter
from app.services.rate_limit_service import login_tracker
from app.services.email_service import email_service

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/register", response_model=TokenResponse)
@limiter.limit("3/minute")
async def register(
    request: Request,
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
        
        # Generate email verification token
        verification_token = secrets.token_urlsafe(32)
        
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            organization_id=org.id if org else None,
            created_at=datetime.utcnow(),
            is_active=True,
            is_email_verified=False,
            email_verification_token=verification_token,
            email_verification_expires=datetime.utcnow() + timedelta(days=1)
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
        
        # Send verification email
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        if email_service.client:
            try:
                await email_service.send_email(
                    to_email=email,
                    subject="Verify your email - FrankTech Intelligence",
                    html_content=f"""
                    <h1>Welcome to FrankTech!</h1>
                    <p>Please verify your email by clicking the link below:</p>
                    <a href="{verification_link}">Verify Email</a>
                    <p>This link expires in 24 hours.</p>
                    """
                )
            except Exception as e:
                print(f"Failed to send verification email: {e}")
        
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


@router.get("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(
            User.email_verification_token == token,
            User.email_verification_expires > datetime.utcnow()
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    await db.commit()
    
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    try:
        print(f"Login attempt for: {login_data.email}")
        
        if not login_tracker.track_attempt(login_data.email):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please try again later."
            )
        
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
        
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Please verify your email before logging in"
            )
        
        # Check password with bcrypt
        password_valid = verify_password(login_data.password, user.hashed_password)
        
        # If bcrypt fails, check if it's an old SHA256 hash
        if not password_valid and _is_sha256_hash(user.hashed_password):
            # Old SHA256 hash - force password reset
            # Generate reset token automatically
            reset_token = secrets.token_urlsafe(32)
            user.reset_token = reset_token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=24)
            await db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your password needs to be reset. Please use the 'Forgot Password' feature."
            )
        
        if not password_valid:
            print(f"Invalid password for: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        login_tracker.reset_attempts(login_data.email)
        
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


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: dict,
    db: AsyncSession = Depends(get_db)
):
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    try:
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        # Always return success even if user not found (security best practice)
        if not user:
            return {"message": "If that email exists, a reset link has been sent"}
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        await db.commit()
        
        # Send reset email
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        if email_service.client:
            try:
                await email_service.send_email(
                    to_email=email,
                    subject="Reset your password - FrankTech Intelligence",
                    html_content=f"""
                    <h1>Reset Your Password</h1>
                    <p>Click the link below to reset your password:</p>
                    <a href="{reset_link}">Reset Password</a>
                    <p>This link expires in 1 hour.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                    """
                )
            except Exception as e:
                print(f"Failed to send reset email: {e}")
        
        return {"message": "If that email exists, a reset link has been sent"}
        
    except Exception as e:
        print(f"Forgot password error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process request")


@router.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    data: dict,
    db: AsyncSession = Depends(get_db)
):
    token = data.get("token")
    new_password = data.get("new_password")
    
    if not token:
        raise HTTPException(status_code=400, detail="Reset token is required")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    try:
        result = await db.execute(
            select(User).where(
                User.reset_token == token,
                User.reset_token_expires > datetime.utcnow()
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        # Hash with bcrypt
        user.hashed_password = get_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await db.commit()
        
        return {"message": "Password reset successfully. You can now log in with your new password."}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Reset password error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset password")


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