"""
title: Paperless-ngx Document Search
author: Marc Plogas
author_url: https://github.com/mplogas
funding_url: https://github.com/sponsors/mplogas
version: 1.0.0
license: MIT
description: Search and retrieve documents from your Paperless-ngx instance. Supports full-text search, filtering, and document content extraction for AI-powered summaries.
requirements: requests>=2.31.0
required_open_webui_version: 0.4.0
"""

import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, quote
from pydantic import BaseModel, Field
import requests


class Tools:
    def __init__(self):
        """Initialize the Paperless-ngx Document Search tool."""
        self.valves = self.Valves()
        self.citation = False  # We'll handle citations manually

    class Valves(BaseModel):
        """Admin-configurable settings"""

        paperless_url: str = Field(
            default="http://localhost:8000",
            description="Base URL of your Paperless-ngx instance (e.g., https://paperless.example.com)",
        )
        api_token: str = Field(
            default="",
            description="API token for authentication (get from My Profile in Paperless UI)",
        )
        api_version: int = Field(
            default=5, description="API version to use (1-9). Version 5+ recommended."
        )
        default_page_size: int = Field(
            default=10, description="Default number of results to return per search"
        )
        max_document_size: int = Field(
            default=500000,
            description="Maximum document content size to retrieve (bytes). Default 500KB.",
        )
        enable_status_updates: bool = Field(
            default=True, description="Show status updates during operations"
        )

    class UserValves(BaseModel):
        """User-configurable settings"""

        include_content: bool = Field(
            default=True,
            description="Include full document content in results for AI analysis",
        )
        max_results: int = Field(
            default=5, description="Maximum number of search results to return (1-25)"
        )
        show_highlights: bool = Field(
            default=True, description="Show search term highlights in results"
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        headers = {
            "Authorization": f"Token {self.valves.api_token}",
            "Accept": f"application/json; version={self.valves.api_version}",
        }
        return headers

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None, method: str = "GET"
    ) -> Dict[str, Any]:
        """Make an API request to Paperless-ngx"""
        url = urljoin(self.valves.paperless_url, endpoint)

        try:
            response = requests.request(
                method, url, headers=self._get_headers(), params=params, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")

    async def search_documents(
        self,
        query: str = Field(
            ...,
            description="Search query to find documents. Use natural language or specific terms.",
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Search for documents in Paperless-ngx using full-text search.

        Returns document metadata including title, correspondent, tags, dates,
        and optionally the full content for AI analysis and summarization.

        :param query: The search query (e.g., "tax documents 2024", "invoice from ACME Corp")
        :return: Formatted search results with document details and content
        """

        # Validate configuration
        if not self.valves.api_token:
            return "Paperless-ngx API token not configured. Please set it in the tool settings."

        # Get user preferences
        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves(**dict(user_valves))

        max_results = min(user_valves.max_results, 25)  # Cap at 25

        # Emit initial status
        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Searching Paperless for: {query}",
                        "done": False,
                    },
                }
            )

        try:
            # Search for documents
            search_params = {
                "query": query,
                "page_size": max_results,
                "truncate_content": True,
            }

            results = self._make_request("/api/documents/", params=search_params)

            if not results.get("results"):
                if __event_emitter__ and self.valves.enable_status_updates:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": "No documents found", "done": True},
                        }
                    )
                return f"No documents found matching: '{query}'"

            documents = results["results"]
            total_count = results.get("count", len(documents))

            # Update status
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Found {total_count} documents, retrieving content...",
                            "done": False,
                        },
                    }
                )

            # Format results
            output_parts = [f"# Search Results for: {query}\n"]
            output_parts.append(
                f"Found {total_count} documents, showing top {len(documents)}:\n\n"
            )
            output_parts.append("---\n\n")

            for idx, doc in enumerate(documents, 1):
                doc_id = doc["id"]
                title = doc.get("title", "Untitled")

                # Format document metadata
                doc_output = self._format_document(doc, idx, user_valves)
                output_parts.append(doc_output)

                # Retrieve full content if requested
                if user_valves.include_content:
                    content = self._get_document_content(doc_id)
                    if content:
                        # Truncate if too large
                        if len(content) > self.valves.max_document_size:
                            content = (
                                content[: self.valves.max_document_size]
                                + "\n\n[Content truncated...]"
                            )
                        output_parts.append(
                            f"\n**Full Document Content:**\n\n{content}\n\n"
                        )

                # Emit citation for this document
                if __event_emitter__:
                    doc_url = urljoin(self.valves.paperless_url, f"/documents/{doc_id}")

                    await __event_emitter__(
                        {
                            "type": "citation",
                            "data": {
                                "document": [
                                    doc_output
                                    + (
                                        f"\n\n{content}"
                                        if user_valves.include_content and content
                                        else ""
                                    )
                                ],
                                "metadata": [
                                    {
                                        "source": f"Paperless Document #{doc_id}",
                                        "title": title,
                                        "document_id": doc_id,
                                        "added": doc.get("added"),
                                        "correspondent": (
                                            doc.get("correspondent", {}).get("name")
                                            if isinstance(
                                                doc.get("correspondent"), dict
                                            )
                                            else None
                                        ),
                                    }
                                ],
                                "source": {
                                    "name": f"#{doc_id}: {title}",
                                    "url": doc_url,
                                },
                            },
                        }
                    )

                output_parts.append("---\n\n")

            # Completion status
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Retrieved {len(documents)} documents",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output_parts)

        except Exception as e:
            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Error: {str(e)}", "done": True},
                    }
                )
            return f"Error searching documents: {str(e)}"

    async def get_document_by_id(
        self,
        document_id: int = Field(
            ..., description="The numeric ID of the document to retrieve"
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Retrieve a specific document by its ID from Paperless-ngx.

        Returns complete document metadata and content for detailed analysis.

        :param document_id: The document ID (e.g., 123)
        :return: Complete document information including metadata and full text content
        """

        if not self.valves.api_token:
            return "Paperless-ngx API token not configured."

        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves(**dict(user_valves))

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Retrieving document #{document_id}",
                        "done": False,
                    },
                }
            )

        try:
            # Get document metadata
            doc = self._make_request(f"/api/documents/{document_id}/")

            output_parts = [
                self._format_document(doc, position=None, user_valves=user_valves)
            ]

            # Get full content
            if user_valves.include_content:
                content = self._get_document_content(document_id)
                if content:
                    if len(content) > self.valves.max_document_size:
                        content = (
                            content[: self.valves.max_document_size]
                            + "\n\n[Content truncated...]"
                        )
                    output_parts.append(
                        f"\n**Full Document Content:**\n\n{content}\n\n"
                    )

            # Emit citation
            if __event_emitter__:
                doc_url = urljoin(
                    self.valves.paperless_url, f"/documents/{document_id}"
                )
                await __event_emitter__(
                    {
                        "type": "citation",
                        "data": {
                            "document": ["".join(output_parts)],
                            "metadata": [
                                {
                                    "source": f"Paperless Document #{document_id}",
                                    "title": doc.get("title", "Untitled"),
                                    "document_id": document_id,
                                }
                            ],
                            "source": {
                                "name": f"#{document_id}: {doc.get('title', 'Untitled')}",
                                "url": doc_url,
                            },
                        },
                    }
                )

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Document retrieved successfully",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output_parts)

        except Exception as e:
            return f"Error retrieving document #{document_id}: {str(e)}"

    async def find_similar_documents(
        self,
        document_id: int = Field(
            ..., description="Find documents similar to this document ID"
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Find documents similar to a given document using Paperless-ngx's "more like this" feature.

        Useful for finding related documents, duplicates, or documents on similar topics.

        :param document_id: The reference document ID to find similar documents
        :return: List of similar documents with relevance scores
        """

        if not self.valves.api_token:
            return "Paperless-ngx API token not configured."

        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves(**dict(user_valves))

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Finding documents similar to #{document_id}",
                        "done": False,
                    },
                }
            )

        try:
            # First get the reference document
            ref_doc = self._make_request(f"/api/documents/{document_id}/")
            ref_title = ref_doc.get("title", "Untitled")

            # Find similar documents
            params = {
                "more_like_id": document_id,
                "page_size": min(user_valves.max_results, 25),
            }
            results = self._make_request("/api/documents/", params=params)

            if not results.get("results"):
                return f"No similar documents found for #{document_id}: {ref_title}"

            documents = results["results"]

            output_parts = [f"# Documents Similar to: {ref_title} (#{document_id})\n\n"]
            output_parts.append(f"Found {len(documents)} similar documents:\n\n")
            output_parts.append("---\n\n")

            for idx, doc in enumerate(documents, 1):
                doc_output = self._format_document(doc, idx, user_valves)
                output_parts.append(doc_output)
                output_parts.append("---\n\n")

                # Emit citations
                if __event_emitter__:
                    doc_url = urljoin(
                        self.valves.paperless_url, f"/documents/{doc['id']}"
                    )
                    await __event_emitter__(
                        {
                            "type": "citation",
                            "data": {
                                "document": [doc_output],
                                "metadata": [
                                    {
                                        "document_id": doc["id"],
                                        "title": doc.get("title"),
                                    }
                                ],
                                "source": {
                                    "name": f"#{doc['id']}: {doc.get('title', 'Untitled')}",
                                    "url": doc_url,
                                },
                            },
                        }
                    )

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Similar documents retrieved",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output_parts)

        except Exception as e:
            return f"Error finding similar documents: {str(e)}"

    async def advanced_document_search(
        self,
        query: Optional[str] = Field(
            None, description="Optional full-text search query"
        ),
        tags: Optional[str] = Field(
            None, description="Comma-separated tag IDs or names"
        ),
        correspondent: Optional[str] = Field(
            None, description="Correspondent ID or name"
        ),
        document_type: Optional[str] = Field(
            None, description="Document type ID or name"
        ),
        created_after: Optional[str] = Field(
            None, description="Created after date (YYYY-MM-DD)"
        ),
        created_before: Optional[str] = Field(
            None, description="Created before date (YYYY-MM-DD)"
        ),
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Advanced document search with multiple filter options.

        Combine full-text search with metadata filters for precise document discovery.

        :param query: Optional search query text
        :param tags: Filter by tag IDs (comma-separated, e.g., "1,3,5")
        :param correspondent: Filter by correspondent ID
        :param document_type: Filter by document type ID
        :param created_after: Show documents created after this date
        :param created_before: Show documents created before this date
        :return: Filtered and formatted document results
        """

        if not self.valves.api_token:
            return "Paperless-ngx API token not configured."

        user_valves = __user__.get("valves", self.UserValves())
        if not isinstance(user_valves, self.UserValves):
            user_valves = self.UserValves(**dict(user_valves))

        # Build search parameters
        params = {"page_size": min(user_valves.max_results, 25)}

        if query:
            params["query"] = query
        if tags:
            params["tags__id__in"] = tags
        if correspondent:
            params["correspondent__id"] = correspondent
        if document_type:
            params["document_type__id"] = document_type
        if created_after:
            params["created__date__gte"] = created_after
        if created_before:
            params["created__date__lte"] = created_before

        filter_desc = []
        if query:
            filter_desc.append(f"query: '{query}'")
        if tags:
            filter_desc.append(f"tags: {tags}")
        if correspondent:
            filter_desc.append(f"correspondent: {correspondent}")
        if document_type:
            filter_desc.append(f"type: {document_type}")
        if created_after or created_before:
            date_range = f"{created_after or '...'} to {created_before or '...'}"
            filter_desc.append(f"dates: {date_range}")

        if __event_emitter__ and self.valves.enable_status_updates:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Searching with filters: {', '.join(filter_desc)}",
                        "done": False,
                    },
                }
            )

        try:
            results = self._make_request("/api/documents/", params=params)

            if not results.get("results"):
                return f"No documents found matching filters: {', '.join(filter_desc)}"

            documents = results["results"]
            total_count = results.get("count", len(documents))

            output_parts = [f"# Advanced Search Results\n"]
            output_parts.append(f"**Filters:** {', '.join(filter_desc)}\n\n")
            output_parts.append(
                f"Found {total_count} documents, showing top {len(documents)}:\n\n"
            )
            output_parts.append("---\n\n")

            for idx, doc in enumerate(documents, 1):
                doc_output = self._format_document(doc, idx, user_valves)
                output_parts.append(doc_output)

                if user_valves.include_content:
                    content = self._get_document_content(doc["id"])
                    if content:
                        if len(content) > self.valves.max_document_size:
                            content = (
                                content[: self.valves.max_document_size]
                                + "\n\n[Content truncated...]"
                            )
                        output_parts.append(f"\n**Content:**\n\n{content}\n\n")

                output_parts.append("---\n\n")

            if __event_emitter__ and self.valves.enable_status_updates:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Search completed",
                            "done": True,
                            "hidden": True,
                        },
                    }
                )

            return "".join(output_parts)

        except Exception as e:
            return f"Error in advanced search: {str(e)}"

    def _format_document(
        self,
        doc: Dict[str, Any],
        position: Optional[int],
        user_valves: "Tools.UserValves",
    ) -> str:
        """Format a document's metadata for display"""

        parts = []

        # Title and ID
        title = doc.get("title", "Untitled")
        doc_id = doc["id"]
        if position:
            parts.append(f"## {position}. {title} (ID: #{doc_id})\n\n")
        else:
            parts.append(f"## {title} (ID: #{doc_id})\n\n")

        # Search relevance (if available)
        if "__search_hit__" in doc:
            search_hit = doc["__search_hit__"]
            score = search_hit.get("score", 0)
            parts.append(f"**Relevance Score:** {score:.3f}\n\n")

            if user_valves.show_highlights and search_hit.get("highlights"):
                # Clean HTML tags from highlights for plain text display
                highlights = re.sub(r"<[^>]+>", "**", search_hit["highlights"])
                parts.append(f"**Highlights:** {highlights}\n\n")

        # Metadata
        if doc.get("created"):
            parts.append(f"**Created:** {doc['created']}\n")
        if doc.get("added"):
            parts.append(f"**Added:** {doc['added']}\n")

        # Correspondent
        correspondent = doc.get("correspondent")
        if correspondent:
            if isinstance(correspondent, dict):
                parts.append(
                    f"**Correspondent:** {correspondent.get('name', 'Unknown')}\n"
                )
            else:
                parts.append(f"**Correspondent ID:** {correspondent}\n")

        # Document Type
        doc_type = doc.get("document_type")
        if doc_type:
            if isinstance(doc_type, dict):
                parts.append(f"**Type:** {doc_type.get('name', 'Unknown')}\n")
            else:
                parts.append(f"**Type ID:** {doc_type}\n")

        # Tags
        tags = doc.get("tags", [])
        if tags:
            tag_names = []
            for tag in tags:
                if isinstance(tag, dict):
                    tag_names.append(tag.get("name", "Unknown"))
                else:
                    tag_names.append(str(tag))
            parts.append(f"**Tags:** {', '.join(tag_names)}\n")

        # Archive Serial Number
        asn = doc.get("archive_serial_number")
        if asn:
            parts.append(f"**ASN:** {asn}\n")

        # Notes preview
        if doc.get("notes"):
            notes_preview = doc["notes"][:200]
            if len(doc["notes"]) > 200:
                notes_preview += "..."
            parts.append(f"\n**Notes:** {notes_preview}\n")

        parts.append("\n")
        return "".join(parts)

    def _get_document_content(self, document_id: int) -> Optional[str]:
        """Retrieve the full text content of a document"""
        try:
            doc = self._make_request(f"/api/documents/{document_id}/")
            return doc.get("content", "")
        except Exception as e:
            print(f"Error retrieving content for document {document_id}: {e}")
            return None
