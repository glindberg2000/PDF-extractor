"""
Brave Search API Integration for Vendor Information Lookup

This tool uses the Brave Search API to look up vendor information and descriptions.
It takes a vendor name as input and returns structured information about the vendor,
including a description and relevant details.

The tool requires a BRAVE_SEARCH_API_KEY environment variable to be set.
"""

import os
import json
import time
import requests
import re
from typing import Dict, List, Optional, TypedDict, Union, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Schema for the tool's response
SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "url": {"type": "string"},
            "score": {"type": "number"},
        },
        "required": ["title", "description"],
    },
}


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
    brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not brave_api_key:
        raise ValueError("BRAVE_SEARCH_API_KEY not found in environment variables")

    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20")

    # Use default location abbreviations if none provided
    location_abbreviations = location_abbreviations or {
        "ABQ": "Albuquerque",
        "NYC": "New York City",
        "LA": "Los Angeles",
        "SF": "San Francisco",
        "PHX": "Phoenix",
        "NM": "New Mexico",  # Added New Mexico
        "AZ": "Arizona",  # Added more states
        "CA": "California",
        "TX": "Texas",
        "CO": "Colorado",
    }

    # Clean vendor name and extract location
    vendor_parts = vendor_name.split()
    location = None
    if len(vendor_parts) > 1:
        # Check for state abbreviation at the end
        possible_state = vendor_parts[-1].upper()
        if possible_state in location_abbreviations:
            location = location_abbreviations[possible_state]
            # Remove state from vendor name for search
            vendor_parts = vendor_parts[:-1]

        # Check for city name before state
        if len(vendor_parts) > 2:
            possible_city = " ".join(vendor_parts[-2:])
            if any(
                city.lower() in possible_city.lower()
                for city in location_abbreviations.values()
            ):
                # Found a city, remove it from vendor name
                vendor_parts = vendor_parts[:-2]

    # Clean the vendor name - remove store numbers and common suffixes
    clean_vendor = " ".join(vendor_parts)
    clean_vendor = re.sub(r"\s*#?\d+\s*", " ", clean_vendor)  # Remove store numbers
    clean_vendor = re.sub(r"\s+", " ", clean_vendor).strip()  # Clean up whitespace

    # First search: Get basic info about the business
    initial_query = f"{clean_vendor}"
    if location:
        initial_query += f" {location}"

    # Business type keywords to look for in results
    business_types = {
        "gas_station": [
            "gas station",
            "fuel",
            "gasoline",
            "petroleum",
            "convenience store",
        ],
        "retail": ["retail", "store", "supermarket", "department store", "shopping"],
        "restaurant": ["restaurant", "food", "dining", "cafe", "eatery"],
        "pharmacy": ["pharmacy", "drug store", "prescription", "medications"],
        "service": ["service", "repair", "maintenance", "professional"],
    }

    # Add retry logic for rate limits
    max_retries = 3
    retry_delay = 1  # Start with 1 second delay

    for attempt in range(max_retries):
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": brave_api_key,
            }
            params = {
                "q": initial_query,
                "count": max_results,
                "text_format": "html",
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            results = response.json()

            # Process and score results
            business_results: List[VendorInfo] = []

            if "web" in results and "results" in results["web"]:
                # First pass: Identify business type from results
                business_type_scores = {btype: 0 for btype in business_types}

                for result in results["web"]["results"]:
                    content = (
                        result["title"] + " " + result.get("description", "")
                    ).lower()

                    # Score each business type based on keyword matches
                    for btype, keywords in business_types.items():
                        for keyword in keywords:
                            if keyword in content:
                                business_type_scores[btype] += 1

                # Get the most likely business type
                likely_type = (
                    max(business_type_scores.items(), key=lambda x: x[1])[0]
                    if any(business_type_scores.values())
                    else None
                )

                # Second pass: Score results with business type context
                for result in results["web"]["results"]:
                    relevance_score = 0
                    title = result["title"]
                    description = result.get("description", "")
                    url = result["url"]
                    content = (title + " " + description).lower()

                    # Basic relevance scoring
                    if clean_vendor.lower() in title.lower():
                        relevance_score += 5

                    # Domain relevance
                    domain = url.lower().split("//")[-1].split("/")[0]
                    if clean_vendor.lower().replace(" ", "") in domain:
                        relevance_score += 3

                    # Location match
                    if location and location.lower() in content:
                        relevance_score += 2

                    # Business type relevance
                    if likely_type:
                        for keyword in business_types[likely_type]:
                            if keyword in content:
                                relevance_score += 2

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
            raise RuntimeError(f"Brave Search API error: {error_detail}")


def search(query: str, num_results: int = 3) -> List[Dict[str, Any]]:
    """
    Wrapper function for the tool discovery system.
    Takes a query and returns a list of search results.

    Args:
        query: The search query
        num_results: Number of results to return (default: 3)

    Returns:
        List of search results with title, description, and URL
    """
    results = lookup_vendor_info(query, max_results=num_results)
    return [
        {
            "title": r["title"],
            "description": r["description"],
            "url": r["url"],
            "score": r["relevance_score"],
        }
        for r in results
    ]
