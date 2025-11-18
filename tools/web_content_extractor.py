"""
title: Web Content Extractor
author: Marc Plogas
author_url: https://github.com/mplogas
funding_url: https://github.com/sponsors/mplogas
version: 1.0.0
license: MIT
description: Fetch and extract clean content from web URLs without external services. Supports multiple extraction methods and works entirely locally.
requirements: trafilatura>=1.12.0,beautifulsoup4>=4.12.0,markdownify>=0.12.0,requests>=2.31.0,readability-lxml>=0.8.1
required_open_webui_version: 0.4.0
"""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field
import requests


class Tools:
    def __init__(self):
        """Initialize the Web Content Extractor tool."""
        self.valves = self.Valves()
        self.citation = False  # We'll handle citations manually

        # Check for available extraction libraries
        self.has_trafilatura = False
        self.has_readability = False

        try:
            import trafilatura

            self.trafilatura = trafilatura
            self.has_trafilatura = True
        except ImportError:
            pass

        try:
            from readability import Document

            self.Document = Document
            self.has_readability = True
        except ImportError:
            pass

        # BeautifulSoup and markdownify are required
        try:
            from bs4 import BeautifulSoup
            import markdownify

            self.BeautifulSoup = BeautifulSoup
            self.markdownify = markdownify
        except ImportError:
            raise ImportError(
                "Required dependencies missing. "
                "Add to requirements: beautifulsoup4, markdownify, requests"
            )

    class Valves(BaseModel):
        """Admin-configurable settings"""

        default_timeout: int = Field(
            default=30, description="Default timeout for web requests in seconds"
        )
        max_content_length: int = Field(
            default=1000000,
            description="Maximum content length to fetch (bytes). Default 1MB",
        )
        user_agent: str = Field(
            default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            description="User agent string for requests",
        )
        enable_status_updates: bool = Field(
            default=True, description="Show status updates during content extraction"
        )

    class UserValves(BaseModel):
        """User-configurable settings"""

        preferred_method: str = Field(
            default="auto",
            description="Preferred extraction method: auto, trafilatura, readability, or basic",
        )
        include_links: bool = Field(
            default=True, description="Include links in extracted content"
        )
        show_metadata: bool = Field(
            default=True, description="Show page metadata (title, date) in output"
        )

    async def fetch_url_content(
        self,
        url: str = Field(..., description="The URL to fetch and extract content from"),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Fetch and extract clean, readable content from a web URL.

        This tool extracts the main content from web pages, removing navigation,
        ads, footers, and other boilerplate. Works entirely locally without
        external API services.

        :param url: The complete URL to fetch (e.g., https://example.com/article)
        :return: Extracted content in markdown format
        """

        # Get user preferences
        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves(**dict(user_valves))

        method = user_valves.preferred_method
        include_links = user_valves.include_links
        show_metadata = user_valves.show_metadata

        # Emit initial status
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Fetching content from {url}...",
                        "done": False,
                    },
                }
            )

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return "❌ Invalid URL format. Please provide a complete URL (e.g., https://example.com)"
        except Exception as e:
            return f"❌ Invalid URL: {str(e)}"

        # Fetch content
        try:
            headers = {"User-Agent": self.valves.user_agent}

            response = requests.get(
                url, headers=headers, timeout=self.valves.default_timeout, stream=True
            )
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.valves.max_content_length:
                return f"Content too large ({content_length} bytes). Maximum: {self.valves.max_content_length}"

            html_content = response.text

        except requests.exceptions.Timeout:
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Request timed out", "done": True},
                    }
                )
            return f"Request timed out after {self.valves.default_timeout} seconds"

        except requests.exceptions.RequestException as e:
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Failed to fetch URL", "done": True},
                    }
                )
            return f"Error fetching URL: {str(e)}"

        # Extract content
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Extracting content using {method} method...",
                        "done": False,
                    },
                }
            )

        content = None
        metadata = {}

        if method == "auto":
            # Try trafilatura first
            if self.has_trafilatura:
                content, metadata = self._extract_with_trafilatura(
                    html_content, url, include_links
                )

            # Try readability if trafilatura failed
            if not content and self.has_readability:
                content, metadata = self._extract_with_readability(
                    html_content, include_links
                )

            # Fall back to basic
            if not content:
                content, metadata = self._extract_basic(html_content, include_links)

        elif method == "trafilatura":
            if not self.has_trafilatura:
                return "Trafilatura not available. Change method to 'auto' or 'basic' in user settings."
            content, metadata = self._extract_with_trafilatura(
                html_content, url, include_links
            )

        elif method == "readability":
            if not self.has_readability:
                return "Readability not available. Change method to 'auto' or 'basic' in user settings."
            content, metadata = self._extract_with_readability(
                html_content, include_links
            )

        elif method == "basic":
            content, metadata = self._extract_basic(html_content, include_links)

        else:
            return f"Unknown extraction method: {method}"

        if not content:
            return "Could not extract content from the page"

        # Emit citation
        if __event_emitter__:
            citation_data = {
                "document": [content],
                "metadata": [
                    {
                        "source": url,
                        "date_accessed": datetime.now().isoformat(),
                    }
                ],
                "source": {"name": metadata.get("title", url), "url": url},
            }

            if metadata.get("author"):
                citation_data["metadata"][0]["author"] = metadata["author"]
            if metadata.get("date"):
                citation_data["metadata"][0]["published_date"] = metadata["date"]

            await __event_emitter__({"type": "citation", "data": citation_data})

        # Emit completion status
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Content extracted successfully",
                        "done": True,
                        "hidden": True,
                    },
                }
            )

        # Format output
        output_parts = []

        if show_metadata:
            output_parts.append(f"# {metadata.get('title', 'Web Content')}\n")
            output_parts.append(f"**Source:** {url}\n")
            if metadata.get("author"):
                output_parts.append(f"**Author:** {metadata['author']}\n")
            if metadata.get("date"):
                output_parts.append(f"**Date:** {metadata['date']}\n")
            output_parts.append("\n---\n\n")

        output_parts.append(content)

        return "".join(output_parts)

    async def fetch_multiple_urls(
        self,
        urls: str = Field(
            ..., description="Comma-separated list of URLs to fetch and extract"
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Fetch and extract content from multiple URLs at once.

        Useful for comparing articles, gathering information from multiple
        sources, or batch processing web content.

        :param urls: Comma-separated URLs (e.g., "https://site1.com, https://site2.com")
        :return: Combined extracted content from all URLs
        """

        url_list = [url.strip() for url in urls.split(",") if url.strip()]

        if not url_list:
            return "No valid URLs provided. Please provide comma-separated URLs."

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Processing {len(url_list)} URLs...",
                        "done": False,
                    },
                }
            )

        results = []
        for i, url in enumerate(url_list, 1):
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Processing URL {i}/{len(url_list)}: {url}",
                            "done": False,
                        },
                    }
                )

            content = await self.fetch_url_content(
                url=url, __user__=__user__, __event_emitter__=__event_emitter__
            )
            results.append(content)

            if i < len(url_list):
                results.append("\n\n---\n\n")

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Completed processing {len(url_list)} URLs",
                        "done": True,
                        "hidden": True,
                    },
                }
            )

        return "".join(results)

    def _extract_with_trafilatura(
        self, html: str, url: str, include_links: bool
    ) -> tuple[Optional[str], dict]:
        """Extract content using trafilatura"""
        try:
            content = self.trafilatura.extract(
                html,
                output_format="markdown",
                include_links=include_links,
                include_images=True,
                include_tables=True,
                url=url,
                with_metadata=True,
            )

            # Extract metadata
            metadata_obj = self.trafilatura.extract_metadata(html)
            metadata = {}
            if metadata_obj:
                metadata["title"] = metadata_obj.title or ""
                metadata["author"] = metadata_obj.author or ""
                metadata["date"] = metadata_obj.date or ""

            return content, metadata

        except Exception as e:
            print(f"Trafilatura extraction failed: {e}")
            return None, {}

    def _extract_with_readability(
        self, html: str, include_links: bool
    ) -> tuple[Optional[str], dict]:
        """Extract content using readability"""
        try:
            doc = self.Document(html)
            readable_html = doc.summary()

            # Extract metadata
            metadata = {"title": doc.title() or "", "author": "", "date": ""}

            # Convert to markdown
            markdown = self.markdownify.markdownify(
                readable_html,
                heading_style="ATX",
                bullets="-",
                strip=["script", "style"],
            )

            if not include_links:
                markdown = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", markdown)

            return markdown, metadata

        except Exception as e:
            print(f"Readability extraction failed: {e}")
            return None, {}

    def _extract_basic(self, html: str, include_links: bool) -> tuple[str, dict]:
        """Basic extraction using BeautifulSoup"""
        try:
            soup = self.BeautifulSoup(html, "html.parser")

            # Extract metadata
            metadata = {"title": "", "author": "", "date": ""}

            title_tag = soup.find("title")
            if title_tag:
                metadata["title"] = title_tag.get_text().strip()

            # Look for author in meta tags
            author_tag = soup.find("meta", attrs={"name": "author"})
            if author_tag:
                metadata["author"] = author_tag.get("content", "")

            # Remove unwanted elements
            for element in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "footer",
                    "header",
                    "aside",
                    "noscript",
                    "iframe",
                ]
            ):
                element.decompose()

            # Find main content
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find(
                    "div", class_=re.compile(r"content|main|article|post", re.I)
                )
                or soup.find("body")
            )

            if main_content:
                markdown = self.markdownify.markdownify(
                    str(main_content),
                    heading_style="ATX",
                    bullets="-",
                    strip=["script", "style"],
                )

                if not include_links:
                    markdown = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", markdown)

                # Clean up excessive newlines
                markdown = re.sub(r"\n{3,}", "\n\n", markdown)

                return markdown.strip(), metadata
            else:
                return "Could not find main content", metadata

        except Exception as e:
            return f"Error during extraction: {str(e)}", {}
