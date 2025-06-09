def extract_date_from_filename(filename: str) -> str | None:
    """Extracts a YYYY-MM-DD date from an 8-digit sequence in the filename, if possible."""
    import os
    import re
    from dateutil import parser as dateutil_parser

    base = os.path.basename(filename)
    m = re.search(r"(\d{8})", base)
    if m:
        try:
            dt = dateutil_parser.parse(m.group(1), fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None
    return None
