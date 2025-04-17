"""
SearXNG Search Tool

This module provides a standalone search tool using SearXNG.
It's designed to be used without Django dependencies.
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


class SafeSearchLevel(IntEnum):
    OFF = 0
    MODERATE = 1
    STRICT = 2


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    relevance_score: int = 0


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

    # Add retry logic for rate limits
    max_retries = 3
    retry_delay = 1  # Start with 1 second delay

    for attempt in range(max_retries):
        try:
            # Make the request
            response = requests.get(f"{host}/search", params=params, timeout=30)
            response.raise_for_status()

            # Parse the response
            data = response.json()

            # Extract and format results
            results = []
            for result in data.get("results", [])[:num_results]:
                # Calculate relevance score based on query match
                relevance_score = 0
                title = result.get("title", "")
                content = result.get("content", "")

                # Basic relevance scoring
                if query.lower() in title.lower():
                    relevance_score += 5
                if query.lower() in content.lower():
                    relevance_score += 3

                results.append(
                    SearchResult(
                        title=title,
                        url=result.get("url", ""),
                        content=content,
                        relevance_score=relevance_score,
                    )
                )

            # Sort by relevance score
            results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Convert to dictionary format for compatibility
            return [
                {"title": r.title, "url": r.url, "content": r.content} for r in results
            ]

        except requests.exceptions.RequestException as e:
            if response := getattr(e, "response", None):
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    raise RuntimeError(
                        "Rate limit exceeded. Wait 1 second between requests."
                    )
                error_detail = (
                    f"Status: {response.status_code}, Response: {response.text}"
                )
            else:
                error_detail = str(e)
            raise RuntimeError(f"SearXNG API error: {error_detail}")

    return []  # Return empty list if all retries failed


def format_search_results(results: List[Dict[str, str]], query: str) -> str:
    """
    Format search results into a readable string.

    Args:
        results: List of search results from search_web
        query: Original search query

    Returns:
        Formatted string containing search results
    """
    output = []
    output.append(f"\nSearch Results for '{query}':")

    if results:
        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. {result['title']}")
            output.append(f"   URL: {result['url']}")
            if result["content"]:
                output.append(f"   Content: {result['content'][:200]}...")
            output.append("")
    else:
        output.append("\nNo results found. Try refining your search query.")

    return "\n".join(output)
