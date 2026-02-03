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
# All standard fixtures (row, driver, wait) are provided by robo_automation_test_kit plugin
# Add project-specific fixtures here if required


# ============================================================================
# robo_modify_report_row Hook Implementation
# ============================================================================
# This function enriches test report rows with custom data from CSV test data
# Called directly by robo_automation_test_kit plugin for each test execution


def robo_modify_report_row(report_row, test_data):
    """
    Example implementation of robo_custom_attribute_data hook.

    This function allows the source project to:
    - Extract custom attributes from the data_row
    - Add project-specific fields to test results
    - Transform or enrich test data

    Args:
        report_row: Dictionary with default test report data
        test_data: Dictionary with parametrized test data from CSV

    Returns:
        Dictionary with custom attributes to merge into test_data.
        Keys will override or extend the default test_data fields.
    """
    # Example: Extract 'Test Case Name' from data_row
    # and add any custom fields
    report_row["test_case_name"] = test_data.get("Test Case Name", "")
    report_row["Phase"] = test_data.get("Phase", "")
    report_row["Request Category"] = test_data.get("Request Category", "")
    report_row["Request Sub-Category"] = test_data.get("Request Sub-Category", "")
    report_row["Center"] = test_data.get("Center", "")
    # Add more custom attributes as needed from data_row
    # "Jira ID": data_row.get("Jira ID", ""),
    # "sprint": data_row.get("Sprint", ""),

    return report_row


# ============================================================================
# Report Summary Hook
# ============================================================================
