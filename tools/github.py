"""
title: GitHub Code Reader
author: Your Name
author_url: https://github.com/yourusername
version: 1.0.0
license: MIT
description: Read code from GitHub repositories including private repos. Browse files and analyze code with AI.
requirements: requests>=2.31.0
required_open_webui_version: 0.4.0
"""

import base64
from typing import Any, Dict, Optional
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

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url, headers=self._get_headers(), params=params, timeout=30
            )
            response.raise_for_status()
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
            parts = repo.split("/")
            if len(parts) != 2:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = parts
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

            if user_valves.syntax_highlighting and lang:
                output.append(f"```{lang}\n")
            else:
                output.append("```\n")

            if user_valves.show_line_numbers:
                lines = content.split("\n")
                width = len(str(len(lines)))
                for i, line in enumerate(lines, 1):
                    output.append(f"{i:>{width}} | {line}\n")
            else:
                output.append(content)
                if not content.endswith("\n"):
                    output.append("\n")

            output.append("```\n")

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
            parts = repo.split("/")
            if len(parts) != 2:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = parts
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
            parts = repo.split("/")
            if len(parts) != 2:
                return "Invalid repo format. Use owner/repo"

            owner, repo_name = parts
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
