"""
Hook specifications for robo_automation_test_kit plugin.
These hooks allow source projects to customize the reporting behavior.
"""

import pytest


@pytest.hookspec
def robo_modify_report_row(report_row, test_data):
    """
    Hook specification for source projects to provide custom test data attributes.

    Source projects can implement this hook in their conftest.py to:
    - Extract custom attributes from test_data (CSV/Excel row)
    - Add project-specific fields to test results
    - Transform or enrich test data using both report_row and test_data

    Args:
        report_row: Dictionary with base test result data (status, duration, error_log, etc.)
        test_data: Dictionary with parametrized test data from CSV/Excel

    Returns:
        Dictionary with custom attributes to merge into report_row.
        Keys in this dict will override or extend the default report_row fields.

    Example in source project's conftest.py:
        @pytest.hookimpl
        def robo_modify_report_row(report_row, test_data):
            return {
                'test_case_name': test_data.get('Test Case Name', ''),
                'custom_field': test_data.get('Custom Field', ''),
                'priority': test_data.get('Priority', 'Medium'),
            }
    """
    pass
