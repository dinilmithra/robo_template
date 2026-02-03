"""
Setup configuration for pytest-html-reporter plugin
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = ""
readme_file = this_directory / "README.md"
if readme_file.exists():
    long_description = readme_file.read_text(encoding='utf-8')

setup(
    name="robo-automation-test-kit",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Complete automation testing starter kit with pytest plugin, HTML reports, charts, and parallel execution support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/robo-automation-test-kit",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'robo_automation_test_kit': [
            'templates/**/*',
            'templates/**/**/*',
            'templates/**/**/**/*',
            'utils/**/*',
        ],
    },
    classifiers=[
        "Framework :: Pytest",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pytest>=7.0.0",
        "jinja2>=3.0.0",
        "pandas>=2.0.0",
    ],
    entry_points={
        "pytest11": [
            "robo-automation-test-kit = robo_automation_test_kit.plugin",
        ]
    },
    keywords="pytest reporting html charts visualization test-automation automation-testing robo",
)
