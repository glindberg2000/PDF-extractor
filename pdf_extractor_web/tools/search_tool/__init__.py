"""
Search Tool Package

This package provides search functionality using SearXNG.
"""

from .search_standalone import (
    search_web,
    SearchResult,
    SafeSearchLevel,
    SearchToolException,
)

__all__ = ["search_web", "SearchResult", "SafeSearchLevel", "SearchToolException"]
