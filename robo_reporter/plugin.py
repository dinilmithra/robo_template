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

from .report_generator import generate_and_save_html_report, flatten_results
from .utils.RoboTemplateHelper import print_results_summary
from .utils import get_env, get_excel_rows


logger = logging.getLogger(__name__)
logger.propagate = True


# ============================================================================
# Global Variables for pytest-xdist result aggregation
# ============================================================================

test_results_summary = []  # List to collect test result objects (main process)
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
    """
    # Store session start time for HTML report duration calculation
    if not hasattr(config, "workerinput") and not hasattr(config, "_sessionstart_time"):
        config._sessionstart_time = datetime.now()

    # Initialize test_results_summary on config for both master and workers
    config.test_results_summary = []

    # Store master config in global for xdist aggregation
    global _MASTER_CONFIG
    if not hasattr(config, "workerinput"):
        _MASTER_CONFIG = config


def pytest_configure_node(node):
    """
    Called for configuring a worker node before it runs tests (xdist).
    Ensures test_results_summary is initialized for each worker.
    """
    node.config.test_results_summary = []


def pytest_collection(session):
    """
    Called after test collection.
    Store specified test info to help pytest_generate_tests skip unnecessary parametrization.
    """
    config = session.config

    # Parse command line arguments to find test selectors
    specified_tests = set()
    for arg in config.invocation_params.args:
        # Look for test selectors (contain :: and don't start with -)
        if not arg.startswith("-") and "::" in arg:
            # Normalize the path to match nodeid format
            # Handle both relative paths and absolute Windows paths
            normalized = arg.replace("\\", "/")

            # If this is an absolute path, extract the relative portion
            # by finding the part after the last occurrence of a known test directory
            # or just extract the part starting from the test filename
            if ":" in normalized and "/" in normalized:  # Windows absolute path
                # Find the test file part (everything from the test file onwards)
                # Look for common test paths like "tests/", "test/", or just get the part with ::
                parts = normalized.split("/")
                for i, part in enumerate(parts):
                    if part in ("tests", "test") or part.startswith("test_"):
                        # Found the test directory or test file, reconstruct from here
                        normalized = "/".join(parts[i:])
                        break

            # Remove parameter indices like [0], [abc], etc.
            normalized = normalized.split("[")[0]
            specified_tests.add(normalized)

    config._specified_test_functions = specified_tests


def pytest_generate_tests(metafunc):
    """
    Called for each test function to generate parameters.
    Parametrizes tests with rows from CSV file if 'row' fixture is present
    and @pytest.mark.datafile marker is used.
    Only parametrizes tests that are being collected (if specific tests were requested).
    """
    marker = metafunc.definition.get_closest_marker("datafile")
    if not marker or not marker.args:
        return

    # Get the test function's nodeid
    test_nodeid = metafunc.definition.nodeid
    config = metafunc.config

    # If specific test functions were requested, check if this test is one of them
    if (
        hasattr(config, "_specified_test_functions")
        and config._specified_test_functions
    ):
        # Check if this test matches any of the requested tests
        is_requested = False
        for spec in config._specified_test_functions:
            # Match test against spec (both already normalized without parameters)
            if test_nodeid.startswith(spec):
                is_requested = True
                break

        # If this test wasn't requested, skip parametrization
        if not is_requested:
            return

    csv_file = marker.args[0]
    # Get data path relative to the test file's directory
    test_dir = Path(metafunc.definition.path).parent
    data_path = test_dir.parent / "data" / csv_file

    rows = get_excel_rows(data_path, logger=logger)

    if not rows:
        pytest.fail(f"{csv_file} is missing or empty")

    ids = [str(r.get("Row Name") or r.get("Title") or "row") for r in rows]
    metafunc.parametrize("row", rows, ids=ids)


def pytest_runtest_makereport(item, call):
    """
    Called to create a test report for each test phase.
    Collects test result summary including status, duration, and error logs.
    """

    if call.when != "call":
        return

    # Extract test metadata
    row_name = title = phase = req_cat = req_sub_cat = center = ""

    # Check if test has parametrized 'row' data
    if "row" in item.fixturenames:
        row_value = item.funcargs.get("row", {})
        row_name = row_value.get("Row Name", "")
        title = row_value.get("Title", "")
        phase = row_value.get("Phase", "")
        req_cat = row_value.get("Request Category", "")
        req_sub_cat = row_value.get("Request Sub Category", "")
        center = row_value.get("Center", "")
    else:
        row_name = ""
        title = getattr(item, "name", item.nodeid)
        phase = req_cat = req_sub_cat = center = ""
    # Determine test status and error log
    if call.excinfo is None:
        status = "PASSED"
        error_log = ""
    else:
        error_log = call.excinfo.getrepr().reprcrash.message

        if call.excinfo.typename == "Skipped":
            status = "SKIPPED"
        elif hasattr(call, "wasxfail") and call.wasxfail:
            status = "RERUN"
        else:
            status = "ERROR"

    # Extract test case name from docstring if available
    test_case_name = None
    try:
        if item.obj and item.obj.__doc__:
            # Simple extraction - first line of docstring
            test_case_name = item.obj.__doc__.strip().split("\n")[0]
    except Exception:
        test_case_name = None

    result = {
        "test_status": status,
        "test_case_name": test_case_name,
        "title": title,
        "Row Name": row_name,
        "Phase": phase,
        "Request Category": req_cat,
        "Request Sub Category": req_sub_cat,
        "Center": center,
        "error_log": error_log,
        "duration": getattr(call, "duration", None),
    }

    # Store result in appropriate location
    if hasattr(item.config, "workerinput"):
        # Worker process - store in config and workeroutput
        item.config.test_results_summary.append(result)
        item.config.workeroutput["test_results_summary"] = list(
            item.config.test_results_summary
        )
    else:
        # Main process - store in global
        test_results_summary.append(result)


def pytest_testnodedown(node, error):
    """
    Called when a worker node goes down (xdist).
    Aggregates test results from the completed worker.
    """
    # Use global _MASTER_CONFIG for aggregation
    config = _MASTER_CONFIG
    if config is None:
        return

    if not hasattr(config, "_test_results_from_workers"):
        config._test_results_from_workers = []

    results = node.workeroutput.get("test_results_summary", [])
    flatten_results(results, config)


def pytest_unconfigure(config):
    """
    Called after all teardown and xdist worker aggregation is complete.
    Aggregates all test results and generates the HTML report.
    """
    # Only run in master process
    if hasattr(config, "workerinput"):
        return

    all_results = []

    # Include results from config.test_results_summary (main process)
    if hasattr(config, "test_results_summary") and config.test_results_summary:
        all_results.extend(
            [r for r in config.test_results_summary if isinstance(r, dict)]
        )

    # Include global test_results_summary (for single test runs)
    global test_results_summary
    if not all_results and test_results_summary:
        all_results.extend([r for r in test_results_summary if isinstance(r, dict)])

    # Include results from xdist workers
    if (
        hasattr(config, "_test_results_from_workers")
        and config._test_results_from_workers
    ):
        for entry in config._test_results_from_workers:
            if isinstance(entry, dict):
                all_results.append(entry)
            elif isinstance(entry, list):
                all_results.extend([r for r in entry if isinstance(r, dict)])

    # Get report configuration
    report_path = config.getoption("robo_report_path")
    # Get report title from environment variable
    report_title = get_env("REPORT_TITLE", "Test Execution Report")
    start_time = getattr(config, "_sessionstart_time", None)

    # Print results summary to console
    print_results_summary(all_results)

    # Generate HTML report
    try:
        generate_and_save_html_report(
            all_results, start_time, custom_path=report_path, report_title=report_title
        )
    except Exception as e:
        pass


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
