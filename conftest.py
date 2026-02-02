"""
Simplified conftest.py - uses robo-reporter plugin for report generation
All fixtures and hooks are provided by the robo_reporter plugin
"""

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# Project-Specific Fixtures (if needed)
# ============================================================================
# All standard fixtures (row, driver, wait) are provided by robo_reporter plugin
# Add project-specific fixtures here if required
