import httpx
import json
from typing import Optional
from app.config import settings

class GitHubService:
    def __init__(self):
        self.api_url = "https://api.github.com"
        self.headers = {}
        
        # Check for GitHub token
        if settings.GITHUB_TOKEN:
            self.headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
        else:
            print("⚠️ GITHUB_TOKEN not set. GitHub features disabled.")

    async def create_pull_request(
        self,
        repo: str,
        token: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        file_changes: list = None,
    ) -> dict:
        """
        Create a pull request with file changes
        
        Args:
            repo: GitHub repo in format "owner/repo"
            token: User's GitHub token for authentication
            title: PR title
            body: PR description
            head_branch: Branch name with changes
            base_branch: Target branch (main/master)
            file_changes: List of dicts with {"path": "file.py", "content": "new content"}
        """
        if not token:
            return {"error": "GitHub token not provided", "success": False}
        
        # Use the token passed in (user's token)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        owner, repo_name = repo.split("/")
        
        # 1. Get the default branch SHA
        repo_info = await self._get_repo_info(owner, repo_name, headers)
        base_sha = repo_info["default_branch_sha"]
        
        # 2. Create a new branch
        branch_ref = await self._create_branch(
            owner, repo_name, head_branch, base_sha, headers
        )
        if not branch_ref:
            return {"error": "Failed to create branch", "success": False}
        
        # 3. Commit file changes
        if file_changes:
            commit = await self._create_commit(
                owner, repo_name, head_branch, file_changes, title, headers
            )
            if not commit:
                return {"error": "Failed to commit changes", "success": False}
        
        # 4. Create pull request
        pr = await self._create_pr(
            owner, repo_name, title, body, head_branch, base_branch, headers
        )
        
        return {
            "success": True,
            "pr_url": pr.get("html_url"),
            "pr_number": pr.get("number"),
            "branch": head_branch,
        }

    async def _get_repo_info(self, owner: str, repo: str, headers: dict) -> dict:
        """Get repository information"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/repos/{owner}/{repo}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                default_branch = data.get("default_branch", "main")
                branch_response = await client.get(
                    f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{default_branch}",
                    headers=headers
                )
                branch_data = branch_response.json()
                return {
                    "default_branch": default_branch,
                    "default_branch_sha": branch_data["object"]["sha"],
                }
            return {"error": "Failed to get repo info"}

    async def _create_branch(self, owner: str, repo: str, branch_name: str, base_sha: str, headers: dict) -> bool:
        """Create a new branch"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/repos/{owner}/{repo}/git/refs",
                headers=headers,
                json={
                    "ref": f"refs/heads/{branch_name}",
                    "sha": base_sha
                }
            )
            return response.status_code == 201

    async def _create_commit(self, owner: str, repo: str, branch: str, file_changes: list, message: str, headers: dict) -> bool:
        """Create a commit with file changes"""
        # Get current tree
        async with httpx.AsyncClient() as client:
            ref_response = await client.get(
                f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{branch}",
                headers=headers
            )
            if ref_response.status_code != 200:
                return False
            
            current_sha = ref_response.json()["object"]["sha"]
            
            # Create blobs for each file
            tree_items = []
            for change in file_changes:
                # Create blob
                blob_response = await client.post(
                    f"{self.api_url}/repos/{owner}/{repo}/git/blobs",
                    headers=headers,
                    json={
                        "content": change["content"],
                        "encoding": "utf-8"
                    }
                )
                if blob_response.status_code != 201:
                    return False
                
                tree_items.append({
                    "path": change["path"],
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_response.json()["sha"]
                })
            
            # Create tree
            tree_response = await client.post(
                f"{self.api_url}/repos/{owner}/{repo}/git/trees",
                headers=headers,
                json={
                    "base_tree": current_sha,
                    "tree": tree_items
                }
            )
            if tree_response.status_code != 201:
                return False
            
            tree_sha = tree_response.json()["sha"]
            
            # Create commit
            commit_response = await client.post(
                f"{self.api_url}/repos/{owner}/{repo}/git/commits",
                headers=headers,
                json={
                    "message": message,
                    "tree": tree_sha,
                    "parents": [current_sha]
                }
            )
            if commit_response.status_code != 201:
                return False
            
            commit_sha = commit_response.json()["sha"]
            
            # Update branch reference
            update_response = await client.patch(
                f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{branch}",
                headers=headers,
                json={"sha": commit_sha}
            )
            return update_response.status_code == 200

    async def _create_pr(self, owner: str, repo: str, title: str, body: str, head: str, base: str, headers: dict) -> dict:
        """Create a pull request"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/repos/{owner}/{repo}/pulls",
                headers=headers,
                json={
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                }
            )
            if response.status_code == 201:
                return response.json()
            return {"error": "Failed to create PR", "status_code": response.status_code}

    async def create_fix_pr(
        self,
        repo: str,
        token: str,  
        error: dict,
        analysis: dict,
        code_file: Optional[str] = None,
        code_content: Optional[str] = None,
        fix_content: Optional[str] = None,
    ) -> dict:
        """
        Create a PR with an AI-generated fix using user's token
        """
        # Use the token passed in (user's token)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Generate branch name
        branch_name = f"fix/franktech-{error.get('id', 'error')[:8]}"
        
        # Build PR title
        title = f"Fix: {error.get('type', 'Error')} - {error.get('message', '')[:50]}"
        
        # Build PR body
        body = f"""
## 🤖 AI-Generated Fix

**Error Type:** {error.get('type', 'Unknown')}
**Error Message:** {error.get('message', 'Unknown')}
**Root Cause:** {analysis.get('root_cause', 'Not provided')}
**Confidence:** {int(analysis.get('confidence', 0) * 100)}%

### Suggested Fix
{analysis.get('suggested_fix', 'No fix provided')}

---
*This PR was automatically created by [FrankTech Intelligence](https://monitor.franktechspace.dev).*
*Review it carefully before merging.*
"""
        
        # Prepare file changes
        file_changes = []
        if code_file and fix_content:
            file_changes.append({
                "path": code_file,
                "content": fix_content
            })
        
        # Create PR
        return await self.create_pull_request(
            repo=repo,
            token=token,  
            title=title,
            body=body,
            head_branch=branch_name,
            base_branch="main",
            file_changes=file_changes
        )

# Create singleton instance
github_service = GitHubService()