from setuptools import setup, find_packages

setup(
    name="dataextractai-vision",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
        "pdf2image>=1.16.3",
        "Pillow>=10.0.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "dataextractai-vision=dataextractai_vision.cli:run",
        ],
    },
    author="Gregory Lindberg",
    author_email="greglindbereg@gmail.com",
    description="Vision-based PDF transaction extractor using GPT-4 Vision",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/glindberg2000/PDF-extractor",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)
