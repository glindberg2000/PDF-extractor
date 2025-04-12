import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add the project root directory to the Python path
import sys

sys.path.append(str(BASE_DIR.parent))

# ... rest of the settings file ...
