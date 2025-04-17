"""
Search Library Package

This package provides search functionality using various search engines.
"""

from .searxng import (
    search_web,
    SearchResult,
    SafeSearchLevel,
    SearchToolException
)

__all__ = [
    'search_web',
    'SearchResult',
    'SafeSearchLevel',
    'SearchToolException'
] 