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


# ============================================================================
# Report Summary Hook
# ============================================================================

def robo_report_summary(config, report_summary, report_rows):
    """
    Customize the report summary before HTML report generation.

    This hook is called by robo_template plugin to allow source projects to:
    - Add custom fields/metrics
    - Modify existing values
    - Calculate derived statistics
    - Override default values

    Args:
        config: Pytest config object (access to environment, markers, options, etc.)
        report_summary: Dictionary with auto-generated summary stats
                       (total, passed, failed, skipped, duration, etc.)
        report_rows: List of all test result dictionaries for custom calculations

    Returns:
        Modified report_summary dictionary
    """
    # Example: Add custom metrics based on test data
    
    # Calculate pass rate percentage
    total = report_summary.get('total', 0)
    passed = report_summary.get('passed', 0)
    pass_rate = (passed / total * 100) if total > 0 else 0.0
    report_summary['pass_rate'] = f"{pass_rate:.1f}%"
    
    # Count tests by phase
    phases = {}
    for row in report_rows:
        phase = row.get('Phase', 'Unknown')
        if phase not in phases:
            phases[phase] = {'total': 0, 'passed': 0, 'failed': 0}
        phases[phase]['total'] += 1
        
        status = row.get('test_status', '')
        if status == 'PASSED':
            phases[phase]['passed'] += 1
        elif status in ['ERROR', 'FAILED']:
            phases[phase]['failed'] += 1
    
    report_summary['phases'] = phases
    
    # Count tests by request category
    categories = {}
    for row in report_rows:
        category = row.get('Request Category', 'Unknown')
        if category not in categories:
            categories[category] = {'total': 0, 'passed': 0}
        categories[category]['total'] += 1
        
        if row.get('test_status') == 'PASSED':
            categories[category]['passed'] += 1
    
    report_summary['categories'] = categories
    
    # Count tests by center
    centers = {}
    for row in report_rows:
        center = row.get('Center', 'Unknown')
        if center not in centers:
            centers[center] = {'total': 0, 'passed': 0}
        centers[center]['total'] += 1
        
        if row.get('test_status') == 'PASSED':
            centers[center]['passed'] += 1
    
    report_summary['centers'] = centers
    
    return report_summary


# ============================================================================
# Report Rows Hook
# ============================================================================

def robo_report_rows(config, report_rows):
    """
    Customize the report rows before HTML report generation.

    This hook is called by robo_template plugin to allow source projects to:
    - Filter test results
    - Add/modify/delete result fields
    - Reorder results
    - Enrich result data

    Args:
        config: Pytest config object (access to environment, markers, options, etc.)
        report_rows: List of all test result dictionaries

    Returns:
        Modified report_rows list (or original if no changes)

    Examples:
        # Filter to show only failed tests:
        # failed_tests = [r for r in report_rows if r.get('test_status') in ['ERROR', 'FAILED']]
        # return failed_tests
        
        # Add custom field to each result:
        # for row in report_rows:
        #     row['custom_id'] = row.get('test_name', '').split('::')[-1]
        # return report_rows
        
        # Sort by phase then status:
        # return sorted(report_rows, key=lambda r: (r.get('Phase', ''), r.get('test_status', '')))
    """
    # Example: Add custom ID field based on test name
    for row in report_rows:
        test_name = row.get('test_name', '')
        # Extract the parametrized part if present
        test_id = test_name.split('[')[1].rstrip(']') if '[' in test_name else test_name.split('::')[-1]
        row['custom_test_id'] = test_id
    
    return report_rows
