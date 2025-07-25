"""
Setup script for PDF-extractor (dataextractai)

Allows editable install for Django and plugin integration:
    pip install -e .

This ensures dataextractai modules are importable from Django and other projects.
"""

from setuptools import setup, find_packages

# Use include pattern to ensure all subpackages (like parsers) are included
setup(
    name="dataextractai",
    version="0.1.0",
    packages=find_packages(include=["dataextractai", "dataextractai.*"]),
    install_requires=[
        "pandas>=2.0.0",
        "PyYAML>=6.0.0",
        "PyPDF2>=3.0.0",
        "numpy>=1.21.0",
        "python-dateutil>=2.8.2",
        "pytz>=2020.1",
        "PyMuPDF>=1.23.0",
    ],
    author="PDF Extractor Team",
    description="Modular PDF data extraction system (parsers, registry, CLI, Django integration)",
    include_package_data=True,
)
