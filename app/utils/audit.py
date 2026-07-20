"""Audit logging utilities"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog


async def log_action(
    db: AsyncSession,
    user_id: int | None,
    project_id: int,
    action: str,
    details: dict | None = None
) -> None:
    """
    Log an action to the audit log.
    
    Args:
        db: Database session
        user_id: ID of the user (None if using API key)
        project_id: ID of the project
        action: Action name (e.g., "error_ingested", "error_viewed")
        details: Optional details dictionary
    """
    log = AuditLog(
        user_id=user_id,
        project_id=project_id,
        action=action,
        details=details,
        timestamp=datetime.utcnow()
    )
    db.add(log)
    await db.commit()