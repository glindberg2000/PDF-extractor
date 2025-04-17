import os
import sys
from pathlib import Path
import requests
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Dict, Optional
from urllib.parse import urljoin
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
    """
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


def test_search():
    """Test the search tool functionality"""
    try:
        # Test a simple search query
        query = "Python Django web framework"
        print(f"\nSearching for: {query}")

        results = search_web(
            query=query,
            num_results=5,
            safesearch=SafeSearchLevel.MODERATE,
            host="http://localhost:8080",
        )

        print("\nSearch Results:")
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(
                f"Content: {result['content'][:200]}..."
            )  # Show first 200 chars of content

    except Exception as e:
        print(f"Error during search: {str(e)}")


if __name__ == "__main__":
    test_search()
