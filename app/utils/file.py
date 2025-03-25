import os
from pathlib import Path


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if it doesn't."""
    os.makedirs(path, exist_ok=True)
