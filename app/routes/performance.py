# app/routers/performance.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from app.database import get_db
from app.models import PerformanceMetric, Project, User
from app.utils.auth import get_current_user
from typing import List, Dict

router = APIRouter(prefix="/api/v1/performance", tags=["Performance"])

@router.post("/metrics")
async def ingest_performance_metrics(
    metrics: List[Dict],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Store performance metrics"""
    project = await db.execute(
        select(Project).where(Project.owner_id == current_user.id)
    )
    project = project.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=400, detail="No project found")
    
    for metric in metrics:
        db_metric = PerformanceMetric(
            project_id=project.id,
            type=metric.get('type'),
            url=metric.get('url'),
            method=metric.get('method'),
            duration=metric.get('duration'),
            status=metric.get('status'),
            metrics=metric.get('metrics'),
            environment=metric.get('environment'),
            release_version=metric.get('release_version'),
            user_id=metric.get('user_id'),
            user_email=metric.get('user_email'),
            timestamp=datetime.fromtimestamp(metric.get('timestamp', datetime.utcnow().timestamp()))
        )
        db.add(db_metric)
    
    await db.commit()
    return {"success": True, "count": len(metrics)}

@router.get("/api")
async def get_api_metrics(
    time_range: str = "24h",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get API performance metrics"""
    # Parse time range
    if time_range == "1h":
        since = datetime.utcnow() - timedelta(hours=1)
    elif time_range == "6h":
        since = datetime.utcnow() - timedelta(hours=6)
    elif time_range == "24h":
        since = datetime.utcnow() - timedelta(hours=24)
    elif time_range == "7d":
        since = datetime.utcnow() - timedelta(days=7)
    else:
        since = datetime.utcnow() - timedelta(hours=24)
    
    # Get metrics
    result = await db.execute(
        select(PerformanceMetric)
        .where(
            PerformanceMetric.project_id.in_(
                select(Project.id).where(Project.owner_id == current_user.id)
            ),
            PerformanceMetric.type == "api",
            PerformanceMetric.timestamp >= since
        )
        .order_by(PerformanceMetric.timestamp.desc())
    )
    metrics = result.scalars().all()
    
    # Calculate averages
    durations = [m.duration for m in metrics if m.duration]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return {
        "metrics": [
            {
                "id": m.id,
                "url": m.url,
                "method": m.method,
                "duration": m.duration,
                "status": m.status,
                "timestamp": m.timestamp
            }
            for m in metrics[:100]
        ],
        "summary": {
            "total": len(metrics),
            "avg_duration": avg_duration,
            "slow_count": len([m for m in metrics if m.duration > 1000]),
            "error_count": len([m for m in metrics if m.status and m.status >= 400])
        }
    }