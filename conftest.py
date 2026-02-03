"""
Simplified conftest.py - uses robo-reporter plugin for report generation
All fixtures and hooks are provided by the robo_reporter plugin
"""

import pytest
from dotenv import load_dotenv


import logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# Project-Specific Fixtures (if needed)
# ============================================================================
# All standard fixtures (row, driver, wait) are provided by robo_reporter plugin
# Add project-specific fixtures here if required


# ============================================================================
# robo_custom_attribute_data Hook Implementation
# ============================================================================
# Source projects can implement this function to provide custom test data attributes
# This function is called for each test and receives the item and row_fixture objects
# No @pytest.hookimpl decorator needed - it's registered programmatically


def robo_custom_attribute_data(row_fixture):
    """
    Example implementation of robo_custom_attribute_data hook.
    
    This function allows the source project to:
    - Extract custom attributes from the row_fixture
    - Add project-specific fields to test results
    - Transform or enrich test data
    
    Args:
        row_fixture: Dictionary with parametrized test data from CSV
    
    Returns:
        Dictionary with custom attributes to merge into test_data.
        Keys will override or extend the default test_data fields.
    """
    # Example: Extract 'Test Case Name' from row_fixture
    # and add any custom fields
    print(f"\n[DEBUG] robo_custom_attribute_data function called")
    print(f"[DEBUG] row_fixture keys: {row_fixture.keys()}")
    
    return {
        "test_case_name": row_fixture.get("Test Case Name", ""),
        "Phase" :row_fixture.get("Phase", ""),
        "Request Category" :row_fixture.get("Request Category", ""),
        "Request Sub-Category" :row_fixture.get("Request Sub-Category", ""),
        "Center" :row_fixture.get("Center", ""),

        # Add more custom attributes as needed from row_fixture
        # "priority": row_fixture.get("Priority", ""),
        # "sprint": row_fixture.get("Sprint", ""),
    }


# ============================================================================
# Report Summary Hook
# ============================================================================

