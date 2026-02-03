# Robo Reporter Plugin - Pytest Hooks Documentation

## Overview

The robo-reporter pytest plugin provides comprehensive test automation reporting with chart visualizations and HTML dashboards. It uses pytest's hook system to intercept test execution events and collect result data.

## Pytest Hook Execution Order

Pytest hooks execute in a specific sequence during a test session. Understanding this order is essential for understanding how the plugin works:

```
1. pytest_addoption          → Register command-line options
2. pytest_plugin_registered  → Manage plugin registration
3. pytest_configure          → Initialize plugin state
4. pytest_collection         → Optimize test collection
5. pytest_generate_tests     → Parametrize tests with CSV data
6. pytest_runtest_makereport → Capture individual test results
7. pytest_testnodedown       → Aggregate xdist worker results
8. pytest_unconfigure        → Generate final HTML report
```

## Hook Details

### 1. pytest_addoption
**When:** Very first - before plugins are loaded  
**Where:** Master and workers  
**Purpose:** Register custom command-line options

```python
def pytest_addoption(parser):
```

**Functionality:**
- Registers `--robo-report` option for custom report path
- Registers `--robo-report-title` option for custom report title

**Usage:**
```bash
pytest --robo-report=custom_report.html --robo-report-title="My Report"
```

---

### 2. pytest_plugin_registered
**When:** When each plugin is registered (after addoption)  
**Where:** Master only  
**Purpose:** Manage plugin lifecycle

```python
def pytest_plugin_registered(plugin, manager):
```

**Functionality:**
- Checks `PARALLEL_EXECUTION` environment variable
- Unregisters pytest-xdist if parallel execution is disabled
- Allows disabling parallel execution via configuration

**Usage:**
```bash
export PARALLEL_EXECUTION=N  # Disable parallel execution
pytest tests/
```

---

### 3. pytest_configure
**When:** After command-line parsing and all plugins loaded  
**Where:** Both master and worker processes  
**Purpose:** Initialize plugin state and global configuration

```python
def pytest_configure(config):
```

**Initialization:**
- Registers hook specifications from `hookspec.py`
- Creates `config.test_results_summary` (empty list)
- Stores session start time in `config._sessionstart_time`
- Saves master config to global `_MASTER_CONFIG` for xdist workers

**Configuration Attributes Created:**
```python
config.test_results_summary = []        # For result collection
config._sessionstart_time = datetime    # For report duration
config._test_results_from_workers = []  # For aggregation
```

---

### 4. pytest_collection
**When:** At start of collection phase (after pytest_configure)  
**Where:** Master only  
**Purpose:** Optimize test collection by parsing test selectors

```python
def pytest_collection(session):
```

**Functionality:**
- Parses command-line test selectors (e.g., `tests/test_file.py::test_name`)
- Stores selected tests in `config._specified_test_functions`
- Helps `pytest_generate_tests` skip parametrization for unselected tests

**Example:**
```bash
pytest tests/test_file.py::specific_test
# Stores: {'tests/test_file.py::specific_test'}
```

**Optimization:**
- Reduces parametrization overhead when running specific tests
- Avoids unnecessary CSV row loading for unselected tests

---

### 5. pytest_generate_tests
**When:** For each test function during collection (after pytest_collection)  
**Where:** Master only  
**Purpose:** Parametrize tests with CSV/Excel data

```python
def pytest_generate_tests(metafunc):
```

**Triggered By:**
1. Test has `@pytest.mark.datafile("filename.csv")` marker
2. Test declares `row` as a fixture/parameter

**Process:**
1. Check for `@pytest.mark.datafile` marker
2. Validate `row` fixture is used by test
3. Check if test is in selected tests (optimization)
4. Load CSV/Excel data from `data/` directory
5. Parametrize test with loaded rows

**Example:**
```python
@pytest.mark.datafile("TestData.csv")
def test_example(row, driver, wait):
    title = row.get("Title", "")
    # Test code
```

**CSV File Location:**
```
tests/
  test_example.py
data/
  TestData.csv  ← Loaded automatically
```

**Data Structure:**
```python
row = {
    'Title': 'Test Case 1',
    'Phase': 'Smoke',
    'Request Category': 'Purchase',
    'Center': 'New York',
    # ... other columns
}
```

---

### 6. pytest_runtest_makereport
**When:** For each test phase (setup, call, teardown)  
**Where:** Both master and worker processes  
**Purpose:** Capture individual test results and metadata

```python
def pytest_runtest_makereport(item, call):
```

**Phases Captured:**
- `setup` phase: Before test execution
- `call` phase: During test execution ✓ (captured by this hook)
- `teardown` phase: After test execution

**Result Data Collected:**
```python
result = {
    'test_status': 'PASSED',           # PASSED, FAILED, ERROR, SKIPPED, RERUN
    'test_name': 'tests/test_file.py::test_name[row0]',
    'title': 'Test Title from CSV',
    'Phase': 'Execution',              # From CSV data
    'Request Category': 'Purchase',    # From CSV data
    'Request Sub Category': 'Micro',   # From CSV data
    'Center': 'New York',              # From CSV data
    'duration': 2.345,                 # Seconds
    'error_log': '',                   # Exception message if failed
    'test_case_name': 'Test description from docstring'
}
```

**Data Storage:**
- Appended to `item.config.test_results_summary`
- For xdist workers, also synced to `workeroutput`

**Status Values:**
- `PASSED` - Test passed successfully
- `FAILED` - Assertion failed
- `ERROR` - Exception during test
- `SKIPPED` - Test was skipped
- `RERUN` - Test rerun (xfail)

---

### 7. pytest_testnodedown
**When:** When xdist worker process terminates  
**Where:** Master process only  
**Purpose:** Aggregate results from workers back to master

```python
def pytest_testnodedown(node, error):
```

**Execution:**
- Called once per worker after all tests finish on that worker
- Only runs in master process, not in workers

**Process:**
1. Extract worker ID from node configuration
2. Get test results from worker's `workeroutput`
3. Call `flatten_results()` to aggregate into master's `_test_results_from_workers`
4. Log worker status (error handling)

**xdist Worker Flow:**
```
Worker Process:
  - Tests execute (pytest_runtest_makereport)
  - Results stored in config.test_results_summary
  - Results synced to workeroutput
  - Worker process terminates

Master Process (pytest_testnodedown):
  - Receives workeroutput
  - Extracts test_results_summary
  - Aggregates into _test_results_from_workers
```

**Example with Multiple Workers:**
```bash
pytest -n 3  # Run with 3 parallel workers
# pytest_testnodedown called 3 times (once per worker)
```

---

### 8. pytest_unconfigure
**When:** Last hook - after all teardown and xdist aggregation  
**Where:** Master process only  
**Purpose:** Generate final HTML report

```python
def pytest_unconfigure(config):
```

**Skip Condition:**
- Skips execution if running in xdist worker process
- Only runs in master process

**Process:**
1. Aggregate results from master and all workers via `aggregate_test_results()`
2. Create report summary with statistics via `create_report_summary()`
3. Print console summary via `print_results_summary()`
4. Generate and save HTML report via `generate_report()`

**Result Aggregation:**
```python
# Combines:
# - config.test_results_summary (master process tests)
# - config._test_results_from_workers (xdist worker tests)
report_rows = aggregate_test_results(config)
```

**Report Summary Created:**
```python
report_summary = {
    'env_name': 'UAT',
    'project_name': 'Robo',
    'test_framework': 'Robo Automation Framework',
    'total': 20,
    'passed': 18,
    'failed': 2,
    'skipped': 0,
    'rerun': 0,
    'duration': '0:02:35',
    'generated_date': '02-02-2026',
    'generated_time': '10:30:00 PM'
}
```

**Output:**
- Console output with results summary table
- HTML report saved to `reports/test_report.html` (or custom path)

---

## Global Variables

### `_MASTER_CONFIG`
- **Scope:** Global
- **Type:** Config object
- **Purpose:** Store master process config for xdist workers
- **Set by:** `pytest_configure()` in master process
- **Used by:** `pytest_testnodedown()` for aggregation

```python
_MASTER_CONFIG = None
if not hasattr(config, "workerinput"):  # Is master process
    _MASTER_CONFIG = config
```

---

## Data Flow Diagram

```
pytest_addoption
    ↓
pytest_plugin_registered
    ↓
pytest_configure
    ↓
pytest_collection
    ↓
pytest_generate_tests (parametrize with CSV data)
    ↓
┌─────────────────────────────┬──────────────────────┐
│ Master Process              │ Worker Processes     │
├─────────────────────────────┼──────────────────────┤
│ pytest_runtest_makereport   │ pytest_runtest_makereport
│ (collect results)           │ (collect results)
│ ↓                           │ ↓
│ config.test_results_summary │ config.test_results_summary
│                             │ workeroutput["test_results_summary"]
└─────────────────────────────┴──────────────────────┘
                    ↓
        pytest_testnodedown (Master)
        (aggregate worker results)
                    ↓
    config._test_results_from_workers
                    ↓
        pytest_unconfigure (Master)
        aggregate_test_results() → combine master + workers
        create_report_summary()
        print_results_summary()
        generate_report() → HTML report
                    ↓
            reports/test_report.html
```

---

## Configuration Environment Variables

### PARALLEL_EXECUTION
- **Default:** "N"
- **Values:** "Y" (enable) or "N" (disable)
- **Effect:** Disables pytest-xdist if set to "N"

```bash
export PARALLEL_EXECUTION=Y  # Enable parallel execution (default)
export PARALLEL_EXECUTION=N  # Disable parallel execution (serial)
```

### HEADLESS
- **Default:** "N"
- **Values:** "Y" (headless) or "N" (visible)
- **Effect:** Controls Chrome browser visibility

```bash
export HEADLESS=Y  # Run browser in headless mode
export HEADLESS=N  # Run browser in visible mode
```

### WAIT_TIME
- **Default:** "15"
- **Type:** Integer (seconds)
- **Effect:** WebDriverWait timeout for finding elements

```bash
export WAIT_TIME=30  # 30 second timeout
```

### REPORT_TITLE
- **Default:** "Test Execution Report"
- **Effect:** Title displayed in HTML report

```bash
export REPORT_TITLE="My Custom Report Title"
```

### REPORT_PATH
- **Default:** "reports"
- **Effect:** Directory where HTML report is saved

```bash
export REPORT_PATH=/custom/report/path
```

---

## Hook Specifications (hookspec.py)

Custom hooks that source projects can implement:

### robo_report_summary
Customize the report summary object before HTML generation:

```python
@pytest.hookimpl
def robo_report_summary(config, report_summary, report_rows):
    # Modify report_summary
    report_summary['custom_field'] = 'value'
    return report_summary
```

### robo_report_rows
Filter or modify test result rows before HTML generation:

```python
@pytest.hookimpl
def robo_report_rows(config, report_rows):
    # Filter or modify rows
    filtered = [r for r in report_rows if r['test_status'] == 'PASSED']
    return filtered
```

---

## Common Test Execution Scenarios

### Serial Execution (No Parallel)
```bash
pytest -n 0
# or
export PARALLEL_EXECUTION=N
pytest
```

**Hook sequence:**
- Single master process
- No workers
- pytest_testnodedown not called

### Parallel Execution with xdist (Default)
```bash
pytest  # or pytest -n logical
```

**Hook sequence:**
- One master process
- Multiple worker processes (by default, number of CPU cores)
- pytest_testnodedown called once per worker

### Specific Test Selection
```bash
pytest tests/test_file.py::test_name[row0]
```

**Hook sequence:**
- pytest_collection stores selected test
- pytest_generate_tests skips unselected tests (optimization)
- Only 1 parametrization created instead of 20

---

## Troubleshooting Guide

### Results Not Appearing in Report
1. Check if `pytest_unconfigure()` is running: Look for "HTML report generated" in output
2. Verify `config.test_results_summary` has items
3. Ensure `aggregate_test_results()` is combining master + worker results

### xdist Workers Not Aggregating
1. Check if `pytest_testnodedown()` is called: Should see worker aggregation logs
2. Verify `workeroutput` contains test results from workers
3. Check if workers have errors: Look for "error" in pytest_testnodedown logs

### CSV Data Not Loading
1. Verify `@pytest.mark.datafile("filename.csv")` marker is present
2. Check CSV file exists at `data/filename.csv`
3. Ensure test declares `row` fixture
4. Check encoding: CSV should be UTF-8 with fallbacks

### Hooks Not Executing
1. Verify plugin is installed: `pip install -e .`
2. Check if plugin is registered: `pytest --co` should show "robo-reporter"
3. Verify hookspecs are registered in `pytest_configure()`

---

## Performance Considerations

### Optimization Strategies

1. **Test Selection Optimization**
   - pytest_collection + pytest_generate_tests work together
   - Skips CSV parametrization for unselected tests
   - Saves time when running specific tests

2. **Parallel Execution**
   - Use `pytest -n logical` for parallel execution
   - xdist distributes tests across workers
   - Results aggregated in pytest_testnodedown

3. **CSV Loading**
   - Only loads rows for selected tests
   - Caches results per test function
   - Handles encoding fallbacks efficiently

### Benchmarks

- Serial execution (1 test with 20 CSV rows): ~8 seconds
- Parallel execution (20 tests × 20 rows = 400): ~30 seconds total
- HTML report generation: ~1-2 seconds

---

## Related Files

- **plugin.py** - Main hook implementations (this document describes)
- **hookspec.py** - Custom hook specifications
- **report_generator.py** - HTML report generation
- **conftest.py** - Project-level hook implementations
- **tests/test_Template.py** - Example test using hooks

