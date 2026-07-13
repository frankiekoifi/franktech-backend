import httpx
from typing import Optional, List, Dict, Any

class GitHubService:
    def __init__(self):
        self.api_url = "https://api.github.com"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange OAuth code for access token"""
        from app.config import settings
        
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
            return response.json()
    
    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get GitHub user info"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/user",
                headers={"Authorization": f"token {token}"}
            )
            return response.json()
    
    async def get_repositories(self, token: str) -> List[Dict[str, Any]]:
        """Get user's repositories"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/user/repos",
                headers={"Authorization": f"token {token}"}
            )
            if response.status_code != 200:
                return []
            
            repos = response.json()
            return [
                {
                    "name": repo["full_name"],
                    "default_branch": repo["default_branch"]
                }
                for repo in repos
            ]
    
    async def create_fix_pr(
        self,
        repo: str,
        token: str,
        username: str,
        error: Dict,
        analysis: Dict,
    ) -> Dict[str, Any]:
        """Create a PR with the fix"""
        owner, repo_name = repo.split("/")
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        branch_name = f"fix/franktech-{error.get('id', 'error')}"
        title = f"Fix: {error.get('type', 'Error')} - {error.get('message', '')[:50]}"
        body = f"""
## 🤖 AI-Generated Fix

**Error Type:** {error.get('type', 'Unknown')}
**Error Message:** {error.get('message', 'Unknown')}
**Root Cause:** {analysis.get('root_cause', 'Not provided')}
**Confidence:** {int(analysis.get('confidence', 0) * 100)}%

### Suggested Fix
{analysis.get('suggested_fix', 'No fix provided')}


---
*This PR was automatically created by FrankTech Intelligence.*
"""
        
        async with httpx.AsyncClient() as client:
            # Get default branch
            repo_info = await client.get(
                f"{self.api_url}/repos/{owner}/{repo_name}",
                headers=headers
            )
            default_branch = repo_info.json().get("default_branch", "main")
            
            # Get branch SHA
            branch_info = await client.get(
                f"{self.api_url}/repos/{owner}/{repo_name}/git/refs/heads/{default_branch}",
                headers=headers
            )
            base_sha = branch_info.json()["object"]["sha"]
            
            # Create new branch
            await client.post(
                f"{self.api_url}/repos/{owner}/{repo_name}/git/refs",
                headers=headers,
                json={
                    "ref": f"refs/heads/{branch_name}",
                    "sha": base_sha
                }
            )
            
            # Create PR
            pr_response = await client.post(
                f"{self.api_url}/repos/{owner}/{repo_name}/pulls",
                headers=headers,
                json={
                    "title": title,
                    "body": body,
                    "head": branch_name,
                    "base": default_branch,
                }
            )
            
            if pr_response.status_code != 201:
                return {"success": False, "error": "Failed to create PR"}
            
            pr_data = pr_response.json()
            return {
                "success": True,
                "pr_url": pr_data.get("html_url"),
                "pr_number": pr_data.get("number"),
            }