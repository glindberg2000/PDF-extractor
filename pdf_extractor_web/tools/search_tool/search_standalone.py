"""
SearXNG Search Tool

This module provides a standalone search tool using SearXNG.
It's designed to be used by LLMs for web search functionality.
"""

import os
import time
import requests
from typing import Dict, List, Optional, TypedDict
from enum import IntEnum
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Tool metadata
name = "searxng_search"
description = "Search the web using SearXNG"


class SafeSearchLevel(IntEnum):
    OFF = 0
    MODERATE = 1
    STRICT = 2


@dataclass
class SearchResult:
    title: str
    url: str
    content: str


def search_web(
    query: str,
    num_results: int = 10,
    engines: Optional[List[str]] = None,
    language: str = "en-US",
    safesearch: SafeSearchLevel = SafeSearchLevel.MODERATE,
    host: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Search the web using a SearXNG instance.

    Args:
        query: The search query
        num_results: Maximum number of results to return (default: 10)
        engines: List of search engines to use (default: None, uses SearXNG defaults)
        language: Language code for results (default: en-US)
        safesearch: SafeSearch level (default: MODERATE)
        host: SearXNG host URL (default: http://localhost:8080)

    Returns:
        List of dictionaries containing search results with 'title', 'url', and 'content' keys
    """
    if not query:
        raise ValueError("Search query cannot be empty")

    if num_results < 1:
        raise ValueError("num_results must be greater than 0")

    # Get host from environment or use default
    host = host or os.getenv("SEARXNG_HOST", "http://localhost:8080")

    # Prepare search parameters
    params = {
        "q": query,
        "format": "json",
        "pageno": 1,
        "language": language,
        "safesearch": safesearch,
    }

    if engines:
        params["engines"] = ",".join(engines)

    try:
        # Make the request
        response = requests.get(f"{host}/search", params=params, timeout=30)
        response.raise_for_status()

        # Parse the response
        data = response.json()

        # Extract and format results
        results = []
        for result in data.get("results", [])[:num_results]:
            results.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                }
            )

        return results

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error during search: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during search: {str(e)}")


# Define function schema for OpenAI function calling
function_schema = {
    "name": "searxng_search",
    "description": "Search the web using SearXNG",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10,
            },
            "engines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of search engines to use",
            },
            "language": {
                "type": "string",
                "description": "Language code for results",
                "default": "en-US",
            },
            "safesearch": {
                "type": "integer",
                "description": "SafeSearch level (0=off, 1=moderate, 2=strict)",
                "default": 1,
            },
        },
        "required": ["query"],
    },
}
