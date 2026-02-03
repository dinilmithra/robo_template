"""
Robo Reporter - Pytest Plugin
Collects test results and generates HTML reports with chart visualizations.

PYTEST HOOK EXECUTION ORDER:
1. pytest_addoption - Register command-line options
2. pytest_plugin_registered - Check and manage plugin registration
3. pytest_configure - Initialize configuration and global state
4. pytest_collection - Optimize test collection
5. pytest_generate_tests - Parametrize tests with CSV data
6. pytest_runtest_makereport - Capture individual test results
7. pytest_testnodedown - Aggregate results from xdist workers
8. pytest_unconfigure - Generate final HTML report
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

from .report_generator import (
    create_report_summary,
    generate_report,
    flatten_results,
    aggregate_test_results,
)
from .utils.RoboHelper import print_results_summary
from .utils import get_env, load_test_data
from . import hookspec


logger = logging.getLogger(__name__)
logger.propagate = True

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# Global Variables for pytest-xdist result aggregation
# ============================================================================

_MASTER_CONFIG = None  # Global reference to master config for xdist aggregation


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
    1. Register hook specifications from hookspec.py module
    2. Store session start time for report duration calculation
    3. Initialize test_results_summary list on config object
    4. Store master config reference in global variable for xdist workers

    Config attributes created:
    - config.test_results_summary: List to collect test result dicts
    - config._sessionstart_time: Session start datetime
    - _MASTER_CONFIG: Global ref to master config for worker aggregation
    """
    # Register hook specifications so source projects can implement them
    # This ensures hookimpls from conftest.py are recognized
    if not hasattr(config.pluginmanager, "_robo_hookspecs_registered"):
        config.pluginmanager.add_hookspecs(hookspec)
        config.pluginmanager._robo_hookspecs_registered = True

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
# HOOK 4: pytest_collection
# Execution: At start of collection phase (after configure)
# Purpose: Optimize test collection by parsing command-line test selectors
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
# HOOK 5: pytest_generate_tests
# Execution: For each test function during collection (after pytest_collection)
# Purpose: Parametrize tests with CSV/Excel data rows
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
# HOOK 6: pytest_runtest_makereport
# Execution: For each test phase (setup, call, teardown)
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

    # Extract test metadata from parametrized 'row' fixture if present
    test_case_name = phase = req_cat = req_sub_cat = center = ""

    if "row" in item.fixturenames:
        row_value = item.funcargs.get("row", {})
        test_case_name = row_value.get("Test Case Name", "")
        phase = row_value.get("Phase", "")
        req_cat = row_value.get("Request Category", "")
        req_sub_cat = row_value.get("Request Sub-Category", "")
        center = row_value.get("Center", "")

    # Determine test status and error log from call phase
    call_excinfo = getattr(item, "_call_excinfo", None)
    if call_excinfo is None:
        status = "PASSED"
        error_log = ""
    else:
        # Safely extract error message
        try:
            error_repr = call_excinfo.getrepr()
            error_log = (
                error_repr.reprcrash.message
                if error_repr.reprcrash
                else str(call_excinfo.value)
            )
        except (AttributeError, Exception):
            error_log = (
                str(call_excinfo.value) if call_excinfo.value else "Unknown error"
            )

        # Determine status based on exception type
        if call_excinfo.typename == "Skipped":
            status = "SKIPPED"
        else:
            status = "FAILED"

    # Calculate total duration (setup + call + teardown)
    total_duration = sum(item._phase_durations.values())

    test_data = {
        "test_case_name": test_case_name,
        "test_status": status,
        "test_id": getattr(item, "name", item.nodeid),
        "Center": center,
        "Phase": phase,
        "Request Category": req_cat,
        "Request Sub-Category": req_sub_cat,
        "error_log": error_log,
        "duration": total_duration,
    }

    # Store result in config (initialized for both main and worker processes)
    item.config.test_results_summary.append(test_data)

    # For xdist workers: sync to workeroutput for master aggregation
    if hasattr(item.config, "workeroutput"):
        item.config.workeroutput["test_results_summary"] = list(
            item.config.test_results_summary
        )


# ============================================================================
# HOOK 7: pytest_testnodedown
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
# HOOK 8: pytest_unconfigure
# Execution: Last hook - after all teardown and xdist aggregation complete
# Purpose: Generate final HTML report with all collected results
# Runs on: Master process only (not in xdist workers)
# ============================================================================


def pytest_unconfigure(config):
    """
    Generate final HTML report after all tests complete.

    Called after all tests have finished and xdist workers are aggregated.
    Only runs in master process (not in xdist workers).

    Process:
    1. Skip if running in xdist worker process
    2. Aggregate results from master and all workers
    3. Create report summary with statistics
    4. Print results summary to console
    5. Generate and save HTML report

    Report includes:
    - Test execution dashboard with charts
    - Results summary with status breakdown
    - Detailed results table with all test data
    """
    # Only run in master process
    if hasattr(config, "workerinput"):
        return

    # Get report configuration
    start_time = getattr(config, "_sessionstart_time", None)

    # Generate HTML report

    # Aggregate test results from master and workers
    report_rows = aggregate_test_results(config)

    # Print results summary to console
    print_results_summary(report_rows)

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

    Used with @pytest.mark.parametrize("row", test_data) or
    pytest_generate_tests hook for data-driven testing.
    """
    return request.param


@pytest.fixture(scope="function")
def driver(request):
    """
    Fixture that provides a Chrome WebDriver instance with a unique profile.

    Automatically handles:
    - Creating unique browser profile
    - Setting headless mode based on HEADLESS environment variable
    - Cleanup and profile directory removal on test completion
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

    Provides WebDriverWait with timeout from WAIT_TIME environment variable.
    Default timeout is 15 seconds.
    """
    timeout = int(get_env("WAIT_TIME", "15"))
    return WebDriverWait(driver, timeout)
