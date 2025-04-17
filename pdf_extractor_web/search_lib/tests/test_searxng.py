"""
Test Suite for SearXNG Search Tool

This module provides tests for the SearXNG search functionality.
It demonstrates various use cases and proper error handling.
"""

import os
import sys
from pathlib import Path
import pytest
from pdf_extractor_web.search_lib import (
    search_web,
    SearchResult,
    SafeSearchLevel,
    SearchToolException
)


def test_basic_search():
    """Test a basic search query with default parameters."""
    print("\n=== Testing Basic Search (Python Django) ===")
    try:
        results = search_web(
            query="Python Django web framework",
            num_results=5,
            safesearch=SafeSearchLevel.MODERATE
        )
        
        assert isinstance(results, list), "Results should be a list"
        assert len(results) <= 5, "Should not exceed requested number of results"
        
        for result in results:
            assert isinstance(result, dict), "Each result should be a dictionary"
            assert "title" in result, "Result should have a title"
            assert "url" in result, "Result should have a URL"
            assert "content" in result, "Result should have content"
            
            print(f"\nTitle: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"Content: {result['content'][:200]}...")  # First 200 chars
            
    except SearchToolException as e:
        pytest.fail(f"Search tool error: {str(e)}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {str(e)}")


def test_empty_query():
    """Test handling of empty search queries."""
    print("\n=== Testing Empty Query ===")
    with pytest.raises(SearchToolException):
        search_web(query="")


def test_invalid_num_results():
    """Test handling of invalid num_results parameter."""
    print("\n=== Testing Invalid num_results ===")
    with pytest.raises(SearchToolException):
        search_web(query="test", num_results=0)
    with pytest.raises(SearchToolException):
        search_web(query="test", num_results=-1)


def test_custom_language():
    """Test search with custom language setting."""
    print("\n=== Testing Custom Language Search ===")
    try:
        results = search_web(
            query="bonjour monde",
            language="fr-FR",
            num_results=3
        )
        assert len(results) <= 3
        print(f"\nFound {len(results)} results in French")
        
    except SearchToolException as e:
        pytest.fail(f"Search tool error: {str(e)}")


def test_safe_search_levels():
    """Test different safe search levels."""
    print("\n=== Testing Safe Search Levels ===")
    for level in SafeSearchLevel:
        try:
            results = search_web(
                query="cute cats",
                safesearch=level,
                num_results=1
            )
            print(f"\nSafe Search Level {level.name}: Found {len(results)} results")
            
        except SearchToolException as e:
            pytest.fail(f"Search tool error with {level.name}: {str(e)}")


def test_custom_engines():
    """Test search with specific engines."""
    print("\n=== Testing Custom Engines ===")
    try:
        results = search_web(
            query="latest news",
            engines=["google", "bing", "duckduckgo"],
            num_results=5
        )
        assert len(results) <= 5
        print(f"\nFound {len(results)} results using custom engines")
        
    except SearchToolException as e:
        pytest.fail(f"Search tool error: {str(e)}")


if __name__ == "__main__":
    # Ensure SearXNG service is running
    print("Running SearXNG search tool tests...")
    print("Make sure the SearXNG service is running at http://localhost:8080")
    
    # Run all tests
    pytest.main([__file__, "-v"]) 