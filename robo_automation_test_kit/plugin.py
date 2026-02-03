"""
Robo Reporter - Pytest Plugin
Collects test results and generates HTML reports with chart visualizations.

PYTEST HOOK EXECUTION ORDER (Session Lifecycle):
=====================================================

PHASE 1: SESSION INITIALIZATION
1. pytest_addoption             - Register command-line options (called once per session)
2. pytest_plugin_registered     - Plugin registration/lifecycle management
3. pytest_configure             - Initialize plugin state and global config
4. pytest_sessionstart          - Session initialization complete

PHASE 2: TEST COLLECTION
5. pytest_collection            - Parse test selections and optimize collection
6. pytest_collection_modifyitems - Modify collected test items
7. pytest_generate_tests        - Parametrize tests with CSV/Excel data (per test function)
8. pytest_collection_finish     - Collection phase complete

PHASE 3: TEST EXECUTION (per test)
9. pytest_runtest_protocol      - Protocol for running individual tests
   ├─ pytest_runtest_setup      - Setup phase before test
   ├─ pytest_runtest_call       - Test execution phase
   ├─ pytest_runtest_teardown   - Teardown phase after test
   └─ pytest_runtest_makereport - Capture result after each phase

PHASE 4: XDIST WORKER COORDINATION (parallel execution only)
10. pytest_configure_node       - Configure xdist worker nodes (workers only)
11. pytest_testnodedown         - Aggregate worker results to master (master only)

PHASE 5: SESSION FINALIZATION
12. pytest_sessionfinish        - Session finalization before report generation
13. pytest_unconfigure          - Generate final HTML report (master only)

CUSTOM HOOKS (Robo Reporter Extensions):
========================================
- robo_modify_report_row        - Allow projects to provide custom test attributes
"""

import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from .utils.RoboHelper import (
    print_results_summary,
    build_test_data,
    create_report_summary,
    generate_report,
    flatten_results,
    aggregate_test_results,
)
from .utils import get_env, load_test_data


logger = logging.getLogger(__name__)
logger.propagate = True

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# Global Variables for pytest-xdist result aggregation
# ============================================================================

_MASTER_CONFIG = None  # Global reference to master config for xdist aggregation
_CONFTEST_HOOK_MODULE = None  # Cached conftest module with robo_modify_report_row


# ============================================================================
# Pytest Hooks (ordered by execution sequence)
# ============================================================================

# ============================================================================
# HOOK 1: pytest_addoption
# Execution: Very first - before plugins are loaded
# Purpose: Register custom command-line options for the pytest command
# ============================================================================


def pytest_addoption(parser):
    """
    Register command-line options for the robo-reporter plugin.

    Options:
    - --robo-report: Custom path for HTML report output
    - --robo-report-title: Custom title for the HTML report
    """
    group = parser.getgroup("robo-reporter", "Robo Reporter Options")
    group.addoption(
        "--robo-report",
        action="store",
        dest="robo_report_path",
        default=None,
        help="Path to save the HTML report (default: reports/test_report_<timestamp>.html)",
    )
    group.addoption(
        "--robo-report-title",
        action="store",
        dest="robo_report_title",
        default="Test Execution Report",
        help="Title for the HTML report",
    )


# ============================================================================
# HOOK 2: pytest_plugin_registered
# Execution: When each plugin is registered (after addoption)
# Purpose: Manage plugin lifecycle - can unregister plugins if conditions met
# ============================================================================


def pytest_plugin_registered(plugin, manager):
    """
    Called when a plugin is registered.

    Functionality:
    - Checks PARALLEL_EXECUTION environment variable
    - Unregisters pytest-xdist if PARALLEL_EXECUTION is disabled
    - Allows disabling parallel execution via environment configuration
    """

    # Check if the registered plugin is the xdist dsession plugin
    if str(plugin).find("xdist.dsession.DSession") != -1:
        # Check PARALLEL_EXECUTION environment variable
        parallel_execution = get_env("PARALLEL_EXECUTION", "N").strip()
        if parallel_execution == "N":
            logger.warning("Parallel execution disabled, unregistering pytest-xdist")
            manager.unregister(plugin)


# ============================================================================
# HOOK 3: pytest_configure
# Execution: After command-line parsing and all plugins loaded
# Purpose: Initialize plugin state, register hookspecs, store global config
# Runs on: Both master and worker processes
# ============================================================================


def pytest_configure(config):
    """
    Initialize robo-reporter plugin configuration.

    Responsibilities:
    1. Store session start time for report duration calculation
    2. Initialize test_results_summary list on config object
    3. Store master config reference in global variable for xdist workers

    Config attributes created:
    - config.test_results_summary: List to collect test result dicts
    - config._sessionstart_time: Session start datetime
    - _MASTER_CONFIG: Global ref to master config for worker aggregation

    Note on hooks:
    - Project-specific hook implementations (robo_modify_report_row) in conftest.py
      are discovered via direct module lookup in pytest_runtest_makereport
    - pytest's hook discovery can't find hookimpls in modules loaded before hookspec
      registration, so we use direct sys.modules lookup instead (more reliable)
    """
    # Discover and cache conftest module with hook implementation (optimization)
    global _CONFTEST_HOOK_MODULE
    if _CONFTEST_HOOK_MODULE is None:
        for module_name, module in list(sys.modules.items()):
            if "conftest" in module_name and hasattr(module, "robo_modify_report_row"):
                _CONFTEST_HOOK_MODULE = module
                break
    
    # Store session start time for HTML report duration calculation (master only)
    if not hasattr(config, "workerinput") and not hasattr(config, "_sessionstart_time"):
        config._sessionstart_time = datetime.now()

    # Initialize test_results_summary on config (runs on both master and workers)
    config.test_results_summary = []

    # Store master config in global for xdist aggregation (master only)
    global _MASTER_CONFIG
    if not hasattr(config, "workerinput"):
        _MASTER_CONFIG = config


# ============================================================================
# HOOK 4: pytest_sessionstart
# Execution: After session object has been created and before collection starts
# Purpose: Setup session-specific state before test collection
# Runs on: Both master and worker processes
# ============================================================================


def pytest_sessionstart(session):
    """
    Called at session initialization after test collection configuration.

    Responsibilities:
    - Session state is now available
    - Plugin setup is complete
    - Ready to start test collection

    Called after:
    - pytest_configure (plugin setup)
    - Command-line options registered

    Called before:
    - pytest_collection (test collection starts)
    """
    pass


# ============================================================================
# HOOK 5: pytest_collection
# Execution: At start of collection phase (after sessionstart)
# Purpose: Optimize test collection by parsing command-line test selectors
# Runs on: Both master and worker processes
# ============================================================================


def pytest_collection(session):
    """
    Parse and store test selections for optimization.

    Parses command-line arguments to identify specific test selections
    (e.g., tests/test_file.py::test_name) and stores them in config.

    Purpose:
    - Helps pytest_generate_tests skip parametrization for unselected tests
    - Reduces overhead when running specific tests instead of full suite

    Config attributes created:
    - config._specified_test_functions: Set of selected test node IDs
    """
    config = session.config
    specified_tests = set()

    # Parse command line arguments to find test selectors (e.g., tests/test_file.py::test_name)
    for arg in config.invocation_params.args:
        # Skip pytest options (start with -)
        if arg.startswith("-"):
            continue

        # Only process test selectors containing ::
        if "::" not in arg:
            continue

        # Normalize path separators for cross-platform compatibility
        normalized = arg.replace("\\", "/")

        # Handle Windows absolute paths (e.g., C:/path/to/tests/test_file.py::test_name)
        # Extract relative path from test directory onwards
        if ":" in normalized.split("::")[0]:  # Has drive letter (Windows absolute path)
            parts = normalized.split("/")
            # Find test directory start (tests/, test/, or test_*.py)
            for i, part in enumerate(parts):
                if part in ("tests", "test") or part.startswith("test_"):
                    normalized = "/".join(parts[i:])
                    break

        # Remove parametrization indices like [0], [row_name], etc.
        normalized = normalized.split("[")[0]

        specified_tests.add(normalized)

    # Store for use in pytest_generate_tests
    config._specified_test_functions = specified_tests


# ============================================================================
# HOOK 6: pytest_collection_modifyitems
# Execution: After test collection, before parametrization of individual tests
# Purpose: Modify collected test items (reorder, filter, mark, etc.)
# Runs on: Both master and worker processes
# ============================================================================


def pytest_collection_modifyitems(session, config, items):
    """
    Modify collected test items before test execution.

    Called after pytest_collection and before parametrization.
    Allows plugins to:
    - Filter or reorder tests
    - Add marks to tests
    - Modify test parameters
    - Skip tests programmatically

    Purpose:
    - Reserved for future enhancements (filtering, reordering, etc.)
    - Can add custom marks or modify test execution order

    Args:
        session: Test session object
        config: Pytest config object
        items: List of collected test items
    """
    pass


# ============================================================================
# HOOK 7: pytest_generate_tests
# Execution: For each test function during collection (after collection_modifyitems)
# Purpose: Parametrize tests with CSV/Excel data rows
# Runs on: Both master and worker processes
# ============================================================================


def pytest_generate_tests(metafunc):
    """
    Parametrize tests with data from CSV/Excel files.

    Triggered when:
    - Test has @pytest.mark.datafile("filename.csv") marker
    - Test declares 'row' as a fixture/parameter

    Process:
    1. Check for @pytest.mark.datafile marker
    2. Validate 'row' fixture is used by test
    3. Check if test is in selected tests (skip if not)
    4. Load CSV/Excel data from data/ directory
    5. Parametrize test with loaded rows

    Optimization:
    - Skips tests not explicitly requested in command line
    - Reduces overhead for targeted test runs
    """
    # Check if test has @pytest.mark.datafile marker
    marker = metafunc.definition.get_closest_marker("datafile")
    if not marker or not marker.args:
        return

    # Check if test actually uses the 'row' fixture
    if "row" not in metafunc.fixturenames:
        return

    csv_file = marker.args[0]
    test_nodeid = metafunc.definition.nodeid
    config = metafunc.config

    # Optimization: If specific tests were requested, skip tests not in the selection
    if (
        hasattr(config, "_specified_test_functions")
        and config._specified_test_functions
    ):
        is_requested = any(
            test_nodeid.split("[")[0] == spec
            or test_nodeid.split("[")[0].startswith(spec + "::")
            for spec in config._specified_test_functions
        )
        if not is_requested:
            return

    # Validate test file path exists
    test_file_path = metafunc.definition.path
    if not test_file_path:
        logger.error(f"Cannot determine file path for test {test_nodeid}")
        return

    # Load CSV data from data/ directory (sibling to test directory)
    test_dir = Path(test_file_path).parent
    data_path = test_dir.parent / "data" / csv_file

    # Load test data from CSV/Excel file
    rows = load_test_data(data_path)

    if not rows:
        logger.error(
            f"Failed to load data file '{csv_file}' at {data_path}; "
            f"file may not exist, be empty, or have encoding issues"
        )
        pytest.fail(f"Data file '{csv_file}' could not be loaded from {data_path}")

    metafunc.parametrize("row", rows)


# ============================================================================
# HOOK 8: pytest_collection_finish
# Execution: After all tests have been collected
# Purpose: Final opportunity to modify or inspect collected tests
# Runs on: Both master and worker processes
# ============================================================================


def pytest_collection_finish(session):
    """
    Called after collection of all test items is complete.

    Process:
    - All tests have been discovered and collected
    - pytest_generate_tests has been called for all test functions
    - Ready to begin test execution phase

    Purpose:
    - Log collection summary
    - Reserved for future enhancements (reporting, validation, etc.)

    Args:
        session: Test session object containing all collected items
    """
    pass


# ============================================================================
# HOOK 9: pytest_runtest_makereport
# Execution: For each test phase (setup, call, teardown) after phase completes
# Purpose: Capture test results and metadata
# Runs on: Both master and worker processes
# ============================================================================


def pytest_runtest_makereport(item, call):
    """
    Capture individual test result data.

    Called for each test phase:
    - setup: Before test execution
    - call: During test execution (captured by this hook)
    - teardown: After test execution

    Result data collected:
    - test_status: PASSED, FAILED, or SKIPPED (RERUN status is converted to FAILED)
    - test_name: Full pytest node ID
    - title: Test title from @pytest.mark.datafile row or docstring
    - Phase, Request Category, Request Sub Category, Center: From CSV data
    - duration: Execution time in seconds (sum of setup + call + teardown)
    - error_log: Exception message if test failed

    Data storage:
    - Appended to config.test_results_summary (master and workers)
    - Synced to workeroutput for xdist workers
    """

    # Store durations for each phase on the item
    if not hasattr(item, "_phase_durations"):
        item._phase_durations = {}

    # Capture duration for this phase
    item._phase_durations[call.when] = getattr(call, "duration", 0)

    # Store call phase info for later use
    if call.when == "call":
        item._call_excinfo = call.excinfo
        item._call_when = call.when

    # Only create final result after teardown completes
    if call.when != "teardown":
        return

    # Build test result data dictionary
    report_row = build_test_data(item)
    test_data = item.funcargs.get("row", {}) if "row" in item.fixturenames else {}

    # Allow source projects to modify/enrich the report row via conftest hook
    final_report_row = report_row

    # Use cached conftest module for better performance
    if _CONFTEST_HOOK_MODULE is not None:
        try:
            result = _CONFTEST_HOOK_MODULE.robo_modify_report_row(
                report_row=report_row, test_data=test_data
            )
            if result and isinstance(result, dict):
                final_report_row = result
            elif result is not None:
                logger.warning(
                    f"robo_modify_report_row returned {type(result).__name__} instead of dict, "
                    f"ignoring result for test {item.nodeid}"
                )
        except Exception as e:
            logger.error(
                f"Error calling robo_modify_report_row for test {item.nodeid}: {e}",
                exc_info=True
            )

    # Store result in config (initialized for both main and worker processes)
    item.config.test_results_summary.append(final_report_row)

    # For xdist workers: sync to workeroutput for master aggregation
    if hasattr(item.config, "workeroutput"):
        item.config.workeroutput["test_results_summary"] = list(
            item.config.test_results_summary
        )


# ============================================================================
# HOOK 10: pytest_configure_node (xdist only)
# Execution: When xdist worker node is being configured
# Purpose: Initialize worker-specific configuration
# Runs on: Worker processes only (not on master)
# ============================================================================


def pytest_configure_node(node):
    """
    Configure individual xdist worker node.

    Called for each worker process during parallel execution.
    Only runs in worker processes, not in master process.

    Responsibilities:
    - Initialize worker-specific test results list
    - Setup worker state for result collection
    - Ensure worker isolation from master process

    Args:
        node: xdist WorkerController object representing the worker node

    Note:
    This hook is only called when running with pytest-xdist.
    Does not run in serial execution mode.
    """
    pass


# ============================================================================
# HOOK 11: pytest_testnodedown (xdist only)
# Execution: When xdist worker process terminates
# Purpose: Aggregate results from workers back to master process
# Runs on: Master process only (for each completed worker)
# ============================================================================


def pytest_testnodedown(node, error):
    """
    Aggregate results from xdist worker process.

    Called once per worker after all tests finish on that worker.
    Only runs in the master process.

    Process:
    1. Get worker ID from node configuration
    2. Extract test_results_summary from worker's workeroutput
    3. Flatten and aggregate into master's _test_results_from_workers list
    4. Log worker status (success or error)

    Args:
        node: xdist worker node object
        error: Exception if worker crashed, None if successful
    """
    # Use global _MASTER_CONFIG for aggregation
    config = _MASTER_CONFIG
    if config is None:
        logger.warning("Master config not available for result aggregation")
        return

    # Get worker ID from xdist WorkerController
    worker_id = (
        node.workerinput.get("workerid", "unknown")
        if hasattr(node, "workerinput")
        else "unknown"
    )

    # Log if worker had an error
    if error:
        logger.warning(f"Worker {worker_id} encountered error: {error}")

    # Validate node has workeroutput
    if not hasattr(node, "workeroutput") or node.workeroutput is None:
        return

    # Initialize aggregation list if needed
    if not hasattr(config, "_test_results_from_workers"):
        config._test_results_from_workers = []

    # Extract and aggregate worker results
    results = node.workeroutput.get("test_results_summary", [])

    if not results:
        return

    flatten_results(results, config)


# ============================================================================
# HOOK 12: pytest_sessionfinish
# Execution: After all tests have finished, before pytest_unconfigure
# Purpose: Perform final cleanup and session-level operations
# Runs on: Both master and worker processes
# ============================================================================


def pytest_sessionfinish(session, exitstatus):
    """
    Called after test session is complete, before report generation.

    Process:
    - All tests have been executed
    - xdist workers have been aggregated (if applicable)
    - Before HTML report generation

    Purpose:
    - Perform final session cleanup
    - Aggregate final results
    - Execute session-level teardown logic

    Args:
        session: Test session object
        exitstatus: Exit status code of the session
                   (0: all passed, 1: failures, 2: interrupted, etc.)

    Note:
    - Called on both master and worker processes
    - Worker processes will not generate reports
    - This runs before pytest_unconfigure hook
    """
    pass


# ============================================================================
# HOOK 13: pytest_unconfigure
# Execution: Last hook - after all teardown and xdist aggregation complete
# Purpose: Generate final HTML report with all collected results
# Runs on: Master process only (not in xdist workers)
# ============================================================================


def pytest_unconfigure(config):
    """
    Generate final HTML report after all tests complete.

    Called after all tests have finished, xdist workers aggregated, and cleanup complete.
    Only runs in master process (not in xdist workers).

    Execution Sequence:
    1. Verify running in master process (skip if worker)
    2. Retrieve session start time
    3. Aggregate test results from master and all workers
    4. Create summary statistics (pass/fail/skip counts)
    5. Generate HTML report with visualizations
    6. Save report to reports/ directory with timestamp

    Process:
    - Aggregate results from config.test_results_summary (master)
    - Aggregate results from config._test_results_from_workers (all workers)
    - Calculate summary statistics (total, passed, failed, skipped)
    - Render Jinja2 HTML template with chart data
    - Save to reports/test_report_<timestamp>.html

    Report Contents:
    - Test execution dashboard with summary metrics
    - Status breakdown charts (passed/failed/skipped)
    - Category breakdown by custom fields (Phase, Center, etc.)
    - Detailed results table with all test data
    - Test durations and error messages

    Args:
        config: Pytest config object

    Note:
    - Called only in master process: skips if hasattr(config, 'workerinput')
    - Called only once per session after all xdist aggregation
    - No action needed if no tests were collected/executed
    """
    # Only run in master process
    if hasattr(config, "workerinput"):
        return

    # Get report configuration
    start_time = getattr(config, "_sessionstart_time", None)

    # Generate HTML report

    # Aggregate test results from master and workers
    report_rows = aggregate_test_results(config)

    # # Print results summary to console
    # print_results_summary(report_rows)

    # Create summary object matching template expectations
    report_summary = create_report_summary(report_rows, start_time)

    try:
        generate_report(report_rows, report_summary, start_time)
    except Exception as e:
        logger.error(f"Failed to generate HTML report: {e}", exc_info=True)


# ============================================================================
# Pytest Fixtures (provided by plugin for all consuming projects)
# ============================================================================


@pytest.fixture(scope="function")
def row(request):
    """
    Fixture to provide parametrized test data row.

    SCOPE: Function-scoped (created/destroyed for each test)

    Usage:
    ======
    Parametrize tests with CSV/Excel data:

    @pytest.mark.datafile("TestData.csv")
    def test_user_login(row, driver, wait):
        '''Test login with parametrized data.

        Args:
            row: Dict containing one row from TestData.csv
            driver: Selenium WebDriver instance
            wait: WebDriverWait with configured timeout
        '''
        username = row['Username']
        password = row['Password']
        # ... test code ...

    Supported Markers:
    - @pytest.mark.datafile("filename.csv"): Load parametrized data from CSV
    - @pytest.mark.datafile("filename.xlsx"): Load parametrized data from Excel

    CSV/Excel Location:
    - Files must be in: data/ directory (sibling to tests/ directory)
    - Example: data/TestData.csv → loaded for tests in tests/test_Template.py

    Encoding Support:
    - CSV: utf-8-sig, latin-1, utf-8 (tries all with fallback)
    - Excel: .xlsx files via openpyxl library

    Row Data:
    - Each row is converted to a dict with column headers as keys
    - Empty cells are converted to empty strings (not NaN or None)
    - All values are strings (numeric values must be converted in test)

    Request Parameter:
    - Provided automatically by pytest
    - request.param contains the parametrized value (the row dict)
    """
    return request.param


@pytest.fixture(scope="function")
def driver(request):
    """
    Fixture that provides a Chrome WebDriver instance with a unique profile.

    SCOPE: Function-scoped (created/destroyed for each test)

    Automatically handles:
    - Creating unique browser profile (isolated from other tests)
    - Setting headless mode based on HEADLESS environment variable
    - Cleanup and profile directory removal on test completion

    Environment Variables:
    - HEADLESS (default: "N")
      - "Y" = Run browser in headless mode (no GUI)
      - "N" = Run browser with visible window
      - Useful for CI/CD environments vs. local debugging

    Browser Configuration:
    - --user-data-dir: Unique temporary profile directory per test
    - --no-sandbox: Required for some environments
    - --disable-dev-shm-usage: Prevents shared memory issues
    - --headless=new: Modern headless implementation (if HEADLESS="Y")

    Profile Isolation:
    - Each test gets its own temporary profile directory
    - Profile directory is automatically cleaned up after test
    - Prevents cache/cookie contamination between tests

    Cleanup:
    - Automatically called via pytest finalizer
    - Calls driver.quit() to close browser
    - Removes temporary profile directory recursively

    Usage:
    ======
    def test_login(driver, wait):
        '''Test with Selenium WebDriver.

        Args:
            driver: Chrome WebDriver instance
            wait: WebDriverWait instance (see wait fixture)
        '''
        driver.get("https://example.com/login")
        wait.until(expected_conditions.presence_of_element_located((By.ID, "username")))
        # ... test code ...

    Browser Information:
    - profile_name: Get profile name via profile_name_from_driver(driver)
    - capabilities: driver.capabilities contains browser details

    Args:
        request: pytest request fixture (provided by pytest)

    Returns:
        Selenium WebDriver instance for Chrome browser
    """
    # Create a temporary directory for the unique profile
    profile_dir = tempfile.mkdtemp(prefix="chrome_profile_")
    profile_name = os.path.basename(profile_dir)

    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Check HEADLESS environment variable (Y = headless, N = visible)
    headless = get_env("HEADLESS", "N")
    if headless.upper() == "Y":
        chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=chrome_options)

    # Register a finalizer to always clean up driver and profile directory
    def finalizer():
        try:
            driver.quit()
        except Exception:
            pass
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass

    request.addfinalizer(finalizer)

    yield driver


@pytest.fixture()
def wait(driver):
    """
    Function-scoped WebDriverWait fixture.

    SCOPE: Function-scoped (created/destroyed for each test)

    Purpose:
    - Provides WebDriverWait instance for implicit waits in tests
    - Configured with timeout from WAIT_TIME environment variable
    - Default timeout is 15 seconds if not configured

    Environment Variables:
    - WAIT_TIME (default: "15")
      - Integer number of seconds to wait for elements
      - Used by Selenium's expected_conditions in tests

    Usage:
    ======
    def test_find_element(driver, wait):
        '''Test with WebDriverWait for element visibility.'''
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        element = wait.until(
            EC.presence_of_element_located((By.ID, "submit_button"))
        )
        element.click()

    Common Expected Conditions:
    - EC.presence_of_element_located((By, locator)): Element in DOM
    - EC.visibility_of_element_located((By, locator)): Element visible
    - EC.element_to_be_clickable((By, locator)): Element clickable
    - EC.text_to_be_present_in_element((By, locator), text): Text present

    Args:
        driver: Selenium WebDriver instance (provided by driver fixture)

    Returns:
        WebDriverWait instance with configured timeout
    """
    timeout = int(get_env("WAIT_TIME", "15"))
    return WebDriverWait(driver, timeout)
