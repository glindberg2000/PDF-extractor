"""
Live test script for the standalone SearXNG search tool.
This script tests the search functionality against a running SearXNG instance.
"""

import sys
from pathlib import Path

# Get the absolute path to the project root
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from standalone_tools.search.search_standalone import (
    search_web,
    format_search_results,
    SafeSearchLevel,
)


def main():
    """Run live tests against the SearXNG instance."""
    print("Testing SearXNG search functionality...")

    # Test basic search
    print("\n1. Testing basic search:")
    query = "python programming"
    results = search_web(query, num_results=3)
    print(format_search_results(results, query))

    # Test search with specific engines
    print("\n2. Testing search with specific engines:")
    query = "python programming"
    results = search_web(query, engines=["google", "bing"], num_results=2)
    print(format_search_results(results, query))

    # Test search with safesearch
    print("\n3. Testing search with safesearch:")
    query = "python programming"
    results = search_web(query, safesearch=SafeSearchLevel.STRICT, num_results=2)
    print(format_search_results(results, query))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        sys.exit(1)
