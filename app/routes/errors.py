from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from typing import Optional
from datetime import datetime
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.database import get_db
from app.models import Error, AIAnalysis, Project, APIKey, User
from app.schemas import ErrorCreate, AIAnalysisResponse
from app.services.ai_service import analyze_error
from app.services.email_service import email_service
from app.config import settings
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/errors", tags=["errors"])

async def validate_api_key(api_key: str, db: AsyncSession):
    """Validate API key and return project"""
    result = await db.execute(
        select(APIKey).where(APIKey.key == api_key, APIKey.is_active == True)
    )
    api_key_obj = result.scalar_one_or_none()
    
    if not api_key_obj:
        return None
    
    api_key_obj.last_used = datetime.utcnow()
    api_key_obj.error_count = (api_key_obj.error_count or 0) + 1
    await db.commit()
    
    project_result = await db.execute(
        select(Project).where(Project.id == api_key_obj.project_id)
    )
    return project_result.scalar_one_or_none()

async def analyze_error_background(error_id: int, db: AsyncSession):
    """Background task to analyze error with AI"""
    try:
        print(f"Starting analysis for error {error_id}")
        
        result = await db.execute(
            select(Error).where(Error.id == error_id)
        )
        error = result.scalar_one_or_none()
        
        if not error:
            print(f"Error {error_id} not found")
            return
        
        error_dict = {
            "id": error.id,
            "type": error.type,
            "message": error.message,
            "stack_trace": error.stack_trace,
            "severity": error.severity,
            "url": error.url,
            "environment": error.environment,
            "user_id": error.user_id,
            "user_email": error.user_email,
            "extra_data": error.extra_data or {},
        }
        
        analysis = await analyze_error(error_dict)
        
        ai_analysis = AIAnalysis(
            error_id=error_id,
            root_cause=analysis.get("root_cause"),
            suggested_fix=analysis.get("suggested_fix"),
            fix_explanation=analysis.get("fix_explanation"),
            confidence=analysis.get("confidence", 0.0),
            status="completed",
            analyzed_at=datetime.utcnow()
        )
        db.add(ai_analysis)
        error.has_ai_analysis = True
        await db.commit()
        print(f"Analysis stored for error {error_id}")
        
        if analysis.get('confidence', 0) > 0.7:
            try:
                project_result = await db.execute(
                    select(Project).where(Project.id == error.project_id)
                )
                project = project_result.scalar_one_or_none()
                
                if project:
                    user_result = await db.execute(
                        select(User).where(User.id == project.owner_id)
                    )
                    owner = user_result.scalar_one_or_none()
                    
                    if owner and hasattr(owner, 'email_notifications') and owner.email_notifications:
                        await email_service.send_error_alert(
                            to_email=owner.email,
                            error=error_dict,
                            analysis=analysis,
                            project_name=project.name,
                        )
                        print(f"Email notification sent to {owner.email}")
                    else:
                        print(f"User {owner.email if owner else 'Unknown'} has email notifications disabled")
                else:
                    print(f"No project found for error {error_id}")
                    
            except Exception as email_error:
                print(f"Email notification error: {email_error}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"Background analysis error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        
        try:
            ai_analysis = AIAnalysis(
                error_id=error_id,
                root_cause=f"Analysis failed: {str(e)}",
                suggested_fix="Please try again or check AI provider configuration",
                status="failed",
                analyzed_at=datetime.utcnow()
            )
            db.add(ai_analysis)
            await db.commit()
        except Exception as inner_e:
            print(f"Failed to store failure: {inner_e}")

@router.post("/")
async def ingest_error(
    error: ErrorCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Store error - accepts either JWT token or API key"""
    try:
        project = None
        user_id = None
        auth_method = None
        
        api_key_header = request.headers.get("X-API-Key") if request else None
        
        if api_key_header:
            project = await validate_api_key(api_key_header, db)
            if project:
                auth_method = "api_key"
        
        if not project:
            auth_header = request.headers.get("Authorization") if request else None
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                
                try:
                    user = await get_current_user(token, db)
                    if user:
                        project_result = await db.execute(
                            select(Project).where(Project.owner_id == user.id)
                        )
                        project = project_result.scalar_one_or_none()
                        if not project:
                            project = Project(
                                name="Default Project",
                                slug="default-project",
                                owner_id=user.id,
                                created_at=datetime.utcnow()
                            )
                            db.add(project)
                            await db.flush()
                        user_id = user.id
                        auth_method = "jwt"
                except Exception as e:
                    print(f"JWT validation failed: {e}")
        
        if not project:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing authentication"
            )
        
        db_error = Error(
            project_id=project.id,
            type=error.type,
            message=error.message,
            stack_trace=error.stack_trace,
            severity=error.severity,
            url=error.url,
            line_no=error.line_no,
            col_no=error.col_no,
            user_id=error.user_id,
            user_email=error.user_email,
            environment=error.environment or "production",
            release_version=error.release_version,
            extra_data=error.extra_data or {},
            status="unresolved",
            created_at=datetime.utcnow(),
            has_ai_analysis=False
        )
        db.add(db_error)
        await db.commit()
        await db.refresh(db_error)
        
        if settings.ai_enabled:
            background_tasks.add_task(analyze_error_background, db_error.id, db)
        
        return {
            "id": db_error.id,
            "accepted": True,
            "analyzing": settings.ai_enabled,
            "message": "Error captured successfully",
            "auth_method": auth_method,
            "project_id": project.id
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_errors(
    limit: int = 50,
    offset: int = 0,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all errors with filters"""
    try:
        query = select(Error).where(Error.project_id.in_(
            select(Project.id).where(Project.owner_id == current_user.id)
        ))
        
        if severity:
            query = query.where(Error.severity == severity)
        
        if status:
            query = query.where(Error.status == status)
        
        query = query.order_by(desc(Error.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        errors = result.scalars().all()
        
        count_query = select(func.count()).select_from(Error).where(Error.project_id.in_(
            select(Project.id).where(Project.owner_id == current_user.id)
        ))
        
        if severity:
            count_query = count_query.where(Error.severity == severity)
        
        if status:
            count_query = count_query.where(Error.status == status)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        result = []
        for error in errors:
            error_dict = {
                "id": error.id,
                "type": error.type,
                "message": error.message,
                "stack_trace": error.stack_trace,
                "severity": error.severity,
                "url": error.url,
                "line_no": error.line_no,
                "col_no": error.col_no,
                "user_id": error.user_id,
                "user_email": error.user_email,
                "environment": error.environment,
                "release_version": error.release_version,
                "extra_data": error.extra_data or {},
                "status": error.status,
                "has_ai_analysis": error.has_ai_analysis,
                "created_at": error.created_at,
                "fixed_at": error.fixed_at
            }
            result.append(error_dict)
        
        return {
            "errors": result,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{error_id}")
async def get_error(
    error_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a single error by ID"""
    try:
        result = await db.execute(
            select(Error).where(Error.id == error_id).where(
                Error.project_id.in_(
                    select(Project.id).where(Project.owner_id == current_user.id)
                )
            )
        )
        error = result.scalar_one_or_none()
        
        if not error:
            raise HTTPException(status_code=404, detail="Error not found")
        
        return {
            "id": error.id,
            "type": error.type,
            "message": error.message,
            "stack_trace": error.stack_trace,
            "severity": error.severity,
            "url": error.url,
            "line_no": error.line_no,
            "col_no": error.col_no,
            "user_id": error.user_id,
            "user_email": error.user_email,
            "environment": error.environment,
            "release_version": error.release_version,
            "extra_data": error.extra_data or {},
            "status": error.status,
            "has_ai_analysis": error.has_ai_analysis,
            "created_at": error.created_at,
            "fixed_at": error.fixed_at
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{error_id}/analysis", response_model=AIAnalysisResponse)
async def get_error_analysis(
    error_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get AI analysis for a specific error"""
    try:
        error_result = await db.execute(
            select(Error).where(Error.id == error_id).where(
                Error.project_id.in_(
                    select(Project.id).where(Project.owner_id == current_user.id)
                )
            )
        )
        error = error_result.scalar_one_or_none()
        
        if not error:
            raise HTTPException(status_code=404, detail="Error not found")
        
        result = await db.execute(
            select(AIAnalysis)
            .where(AIAnalysis.error_id == error_id)
            .order_by(desc(AIAnalysis.analyzed_at))
            .limit(1)
        )
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            return {
                "error_id": error_id,
                "status": "pending",
                "root_cause": None,
                "suggested_fix": None,
                "fix_explanation": None,
                "confidence": None,
                "analyzed_at": None
            }
        
        return {
            "error_id": analysis.error_id,
            "root_cause": analysis.root_cause,
            "suggested_fix": analysis.suggested_fix,
            "fix_explanation": analysis.fix_explanation,
            "confidence": analysis.confidence,
            "analyzed_at": analysis.analyzed_at,
            "status": analysis.status
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))