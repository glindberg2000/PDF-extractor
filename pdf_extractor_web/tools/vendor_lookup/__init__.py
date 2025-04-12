"""
Vendor Lookup Tools

This package provides tools for looking up vendor information using various search APIs.
Currently supports Brave Search API.
"""

from .brave_search import search, SearchResult

__all__ = ['search', 'SearchResult']
