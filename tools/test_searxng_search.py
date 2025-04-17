"""
Tests for the SearXNG search tool.
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.searxng_search import search_web, SafeSearchLevel, format_search_results


def test_search_web_success():
    """Test successful search with mock response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Test Result 1",
                "url": "https://example.com/1",
                "content": "Test content 1",
            },
            {
                "title": "Test Result 2",
                "url": "https://example.com/2",
                "content": "Test content 2",
            },
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response):
        results = search_web("test query", num_results=2)

        assert len(results) == 2
        assert results[0]["title"] == "Test Result 1"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["content"] == "Test content 1"
        assert results[1]["title"] == "Test Result 2"
        assert results[1]["url"] == "https://example.com/2"
        assert results[1]["content"] == "Test content 2"


def test_search_web_empty_query():
    """Test that empty query raises ValueError."""
    with pytest.raises(ValueError, match="Search query cannot be empty"):
        search_web("")


def test_search_web_invalid_num_results():
    """Test that invalid num_results raises ValueError."""
    with pytest.raises(ValueError, match="num_results must be greater than 0"):
        search_web("test query", num_results=0)


def test_search_web_network_error():
    """Test handling of network errors."""
    with patch("requests.get", side_effect=Exception("Network error")):
        with pytest.raises(RuntimeError, match="SearXNG API error"):
            search_web("test query")


def test_search_web_with_engines():
    """Test search with specific engines."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        search_web("test query", engines=["google", "bing"])

        # Check that engines parameter was included in request
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        assert "params" in call_args
        assert call_args["params"]["engines"] == "google,bing"


def test_search_web_with_safesearch():
    """Test search with different safesearch levels."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        search_web("test query", safesearch=SafeSearchLevel.STRICT)

        # Check that safesearch parameter was included in request
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        assert "params" in call_args
        assert call_args["params"]["safesearch"] == SafeSearchLevel.STRICT


def test_format_search_results():
    """Test formatting of search results."""
    results = [
        {
            "title": "Test Result",
            "url": "https://example.com",
            "content": "This is a test result with some content that should be truncated...",
        }
    ]
    query = "test query"

    formatted = format_search_results(results, query)

    assert "Search Results for 'test query'" in formatted
    assert "Test Result" in formatted
    assert "https://example.com" in formatted
    assert "This is a test result" in formatted


def test_format_search_results_empty():
    """Test formatting of empty search results."""
    results = []
    query = "test query"

    formatted = format_search_results(results, query)

    assert "No results found" in formatted
