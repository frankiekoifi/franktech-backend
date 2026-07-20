import httpx
import time
import base64
import asyncio
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse


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

            if response.status_code != 200:
                return {"error": "Failed to exchange code", "status_code": response.status_code}

            return response.json()

    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get GitHub user info"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/user",
                headers={"Authorization": f"token {token}"}
            )

            if response.status_code != 200:
                return {"error": "Failed to get user info", "status_code": response.status_code}

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

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        token: str,
        branch: str = "main"
    ) -> Optional[Dict]:
        """Get file content from GitHub with retry support"""
        headers = {"Authorization": f"token {token}"}

        async def _fetch_file():
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/repos/{owner}/{repo}/contents/{path}",
                    headers=headers,
                    params={"ref": branch}
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                if data.get("encoding") == "base64":
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    return {
                        "content": content,
                        "sha": data.get("sha"),
                        "path": path
                    }
                return None

        # Wrap with retry logic for consistency
        try:
            return await self._call_with_retry(_fetch_file)
        except Exception as e:
            print(f"⚠️ Failed to fetch file content after retries: {e}")
            return None

    def _resolve_file_path(self, file_path: str) -> str:
        """
        Resolve and clean up file path.

        - Removes domain from URLs
        - Strips leading slashes
        - Returns a clean relative path
        """
        if not file_path:
            return "fix_suggestion.txt"

        # If it's a URL, extract the path
        if file_path.startswith(('http://', 'https://')):
            parsed = urlparse(file_path)
            file_path = parsed.path

        # Remove leading slash
        file_path = file_path.lstrip('/')

        # If still empty, use default
        if not file_path:
            file_path = "fix_suggestion.txt"

        return file_path

    def _parse_diff(self, diff_text: str) -> List[Dict[str, Any]]:
        """
        Parse a unified diff format into structured changes.

        Returns a list of changes with:
        - file_path: The file being modified
        - hunks: List of hunks with line numbers and changes
        """
        changes = []
        current_file = None
        current_hunk = None
        current_changes = []

        lines = diff_text.split('\n')

        for line in lines:
            # File header: --- a/file.py
            if line.startswith('--- a/'):
                if current_file and current_hunk:
                    current_hunk['changes'] = current_changes
                    current_file['hunks'].append(current_hunk)
                    changes.append(current_file)

                current_file = {
                    'file_path': line[6:],  # Remove '--- a/'
                    'hunks': []
                }
                current_changes = []
                current_hunk = None

            # Hunk header: @@ -1,5 +1,5 @@
            elif line.startswith('@@'):
                if current_hunk and current_changes:
                    current_hunk['changes'] = current_changes
                    if current_file:
                        current_file['hunks'].append(current_hunk)

                # Parse line numbers
                match = re.match(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
                if match and current_file:
                    current_hunk = {
                        'old_start': int(match.group(1)),
                        'old_count': int(match.group(2)),
                        'new_start': int(match.group(3)),
                        'new_count': int(match.group(4)),
                        'changes': []
                    }
                    current_changes = []

            # Line changes
            elif line.startswith('-'):
                current_changes.append({
                    'type': 'delete',
                    'content': line[1:],
                    'old_line': current_hunk['old_start'] + len(
                        [c for c in current_changes if c['type'] in ['delete', 'context']]
                    ) if current_hunk else None
                })
            elif line.startswith('+'):
                current_changes.append({
                    'type': 'insert',
                    'content': line[1:],
                    'new_line': current_hunk['new_start'] + len(
                        [c for c in current_changes if c['type'] in ['insert', 'context']]
                    ) if current_hunk else None
                })
            elif line.startswith(' '):
                current_changes.append({
                    'type': 'context',
                    'content': line[1:]
                })

        # Add the last file
        if current_file and current_hunk:
            current_hunk['changes'] = current_changes
            current_file['hunks'].append(current_hunk)
            changes.append(current_file)

        return changes

    def _apply_diff(self, current_content: str, diff_text: str) -> str:
        """
        Apply a unified diff to the current content.

        This properly parses the diff and applies changes to the correct lines.
        """
        if not diff_text:
            return current_content

        # Check if it's a unified diff format
        if '@@' in diff_text and '---' in diff_text:
            changes = self._parse_diff(diff_text)

            if not changes:
                # Fallback to append if parsing fails
                return current_content + "\n\n# AI Suggested Fix\n" + diff_text

            # Apply changes for each file (we'll handle the first file only for now)
            for file_change in changes:
                if not file_change['hunks']:
                    continue

                lines = current_content.split('\n')
                new_lines = lines.copy()
                offset = 0

                # Process each hunk in reverse order to handle line number changes
                for hunk in reversed(file_change['hunks']):
                    old_start = hunk['old_start'] - 1  # Convert to 0-index

                    # Find where to apply the hunk
                    old_lines = []
                    new_lines_for_hunk = []

                    for change in hunk['changes']:
                        if change['type'] == 'delete':
                            old_lines.append(change['content'])
                        elif change['type'] == 'insert':
                            new_lines_for_hunk.append(change['content'])
                        elif change['type'] == 'context':
                            old_lines.append(change['content'])
                            new_lines_for_hunk.append(change['content'])

                    # Apply the hunk
                    start_idx = old_start + offset
                    end_idx = start_idx + len(old_lines)

                    # Ensure we're within bounds
                    if start_idx < 0:
                        start_idx = 0
                    if end_idx > len(new_lines):
                        end_idx = len(new_lines)

                    # Replace the lines
                    new_lines[start_idx:end_idx] = new_lines_for_hunk
                    offset += len(new_lines_for_hunk) - len(old_lines)

                return '\n'.join(new_lines)

        # If not a diff or parsing failed, append
        return current_content + "\n\n# AI Suggested Fix\n" + diff_text

    def _apply_suggested_fix(self, current_content: str, suggested_fix: str) -> str:
        """
        Apply the suggested fix to the current file content.

        Now properly applies diffs instead of just appending.
        """
        if not current_content:
            return suggested_fix

        # Check if fix is already applied
        if "AI Suggested Fix" in current_content:
            return current_content

        # Try to apply as a diff
        try:
            return self._apply_diff(current_content, suggested_fix)
        except Exception as e:
            print(f"⚠️ Diff application failed, falling back to append: {e}")
            # Fallback to append if diff application fails
            return current_content + "\n\n# AI Suggested Fix\n" + suggested_fix

    async def _call_with_retry(
        self,
        func,
        max_retries: int = 3,
        delay: int = 1
    ):
        """
        Call a function with retry logic for transient errors.
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await func()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = delay * (attempt + 1)
                    print(f"⚠️ Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                # Don't retry on non-transient errors
                raise e

        raise last_error

    async def create_fix_pr(
        self,
        repo: str,
        token: str,
        username: str,
        error: Dict,
        analysis: Dict,
        log_action=None,
        db=None,
        user_id: Optional[int] = None,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a PR with the fix.

        Args:
            repo: Repository name (e.g., "owner/repo")
            token: GitHub access token
            username: GitHub username
            error: Error details
            analysis: AI analysis results (with suggested_fix)
            log_action: Optional audit logging function
            db: Optional database session
            user_id: Optional user ID for audit logging
            file_path: Path to the file that needs fixing (required)
        """
        owner, repo_name = repo.split("/")

        # Resolve file path
        if not file_path:
            file_path = error.get('file_path', error.get('url', 'fix_suggestion.txt'))

        file_path = self._resolve_file_path(file_path)

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Unique branch name with timestamp
        timestamp = int(time.time())
        error_id = error.get('id', 'error')
        branch_name = f"fix/franktech-{error_id}-{timestamp}"
        title = f"Fix: {error.get('type', 'Error')} - {error.get('message', '')[:50]}"

        # Truncate title if too long
        if len(title) > 72:
            title = title[:69] + "..."

        # Get the suggested fix from analysis
        suggested_fix = analysis.get('suggested_fix', '')

        if not suggested_fix:
            await self._log_audit(
                log_action,
                db,
                user_id,
                error.get('project_id', 0),
                "pr_failed",
                {
                    "repo": repo,
                    "error_id": error_id,
                    "step": "no_fix_provided",
                    "error": "No suggested_fix found in analysis"
                }
            )
            return {"success": False, "error": "No suggested fix provided"}

        body = f"""
## 🤖 AI-Generated Fix

**Error ID:** {error_id}
**Error Type:** {error.get('type', 'Unknown')}
**Error Message:** {error.get('message', 'Unknown')}
**Root Cause:** {analysis.get('root_cause', 'Not provided')}
**Confidence:** {int(analysis.get('confidence', 0) * 100)}%
**File:** {file_path}

### Suggested Fix
```diff
{suggested_fix}
Explanation
{analysis.get('fix_explanation', 'No explanation provided')}

This PR was automatically created by FrankTech Intelligence.
"""

        async with httpx.AsyncClient() as client:
            try:
                # --- Step 1: Get repository info ---
                async def get_repo_info():
                    return await client.get(
                        f"{self.api_url}/repos/{owner}/{repo_name}",
                        headers=headers
                    )

                repo_info = await self._call_with_retry(get_repo_info)
                if repo_info.status_code != 200:
                    await self._log_audit(
                        log_action,
                        db,
                        user_id,
                        error.get('project_id', 0),
                        "pr_failed",
                        {
                            "repo": repo,
                            "error_id": error_id,
                            "step": "get_repo_info",
                            "status_code": repo_info.status_code
                        }
                    )
                    return {"success": False, "error": "Failed to fetch repository info"}

                default_branch = repo_info.json().get("default_branch", "main")

                # --- Step 2: Get base branch SHA ---
                async def get_branch_info():
                    return await client.get(
                        f"{self.api_url}/repos/{owner}/{repo_name}/git/refs/heads/{default_branch}",
                        headers=headers
                    )

                branch_info = await self._call_with_retry(get_branch_info)
                if branch_info.status_code != 200:
                    await self._log_audit(
                        log_action,
                        db,
                        user_id,
                        error.get('project_id', 0),
                        "pr_failed",
                        {
                            "repo": repo,
                            "error_id": error_id,
                            "step": "get_branch_info",
                            "status_code": branch_info.status_code
                        }
                    )
                    return {"success": False, "error": "Failed to fetch branch information"}

                base_sha = branch_info.json()["object"]["sha"]

                # --- Step 3: Get the current file content (with retry) ---
                file_info = await self.get_file_content(
                    owner,
                    repo_name,
                    file_path,
                    token,
                    default_branch
                )

                if file_info:
                    # File exists — apply fix
                    current_content = file_info["content"]

                    # Apply the suggested fix using diff parser
                    new_content = self._apply_suggested_fix(current_content, suggested_fix)

                    # Create a new blob with the updated content
                    async def create_blob():
                        return await client.post(
                            f"{self.api_url}/repos/{owner}/{repo_name}/git/blobs",
                            headers=headers,
                            json={
                                "content": new_content,
                                "encoding": "utf-8"
                            }
                        )

                    blob_response = await self._call_with_retry(create_blob)
                    if blob_response.status_code != 201:
                        await self._log_audit(
                            log_action,
                            db,
                            user_id,
                            error.get('project_id', 0),
                            "pr_failed",
                            {
                                "repo": repo,
                                "error_id": error_id,
                                "step": "create_blob",
                                "status_code": blob_response.status_code
                            }
                        )
                        return {"success": False, "error": "Failed to create blob"}

                    blob_sha = blob_response.json()["sha"]

                    # Get the tree SHA of the base commit
                    async def get_commit_info():
                        return await client.get(
                            f"{self.api_url}/repos/{owner}/{repo_name}/git/commits/{base_sha}",
                            headers=headers
                        )

                    commit_info = await self._call_with_retry(get_commit_info)
                    if commit_info.status_code != 200:
                        await self._log_audit(
                            log_action,
                            db,
                            user_id,
                            error.get('project_id', 0),
                            "pr_failed",
                            {
                                "repo": repo,
                                "error_id": error_id,
                                "step": "get_commit_info",
                                "status_code": commit_info.status_code
                            }
                        )
                        return {"success": False, "error": "Failed to get commit info"}

                    tree_sha = commit_info.json()["tree"]["sha"]

                    # Create a new tree with the updated file
                    async def create_tree():
                        return await client.post(
                            f"{self.api_url}/repos/{owner}/{repo_name}/git/trees",
                            headers=headers,
                            json={
                                "base_tree": tree_sha,
                                "tree": [
                                    {
                                        "path": file_path,
                                        "mode": "100644",
                                        "type": "blob",
                                        "sha": blob_sha
                                    }
                                ]
                            }
                        )

                    tree_response = await self._call_with_retry(create_tree)
                    if tree_response.status_code != 201:
                        await self._log_audit(
                            log_action,
                            db,
                            user_id,
                            error.get('project_id', 0),
                            "pr_failed",
                            {
                                "repo": repo,
                                "error_id": error_id,
                                "step": "create_tree",
                                "status_code": tree_response.status_code
                            }
                        )
                        return {"success": False, "error": "Failed to create tree"}

                    new_tree_sha = tree_response.json()["sha"]

                else:
                    # --- File doesn't exist — create it ---
                    async def create_blob_new_file():
                        return await client.post(
                            f"{self.api_url}/repos/{owner}/{repo_name}/git/blobs",
                            headers=headers,
                            json={
                                "content": f"# AI Suggested Fix\n# Error ID: {error_id}\n\n{suggested_fix}",
                                "encoding": "utf-8"
                            }
                        )

                    blob_response = await self._call_with_retry(create_blob_new_file)
                    if blob_response.status_code != 201:
                        await self._log_audit(
                            log_action,
                            db,
                            user_id,
                            error.get('project_id', 0),
                            "pr_failed",
                            {
                                "repo": repo,
                                "error_id": error_id,
                                "step": "create_blob_new_file",
                                "status_code": blob_response.status_code
                            }
                        )
                        return {"success": False, "error": "Failed to create blob for new file"}

                    blob_sha = blob_response.json()["sha"]

                    async def get_commit_info_new_file():
                        return await client.get(
                            f"{self.api_url}/repos/{owner}/{repo_name}/git/commits/{base_sha}",
                            headers=headers
                        )

                    commit_info = await self._call_with_retry(get_commit_info_new_file)
                    tree_sha = commit_info.json()["tree"]["sha"]

                    async def create_tree_new_file():
                        return await client.post(
                            f"{self.api_url}/repos/{owner}/{repo_name}/git/trees",
                            headers=headers,
                            json={
                                "base_tree": tree_sha,
                                "tree": [
                                    {
                                        "path": file_path,
                                        "mode": "100644",
                                        "type": "blob",
                                        "sha": blob_sha
                                    }
                                ]
                            }
                        )

                    tree_response = await self._call_with_retry(create_tree_new_file)
                    if tree_response.status_code != 201:
                        await self._log_audit(
                            log_action,
                            db,
                            user_id,
                            error.get('project_id', 0),
                            "pr_failed",
                            {
                                "repo": repo,
                                "error_id": error_id,
                                "step": "create_tree_new_file",
                                "status_code": tree_response.status_code
                            }
                        )
                        return {"success": False, "error": "Failed to create tree for new file"}

                    new_tree_sha = tree_response.json()["sha"]

                # --- Step 3b: Create commit with the fix ---
                commit_message = (
                    f"🤖 Fix: {error.get('type', 'Error')} (ID: {error_id})\n\n"
                    f"{analysis.get('root_cause', '')[:200]}\n\n"
                    f"Generated by FrankTech Intelligence"
                )

                async def create_fix_commit():
                    return await client.post(
                        f"{self.api_url}/repos/{owner}/{repo_name}/git/commits",
                        headers=headers,
                        json={
                            "message": commit_message,
                            "tree": new_tree_sha,
                            "parents": [base_sha]
                        }
                    )

                commit_response = await self._call_with_retry(create_fix_commit)
                if commit_response.status_code != 201:
                    await self._log_audit(
                        log_action,
                        db,
                        user_id,
                        error.get('project_id', 0),
                        "pr_failed",
                        {
                            "repo": repo,
                            "error_id": error_id,
                            "step": "create_fix_commit",
                            "status_code": commit_response.status_code
                        }
                    )
                    return {"success": False, "error": "Failed to create commit"}

                commit_sha = commit_response.json()["sha"]

                # --- Step 4: Create new branch ---
                async def create_branch():
                    return await client.post(
                        f"{self.api_url}/repos/{owner}/{repo_name}/git/refs",
                        headers=headers,
                        json={
                            "ref": f"refs/heads/{branch_name}",
                            "sha": commit_sha
                        }
                    )

                branch_response = await self._call_with_retry(create_branch)
                if branch_response.status_code not in [200, 201]:
                    await self._log_audit(
                        log_action,
                        db,
                        user_id,
                        error.get('project_id', 0),
                        "pr_failed",
                        {
                            "repo": repo,
                            "error_id": error_id,
                            "step": "create_branch",
                            "status_code": branch_response.status_code
                        }
                    )
                    return {"success": False, "error": "Failed to create branch"}

                # --- Step 5: Create PR ---
                async def create_pr():
                    return await client.post(
                        f"{self.api_url}/repos/{owner}/{repo_name}/pulls",
                        headers=headers,
                        json={
                            "title": title,
                            "body": body,
                            "head": branch_name,
                            "base": default_branch,
                        }
                    )

                pr_response = await self._call_with_retry(create_pr)

                if pr_response.status_code != 201:
                    await self._log_audit(
                        log_action,
                        db,
                        user_id,
                        error.get('project_id', 0),
                        "pr_failed",
                        {
                            "repo": repo,
                            "error_id": error_id,
                            "step": "create_pr",
                            "status_code": pr_response.status_code,
                            "error": pr_response.text
                        }
                    )
                    return {"success": False, "error": "Failed to create PR"}

                pr_data = pr_response.json()

                # --- Step 6: Log success ---
                await self._log_audit(
                    log_action,
                    db,
                    user_id,
                    error.get('project_id', 0),
                    "pr_created",
                    {
                        "repo": repo,
                        "error_id": error_id,
                        "file_path": file_path,
                        "pr_number": pr_data.get("number"),
                        "pr_url": pr_data.get("html_url"),
                        "branch": branch_name,
                        "commit_sha": commit_sha,
                        "confidence": analysis.get("confidence", 0)
                    }
                )

                return {
                    "success": True,
                    "pr_url": pr_data.get("html_url"),
                    "pr_number": pr_data.get("number"),
                    "branch_name": branch_name,
                    "commit_sha": commit_sha,
                    "file_path": file_path
                }

            except Exception as e:
                await self._log_audit(
                    log_action,
                    db,
                    user_id,
                    error.get('project_id', 0),
                    "pr_failed",
                    {
                        "repo": repo,
                        "error_id": error_id,
                        "step": "exception",
                        "error": str(e)
                    }
                )
                return {"success": False, "error": str(e)}

    async def _log_audit(
        self,
        log_action,
        db,
        user_id,
        project_id,
        action,
        details
    ):
        """Internal helper for audit logging"""
        if log_action and db:
            try:
                await log_action(
                    db=db,
                    user_id=user_id,
                    project_id=project_id,
                    action=action,
                    details=details
                )
            except Exception as e:
                print(f"⚠️ Audit log failed: {e}")