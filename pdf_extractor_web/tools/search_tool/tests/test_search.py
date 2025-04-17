import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from tools.search_tool.search import search_web, SafeSearchLevel


def test_search():
    """Test the search tool functionality"""
    try:
        # Test a simple search query
        query = "Python Django web framework"
        print(f"\nSearching for: {query}")

        results = search_web(
            query=query,
            num_results=5,
            safesearch=SafeSearchLevel.MODERATE,
            host="http://localhost:8888",
        )

        print("\nSearch Results:")
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(
                f"Content: {result['content'][:200]}..."
            )  # Show first 200 chars of content

    except Exception as e:
        print(f"Error during search: {str(e)}")


if __name__ == "__main__":
    test_search()
