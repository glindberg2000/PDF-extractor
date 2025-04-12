"""
Brave Search API Integration

This module provides a simple interface to search for vendor information using the Brave Search API.
"""

import os
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from requests.exceptions import RequestException
from pathlib import Path
from dotenv import load_dotenv

# Find and load the root .env file
project_root = Path(__file__).resolve().parents[3]  # Go up 3 levels to reach project root
env_path = project_root / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_API_KEY")  # Updated to match .env file name
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass
class SearchResult:
    """Schema for search results returned by the tool"""

    title: str
    description: str
    url: Optional[str] = None


def search(query: str) -> List[SearchResult]:
    """
    Search for vendor information using Brave Search API.

    Args:
        query: The vendor name or information to search for

    Returns:
        List of SearchResult objects containing the top 10 search results

    Raises:
        ValueError: If BRAVE_SEARCH_API_KEY is not set
        RequestException: If the API request fails
    """
    if not BRAVE_SEARCH_API_KEY:
        raise ValueError("BRAVE_SEARCH_API_KEY environment variable is not set")

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    }

    params = {"q": query, "count": 10}  # Get top 10 results

    try:
        response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        results = []

        for web_result in data.get("web", {}).get("results", []):
            result = SearchResult(
                title=web_result.get("title", ""),
                description=web_result.get("description", ""),
                url=web_result.get("url"),
            )
            results.append(result)

        return results

    except RequestException as e:
        logger.error(f"Failed to search Brave API: {str(e)}")
        raise
