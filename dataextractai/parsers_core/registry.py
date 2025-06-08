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

    @classmethod
    def detect_parser_for_file(cls, file_path):
        """
        Returns the name of the first parser whose can_parse returns True for the file.
        Returns None if no parser matches.
        """
        for parser_name in cls.list_parsers():
            parser_cls = cls.get_parser(parser_name)
            parser = parser_cls()
            try:
                if hasattr(parser, "can_parse") and parser.can_parse(file_path):
                    return parser_name
            except Exception as e:
                print(f"[WARN] Parser {parser_name} errored on {file_path}: {e}")
        return None

    @classmethod
    def batch_detect_parsers(cls, file_paths):
        """
        Returns a dict mapping file_path -> detected parser name (or None).
        """
        return {fp: cls.detect_parser_for_file(fp) for fp in file_paths}
