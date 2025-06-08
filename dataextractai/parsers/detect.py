import os
from dataextractai.parsers_core.registry import ParserRegistry


def detect_parser_for_file(file_path):
    """
    Given a file path, return the name of the first parser whose can_parse returns True.
    Returns None if no parser matches.
    """
    for parser_name, parser_cls in ParserRegistry.get_all_parsers().items():
        can_parse = getattr(parser_cls, "can_parse", None)
        if callable(can_parse):
            try:
                if can_parse(file_path):
                    return parser_name
            except Exception:
                continue
    return None


def batch_detect_parsers(file_paths):
    """
    Given a list of file paths, return a dict mapping each file to the detected parser name (or None).
    """
    return {fp: detect_parser_for_file(fp) for fp in file_paths}


def _find_files_in_dir(directory, exts=(".pdf", ".csv")):
    files = []
    for root, _, filenames in os.walk(directory):
        for fname in filenames:
            if fname.lower().endswith(exts):
                files.append(os.path.join(root, fname))
    return files


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Detect the correct parser for files.")
    parser.add_argument("path", help="File or directory to scan")
    args = parser.parse_args()
    path = args.path
    if os.path.isdir(path):
        files = _find_files_in_dir(path)
    else:
        files = [path]
    results = batch_detect_parsers(files)
    for fp, parser_name in results.items():
        print(f"{fp}: {parser_name}")
