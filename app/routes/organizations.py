from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
import secrets
import re
from enum import Enum
from app.database import get_db
from app.models import User, Organization, OrganizationInvite, Project
from app.utils.auth import get_current_active_user
from app.utils.audit import log_action
from app.schemas import OrganizationCreate, OrganizationResponse, InviteCreate, InviteResponse
from app.services.email_service import email_service
from app.config import settings

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class RoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


def generate_organization_slug(name: str) -> str:
    if not name:
        return "organization"
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    return slug


@router.post("/")
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.organization_id:
        raise HTTPException(status_code=400, detail="You already belong to an organization")
    
    slug = generate_organization_slug(data.slug or data.name)
    
    existing = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization slug already taken")
    
    org = Organization(
        name=data.name,
        slug=slug,
        owner_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(org)
    await db.flush()
    
    current_user.organization_id = org.id
    current_user.role = RoleEnum.OWNER.value
    await db.commit()
    await db.refresh(current_user)
    
    project = Project(
        name="My Project",
        slug="my-project",
        organization_id=org.id,
        owner_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(project)
    await db.commit()
    
    await log_action(
        db=db,
        user_id=current_user.id,
        project_id=0,
        action="organization_created",
        details={"organization_id": org.id, "organization_name": org.name}
    )
    
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "created_at": org.created_at
    }


@router.get("/me")
async def get_my_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.organization_id:
        return None
    
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        return None
    
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


@router.get("/invites/validate")
async def validate_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.token == token,
            OrganizationInvite.accepted_at.is_(None)
        )
    )
    invite = result.scalar_one_or_none()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")
    
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    org_result = await db.execute(
        select(Organization).where(Organization.id == invite.organization_id)
    )
    org = org_result.scalar_one_or_none()
    
    inviter_result = await db.execute(
        select(User).where(User.id == invite.invited_by)
    )
    inviter = inviter_result.scalar_one_or_none()
    
    return {
        "valid": True,
        "organization_name": org.name if org else "Unknown Organization",
        "organization_id": invite.organization_id,
        "invited_by_email": inviter.email if inviter else "Unknown",
        "invited_by_name": inviter.full_name if inviter else "Unknown",
        "role": invite.role,
        "email": invite.email,
        "expires_at": invite.expires_at,
        "created_at": invite.created_at,
    }


@router.post("/invites")
async def invite_user(
    data: InviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="You are not in an organization")
    
    if current_user.role not in [RoleEnum.OWNER.value, RoleEnum.ADMIN.value]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    if data.role and data.role not in [r.value for r in RoleEnum]:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in RoleEnum]}")
    
    existing_member = await db.execute(
        select(User).where(
            User.email == data.email,
            User.organization_id == current_user.organization_id
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already in organization")
    
    existing_invite = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.email == data.email,
            OrganizationInvite.organization_id == current_user.organization_id,
            OrganizationInvite.accepted_at.is_(None)
        )
    )
    if existing_invite.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invite already pending")
    
    org_result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = org_result.scalar_one_or_none()
    org_name = org.name if org else "FrankTech Team"
    
    token = secrets.token_urlsafe(32)
    invite = OrganizationInvite(
        organization_id=current_user.organization_id,
        email=data.email,
        role=data.role or RoleEnum.MEMBER.value,
        token=token,
        invited_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_at=datetime.utcnow()
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    
    invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    
    await log_action(
        db=db,
        user_id=current_user.id,
        project_id=0,
        action="invite_sent",
        details={
            "invite_id": invite.id,
            "email": data.email,
            "role": data.role,
            "organization_id": current_user.organization_id
        }
    )
    
    if email_service.client:
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>You've been invited to FrankTech</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
                    .header {{ border-bottom: 2px solid #f1f5f9; padding-bottom: 20px; margin-bottom: 20px; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #0f172a; }}
                    .logo span {{ color: #06b6d4; }}
                    .button {{ display: inline-block; background: #06b6d4; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 16px; }}
                    .button:hover {{ background: #0891b2; }}
                    .footer {{ margin-top: 20px; padding-top: 20px; border-top: 2px solid #f1f5f9; color: #64748b; font-size: 14px; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">🚀 <span>FrankTech</span> Intelligence</div>
                    </div>
                    
                    <h2>You've Been Invited! 🎉</h2>
                    <p style="color: #475569; font-size: 16px;">
                        <strong>{current_user.full_name or current_user.email}</strong> has invited you to join the organization
                        <strong>"{org_name}"</strong> on FrankTech Intelligence.
                    </p>
                    
                    <div style="margin: 24px 0;">
                        <p style="color: #475569; font-size: 14px;">
                            <strong>Role:</strong> {data.role or 'member'}
                        </p>
                        <p style="color: #475569; font-size: 14px;">
                            <strong>Expires:</strong> {invite.expires_at.strftime('%B %d, %Y')}
                        </p>
                    </div>
                    
                    <a href="{invite_link}" class="button">Accept Invitation →</a>
                    
                    <p style="color: #64748b; font-size: 14px; margin-top: 24px;">
                        If you don't have a FrankTech account yet, you'll be prompted to create one.
                    </p>
                    
                    <div class="footer">
                        <p>This invitation was sent from FrankTech Intelligence.</p>
                        <p style="font-size: 12px;">If you didn't expect this invitation, you can safely ignore this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            await email_service.send_email(
                to_email=data.email,
                subject=f"You've been invited to join {org_name} on FrankTech",
                html_content=html_content
            )
            
            await log_action(
                db=db,
                user_id=current_user.id,
                project_id=0,
                action="email_sent",
                details={
                    "invite_id": invite.id,
                    "to_email": data.email,
                    "subject": f"You've been invited to join {org_name} on FrankTech"
                }
            )
        except Exception as e:
            print(f"Failed to send invite email: {e}")
    
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "invite_link": invite_link,
        "expires_at": invite.expires_at
    }


@router.post("/invites/accept")
async def accept_invite(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    token = data.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    
    invite_result = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.token == token,
            OrganizationInvite.accepted_at.is_(None)
        )
    )
    invite = invite_result.scalar_one_or_none()
    
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite")
    
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite expired")
    
    if invite.email != current_user.email:
        raise HTTPException(status_code=400, detail="Email does not match invite")
    
    invite.accepted_at = datetime.utcnow()
    current_user.organization_id = invite.organization_id
    current_user.role = invite.role
    await db.commit()
    
    await log_action(
        db=db,
        user_id=current_user.id,
        project_id=0,
        action="invite_accepted",
        details={
            "invite_id": invite.id,
            "organization_id": invite.organization_id,
            "email": current_user.email
        }
    )
    
    return {"message": "Invite accepted successfully"}


@router.post("/leave")
async def leave_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="You are not in an organization")
    
    org_result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = org_result.scalar_one_or_none()
    
    if org and org.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot leave. Transfer ownership first.")
    
    current_user.organization_id = None
    await db.commit()
    
    await log_action(
        db=db,
        user_id=current_user.id,
        project_id=0,
        action="organization_left",
        details={"organization_id": org.id, "organization_name": org.name}
    )
    
    return {"message": "Left organization successfully"}