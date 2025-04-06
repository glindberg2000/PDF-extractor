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


def lookup_vendor_info(
    vendor_name: str,
    max_results: int = 5,
    industry_keywords: Dict[str, int] = None,
    location_abbreviations: Dict[str, str] = None,
    search_query: str = None,
) -> List[VendorInfo]:
    """
    Look up information about a business/vendor using the Brave Search API.

    Args:
        vendor_name: The name of the vendor/business to look up
        max_results: Maximum number of results to return (default: 5, max: 20)
        industry_keywords: Optional dictionary of industry-specific keywords and their scores
            e.g. {"real estate": 3, "property": 2}
        location_abbreviations: Optional dictionary mapping location abbreviations to full names
            e.g. {"ABQ": "Albuquerque", "NYC": "New York City"}
        search_query: Optional custom search query. If not provided, will use vendor_name

    Returns:
        List of VendorInfo dictionaries, sorted by relevance score (highest first).
    """
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        raise ValueError("BRAVE_API_KEY not found in environment variables")

    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20")

    # Use default location abbreviations if none provided
    location_abbreviations = location_abbreviations or {
        "ABQ": "Albuquerque",
        "NYC": "New York City",
        "LA": "Los Angeles",
        "SF": "San Francisco",
        "PHX": "Phoenix",
    }

    # Clean vendor name and extract location
    vendor_parts = vendor_name.split()
    location = None
    if len(vendor_parts) > 1:
        possible_abbrev = vendor_parts[-1].upper()
        if possible_abbrev in location_abbreviations:
            location = location_abbreviations[possible_abbrev]

    # Use provided search query or just vendor name
    query = search_query if search_query else vendor_name

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": brave_api_key,
    }
    params = {
        "q": query,
        "count": max_results,
        "text_format": "html",
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
            title = result["title"]
            description = result.get("description", "")
            url = result["url"]

            # Exact match bonus
            if vendor_name.lower() == title.lower():
                relevance_score += 10

            # Domain name match
            domain = url.lower().split("//")[-1].split("/")[0]
            vendor_domain = vendor_name.lower().replace(" ", "")
            if vendor_domain in domain:
                relevance_score += 8

            # Partial name match in title
            if vendor_name.lower() in title.lower():
                relevance_score += 5

            # Location match
            if location:
                if location.lower() in (title + description + url).lower():
                    relevance_score += 4

            # Industry-specific keyword scoring
            if industry_keywords:
                content = (title + " " + description).lower()
                for keyword, score in industry_keywords.items():
                    if keyword.lower() in content:
                        relevance_score += score

            if relevance_score > 0:
                vendor_info: VendorInfo = {
                    "title": title,
                    "url": url,
                    "description": description.replace("\n", " ").strip(),
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
