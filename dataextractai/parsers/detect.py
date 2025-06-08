import os
from dataextractai.parsers_core.autodiscover import autodiscover_parsers
from dataextractai.parsers_core.registry import ParserRegistry

autodiscover_parsers()


def detect_parser_for_file(file_path):
    """
    Given a file path, return the name of the first parser whose can_parse returns True.
    Returns None if no parser matches.
    """
    return ParserRegistry.detect_parser_for_file(file_path)


def batch_detect_parsers(file_paths):
    """
    Given a list of file paths, return a dict mapping each file to the detected parser name (or None).
    """
    return ParserRegistry.batch_detect_parsers(file_paths)


def _find_files_in_dir(directory, exts=(".pdf", ".csv")):
    files = []
    for root, _, filenames in os.walk(directory):
        for fname in filenames:
            if fname.lower().endswith(exts):
                files.append(os.path.join(root, fname))
    return files


if __name__ == "__main__":
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
