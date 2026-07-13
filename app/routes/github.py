from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from datetime import datetime
from app.database import get_db
from app.models import User, Error, AIAnalysis, Project
from app.utils.auth import get_current_active_user
from app.config import settings
from app.services.github_service import GitHubService

router = APIRouter(prefix="/api/v1/github", tags=["GitHub"])
github_service = GitHubService()

# ============ STATUS ============
@router.get("/status")
async def get_status(current_user: User = Depends(get_current_active_user)):
    """Check GitHub connection status"""
    return {
        "connected": bool(current_user.github_token),
        "username": current_user.github_username,
        "repo": current_user.github_repo,
        "connected_at": current_user.github_connected_at
    }

# ============ CONNECT (OAuth Flow) ============
@router.get("/connect")
async def github_connect(current_user: User = Depends(get_current_active_user)):
    """Initiate GitHub OAuth - redirects to GitHub"""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=400, detail="GitHub OAuth not configured")
    
    state = f"user_{current_user.id}"
    redirect_uri = "https://franktech-api.franktechspace.dev/api/v1/github/callback"
    
    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo"
        f"&state={state}"
    )
    
    # Redirect to GitHub
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def github_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """GitHub OAuth callback"""
    try:
        # Extract user ID
        user_id = None
        if state.startswith("user_"):
            user_id = int(state.split("_")[1])
        
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
        token_data = await github_service.exchange_code_for_token(code)
        
        if not token_data.get("access_token"):
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?error=token_failed"
            )
        
        access_token = token_data["access_token"]
        
        # Get user info
        github_user = await github_service.get_user_info(access_token)
        
        # Save to database
        user.github_token = access_token
        user.github_username = github_user.get("login")
        user.github_connected_at = datetime.utcnow()
        await db.commit()
        
        return RedirectResponse(
            url="https://monitor.franktechspace.dev/settings?github=connected"
        )
        
    except Exception as e:
        print(f"❌ Callback error: {e}")
        return RedirectResponse(
            url="https://monitor.franktechspace.dev/settings?error=failed"
        )

# ============ REPOSITORIES ============
@router.get("/repos")
async def get_repos(current_user: User = Depends(get_current_active_user)):
    """Get user's GitHub repositories"""
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    repos = await github_service.get_repositories(current_user.github_token)
    return repos

@router.post("/repository")
async def set_repository(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Select repository for PRs"""
    repo = data.get("repo")
    if not repo:
        raise HTTPException(status_code=400, detail="Repository name required")
    
    current_user.github_repo = repo
    await db.commit()
    
    return {"success": True, "repo": repo}

# ============ DISCONNECT ============
@router.post("/disconnect")
async def disconnect(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Disconnect GitHub account"""
    current_user.github_token = None
    current_user.github_username = None
    current_user.github_repo = None
    current_user.github_connected_at = None
    await db.commit()
    
    return {"success": True}

# ============ CREATE PR ============
@router.post("/errors/{error_id}/create-pr")
async def create_pr(
    error_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a PR with AI-generated fix"""
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    
    if not current_user.github_repo:
        raise HTTPException(status_code=400, detail="Repository not selected")
    
    # Get error
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
    
    # Get analysis
    analysis_result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.error_id == error_id)
        .order_by(AIAnalysis.analyzed_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    if not analysis or not analysis.suggested_fix:
        raise HTTPException(status_code=400, detail="No analysis available")
    
    if analysis.fix_pr_url:
        return {"success": True, "pr_url": analysis.fix_pr_url, "message": "PR already exists"}
    
    # Create PR
    result = await github_service.create_fix_pr(
        repo=current_user.github_repo,
        token=current_user.github_token,
        username=current_user.github_username,
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
        return {"success": True, "pr_url": result.get("pr_url"), "pr_number": result.get("pr_number")}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create PR"))