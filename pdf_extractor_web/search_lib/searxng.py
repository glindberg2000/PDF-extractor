"""
SearXNG Search Tool

This module provides a Python interface to the SearXNG search engine.
"""

import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Dict, Optional
from urllib.parse import urljoin
import requests
import json


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
        query: The search query
        num_results: Maximum number of results to return (default: 10)
        engines: List of search engines to use (default: None, uses SearXNG defaults)
        language: Language code for results (default: en-US)
        safesearch: SafeSearch level (default: MODERATE)
        host: SearXNG host URL (default: http://localhost:8080)

    Returns:
        List of dictionaries containing search results with 'title', 'url', and 'content' keys

    Raises:
        SearchToolException: If there's an error during the search
    """
    if not query:
        raise SearchToolException("Search query cannot be empty")

    if num_results < 1:
        raise SearchToolException("num_results must be greater than 0")

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
