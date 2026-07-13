from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import json
import logging
from app.database import get_db
from app.models import User, Error, AIAnalysis, Project
from app.utils.auth import get_current_active_user
from app.config import settings
from app.services.github_service import github_service

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["GitHub"])

@router.get("/config")
async def get_github_config(
    current_user: User = Depends(get_current_active_user)
):
    """Check GitHub configuration for the current user"""
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
    """Update GitHub configuration for the current user"""
    
    token_value = config.get("token")
    if token_value and token_value.strip():
        current_user.github_token = token_value
    else:
        current_user.github_token = None
    
    repo_value = config.get("repo")
    if repo_value and repo_value.strip():
        current_user.github_repo = repo_value
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
async def github_auth(
    current_user: User = Depends(get_current_active_user)
):
    """Redirect to GitHub OAuth with user token in state"""
    if not settings.GITHUB_CLIENT_ID:
        logger.error("GITHUB_CLIENT_ID not configured")
        raise HTTPException(status_code=400, detail="GitHub OAuth not configured")
    
    if not settings.GITHUB_CLIENT_SECRET:
        logger.error("GITHUB_CLIENT_SECRET not configured")
        raise HTTPException(status_code=400, detail="GitHub OAuth not configured")
    
    state = f"user_{current_user.id}"
    redirect_uri = "https://franktech-api.franktechspace.dev/api/v1/github/callback"
    
    # ✅ Build the complete auth URL with all parameters
    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo"
        f"&state={state}"
    )
    
    logger.info(f"🔑 Generated OAuth URL for user {current_user.id}")
    logger.info(f"🔑 Redirect URI: {redirect_uri}")
    
    return {"auth_url": auth_url}

@router.get("/callback")
async def github_callback(
    code: str,
    state: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback - redirects back to dashboard"""
    try:
        logger.info(f"📥 OAuth callback received with state: {state}")
        
        user_id = None
        if state and state.startswith("user_"):
            try:
                user_id = int(state.split("_")[1])
                logger.info(f"👤 Extracted user ID: {user_id}")
            except (IndexError, ValueError) as e:
                logger.error(f"❌ Failed to parse state: {e}")
                pass
        
        if not user_id:
            logger.error("❌ No user_id found in state")
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?error=github_invalid_state"
            )
        
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            logger.error(f"❌ User {user_id} not found")
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?error=github_user_not_found"
            )
        
        logger.info(f"👤 Found user: {user.email}")
        
        async with httpx.AsyncClient() as client:
            # Exchange code for token
            logger.info("🔄 Exchanging code for token...")
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                }
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to get token: {response.status_code} - {response.text}")
                return RedirectResponse(
                    url="https://monitor.franktechspace.dev/settings?error=github_token_failed"
                )
            
            data = response.json()
            token = data.get("access_token")
            
            if not token:
                logger.error("❌ No access_token in response")
                return RedirectResponse(
                    url="https://monitor.franktechspace.dev/settings?error=github_token_failed"
                )
            
            logger.info("✅ Access token received")
            
            # Get user's repos
            logger.info("🔄 Fetching user repositories...")
            repos_response = await client.get(
                "https://api.github.com/user/repos",
                headers={"Authorization": f"token {token}"}
            )
            
            if repos_response.status_code != 200:
                logger.error(f"❌ Failed to fetch repos: {repos_response.status_code}")
                first_repo = None
            else:
                repos = repos_response.json()
                first_repo = repos[0]["full_name"] if repos else None
                logger.info(f"📁 Found {len(repos)} repositories, first: {first_repo}")
            
            # Save token and repo
            user.github_token = token
            user.github_repo = first_repo
            await db.commit()
            
            logger.info(f"✅ GitHub token saved for user: {user.email}")
            
            return RedirectResponse(
                url="https://monitor.franktechspace.dev/settings?github=connected"
            )
            
    except Exception as e:
        logger.error(f"❌ GitHub callback error: {e}", exc_info=True)
        return RedirectResponse(
            url="https://monitor.franktechspace.dev/settings?error=github_failed"
        )

@router.get("/repos")
async def get_user_repos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of user's GitHub repositories"""
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
    """Create a GitHub PR with the AI-generated fix"""
    
    if not current_user.github_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub not connected. Please connect your GitHub account in Settings."
        )
    
    if not current_user.github_repo:
        raise HTTPException(
            status_code=400,
            detail="GitHub repo not configured. Please select a repo in Settings."
        )
    
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
        raise HTTPException(
            status_code=400,
            detail="No AI analysis or fix available for this error"
        )
    
    if analysis.fix_pr_url:
        return {
            "success": True,
            "pr_url": analysis.fix_pr_url,
            "message": "PR already exists for this error"
        }
    
    result = await github_service.create_fix_pr(
        repo=current_user.github_repo,
        token=current_user.github_token,
        error={
            "id": error.id,
            "type": error.type,
            "message": error.message,
        },
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
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"❌ Failed to create PR: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create PR: {error_msg}"
        )