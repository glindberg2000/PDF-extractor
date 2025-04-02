"""
Test Suite for Brave Search Vendor Lookup

This module provides tests for the vendor lookup functionality.
It demonstrates various use cases and proper handling of rate limits.
"""

import time
from .brave_search import lookup_vendor_info, format_vendor_results


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


def run_tests_with_rate_limit():
    """
    Run all tests with appropriate delays to respect rate limits.
    Free plan limitation: 1 request per second
    """
    print("Running vendor lookup tests...")
    print("Note: Tests will be executed with 1-second delays to respect rate limits")

    # Run all tests with delays
    test_basic_lookup()
    time.sleep(1)  # Respect rate limit

    test_local_business()
    time.sleep(1)  # Respect rate limit

    test_max_results()
    time.sleep(1)  # Respect rate limit

    test_ambiguous_name()
    time.sleep(1)  # Respect rate limit

    test_error_handling()

    print("\nTests completed!")


if __name__ == "__main__":
    run_tests_with_rate_limit()
