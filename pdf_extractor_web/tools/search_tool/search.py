import os
import requests
from typing import List, Dict, Optional, Union
from urllib.parse import urljoin
import json
from dataclasses import dataclass
from enum import IntEnum


class SafeSearchLevel(IntEnum):
    OFF = 0
    MODERATE = 1
    STRICT = 2


@dataclass
class SearchResult:
    title: str
    url: str
    content: str


class SearchToolException(Exception):
    """Custom exception for search tool errors"""

    pass


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
        query: The search query string
        num_results: Number of results to return (default: 10)
        engines: List of search engines to use (default: None, uses all available)
        language: Language code for results (default: "en-US")
        safesearch: Safe search level (0=off, 1=moderate, 2=strict)
        host: SearXNG instance host URL (default: from environment or localhost)

    Returns:
        List of search results, each containing title, url, and content

    Raises:
        SearchToolException: For any search-related errors
    """
    # Get host from environment or use default
    host = host or os.getenv("SEARXNG_HOST", "http://localhost:8888")

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
        response = requests.get(urljoin(host, "search"), params=params, timeout=30)
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
        raise SearchToolException(f"Network error during search: {str(e)}")
    except json.JSONDecodeError as e:
        raise SearchToolException(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise SearchToolException(f"Unexpected error during search: {str(e)}")


# Tool schema for LLM integration
function_schema = {
    "name": "search_web",
    "description": "Search the web using SearXNG",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
            "num_results": {
                "type": "integer",
                "description": "Number of results to return",
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
                "description": "Safe search level (0=off, 1=moderate, 2=strict)",
                "default": 1,
            },
        },
        "required": ["query"],
    },
}

# Required attributes for tool discovery
name = "searxng_search"
description = "Search the web using a SearXNG instance"
