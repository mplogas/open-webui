"""
title: GitHub Connector
author: Your Name
author_url: https://github.com/mplogas
version: 1.1.0
license: MIT
description: Read code from GitHub repositories including private repos. Manage Gists and control workflows.
requirements: requests>=2.31.0
required_open_webui_version: 0.4.0

"""

import base64
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from pydantic import BaseModel, Field


class Tools:
    def __init__(self):
        self.valves = self.Valves()
        self.citation = False
        self.base_url = "https://api.github.com"

    class Valves(BaseModel):
        github_token: str = Field(
            default="", description="GitHub Personal Access Token"
        )
        default_branch: str = Field(default="main", description="Default branch name")
        max_file_size: int = Field(default=100000, description="Max file size in bytes")
        enable_status_updates: bool = Field(
            default=True, description="Show status updates"
        )

    class UserValves(BaseModel):
        show_line_numbers: bool = Field(default=True, description="Show line numbers")
        syntax_highlighting: bool = Field(
            default=True, description="Enable syntax highlighting"
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.valves.github_token:
            headers["Authorization"] = f"Bearer {self.valves.github_token}"
        return headers

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        method: str = "GET",
        data: Optional[Dict] = None,
    ) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(
                    url, headers=self._get_headers(), params=params, timeout=30
                )
            elif method == "POST":
                response = requests.post(
                    url, headers=self._get_headers(), json=data, timeout=30
                )
            elif method == "PATCH":
                response = requests.patch(
                    url, headers=self._get_headers(), json=data, timeout=30
                )
            elif method == "DELETE":
                response = requests.delete(url, headers=self._get_headers(), timeout=30)
            else:
                raise Exception(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            if method == "DELETE":
                return {"status": "deleted"}
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed")
            elif e.response.status_code == 404:
                raise Exception("Not found")
            elif e.response.status_code == 403:
                raise Exception("Rate limit or access forbidden")
            else:
                raise Exception(f"API error: {e.response.status_code}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    def _detect_language(self, ext: str) -> str:
        langs = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "cs": "csharp",
            "go": "go",
            "rs": "rust",
            "rb": "ruby",
            "php": "php",
            "sh": "bash",
            "md": "markdown",
            "html": "html",
            "css": "css",
            "json": "json",
            "yaml": "yaml",
        }
        return langs.get(ext.lower(), "")

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def _split_repo(self, repo: str) -> Optional[Tuple[str, str]]:
        parts = [part.strip() for part in repo.split("/") if part.strip()]
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    def _format_workflow_status(
        self, status: Optional[str], conclusion: Optional[str] = None
    ) -> str:
        status_text = (status or "unknown").replace("_", " ").strip()
        status_text = status_text.capitalize() if status_text else "Unknown"

        if conclusion and conclusion not in {"", "N/A"}:
            conclusion_text = conclusion.replace("_", " ").strip()
            if conclusion_text:
                status_text = f"{status_text} ({conclusion_text})"

        return status_text

    def _parse_workflow_inputs(self, inputs: Optional[str]) -> Dict[str, str]:
        if not inputs:
            return {}

        inputs = inputs.strip()
        if not inputs:
            return {}

        if inputs.startswith("{"):
            try:
                parsed = json.loads(inputs)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON for inputs: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("Workflow inputs JSON must be an object")
            return {str(key): str(value) for key, value in parsed.items()}

        entries: Dict[str, str] = {}
        for entry in inputs.split("|||"):
            segment = entry.strip()
            if not segment:
                continue
            if "=" not in segment:
                raise ValueError(f"Invalid input format segment: '{segment}'")
            key, value = segment.split("=", 1)
            entries[key.strip()] = value.strip()

        return entries

    def _render_code_block(
        self,
        content: str,
        lang: str,
        show_line_numbers: bool,
        syntax_highlighting: bool,
    ) -> str:
        fence_lang = lang if syntax_highlighting and lang else ""
        block: List[str] = [f"```{fence_lang}\n"]

        if show_line_numbers:
            lines = content.split("\n")
            width = len(str(len(lines))) or 1
            for idx, line in enumerate(lines, 1):
                block.append(f"{idx:>{width}} | {line}\n")
        else:
            block.append(content)
            if not content.endswith("\n"):
                block.append("\n")

        block.append("```\n")
        return "".join(block)

    async def read_file(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        file_path: str = Field(..., description="Path to file"),
        branch: Optional[str] = Field(None, description="Branch name"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Read a file from a GitHub repository"""
        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves()

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Reading {file_path}", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            endpoint = f"/repos/{owner}/{repo_name}/contents/{quote(file_path)}"
            params = {"ref": branch} if branch else {}

            file_data = self._make_request(endpoint, params)

            if file_data.get("type") != "file":
                return f"{file_path} is not a file"

            file_size = file_data.get("size", 0)
            if file_size > self.valves.max_file_size:
                return f"File too large: {file_size} bytes"

            content_encoded = file_data.get("content", "")
            if not content_encoded:
                return "File content is empty"

            content_bytes = base64.b64decode(content_encoded)

            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return f"Binary file ({file_size} bytes)"

            ext = file_path.split(".")[-1] if "." in file_path else ""
            lang = self._detect_language(ext)

            output = []
            output.append(f"# {file_data.get('name', file_path)}\n\n")
            output.append(f"**Repository:** {repo}\n")
            output.append(f"**Path:** `{file_path}`\n")
            if branch:
                output.append(f"**Branch:** {branch}\n")
            output.append(f"**Size:** {file_size} bytes\n\n")
            output.append("---\n\n")
            output.append(
                self._render_code_block(
                    content,
                    lang,
                    user_valves.show_line_numbers,
                    user_valves.syntax_highlighting,
                )
            )

            if __event_emitter__:
                file_url = f"https://github.com/{repo}/blob/{branch or self.valves.default_branch}/{file_path}"
                await __event_emitter__(
                    {
                        "type": "citation",
                        "data": {
                            "document": ["".join(output)],
                            "metadata": [
                                {"source": f"GitHub: {repo}", "file_path": file_path}
                            ],
                            "source": {"name": f"{repo}/{file_path}", "url": file_url},
                        },
                    }
                )

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Error: {str(e)}", "done": True},
                    }
                )
            return f"Error: {str(e)}"

    async def list_repository_files(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        path: str = Field(default="", description="Directory path"),
        branch: Optional[str] = Field(None, description="Branch name"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """List files in a repository directory"""
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Listing {repo}", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            endpoint = (
                f"/repos/{owner}/{repo_name}/contents/{quote(path) if path else ''}"
            )
            params = {"ref": branch} if branch else {}

            contents = self._make_request(endpoint, params)

            if isinstance(contents, dict) and contents.get("type") == "file":
                return f"{path} is a file. Use read_file to view it"

            output = []
            output.append(f"# Contents: {repo}/{path or 'root'}\n\n")
            if branch:
                output.append(f"**Branch:** {branch}\n\n")

            dirs = [item for item in contents if item.get("type") == "dir"]
            files = [item for item in contents if item.get("type") == "file"]

            if dirs:
                output.append("## Directories\n\n")
                for d in sorted(dirs, key=lambda x: x["name"]):
                    output.append(f"- **{d['name']}/**\n")
                output.append("\n")

            if files:
                output.append("## Files\n\n")
                for f in sorted(files, key=lambda x: x["name"]):
                    size_str = self._format_size(f.get("size", 0))
                    output.append(f"- `{f['name']}` ({size_str})\n")

            if not dirs and not files:
                output.append("*Empty directory*\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def get_repository_info(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Get repository information"""
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Fetching {repo}", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            repo_data = self._make_request(f"/repos/{owner}/{repo_name}")

            output = []
            output.append(f"# {repo_data.get('full_name', repo)}\n\n")

            if repo_data.get("description"):
                output.append(f"{repo_data['description']}\n\n")

            output.append("## Details\n\n")
            output.append(
                f"**Owner:** {repo_data.get('owner', {}).get('login', 'Unknown')}\n"
            )
            output.append(f"**Branch:** {repo_data.get('default_branch', 'main')}\n")
            output.append(
                f"**Language:** {repo_data.get('language', 'Not specified')}\n"
            )
            output.append(f"**Stars:** {repo_data.get('stargazers_count', 0)}\n")
            output.append(f"**Forks:** {repo_data.get('forks_count', 0)}\n")
            output.append(
                f"**Visibility:** {'Private' if repo_data.get('private') else 'Public'}\n"
            )
            output.append(f"\n**URL:** {repo_data.get('html_url', '')}\n")

            try:
                langs = self._make_request(f"/repos/{owner}/{repo_name}/languages")
                if langs:
                    output.append("\n## Languages\n\n")
                    total = sum(langs.values())
                    for lang, bytes_count in sorted(
                        langs.items(), key=lambda item: item[1], reverse=True
                    ):
                        pct = (bytes_count / total * 100) if total > 0 else 0
                        output.append(f"- **{lang}**: {pct:.1f}%\n")
            except Exception:
                pass

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def list_my_gists(
        self,
        limit: int = Field(default=10, description="Number of gists to list"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """List your gists"""
        if not self.valves.github_token:
            return "GitHub token required to list your gists"

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Fetching your gists", "done": False},
                }
            )

        try:
            gists = self._make_request("/gists", params={"per_page": min(limit, 100)})

            if not gists:
                return "No gists found"

            output = []
            output.append(f"# Your Gists ({len(gists)} shown)\n\n")

            for idx, gist in enumerate(gists, 1):
                gist_id = gist["id"]
                description = gist.get("description") or "No description"
                public = "Public" if gist.get("public") else "Secret"
                created = gist.get("created_at", "Unknown")

                files = list(gist.get("files", {}).keys())
                file_list = ", ".join(files[:3])
                if len(files) > 3:
                    file_list += f" (+{len(files)-3} more)"

                output.append(f"## {idx}. {description}\n\n")
                output.append(f"**ID:** `{gist_id}`\n")
                output.append(f"**Visibility:** {public}\n")
                output.append(f"**Files:** {file_list}\n")
                output.append(f"**Created:** {created}\n")
                output.append(f"**URL:** {gist.get('html_url', '')}\n\n")
                output.append("---\n\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def get_gist(
        self,
        gist_id: str = Field(..., description="Gist ID"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Get a gist by ID and read its content"""
        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves()

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Fetching gist {gist_id}", "done": False},
                }
            )

        try:
            gist = self._make_request(f"/gists/{gist_id}")

            output = []
            description = gist.get("description") or "Untitled Gist"
            output.append(f"# {description}\n\n")
            output.append(f"**ID:** `{gist['id']}`\n")
            output.append(
                f"**Visibility:** {'Public' if gist.get('public') else 'Secret'}\n"
            )
            output.append(
                f"**Owner:** {gist.get('owner', {}).get('login', 'Anonymous')}\n"
            )
            output.append(f"**Created:** {gist.get('created_at', 'Unknown')}\n")
            output.append(f"**Updated:** {gist.get('updated_at', 'Unknown')}\n")
            output.append(f"**URL:** {gist.get('html_url', '')}\n\n")
            output.append("---\n\n")

            files = gist.get("files", {})
            for filename, file_data in files.items():
                content = file_data.get("content", "")
                lang = file_data.get("language", "").lower()
                size = file_data.get("size", 0)

                output.append(f"## File: {filename}\n\n")
                output.append(f"**Size:** {size} bytes\n")
                if lang:
                    output.append(f"**Language:** {lang}\n")
                output.append("\n")
                output.append(
                    self._render_code_block(
                        content,
                        lang,
                        user_valves.show_line_numbers,
                        user_valves.syntax_highlighting,
                    )
                )
                output.append("\n")

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "citation",
                        "data": {
                            "document": ["".join(output)],
                            "metadata": [{"source": "GitHub Gist", "gist_id": gist_id}],
                            "source": {
                                "name": f"Gist: {description}",
                                "url": gist.get("html_url", ""),
                            },
                        },
                    }
                )

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def create_gist(
        self,
        description: str = Field(..., description="Gist description"),
        files: str = Field(
            ...,
            description="Files in format: filename1.ext=content1|||filename2.ext=content2",
        ),
        public: bool = Field(default=True, description="Make gist public"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Create a new gist"""
        if not self.valves.github_token:
            return "GitHub token required to create gists"

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Creating gist", "done": False},
                }
            )

        try:
            files_dict = {}
            file_entries = files.split("|||")

            for entry in file_entries:
                entry = entry.strip()
                if "=" not in entry:
                    return f"Invalid file format. Use: filename.ext=content|||filename2.ext=content2"

                filename, content = entry.split("=", 1)
                filename = filename.strip()
                content = content.strip()

                if not filename:
                    return "Filename cannot be empty"

                files_dict[filename] = {"content": content}

            if not files_dict:
                return "At least one file is required"

            data = {"description": description, "public": public, "files": files_dict}

            gist = self._make_request("/gists", method="POST", data=data)

            output = []
            output.append("# Gist Created Successfully!\n\n")
            output.append(f"**ID:** `{gist['id']}`\n")
            output.append(f"**Description:** {description}\n")
            output.append(f"**Visibility:** {'Public' if public else 'Secret'}\n")
            output.append(f"**Files:** {', '.join(files_dict.keys())}\n")
            output.append(f"\n**URL:** {gist.get('html_url', '')}\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Gist created",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def update_gist(
        self,
        gist_id: str = Field(..., description="Gist ID to update"),
        description: Optional[str] = Field(None, description="New description"),
        files: Optional[str] = Field(
            None,
            description="Files to update: filename.ext=newcontent|||filename2.ext=content2",
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Update an existing gist"""
        if not self.valves.github_token:
            return "GitHub token required to update gists"

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Updating gist", "done": False},
                }
            )

        try:
            data = {}

            if description:
                data["description"] = description

            if files:
                files_dict = {}
                file_entries = files.split("|||")

                for entry in file_entries:
                    entry = entry.strip()
                    if "=" not in entry:
                        return f"Invalid file format. Use: filename.ext=content|||filename2.ext=content2"

                    filename, content = entry.split("=", 1)
                    filename = filename.strip()
                    content = content.strip()

                    files_dict[filename] = {"content": content}

                data["files"] = files_dict

            if not data:
                return "Nothing to update. Provide description or files"

            gist = self._make_request(f"/gists/{gist_id}", method="PATCH", data=data)

            output = []
            output.append("# Gist Updated Successfully!\n\n")
            output.append(f"**ID:** `{gist['id']}`\n")
            output.append(
                f"**Description:** {gist.get('description', 'No description')}\n"
            )
            output.append(f"**Updated:** {gist.get('updated_at', 'Unknown')}\n")
            output.append(f"\n**URL:** {gist.get('html_url', '')}\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Gist updated",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def delete_gist(
        self,
        gist_id: str = Field(..., description="Gist ID to delete"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Delete a gist"""
        if not self.valves.github_token:
            return "GitHub token required to delete gists"

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Deleting gist", "done": False},
                }
            )

        try:
            self._make_request(f"/gists/{gist_id}", method="DELETE")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Gist deleted",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return f"Gist {gist_id} deleted successfully"

        except Exception as e:
            return f"Error: {str(e)}"

    async def list_workflow_runs(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        workflow_id: Optional[str] = Field(
            None, description="Workflow ID or filename (e.g., 'ci.yml')"
        ),
        branch: Optional[str] = Field(None, description="Filter by branch"),
        status: Optional[str] = Field(
            None,
            description="Filter by status: completed, action_required, cancelled, failure, neutral, skipped, stale, success, timed_out, in_progress, queued, requested, waiting, pending",
        ),
        limit: int = Field(default=10, description="Number of runs to list"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """List workflow runs for a repository"""
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Fetching workflow runs", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo

            if workflow_id:
                endpoint = (
                    f"/repos/{owner}/{repo_name}/actions/workflows/{workflow_id}/runs"
                )
            else:
                endpoint = f"/repos/{owner}/{repo_name}/actions/runs"

            params = {"per_page": min(limit, 100)}
            if branch:
                params["branch"] = branch
            if status:
                params["status"] = status

            data = self._make_request(endpoint, params)
            runs = data.get("workflow_runs", [])

            if not runs:
                return "No workflow runs found"

            output = []
            output.append(f"# Workflow Runs: {repo}\n\n")
            if workflow_id:
                output.append(f"**Workflow:** {workflow_id}\n")
            if branch:
                output.append(f"**Branch:** {branch}\n")
            if status:
                output.append(f"**Status Filter:** {status}\n")
            output.append(f"\nShowing {len(runs)} run(s):\n\n")

            for idx, run in enumerate(runs, 1):
                run_id = run.get("id")
                name = run.get("name", "Unknown")
                run_number = run.get("run_number", "N/A")
                status_val = run.get("status")
                conclusion = run.get("conclusion")
                branch_name = run.get("head_branch", "N/A")
                commit = (run.get("head_sha") or "N/A")[:7]
                created = run.get("created_at", "Unknown")
                updated = run.get("updated_at", "Unknown")

                status_label = self._format_workflow_status(status_val, conclusion)

                output.append(f"## {idx}. {name} #{run_number}\n\n")
                output.append(f"**Run ID:** `{run_id}`\n")
                output.append(f"**Status:** {status_label}\n")
                if conclusion:
                    output.append(f"**Conclusion:** {conclusion}\n")
                output.append(f"**Branch:** {branch_name}\n")
                output.append(f"**Commit:** `{commit}`\n")
                output.append(f"**Created:** {created}\n")
                output.append(f"**Updated:** {updated}\n")
                output.append(f"**URL:** {run.get('html_url', '')}\n\n")
                output.append("---\n\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def get_workflow_run(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        run_id: int = Field(..., description="Workflow run ID"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Get detailed information about a specific workflow run"""
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Fetching run #{run_id}", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            endpoint = f"/repos/{owner}/{repo_name}/actions/runs/{run_id}"

            run = self._make_request(endpoint)

            output = []
            output.append(
                f"# {run.get('name', 'Workflow Run')} #{run.get('run_number', run_id)}\n\n"
            )

            status_val = run.get("status")
            conclusion = run.get("conclusion")
            status_label = self._format_workflow_status(status_val, conclusion)

            output.append(f"**Status:** {status_label}\n")
            if conclusion:
                output.append(f"**Conclusion:** {conclusion}\n")
            output.append(f"**Run ID:** `{run.get('id')}`\n")
            output.append(f"**Run Number:** #{run.get('run_number', 'N/A')}\n")
            output.append(f"**Workflow:** {run.get('path', 'N/A')}\n")
            output.append(f"**Branch:** {run.get('head_branch', 'N/A')}\n")
            output.append(f"**Commit:** `{run.get('head_sha', 'N/A')[:7]}`\n")
            output.append(f"**Event:** {run.get('event', 'N/A')}\n")
            output.append(
                f"**Actor:** {run.get('actor', {}).get('login', 'Unknown')}\n"
            )
            output.append(f"**Created:** {run.get('created_at', 'Unknown')}\n")
            output.append(f"**Updated:** {run.get('updated_at', 'Unknown')}\n")
            output.append(f"\n**URL:** {run.get('html_url', '')}\n\n")

            jobs_endpoint = f"/repos/{owner}/{repo_name}/actions/runs/{run_id}/jobs"
            try:
                jobs_data = self._make_request(jobs_endpoint)
                jobs = jobs_data.get("jobs", [])

                if jobs:
                    output.append("## Jobs\n\n")
                    for job in jobs:
                        job_status = job.get("status")
                        job_conclusion = job.get("conclusion")
                        job_label = self._format_workflow_status(
                            job_status, job_conclusion
                        )

                        output.append(f"### {job.get('name', 'Unnamed Job')}\n\n")
                        output.append(f"**Status:** {job_label}\n")
                        if job_conclusion:
                            output.append(f"**Conclusion:** {job_conclusion}\n")
                        output.append(
                            f"**Started:** {job.get('started_at', 'Not started')}\n"
                        )
                        output.append(
                            f"**Completed:** {job.get('completed_at', 'Not completed')}\n\n"
                        )
            except Exception:
                pass

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def trigger_workflow(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        workflow_id: str = Field(
            ..., description="Workflow ID or filename (e.g., 'ci.yml')"
        ),
        ref: str = Field(
            default="main", description="Git ref (branch or tag) to run workflow on"
        ),
        inputs: Optional[str] = Field(
            None,
            description="Workflow inputs as JSON string or key=value|||key2=value2 format",
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Trigger a workflow_dispatch event to run a workflow"""
        if not self.valves.github_token:
            return "GitHub token required to trigger workflows"

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Triggering workflow", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            endpoint = (
                f"/repos/{owner}/{repo_name}/actions/workflows/{workflow_id}/dispatches"
            )

            data = {"ref": ref}

            try:
                inputs_dict = self._parse_workflow_inputs(inputs)
            except ValueError as exc:
                return f"Invalid workflow inputs: {exc}"

            if inputs_dict:
                data["inputs"] = inputs_dict

            self._make_request(endpoint, method="POST", data=data)

            output = []
            output.append("# Workflow Triggered Successfully!\n\n")
            output.append(f"**Repository:** {repo}\n")
            output.append(f"**Workflow:** {workflow_id}\n")
            output.append(f"**Ref:** {ref}\n")
            if inputs:
                output.append(f"**Inputs:** Provided\n")
            output.append(
                f"\n**Note:** The workflow run has been queued. Use `list_workflow_runs` to check its status.\n"
            )

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Workflow triggered",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def list_workflows(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """List all workflows in a repository"""
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Fetching workflows", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            endpoint = f"/repos/{owner}/{repo_name}/actions/workflows"

            data = self._make_request(endpoint)
            workflows = data.get("workflows", [])

            if not workflows:
                return "No workflows found in this repository"

            output = []
            output.append(f"# Workflows in {repo}\n\n")
            output.append(f"Total: {len(workflows)} workflow(s)\n\n")

            for idx, workflow in enumerate(workflows, 1):
                workflow_id = workflow.get("id")
                name = workflow.get("name", "Unnamed")
                path = workflow.get("path", "N/A")
                state = workflow.get("state", "unknown")
                state_label = state.replace("_", " ").title() if state else "Unknown"

                output.append(f"## {idx}. {name}\n\n")
                output.append(f"**ID:** `{workflow_id}`\n")
                output.append(f"**Path:** `{path}`\n")
                output.append(f"**State:** {state_label}\n")
                output.append(f"**URL:** {workflow.get('html_url', '')}\n\n")
                output.append("---\n\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Done", "done": True, "hidden": True},
                    }
                )

            return "".join(output)

        except Exception as e:
            return f"Error: {str(e)}"

    async def cancel_workflow_run(
        self,
        repo: str = Field(..., description="Repository in format owner/repo"),
        run_id: int = Field(..., description="Workflow run ID to cancel"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Cancel a workflow run"""
        if not self.valves.github_token:
            return "GitHub token required to cancel workflow runs"

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Cancelling workflow run", "done": False},
                }
            )

        try:
            owner_repo = self._split_repo(repo)
            if not owner_repo:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = owner_repo
            endpoint = f"/repos/{owner}/{repo_name}/actions/runs/{run_id}/cancel"

            self._make_request(endpoint, method="POST", data={})

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Run cancelled",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return f"Workflow run #{run_id} has been cancelled successfully"

        except Exception as e:
            return f"Error: {str(e)}"
