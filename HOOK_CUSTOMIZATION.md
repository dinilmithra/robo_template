# Hook Customization Guide - robo_template

## Customizing Report Summary

The `robo_template` plugin provides a hook that allows source projects to customize the report summary object before HTML report generation.

### Available Hook

#### `robo_report_summary(report_summary, report_rows)`

Implement this hook in your source project's `conftest.py` to modify the report summary object.

**Parameters:**
- `report_summary` (dict): Dictionary containing:
  - `env_name`: Environment name (uppercase from APP_ENV)
  - `project_name`: Project name from PROJECT_NAME env var
  - `test_framework`: Test framework name
  - `total`: Total number of tests
  - `passed`: Number of passed tests
  - `failed`: Number of failed tests
  - `skipped`: Number of skipped tests
  - `rerun`: Number of rerun tests (always 0 in current implementation)
  - `duration`: Test session duration as HH:MM:SS
  - `generated_date`: Report generation date (MM-DD-YYYY format)
  - `generated_time`: Report generation time (HH:MM:SS AM/PM format)

- `report_rows` (list): List of all test result dictionaries, each containing:
  - `test_status`: Status (PASSED, FAILED, ERROR, SKIPPED, RERUN)
  - `test_case_name`: Docstring first line or None
  - `test_name`: Full pytest nodeid
  - `title`: Test title from CSV
  - `Phase`: Phase from CSV
  - `Request Category`: Request category from CSV
  - `Request Sub Category`: Request subcategory from CSV
  - `Center`: Center from CSV
  - `error_log`: Error message if test failed
  - `duration`: Test duration (will be formatted after this hook)

**Returns:**
- Modified `report_summary` dictionary (must return dict or None)
- Return `None` or the original `report_summary` to skip modifications

### Usage Examples

#### Example 1: Add custom metrics

```python
# In your source project's conftest.py

def robo_report_summary(report_summary, report_rows):
    """Add custom metrics to the report."""
    
    # Count tests by phase
    smoke_tests = len([r for r in report_rows if r.get('Phase') == 'Smoke'])
    regression_tests = len([r for r in report_rows if r.get('Phase') == 'Regression'])
    
    report_summary['smoke_tests'] = smoke_tests
    report_summary['regression_tests'] = regression_tests
    
    # Calculate pass rate
    total = report_summary['total']
    passed = report_summary['passed']
    pass_rate = (passed / total * 100) if total > 0 else 0
    report_summary['pass_rate'] = f"{pass_rate:.1f}%"
    
    return report_summary
```

#### Example 2: Override project information

```python
def robo_report_summary(report_summary, report_rows):
    """Customize project information."""
    
    # Override with dynamic values
    report_summary['project_name'] = 'My Automation Suite'
    report_summary['env_name'] = 'STAGING'
    
    # Add custom field for build number
    import os
    report_summary['build_number'] = os.getenv('BUILD_NUMBER', 'N/A')
    
    return report_summary
```

#### Example 3: Calculate center-specific metrics

```python
def robo_report_summary(report_summary, report_rows):
    """Add center-based analytics."""
    
    centers = {}
    for row in report_rows:
        center = row.get('Center', 'Unknown')
        if center not in centers:
            centers[center] = {'total': 0, 'passed': 0, 'failed': 0}
        
        centers[center]['total'] += 1
        if row.get('test_status') == 'PASSED':
            centers[center]['passed'] += 1
        else:
            centers[center]['failed'] += 1
    
    report_summary['centers'] = centers
    return report_summary
```

#### Example 4: Filter and calculate subset metrics

```python
def robo_report_summary(report_summary, report_rows):
    """Add metrics for specific request categories."""
    
    # Find all unique request categories
    categories = {}
    for row in report_rows:
        category = row.get('Request Category', 'Unknown')
        status = row.get('test_status', 'UNKNOWN')
        
        if category not in categories:
            categories[category] = {'total': 0, 'passed': 0, 'failed': 0}
        
        categories[category]['total'] += 1
        if status == 'PASSED':
            categories[category]['passed'] += 1
        else:
            categories[category]['failed'] += 1
    
    report_summary['categories'] = categories
    
    # Also add high-level category stats
    report_summary['category_count'] = len(categories)
    
    return report_summary
```

#### Example 5: Conditional modifications based on environment

```python
def robo_report_summary(report_summary, report_rows):
    """Apply environment-specific customizations."""
    
    import os
    
    env_name = report_summary['env_name']
    
    if env_name == 'PRODUCTION':
        # For production, require high pass rate
        total = report_summary['total']
        passed = report_summary['passed']
        pass_rate = (passed / total * 100) if total > 0 else 0
        report_summary['min_pass_rate'] = 95.0
        report_summary['pass_rate'] = pass_rate
        report_summary['status'] = 'PASS' if pass_rate >= 95.0 else 'FAIL'
    
    return report_summary
```

### Important Notes

1. **Hook is Optional**: Source projects don't need to implement this hook if they don't need customizations.

2. **Return Value Matters**: Always return the `report_summary` dictionary. Returning `None` will be ignored and the original will be used.

3. **Access to Report Data**: The hook receives both the summary object AND all individual test rows, allowing you to compute any derived metrics.

4. **Custom Fields**: You can add any custom fields to `report_summary`. If you want these displayed in the HTML report, you'll also need to modify the Jinja2 template.

5. **Don't Lose Data**: Be careful not to accidentally delete important fields. If you're unsure, always return the entire modified dictionary.

6. **Template Integration**: Custom fields added to `report_summary` will be available in your Jinja2 templates as variables. For example:
   ```html
   <!-- In your custom template -->
   <p>Pass Rate: {{ summary.pass_rate }}</p>
   <p>Build: {{ summary.build_number }}</p>
   ```

### Implementation Location

Add the hook implementation to your source project's `conftest.py`:

```python
# source_project/conftest.py

def robo_report_summary(report_summary, report_rows):
    """
    Customize the report summary before HTML generation.
    
    This hook is called by robo_template plugin during pytest_unconfigure.
    """
    # Your customization logic here
    return report_summary
```

The `pytest` framework will automatically discover and call this hook when it matches the hook specification defined in the plugin.

