"""
Test Suite for Brave Search Vendor Lookup

This module provides tests for the vendor lookup functionality.
It demonstrates various use cases and proper handling of rate limits.
"""

import time
from brave_search import lookup_vendor_info, format_vendor_results


def test_basic_lookup():
    """
    Test a basic vendor lookup with a well-known company.
    Tests exact name matching and business relevance scoring.
    """
    print("\n=== Testing Basic Lookup (Apple Inc) ===")
    try:
        results = lookup_vendor_info("Apple Inc")
        print(format_vendor_results(results, "Apple Inc"))
    except Exception as e:
        print(f"Error: {e}")


def test_local_business():
    """
    Test lookup of a local business.
    Tests handling of retail chains and location-based businesses.
    """
    print("\n=== Testing Local Business (Albertsons) ===")
    try:
        results = lookup_vendor_info("Albertsons")
        print(format_vendor_results(results, "Albertsons"))
    except Exception as e:
        print(f"Error: {e}")


def test_industry_specific_lookup():
    """
    Test lookup with industry-specific keywords.
    Tests:
    - Industry keyword scoring based on business context
    - Location abbreviation handling
    - Domain matching
    - Result relevance without perfect knowledge
    """
    print("\n=== Testing Industry-Specific Lookup ===")

    # Test real estate business with realistic context
    print("\nTesting Real Estate Service Provider:")
    try:
        # Only use terms we'd definitely know from a real estate agent's business context
        real_estate_keywords = {
            "real estate": 5,  # Increased weight since this is our primary context
            "property": 3,
            "home": 3,
            "house": 3,
            "listing": 3,
            "residential": 2,
            "commercial": 2,
        }

        # Test with minimal context - just the business name and real estate context
        results = lookup_vendor_info(
            "Style Tours ABQ",
            max_results=15,
            industry_keywords=real_estate_keywords,
            search_query="Style Tours ABQ real estate",  # Add real estate to help context
        )
        print("\nResults with real estate context:")
        print(format_vendor_results(results, "Style Tours ABQ"))

        # Verify the results
        if results:
            top_result = results[0]
            print("\nScoring Analysis:")
            print(f"Top Result Score: {top_result['relevance_score']}")
            print(f"URL: {top_result['url']}")
            print(f"Description: {top_result['description']}")

            # Check what terms were actually found
            description = top_result["description"].lower()
            found_terms = [
                kw for kw in real_estate_keywords if kw.lower() in description
            ]
            print(f"Industry Terms Found: {', '.join(found_terms)}")

            # Log if we found additional relevant terms we didn't search for
            # Only log terms that might help us understand the vendor's services
            interesting_terms = ["listing", "broker", "agent", "realty"]
            additional_terms = [
                term for term in interesting_terms if term in description.lower()
            ]
            if additional_terms:
                print(f"Additional Relevant Terms Found: {', '.join(additional_terms)}")
    except Exception as e:
        print(f"Error: {e}")

    time.sleep(1.1)  # Ensure we wait long enough between requests

    # Test another real estate vendor with different service type
    print("\nTesting Another Real Estate Service Provider:")
    try:
        results = lookup_vendor_info(
            "Staged to Sell ABQ",
            max_results=15,
            industry_keywords=real_estate_keywords,
            search_query="Staged to Sell ABQ real estate",  # Add real estate to help context
        )
        print(format_vendor_results(results, "Staged to Sell ABQ"))
    except Exception as e:
        print(f"Error: {e}")


def test_max_results():
    """
    Test getting maximum results.
    Demonstrates:
    - How to request more results
    - Raw data format
    - Relevance scoring system
    """
    print("\n=== Testing Max Results (Microsoft, 10 results) ===")
    try:
        results = lookup_vendor_info("Microsoft", max_results=10)
        # Print raw data to see all fields
        print("\nRaw Results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Score: {result['relevance_score']}")
            print(f"   Title: {result['title']}")
            print(f"   URL: {result['url']}")
    except Exception as e:
        print(f"Error: {e}")


def test_ambiguous_name():
    """
    Test lookup with an ambiguous vendor name.
    Tests how the API handles:
    - Generic company names
    - Multiple possible matches
    - Business relevance scoring with ambiguous terms
    """
    print("\n=== Testing Ambiguous Name (Square) ===")
    try:
        results = lookup_vendor_info("Square")
        print(format_vendor_results(results, "Square"))
    except Exception as e:
        print(f"Error: {e}")


def test_error_handling():
    """
    Test error handling with invalid input.
    Tests:
    - Invalid max_results parameter
    - Error message formatting
    - Exception handling
    """
    print("\n=== Testing Error Handling ===")
    try:
        # Test with invalid max_results
        results = lookup_vendor_info("Test", max_results=30)
        print("This should not be printed due to ValueError")
    except ValueError as e:
        print(f"Successfully caught ValueError: {e}")


def test_custom_location_abbreviations():
    """
    Test custom location abbreviation handling.
    Tests:
    - Custom location mappings
    - Location score contribution
    - Multiple location formats
    """
    print("\n=== Testing Custom Location Abbreviations ===")
    try:
        # Use realistic location mappings for the area
        custom_locations = {
            "ABQ": "Albuquerque",
            "RIO": "Rio Rancho",
            "SANT": "Santa Fe",
            "NM": "New Mexico",
        }

        # Test with a real estate service provider
        results = lookup_vendor_info(
            "Style Tours ABQ",
            max_results=15,
            location_abbreviations=custom_locations,
            search_query="Style Tours ABQ real estate",  # Add real estate to help context
        )
        print(format_vendor_results(results, "Style Tours ABQ"))

        time.sleep(1.1)  # Ensure we wait long enough between requests

        # Test with different location format
        results = lookup_vendor_info(
            "Staged to Sell NM",
            max_results=15,
            location_abbreviations=custom_locations,
            search_query="Staged to Sell NM real estate",  # Add real estate to help context
        )
        print(format_vendor_results(results, "Staged to Sell NM"))
    except Exception as e:
        print(f"Error: {e}")


def run_tests_with_rate_limit():
    """
    Run all tests with appropriate delays to respect rate limits.
    Free plan limitation: 1 request per second
    """
    print("Running vendor lookup tests...")
    print("Note: Tests will be executed with 1-second delays to respect rate limits")

    # Run all tests with delays
    test_basic_lookup()
    time.sleep(1.1)  # Added .1 second buffer to be safe

    test_local_business()
    time.sleep(1.1)

    test_industry_specific_lookup()  # This test has its own internal delays
    time.sleep(1.1)

    test_max_results()
    time.sleep(1.1)

    test_ambiguous_name()
    time.sleep(1.1)

    test_error_handling()
    time.sleep(1.1)

    test_custom_location_abbreviations()  # This test has its own internal delays

    print("\nTests completed!")


if __name__ == "__main__":
    run_tests_with_rate_limit()
