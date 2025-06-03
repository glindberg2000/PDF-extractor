"""
Parser Autodiscovery Utility

This module provides autodiscover_parsers(), which recursively imports all modules in
dataextractai.parsers, ensuring all register_parser calls are executed and the parser
registry is fully populated. Use this in Django, CLI, or any integration to dynamically
discover all available parsers.

Usage:
    from dataextractai.parsers_core.autodiscover import autodiscover_parsers
    autodiscover_parsers()  # Populates ParserRegistry

    # List all registered parser names:
    from dataextractai.parsers_core.registry import ParserRegistry
    print(ParserRegistry.list_parsers())
"""

import importlib
import pkgutil
from dataextractai.parsers_core.registry import ParserRegistry
import sys


def autodiscover_parsers():
    """
    Recursively import all modules in dataextractai.parsers to trigger parser registration.
    Returns the parser registry dict for inspection.
    """
    import dataextractai.parsers

    package = dataextractai.parsers
    for _, modname, ispkg in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        print(f"[DEBUG] Importing module: {modname}", file=sys.stderr)
        importlib.import_module(modname)
    return ParserRegistry._parsers
