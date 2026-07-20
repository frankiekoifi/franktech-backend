from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.utils.auth import get_current_active_user
from app.schemas import NotificationUpdate

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.post("/notifications")
async def update_notifications(
    data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    current_user.email_notifications = data.email_notifications
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "message": "Notification settings updated",
        "email_notifications": current_user.email_notifications
    }