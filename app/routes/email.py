from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_current_active_user
from app.models import User
from app.services.email_service import email_service

router = APIRouter(prefix="/api/v1/email", tags=["Email"])

@router.post("/test")
async def send_test_email(
    current_user: User = Depends(get_current_active_user)
):
    """Send a test email to the current user"""
    if not email_service.client:
        raise HTTPException(status_code=400, detail="Email service not configured")
    
    success = await email_service.send_test_email(current_user.email)
    if success:
        return {"message": "Test email sent successfully!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test email")