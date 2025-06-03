from typing import Type, Dict
from .base import BaseParser
import sys


class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register_parser(cls, name: str, parser_cls: Type[BaseParser]):
        print(f"[DEBUG] Registering parser: {name} -> {parser_cls}", file=sys.stderr)
        cls._parsers[name] = parser_cls

    @classmethod
    def get_parser(cls, name: str) -> Type[BaseParser]:
        return cls._parsers.get(name)

    @classmethod
    def list_parsers(cls):
        return list(cls._parsers.keys())
