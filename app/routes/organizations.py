from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
import secrets
from app.database import get_db
from app.models import User, Organization, OrganizationInvite, Project
from app.utils.auth import get_current_active_user
from app.schemas import OrganizationCreate, OrganizationResponse, InviteCreate, InviteResponse

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])

# ============ Create Organization ============
@router.post("/")
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new organization"""
    # Check if user already has an organization
    if current_user.organization_id:
        raise HTTPException(status_code=400, detail="You already belong to an organization")
    
    # Check if slug exists
    existing = await db.execute(
        select(Organization).where(Organization.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization slug already taken")
    
    # Create organization
    org = Organization(
        name=data.name,
        slug=data.slug,
        owner_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(org)
    await db.flush()
    
    # Update user
    current_user.organization_id = org.id
    current_user.role = "owner"
    await db.commit()
    await db.refresh(current_user)
    
    # Create default project
    project = Project(
        name="My Project",
        slug="my-project",
        organization_id=org.id,
        owner_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(project)
    await db.commit()
    
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "created_at": org.created_at
    }

# ============ Get Organization ============
@router.get("/me")
async def get_my_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's organization"""
    if not current_user.organization_id:
        return None
    
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        return None
    
    # Get members count
    members_result = await db.execute(
        select(User).where(User.organization_id == org.id)
    )
    members = members_result.scalars().all()
    
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "member_count": len(members),
        "created_at": org.created_at,
        "members": [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "joined_at": user.created_at
            }
            for user in members
        ]
    }

# ============ Invite User ============
@router.post("/invites")
async def invite_user(
    data: InviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Invite a user to the organization"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="You are not in an organization")
    
    # Check if user has permission (owner or admin)
    if current_user.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Check if email already in organization
    existing_member = await db.execute(
        select(User).where(
            User.email == data.email,
            User.organization_id == current_user.organization_id
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already in organization")
    
    # Check if invite already exists
    existing_invite = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.email == data.email,
            OrganizationInvite.organization_id == current_user.organization_id,
            OrganizationInvite.accepted_at.is_(None)
        )
    )
    if existing_invite.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invite already pending")
    
    # Create invite
    token = secrets.token_urlsafe(32)
    invite = OrganizationInvite(
        organization_id=current_user.organization_id,
        email=data.email,
        role=data.role or "member",
        token=token,
        invited_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_at=datetime.utcnow()
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    
    # TODO: Send email with invite link
    invite_link = f"https://monitor.franktechspace.dev/accept-invite?token={token}"
    
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "invite_link": invite_link,
        "expires_at": invite.expires_at
    }

# ============ Accept Invite ============
@router.post("/invites/accept")
async def accept_invite(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Accept an organization invite"""
    token = data.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    
    # Find invite
    invite_result = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.token == token,
            OrganizationInvite.accepted_at.is_(None)
        )
    )
    invite = invite_result.scalar_one_or_none()
    
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite")
    
    # Check expiry
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite expired")
    
    # Check email matches
    if invite.email != current_user.email:
        raise HTTPException(status_code=400, detail="Email does not match invite")
    
    # Accept invite
    invite.accepted_at = datetime.utcnow()
    current_user.organization_id = invite.organization_id
    current_user.role = invite.role
    await db.commit()
    
    return {"message": "Invite accepted successfully"}

# ============ Leave Organization ============
@router.post("/leave")
async def leave_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Leave the current organization"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="You are not in an organization")
    
    # Check if user is the owner
    org_result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = org_result.scalar_one_or_none()
    
    if org and org.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot leave. Transfer ownership first.")
    
    current_user.organization_id = None
    await db.commit()
    
    return {"message": "Left organization successfully"}