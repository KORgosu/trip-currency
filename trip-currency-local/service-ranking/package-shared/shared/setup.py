#!/usr/bin/env python3
"""
Trip Currency Shared Package Setup
환율 서비스의 공통 모듈 라이브러리
"""

from setuptools import setup, find_packages
import os

# README 파일 읽기
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Trip Currency Shared Package"

# requirements.txt 읽기
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="shared",
    version="1.0.0",
    author="KORgosu",
    author_email="korgosu@example.com",
    description="Trip Currency Service의 공통 모듈 라이브러리",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/KORgosu/shared_package_local",
    project_urls={
        "Bug Tracker": "https://github.com/KORgosu/shared_package_local/issues",
        "Documentation": "https://github.com/KORgosu/shared_package_local#readme",
        "Source Code": "https://github.com/KORgosu/shared_package_local",
    },
    packages=["shared"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Database",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.8",
    install_requires=[
        # FastAPI and web framework
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        
        # Database drivers
        "aiomysql>=0.2.0",
        "redis[hiredis]>=5.0.1",
        "motor>=3.3.2",
        "pymongo>=4.6.0",
        
        # AWS SDK
        "boto3>=1.34.0",
        "botocore>=1.34.0",
        
        # HTTP clients
        "aiohttp>=3.9.1",
        "httpx>=0.25.2",
        "requests>=2.31.0",
        
        # Data processing
        "pandas>=2.1.4",
        "numpy>=1.24.4",
        
        # Messaging
        "aiokafka>=0.12.0",
        
        # Utilities
        "python-dateutil>=2.8.2",
        "structlog>=23.2.0",
        "cryptography>=41.0.7",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
        ],
    },
    include_package_data=True,
    package_data={
        "shared": [
            "*.py",
            "*.md",
            "*.txt",
        ],
    },
    entry_points={
        "console_scripts": [
            "trip-currency-shared=shared.cli:main",
        ],
    },
    keywords=[
        "currency",
        "exchange-rate",
        "microservices",
        "fastapi",
        "database",
        "kafka",
        "redis",
        "mongodb",
        "mysql",
    ],
    license="MIT",
    zip_safe=False,
    platforms=["any"],
)
