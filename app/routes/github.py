from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from app.database import get_db
from app.models import User, Error, AIAnalysis, Project
from app.utils.auth import get_current_active_user
from app.config import settings
from app.services.github_service import github_service

router = APIRouter(prefix="/api/v1/github", tags=["GitHub"])

@router.get("/config")
async def get_github_config(current_user: User = Depends(get_current_active_user)):
    return {
        "configured": bool(current_user.github_token and current_user.github_repo),
        "repo": current_user.github_repo or "Not configured",
        "has_token": bool(current_user.github_token),
    }

@router.post("/config")
async def update_github_config(
    config: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if config.get("token"):
        current_user.github_token = config.get("token")
    else:
        current_user.github_token = None
    
    if config.get("repo"):
        current_user.github_repo = config.get("repo")
    else:
        current_user.github_repo = None
    
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "message": "GitHub configuration updated",
        "configured": bool(current_user.github_token and current_user.github_repo),
        "repo": current_user.github_repo or "Not configured",
        "has_token": bool(current_user.github_token)
    }

@router.get("/auth")
async def github_auth(current_user: User = Depends(get_current_active_user)):
    """Return GitHub OAuth URL"""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=400, detail="GitHub OAuth not configured")
    
    redirect_uri = "https://franktech-api.franktechspace.dev/api/v1/github/callback"
    state = f"user_{current_user.id}"
    
    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo"
        f"&state={state}"
    )
    
    print(f"🔑 Auth URL: {auth_url}")  # Debug log
    return {"auth_url": auth_url}

@router.get("/callback")
async def github_callback(
    code: str,
    state: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback - redirects to dashboard"""
    try:
        # Extract user ID from state
        user_id = None
        if state and state.startswith("user_"):
            try:
                user_id = int(state.split("_")[1])
            except (IndexError, ValueError):
                pass
        
        if not user_id:
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?error=invalid_state"
            )
        
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?error=user_not_found"
            )
        
        # Exchange code for token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                }
            )
            data = response.json()
            token = data.get("access_token")
            
            if not token:
                return RedirectResponse(
                    url="https://monitor.franktechspace.dev/settings?error=token_failed"
                )
            
            # Get user's repos to get first one
            repos_response = await client.get(
                "https://api.github.com/user/repos",
                headers={"Authorization": f"token {token}"}
            )
            repos = repos_response.json()
            first_repo = repos[0]["full_name"] if repos else None
            
            # Save token and repo
            user.github_token = token
            user.github_repo = first_repo
            await db.commit()
            
            print(f"✅ GitHub connected for {user.email}")
            
            # Redirect to settings with success
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?github=connected"
            )
            
    except Exception as e:
        print(f"❌ Callback error: {e}")
        return RedirectResponse(
            url="https://monitor.franktechspace.dev/settings?error=failed"
        )

@router.get("/repos")
async def get_user_repos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/repos",
            headers={"Authorization": f"token {current_user.github_token}"}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch repositories")
        
        repos = response.json()
        return [{"name": repo["full_name"], "default": repo["default_branch"]} for repo in repos]

@router.post("/errors/{error_id}/create-pr")
async def create_fix_pr(
    error_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    if not current_user.github_repo:
        raise HTTPException(status_code=400, detail="GitHub repo not configured")
    
    # Get error and analysis
    error_result = await db.execute(
        select(Error).where(
            Error.id == error_id,
            Error.project_id.in_(
                select(Project.id).where(Project.owner_id == current_user.id)
            )
        )
    )
    error = error_result.scalar_one_or_none()
    if not error:
        raise HTTPException(status_code=404, detail="Error not found")
    
    analysis_result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.error_id == error_id)
        .order_by(AIAnalysis.analyzed_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    if not analysis or not analysis.suggested_fix:
        raise HTTPException(status_code=400, detail="No analysis or fix available")
    
    if analysis.fix_pr_url:
        return {
            "success": True,
            "pr_url": analysis.fix_pr_url,
            "message": "PR already exists"
        }
    
    result = await github_service.create_fix_pr(
        repo=current_user.github_repo,
        token=current_user.github_token,
        error={"id": error.id, "type": error.type, "message": error.message},
        analysis={
            "root_cause": analysis.root_cause,
            "suggested_fix": analysis.suggested_fix,
            "confidence": analysis.confidence,
        },
    )
    
    if result.get("success"):
        analysis.fix_pr_url = result.get("pr_url")
        await db.commit()
        return {
            "success": True,
            "pr_url": result.get("pr_url"),
            "pr_number": result.get("pr_number"),
            "message": "PR created successfully"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create PR: {result.get('error', 'Unknown error')}"
        )