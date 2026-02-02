"""
Robo Reporter - Pytest Plugin
Collects test results and generates HTML reports with chart visualizations.
"""

import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

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
from .utils.RoboTemplateHelper import print_results_summary
from .utils import get_env, get_excel_rows


logger = logging.getLogger(__name__)
logger.propagate = True


# ============================================================================
# Pytest Hook Specifications (for source projects to implement)
# ============================================================================

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


# ============================================================================
# Global Variables for pytest-xdist result aggregation
# ============================================================================

_MASTER_CONFIG = None  # Global reference to master config for xdist aggregation


# ============================================================================
# Pytest Hooks
# ============================================================================


def pytest_addoption(parser):
    """Add custom command line options."""
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


def pytest_plugin_registered(plugin, manager):
    """
    Called when a plugin is registered.
    - Unregisters xdist if PARALLEL_EXECUTION is disabled.
    """

    # Check if the registered plugin is the xdist dsession plugin
    if str(plugin).find("xdist.dsession.DSession") != -1:
        # Check PARALLEL_EXECUTION environment variable
        parallel_execution = get_env("PARALLEL_EXECUTION", "N").strip()
        if parallel_execution == "N":
            logger.warning("Parallel execution disabled, unregistering pytest-xdist")
            manager.unregister(plugin)


def pytest_configure(config):
    """
    Called after command line options have been parsed and all plugins loaded.
    Initializes test results collection and stores session start time.
    Runs on both master and worker processes.
    """
    # Store session start time for HTML report duration calculation (master only)
    if not hasattr(config, "workerinput") and not hasattr(config, "_sessionstart_time"):
        config._sessionstart_time = datetime.now()

    # Initialize test_results_summary on config (runs on both master and workers)
    config.test_results_summary = []

    # Store master config in global for xdist aggregation (master only)
    global _MASTER_CONFIG
    if not hasattr(config, "workerinput"):
        _MASTER_CONFIG = config


# pytest_configure_node removed - redundant since pytest_configure handles worker initialization


def pytest_collection(session):
    """
    Called at the start of the collection phase.
    Parses command line arguments to identify specific test selections.
    This data helps pytest_generate_tests skip unnecessary parametrization.
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


def pytest_generate_tests(metafunc):
    """
    Called for each test function to generate parameters.

    Parametrizes tests with rows from CSV file when:
    - Test uses 'row' fixture
    - Test has @pytest.mark.datafile("filename.csv") marker

    Prerequisites:
    - @pytest.mark.datafile("filename.csv") marker must be present
    - Test function must declare 'row' parameter/fixture

    Optimization: Skips parametrization for tests not explicitly requested
    when specific tests are run (e.g., pytest tests/test_file.py::specific_test)
    """
    # Check if test has @pytest.mark.datafile marker
    marker = metafunc.definition.get_closest_marker("datafile")
    if not marker or not marker.args:
        return

    # Check if test actually uses the 'row' fixture
    if "row" not in metafunc.fixturenames:
        logger.debug(
            f"Skipping parametrization for {metafunc.nodeid}: 'row' fixture not found"
        )
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
            logger.debug(
                f"Skipping parametrization for {test_nodeid}: not in requested tests"
            )
            return

    # Validate test file path exists
    test_file_path = metafunc.definition.path
    if not test_file_path:
        logger.error(f"Cannot determine file path for test {test_nodeid}")
        return

    # Load CSV data from data/ directory (sibling to test directory)
    test_dir = Path(test_file_path).parent
    data_path = test_dir.parent / "data" / csv_file

    rows = get_excel_rows(data_path)

    if not rows:
        logger.error(
            f"Failed to load data file '{csv_file}' at {data_path}; "
            f"file may not exist, be empty, or have encoding issues"
        )
        pytest.fail(f"Data file '{csv_file}' could not be loaded from {data_path}")

    logger.info(f"Parametrized {test_nodeid} with {len(rows)} rows from {csv_file}")
    metafunc.parametrize("row", rows)


def pytest_runtest_makereport(item, call):
    """
    Called to create a test report for each test phase.

    Collects test result summary including status, duration, title, and error logs.
    Runs on both main process and xdist workers.
    """

    if call.when != "call":
        return

    # Extract test metadata from parametrized 'row' fixture if present
    title = phase = req_cat = req_sub_cat = center = ""

    if "row" in item.fixturenames:
        row_value = item.funcargs.get("row", {})
        title = row_value.get("Title", "")
        phase = row_value.get("Phase", "")
        req_cat = row_value.get("Request Category", "")
        req_sub_cat = row_value.get("Request Sub Category", "")
        center = row_value.get("Center", "")
    else:
        title = getattr(item, "name", item.nodeid)

    # Determine test status and error log
    if call.excinfo is None:
        status = "PASSED"
        error_log = ""
    else:
        # Safely extract error message
        try:
            error_repr = call.excinfo.getrepr()
            error_log = (
                error_repr.reprcrash.message
                if error_repr.reprcrash
                else str(call.excinfo.value)
            )
        except (AttributeError, Exception):
            error_log = (
                str(call.excinfo.value) if call.excinfo.value else "Unknown error"
            )

        # Determine status based on exception type
        if call.excinfo.typename == "Skipped":
            status = "SKIPPED"
        elif hasattr(call, "wasxfail") and call.wasxfail:
            status = "RERUN"
        else:
            status = "ERROR"

    # Extract test case name from docstring if available
    test_case_name = None
    if item.obj and hasattr(item.obj, "__doc__") and item.obj.__doc__:
        try:
            test_case_name = item.obj.__doc__.strip().split("\n")[0]
        except Exception:
            test_case_name = None

    result = {
        "test_status": status,
        "test_case_name": test_case_name,
        "test_name": item.nodeid,
        "title": title,
        "Phase": phase,
        "Request Category": req_cat,
        "Request Sub Category": req_sub_cat,
        "Center": center,
        "error_log": error_log,
        "duration": getattr(call, "duration", None),
    }

    logger.debug(
        f"Collected result for {item.nodeid}: status={status}, duration={getattr(call, 'duration', None)}"
    )

    # Store result in config (initialized for both main and worker processes)
    item.config.test_results_summary.append(result)

    # For xdist workers: sync to workeroutput for master aggregation
    if hasattr(item.config, "workeroutput"):
        item.config.workeroutput["test_results_summary"] = list(
            item.config.test_results_summary
        )


def pytest_testnodedown(node, error):
    """
    Called when a worker node goes down (xdist).

    Aggregates test results from the completed worker into master config.
    Called once per worker after all tests finish on that worker.

    Args:
        node: xdist worker node
        error: Exception if worker crashed, None otherwise
    """
    # Use global _MASTER_CONFIG for aggregation
    config = _MASTER_CONFIG
    if config is None:
        logger.warning("Master config not available for result aggregation")
        return

    # Get worker ID from xdist WorkerController
    worker_id = node.workerinput.get("workerid", "unknown") if hasattr(node, "workerinput") else "unknown"

    # Log if worker had an error
    if error:
        logger.warning(f"Worker {worker_id} encountered error: {error}")

    # Validate node has workeroutput
    if not hasattr(node, "workeroutput") or node.workeroutput is None:
        logger.info(f"Worker {worker_id} has no workeroutput to aggregate")
        return

    # Initialize aggregation list if needed
    if not hasattr(config, "_test_results_from_workers"):
        config._test_results_from_workers = []

    # Extract and aggregate worker results
    results = node.workeroutput.get("test_results_summary", [])

    if not results:
        logger.info(f"Worker {worker_id} completed with 0 results")
        return

    logger.info(f"Aggregating {len(results)} results from worker {worker_id}")
    flatten_results(results, config)
    logger.debug(f"Successfully aggregated results from worker {worker_id}")


def pytest_unconfigure(config):
    """
    Called after all teardown and xdist worker aggregation is complete.
    Aggregates all test results and generates the HTML report.

    Only runs in master process (not in xdist workers).
    """
    # Only run in master process
    if hasattr(config, "workerinput"):
        logger.info("Skipping unconfigure in worker process")
        return

    # Get report configuration
    start_time = getattr(config, "_sessionstart_time", None)

    # Generate HTML report

    # Aggregate test results from master and workers
    report_rows = aggregate_test_results(config)

    # Allow source projects to customize report_rows via hook
    if hasattr(config.hook, "robo_report_rows"):
        hook_result = config.hook.robo_report_rows(config=config, report_rows=report_rows)
        if hook_result is not None:
            report_rows = hook_result
            logger.debug("Report rows customized by source project hook")

    # Print results summary to console
    print_results_summary(report_rows)

    # Create summary object matching template expectations
    report_summary = create_report_summary(report_rows, start_time)

    # Allow source projects to customize report_summary via hook
    if hasattr(config.hook, "robo_report_summary"):
        hook_result = config.hook.robo_report_summary(
            config=config, report_summary=report_summary, report_rows=report_rows
        )
        if hook_result is not None:
            report_summary = hook_result
            logger.debug("Report summary customized by source project hook")

    try:
        generate_report(report_rows, report_summary, start_time)
        logger.info("HTML report generation completed successfully")
    except Exception as e:
        logger.error(f"Failed to generate HTML report: {e}", exc_info=True)


# ============================================================================
# Fixtures (provided by plugin for all consuming projects)
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
