import requests
import os
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def searxng_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Search for vendor information using SearXNG.

    Args:
        query (str): The search query
        num_results (int): Number of results to return (default: 5)

    Returns:
        List[Dict[str, str]]: List of search results with title, link, and snippet
    """
    try:
        # Get SearXNG URL from environment or use default
        searxng_url = os.getenv("SEARXNG_URL", "http://localhost:8080")

        # Prepare the search request
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
            "time_range": None,
            "safesearch": 1,
            "engines": "google,bing,duckduckgo",
            "categories": "general",
            "language": "en",
            "limit": num_results,
        }

        # Make the request
        response = requests.get(f"{searxng_url}/search", params=params, timeout=10)
        response.raise_for_status()

        # Parse the results
        data = response.json()
        results = []

        for result in data.get("results", [])[:num_results]:
            results.append(
                {
                    "title": result.get("title", ""),
                    "link": result.get("url", ""),
                    "snippet": result.get("content", ""),
                }
            )

        return results

    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching with SearXNG: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in searxng_search: {str(e)}")
        return []
