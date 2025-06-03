from typing import Type, Dict
from .base import BaseParser


class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register_parser(cls, name: str, parser_cls: Type[BaseParser]):
        cls._parsers[name] = parser_cls

    @classmethod
    def get_parser(cls, name: str) -> Type[BaseParser]:
        return cls._parsers.get(name)
