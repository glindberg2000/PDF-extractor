"""
Search Tool Package

This package provides search functionality using SearXNG.
"""

from .search_standalone import (
    search_web,
    SafeSearchLevel,
    SearchResult,
    function_schema,
)

__all__ = ["search_web", "SafeSearchLevel", "SearchResult", "function_schema"]
