"""
Hook specifications for robo_reporter plugin.
These hooks allow source projects to customize the reporting behavior.
"""

import pytest


@pytest.hookspec
def robo_report_summary(config, report_summary, report_rows):
    """
    Hook specification for source projects to customize the report_summary object.

    Source projects can implement this hook in their conftest.py to:
    - Add custom fields
    - Modify existing values
    - Delete fields
    - Add custom logic

    Args:
        config: Pytest config object (allows access to environment, markers, etc.)
        report_summary: Dictionary with summary stats (total, passed, failed, skipped, etc.)
        report_rows: List of all test result dictionaries

    Returns:
        Modified report_summary dictionary (or original if no changes)

    Example in source project's conftest.py:
        def robo_report_summary(config, report_summary, report_rows):
            # Add custom field
            report_summary['custom_metric'] = len([r for r in report_rows if r.get('Phase') == 'Smoke'])
            # Modify existing field
            report_summary['project_name'] = 'My Custom Project'
            return report_summary
    """
    pass


@pytest.hookspec
def robo_report_rows(config, report_rows):
    """
    Hook specification for source projects to customize the report_rows list.

    Source projects can implement this hook in their conftest.py to:
    - Filter test results
    - Add/modify/delete result fields
    - Reorder results
    - Enrich result data

    Args:
        config: Pytest config object (allows access to environment, markers, etc.)
        report_rows: List of all test result dictionaries

    Returns:
        Modified report_rows list (or original if no changes)

    Example in source project's conftest.py:
        def robo_report_rows(config, report_rows):
            # Filter to only show failed tests
            failed_tests = [r for r in report_rows if r.get('test_status') in ['ERROR', 'FAILED']]
            return failed_tests

            # Or add custom fields to each result
            for row in report_rows:
                row['custom_id'] = row.get('test_name', '').split('::')[-1]
            return report_rows
    """
    pass
