import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Tool metadata
name = "brave_search"
description = "Search for vendor information using Brave Search API"


def brave_search(query):
    """Search for vendor information using Brave Search API."""
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise ValueError("BRAVE_SEARCH_API_KEY not found in environment variables")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": 5}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    results = response.json()
    return {
        "results": [
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "description": result.get("description", ""),
            }
            for result in results.get("web", {}).get("results", [])
        ]
    }
