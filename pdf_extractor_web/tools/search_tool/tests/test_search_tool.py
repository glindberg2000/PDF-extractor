import pytest
from unittest.mock import patch, MagicMock
from ..search import search_web, SearchToolException, SafeSearchLevel

# Mock response data
MOCK_RESPONSE = {
    "results": [
        {
            "title": "Test Result 1",
            "url": "https://example.com/1",
            "content": "This is a test result",
        },
        {
            "title": "Test Result 2",
            "url": "https://example.com/2",
            "content": "Another test result",
        },
    ]
}


def test_search_web_success():
    """Test successful search with default parameters"""
    with patch("requests.get") as mock_get:
        # Configure mock
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        results = search_web("test query")

        # Verify results
        assert len(results) == 2
        assert results[0]["title"] == "Test Result 1"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["content"] == "This is a test result"

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        assert "params" in call_args
        assert call_args["params"]["q"] == "test query"
        assert call_args["params"]["format"] == "json"
        assert call_args["params"]["pageno"] == 1


def test_search_web_custom_params():
    """Test search with custom parameters"""
    with patch("requests.get") as mock_get:
        # Configure mock
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call with custom parameters
        results = search_web(
            "test query",
            num_results=1,
            engines=["google", "bing"],
            language="fr-FR",
            safesearch=SafeSearchLevel.STRICT,
        )

        # Verify results
        assert len(results) == 1

        # Verify API call
        call_args = mock_get.call_args[1]
        assert call_args["params"]["engines"] == "google,bing"
        assert call_args["params"]["language"] == "fr-FR"
        assert call_args["params"]["safesearch"] == SafeSearchLevel.STRICT


def test_search_web_empty_query():
    """Test handling of empty query"""
    with pytest.raises(SearchToolException):
        search_web("")


def test_search_web_network_error():
    """Test handling of network errors"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(SearchToolException) as exc_info:
            search_web("test query")
        assert "Network error" in str(exc_info.value)


def test_search_web_invalid_json():
    """Test handling of invalid JSON response"""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(SearchToolException) as exc_info:
            search_web("test query")
        assert "Invalid JSON" in str(exc_info.value)


def test_search_web_custom_host():
    """Test search with custom host URL"""
    with patch("requests.get") as mock_get:
        # Configure mock
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call with custom host
        search_web("test query", host="https://custom.searxng.com")

        # Verify API call
        mock_get.assert_called_once()
        assert "https://custom.searxng.com/search" in mock_get.call_args[0][0]
