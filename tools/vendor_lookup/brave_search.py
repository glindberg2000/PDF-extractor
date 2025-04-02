"""
Brave Search API Integration for Vendor Information Lookup

This module provides functionality to look up vendor/business information using the Brave Search API.
It's designed to help identify and categorize vendors from financial statements or transaction records.

Rate Limits:
    Free Plan: 1 request per second (1 QPS)
    To handle rate limits:
    - Add delays between requests (time.sleep(1))
    - Catch 429 errors and implement backoff
    - Consider caching results for frequently looked up vendors

Usage:
    from tools.vendor_lookup import lookup_vendor_info, format_vendor_results

    # Basic lookup
    results = lookup_vendor_info("Apple Inc")

    # With custom result count (max 20)
    results = lookup_vendor_info("Microsoft", max_results=10)

    # Format results for display
    formatted = format_vendor_results(results, "Apple Inc")
    print(formatted)

Environment Variables Required:
    BRAVE_API_KEY: Your Brave Search API key
"""

import os
import json
import time
import requests
from typing import Dict, List, Optional, TypedDict, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class VendorInfo(TypedDict):
    """
    Type definition for vendor information returned by the lookup.

    Attributes:
        title: The business name or title from search results
        url: Website URL of the business
        description: Business description if available
        last_updated: When the information was last updated
        relevance_score: Numerical score indicating result relevance
    """

    title: str
    url: str
    description: Optional[str]
    last_updated: Optional[str]
    relevance_score: int


def lookup_vendor_info(vendor_name: str, max_results: int = 5) -> List[VendorInfo]:
    """
    Look up information about a business/vendor using the Brave Search API.

    Note on Rate Limits:
        The free plan is limited to 1 request per second.
        If you need to make multiple lookups, add a 1-second delay between calls.

    Args:
        vendor_name: The name of the vendor/business to look up
        max_results: Maximum number of results to return (default: 5, max: 20)

    Returns:
        List of VendorInfo dictionaries, sorted by relevance score (highest first).
        Each dictionary contains:
            - title: The business title
            - url: The business website URL
            - description: Business description (if available)
            - last_updated: When the information was last updated (if available)
            - relevance_score: How relevant the result is to the search

    Raises:
        ValueError: If BRAVE_API_KEY is missing or max_results is invalid
        RuntimeError: If the API request fails (including rate limit errors)

    Example:
        >>> results = lookup_vendor_info("Apple Inc", max_results=3)
        >>> for result in results:
        ...     print(f"{result['title']}: {result['relevance_score']}")
    """
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        raise ValueError("BRAVE_API_KEY not found in environment variables")

    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20")

    # Add business-focused keywords to improve results
    search_query = f"{vendor_name} business company information"

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": brave_api_key,
    }
    params = {
        "q": search_query,
        "count": max_results,
        "text_format": "html",  # Get formatted text for better parsing
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        results = response.json()
    except requests.exceptions.RequestException as e:
        if response := getattr(e, "response", None):
            if response.status_code == 429:
                raise RuntimeError(
                    "Rate limit exceeded. Wait 1 second between requests."
                )
            error_detail = f"Status: {response.status_code}, Response: {response.text}"
        else:
            error_detail = str(e)
        raise RuntimeError(f"Brave Search API error: {error_detail}")

    # Process and score results
    business_results: List[VendorInfo] = []

    if "web" in results and "results" in results["web"]:
        for result in results["web"]["results"]:
            relevance_score = 0

            # Business indicators for scoring
            business_keywords = [
                "inc",
                "llc",
                "ltd",
                "corporation",
                "company",
                "corp",
                "business",
                "official site",
                "official website",
                "store",
                "shop",
            ]

            title_lower = result["title"].lower()
            desc_lower = result.get("description", "").lower()

            # Score based on vendor name match
            if vendor_name.lower() in title_lower:
                relevance_score += 3
            if vendor_name.lower() in desc_lower:
                relevance_score += 2

            # Score based on business keywords
            for keyword in business_keywords:
                if keyword in title_lower:
                    relevance_score += 2
                if keyword in desc_lower:
                    relevance_score += 1

            if relevance_score > 0:
                vendor_info: VendorInfo = {
                    "title": result["title"],
                    "url": result["url"],
                    "description": result.get("description", "")
                    .replace("\n", " ")
                    .strip(),
                    "last_updated": result.get("age"),
                    "relevance_score": relevance_score,
                }
                business_results.append(vendor_info)

    # Sort by relevance score
    business_results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return business_results


def format_vendor_results(vendor_results: List[VendorInfo], vendor_name: str) -> str:
    """
    Format vendor results into a readable string.

    Args:
        vendor_results: List of vendor information from lookup_vendor_info
        vendor_name: Original vendor name searched for

    Returns:
        Formatted string containing vendor information, including:
        - Business name
        - Website URL
        - Business description
        - Last updated date

    Example:
        >>> results = lookup_vendor_info("Apple Inc")
        >>> print(format_vendor_results(results, "Apple Inc"))
    """
    output = []
    output.append(f"\nVendor Information for '{vendor_name}':")

    if vendor_results:
        output.append("\nPossible Business Matches:")
        for result in vendor_results:
            output.append(f"\n• {result['title']}")
            output.append(f"  URL: {result['url']}")
            if result["description"]:
                output.append(f"  Description: {result['description']}")
            if result["last_updated"]:
                output.append(f"  Last Updated: {result['last_updated']}")
            output.append("")
    else:
        output.append(
            "\nNo clear business matches found. Try refining the vendor name."
        )

    return "\n".join(output)
