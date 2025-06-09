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
import os
import pathlib


def autodiscover_parsers():
    """
    Recursively import all parser modules in dataextractai.parsers, handling both *_parser.py and *.py files (except __init__.py).
    Ensures all register_parser calls are executed and the parser registry is fully populated with canonical names.
    Returns the parser registry dict for inspection.
    """
    import dataextractai.parsers

    package = dataextractai.parsers
    package_dir = pathlib.Path(package.__path__[0])
    imported = set()
    for pyfile in package_dir.glob("*.py"):
        if pyfile.name == "__init__.py":
            continue
        modname = f"{package.__name__}.{pyfile.stem}"
        print(f"[DEBUG] Importing parser module: {modname}", file=sys.stderr)
        importlib.import_module(modname)
        imported.add(pyfile.stem)
    for pyfile in package_dir.glob("*_parser.py"):
        if pyfile.name == "__init__.py":
            continue
        modname = f"{package.__name__}.{pyfile.stem}"
        if pyfile.stem in imported:
            continue  # Already imported
        print(f"[DEBUG] Importing parser module: {modname}", file=sys.stderr)
        importlib.import_module(modname)
        imported.add(pyfile.stem)
    print(
        f"[DEBUG] Registered parsers: {ParserRegistry.list_parsers()}", file=sys.stderr
    )
    return ParserRegistry._parsers
