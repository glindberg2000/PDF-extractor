from setuptools import setup, find_packages
import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """Check and install required dependencies."""
    required_packages = [
        "pandas>=2.0.0",
        "numpy>=1.21.0",
        "PyYAML>=6.0.0",
        "python-dotenv>=1.0.0",
        "openai>=1.0.0",
        "pdfplumber>=0.7.0",
        "PyPDF2>=3.0.0",
        "PyMuPDF>=1.23.0",
        "typer>=0.9.0",
        "rich>=12.0.0",
        "click>=8.0.0",
        "google-auth-oauthlib>=1.0.0",
        "google-auth-httplib2>=0.1.0",
        "google-api-python-client>=2.0.0",
        "gspread>=5.0.0",
    ]

    print("Checking dependencies...")
    for package in required_packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")
            print("Please try installing manually:")
            print(f"pip install {package}")
            sys.exit(1)


def check_environment():
    """Check environment variables and files."""
    required_vars = [
        "OPENAI_API_KEY",
        "GOOGLE_SHEETS_CREDENTIALS_PATH",
        "GOOGLE_SHEETS_ID",
    ]

    missing_vars = []
    for var in required_vars:
        if not Path(f".env").exists():
            print("Creating .env file...")
            with open(".env", "w") as f:
                for v in required_vars:
                    f.write(f"{v}=\n")
            print("Please edit .env with your API keys and credentials")
            sys.exit(1)

    if not Path("credentials.json").exists():
        print("Google Sheets credentials not found!")
        print("Please:")
        print("1. Go to Google Cloud Console")
        print("2. Create a project")
        print("3. Enable Google Sheets API")
        print("4. Create OAuth 2.0 credentials")
        print("5. Download as credentials.json")
        sys.exit(1)


def main():
    """Main setup function."""
    print("Setting up PDF-extractor...")

    # Check dependencies
    check_dependencies()

    # Check environment
    check_environment()

    # Create client directories
    Path("clients").mkdir(exist_ok=True)
    Path("data/sample").mkdir(parents=True, exist_ok=True)

    print("\nSetup complete! You can now use PDF-extractor.")
    print("\nQuick start:")
    print("1. python -m dataextractai.cli.main setup my_client")
    print("2. Place PDF files in clients/my_client/input/")
    print("3. python -m dataextractai.cli.main process my_client")
    print("4. python -m dataextractai.cli.main upload my_client")


if __name__ == "__main__":
    main()

setup(
    name="dataextractai",
    version="0.1",
    packages=find_packages(),
    install_requires=["openai", "python-dotenv", "pandas", "questionary", "click"],
    entry_points={
        "console_scripts": [
            "dataextractai=dataextractai.cli.main:app",
        ],
    },
    author="Gregory Lindberg",
    author_email="greglindbereg@gmail.com",
    description="PDF-extractor: Extract and process financial data from PDF statements",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/glindberg2000/PDF-extractor",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)
