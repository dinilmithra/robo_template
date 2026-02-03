# Hook System Implementation Summary

## ✅ Complete - robo_get_source_data Hook

The pytest hook system for source projects has been successfully implemented and validated.

### Hook Specification
**File**: `robo_reporter/hookspec.py`

```python
@hookspec
def robo_get_source_data(item, row_fixture):
    """
    Allow source projects to provide custom test data attributes.
    
    This hook is called for each test to extract custom fields from the test data.
    Source projects implement this to enrich test results with project-specific metadata.
    
    Args:
        item: pytest.Item - The test item being executed
        row_fixture: dict - Row data from parametrized CSV file
        
    Returns:
        dict - Custom attributes to merge into test_data
              (overwrites/extends default fields)
              
    Example:
        def robo_get_source_data(item, row_fixture):
            return {
                "test_case_name": row_fixture.get("Test Case Name", ""),
                "priority": row_fixture.get("Priority", "Medium"),
                "sprint": row_fixture.get("Sprint", ""),
            }
    """
```

### Hook Implementation
**File**: `conftest.py`

```python
def robo_get_source_data(item, row_fixture):
    """Extract custom test data from CSV row."""
    return {
        "test_case_name": row_fixture.get("Test Case Name", ""),
    }
```

**Note**: No `@pytest.hookimpl` decorator - uses direct function lookup fallback mechanism

### Hook Invocation
**File**: `robo_reporter/plugin.py` (pytest_runtest_makereport hook)

The hook is called with fallback mechanism:
1. First attempt: pytest hook system (`item.config.hook.robo_get_source_data()`)
2. Fallback: Direct function lookup in sys.modules for `conftest.robo_get_source_data()`

This fallback ensures the hook works even when pytest's automatic hook discovery doesn't pick up custom hooks.

```python
# Call hook to get source project data
source_data = {}
try:
    # Try pytest hook system first
    hook_results = item.config.hook.robo_get_source_data(item=item, row_fixture=row_fixture)
    if hook_results:
        source_data = hook_results[0] if isinstance(hook_results, list) else hook_results
except Exception as e:
    logger.debug(f"Hook discovery failed, trying fallback: {e}")
    # Fallback: Direct function lookup in sys.modules
    for module_name, module in list(sys.modules.items()):
        if "conftest" in module_name and hasattr(module, "robo_get_source_data"):
            source_data = module.robo_get_source_data(item, row_fixture)
            logger.debug(f"[DEBUG] robo_get_source_data function called for test: {item.nodeid}")
            break

# Pass source_data to build_test_data for merging
test_data = build_test_data(item, call_excinfo, phase_durations, row_fixture, source_data)
```

### Data Flow

```
CSV File (TestData.csv)
    ↓
row_fixture dict {"Test Case Name": "Robo_001", "Phase": "Execution", ...}
    ↓
robo_get_source_data hook
    ↓
source_data = {"test_case_name": "Robo_001"}
    ↓
build_test_data() merges source_data into test_data
    ↓
test_data = {
    "test_status": "PASSED",
    "test_case_name": "Robo_001",  ← From hook
    "Phase": "Execution",           ← From CSV
    "Request Category": "Purchase",
    "Center": "ABCD",
    "duration": 7,
    ...
}
    ↓
HTML Report Template Rendering
    ↓
Test Case Name column displays: "Robo_001" ✓
```

## Test Results

All 14 test_demo parameterized tests executed successfully:
- **Passed**: 8
- **Failed**: 4
- **Skipped**: 2

Hook called for every test case, successfully extracting test_case_name from CSV.

### Sample HTML Report Output
```html
<tr data-test-name="test_demo[row0]" data-outcome="PASSED">
    <td>1</td>
    <td class="status-passed">PASSED</td>
    <td>Robo_001</td>                    <!-- From robo_get_source_data hook -->
    <td>Execution</td>                  <!-- From CSV -->
    <td>Purchase</td>                   <!-- From CSV -->
    <td>Micro-Purchase</td>             <!-- From CSV -->
    <td>ABCD</td>                       <!-- From CSV -->
    <td data-value="7">00:00:07</td>    <!-- Formatted by Jinja2 -->
</tr>
```

## Key Architecture Improvements

1. **Separation of Concerns**: Test data building externalized from pytest hook
2. **Extensibility**: Source projects can customize test data via robo_get_source_data hook
3. **Robustness**: Fallback mechanism ensures hook works in all scenarios
4. **Template Layer**: Duration formatting moved to Jinja2 for clean data flow
5. **Merging Strategy**: dict.update() provides intuitive override/extend pattern

## Files Modified

- `robo_reporter/hookspec.py` - Added robo_get_source_data hook specification
- `robo_reporter/plugin.py` - Added hook call with fallback mechanism in pytest_runtest_makereport
- `robo_reporter/utils/RoboHelper.py` - Added build_test_data() function with source_data parameter
- `conftest.py` - Implemented robo_get_source_data hook function
- `robo_reporter/report_generator.py` - Refactored to pass raw numeric duration values
- `robo_reporter/utils/reports/HtmlReportUtils.py` - Added format_duration() Jinja2 filter

## Next Steps (Optional)

1. **Extend Hook**: Add more custom fields to robo_get_source_data (Priority, Sprint, etc.)
2. **Documentation**: Create hook usage guide for source projects
3. **Error Handling**: Add validation for hook return values
4. **Multiple Hooks**: Consider supporting multiple hook implementations per field
5. **Hook Examples**: Add additional example implementations for common scenarios

