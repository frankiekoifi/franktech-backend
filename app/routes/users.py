from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.utils.auth import get_current_active_user

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.post("/notifications")
async def update_notifications(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user notification settings"""
    email_notifications = data.get("email_notifications")
    
    if email_notifications is None:
        raise HTTPException(status_code=400, detail="email_notifications field required")
    
    current_user.email_notifications = email_notifications
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "message": "Notification settings updated",
        "email_notifications": current_user.email_notifications
    }