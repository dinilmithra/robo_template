"""
Global variables for pytest-xdist result aggregation
"""

test_results_summary = []  # List to collect test result objects (main process)
_MASTER_CONFIG = None  # Global reference to master config for xdist aggregation
from datetime import datetime
import logging
import os
import sys
import tempfile
import shutil
from pathlib import Path

from dotenv import load_dotenv
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.support.ui import WebDriverWait
from src.utils.RoboTemplateHelper import (
    get_excel_rows,
    get_env,
    extract_test_case_name_from_docstring,
    print_results_summary,
    flatten_results,
)
from src.utils.reports.HtmlReportUtils import generate_and_save_html_report

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# Logger Configuration
# ============================================================================


# Get logger - pytest will configure it based on pytest.ini [logging] section
logger = logging.getLogger(__name__)


# Ensure logger propagates to root logger so pytest can capture it
logger.propagate = True


# ============================================================================
# Pytest Hooks
# ============================================================================


# Implemented Pytest Hooks (in execution order)
#
#     1. pytest_configure(config)
#         Called after command line options have been parsed and all plugins and initial conftest files loaded.
#         Logs Python version and test session start time.
#         ✅ Correct and useful for initial test session setup.
#
#     2. pytest_plugin_registered(plugin, manager)
#         Called when a plugin is registered.
#         Unregisters xdist if PARALLEL is disabled.
#         ✅ Useful for controlling parallel execution in debug mode.
#
#     3. pytest_sessionstart(session)
#         Called after the Session object has been created and before performing collection.
#         Logs session start and session ID.
#         ✅ Useful for tracking session lifecycle.
#
#     4. pytest_collection_modifyitems(config, items)
#         Called after collection has been performed, can filter or re-order items.
#         Logs the number of collected test items.
#         ✅ Useful for debugging test discovery.
#
#     5. pytest_generate_tests(metafunc)
#         Called for each test function to generate parameters.
#         Parametrizes tests with proxy rows if 'row' fixture is present.
#         ✅ Useful for dynamic test generation.
#
#     6. pytest_configure_node(node) [xdist-specific]
#         Called for configuring a worker node before it runs tests.
#         Initializes test_results_summary for each worker config.
#         ✅ Useful for per-worker setup in parallel execution.
#
#     7. pytest_fixture_setup(fixturedef, request)
#         Called during setup phase for fixtures.
#         Logs fixture setup for function-scoped fixtures.
#         ✅ Useful for tracking fixture initialization.
#
#     8. pytest_runtest_setup(item)
#         Called before running each test item.
#         Logs setup phase for the test item.
#         ✅ Useful for debugging test setup.
#
#     9. pytest_runtest_call(item)
#         Called to execute the test item.
#         Logs call phase for the test item.
#         ✅ Useful for tracking test execution.
#
#     10. pytest_runtest_makereport(item, call)
#         Called to create a test report for each test phase.
#         Collects test result summary and error logs.
#         ✅ Useful for custom result handling and reporting.
#
#     11. pytest_runtest_logreport(report)
#         Called after each test phase to process the report.
#         Logs test result status and tracks test outcomes.
#         ✅ Useful for logging and custom reporting.
#
#     12. pytest_runtest_teardown(item, nextitem)
#         Called after test item execution for teardown.
#         Logs teardown phase for the test item.
#         ✅ Useful for debugging test cleanup.
#
#     13. pytest_testnodedown(node, error) [xdist-specific]
#         Called when a worker node goes down after completing its tests.
#         Aggregates test results from completed worker and logs any errors.
#         ✅ Useful for collecting results and monitoring node failures.
#
#     14. pytest_sessionfinish(session, exitstatus)
#         Called after the whole test run finishes, right before returning the exit status.
#         Logs session end and exit status.
#         ✅ Useful for final cleanup and reporting.
#
#     15. pytest_unconfigure(config)
#         Called after all teardown and xdist worker aggregation is complete.
#         Aggregates test results from all workers and generates HTML report.
#         ✅ Useful for final report generation and result aggregation.
#
# ============================================================================


# Add custom CLI option for log level
def pytest_addoption(parser):
    # parser.addoption(
    #     "--log-cli-level",
    #     action="store",
    #     default="ERROR",
    #     help="Set log level for custom logger (overrides LOG_LEVEL env variable)",
    # )
    pass


def pytest_configure(config):
    """
    Called after command line options have been parsed and all plugins and initial conftest files loaded.
    Logs Python version and test session start time.
    ✅ Correct and useful for initial test session setup.
    """
    logger.info("=" * 70)
    logger.info("HOOK: pytest_configure")
    logger.info("=" * 70)
    logger.info("PYTEST CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"Python version: {sys.version}")
    logger.info(
        f"Test session started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    logger.info("=" * 70)

    # Store session start time for HTML report duration calculation (only in master process)
    if not hasattr(config, "workerinput") and not hasattr(config, "_sessionstart_time"):
        config._sessionstart_time = datetime.now()

    # Always initialize test_results_summary on config for both master and workers
    # Always initialize test_results_summary for all configs (master and workers)
    config.test_results_summary = []

    # Store master config in global for xdist aggregation
    global _MASTER_CONFIG
    if not hasattr(config, "workerinput"):
        _MASTER_CONFIG = config


def pytest_plugin_registered(plugin, manager):
    """
    Called when a plugin is registered.
    - Unregisters xdist if PARALLEL is disabled.
    - Useful for controlling parallel execution in debug mode.
    """

    # Check PARALLEL environment variable
    parallel_disabled = os.getenv("PARALLEL_EXECUTION", "N").upper() == "N"

    # Check if the registered plugin is the xdist dsession plugin
    if str(plugin).find("xdist.dsession.DSession") != -1:
        if parallel_disabled:
            logger.warning("Debugger active, unregistering pytest-xdist")
            manager.unregister(plugin)


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and before performing collection.
    - Logs session start and session ID.
    - Useful for tracking session lifecycle.
    """
    logger.info("HOOK: pytest_sessionstart")
    logger.info(f"{'Session Start':^70}")
    logger.info(f"Test session ID: {session.name}")
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def pytest_collection_modifyitems(config, items):
    """
    Called after collection has been performed, can filter or re-order items.
    - Logs the number of collected test items.
    - Useful for debugging test discovery.
    """
    logger.info("HOOK: pytest_collection_modifyitems")
    logger.info(f"Collected {len(items)} test item(s)")


def pytest_generate_tests(metafunc):
    """
    Called for each test function to generate parameters.
    - Parametrizes tests with proxy rows if 'row' fixture is present.
    - Useful for dynamic test generation.
    """

    marker = metafunc.definition.get_closest_marker("datafile")
    if not marker or not marker.args:
        # No marker, skip parameterization
        return
    csv_file = marker.args[0]
    data_path = Path(__file__).resolve().parent / "data" / csv_file
    rows = get_excel_rows(data_path)
    if not rows:
        pytest.fail(f"{csv_file} is missing or empty")
    ids = [str(r.get("Row Name") or r.get("Title") or "row") for r in rows]
    metafunc.parametrize("row", rows, ids=ids)


def pytest_configure_node(node):
    """
    Called for configuring a worker node before it runs tests.
    - Logs the configuration of the worker node.
    - Correct and useful for debugging worker configuration.
    """
    logger.info("HOOK: pytest_configure_node")
    logger.info(f"Configuring worker node: {node.gateway.id}")
    # Ensure test_results_summary is initialized for each worker config (required for xdist)
    node.config.test_results_summary = []


def pytest_fixture_setup(fixturedef, request):
    """
    Called during setup phase for fixtures.
    - Logs fixture setup for function-scoped fixtures.
    - Useful for tracking fixture initialization.
    """
    logger.info(f"HOOK: pytest_fixture_setup")
    if fixturedef.scope == "function":
        logger.info(f"  [fixture setup] {fixturedef.argname}")


def pytest_runtest_setup(item):
    """
    Called before running each test item.
    - Logs setup phase for the test item.
    - Useful for debugging test setup.
    """
    logger.info(f"HOOK: pytest_runtest_setup")
    logger.info(f"[SETUP] {item.name}")


def pytest_runtest_call(item):
    """
    Called to execute the test item.
    - Logs call phase for the test item.
    - Useful for tracking test execution.
    """
    logger.info(f"HOOK: pytest_runtest_call")
    logger.info(f"[CALL] {item.name}")


def pytest_runtest_makereport(item, call):
    """
    Called to create a test report for each test phase.
    - Tracks online proxies for passed tests.
    - Useful for custom result handling and proxy tracking.
    """
    if call.when != "call":
        return

    # Collect test result summary
    row_name = title = phase = req_cat = req_sub_cat = center = "N/A"
    if "row" in item.fixturenames:
        row_value = item.funcargs.get("row", {})
        row_name = row_value.get("Row Name", row_value.get("Row Name", "N/A"))
        title = row_value.get("Title", "N/A")
        phase = row_value.get("Phase", "N/A")
        req_cat = row_value.get("Request Category", "N/A")
        req_sub_cat = row_value.get("Request Sub Category", "N/A")
        center = row_value.get("Center", "N/A")
    else:
        row_name = "N/A"
        title = getattr(item, "name", item.nodeid)
        phase = req_cat = req_sub_cat = center = "N/A"

    # Determine test status and error log

    if call.excinfo is None:
        status = "PASSED"
        error_log = ""
    else:
        # This gives the full traceback as a string (file, line, code, error)
        error_log = call.excinfo.getrepr().reprcrash.message

        if call.excinfo.typename == "Skipped":
            status = "SKIPPED"
        elif hasattr(call, "wasxfail") and call.wasxfail:
            status = "RERUN"
        else:
            status = "ERROR"

    # Optionally extract test_case_name if needed (if extract_test_case_name_from_docstring is used elsewhere)
    test_case_name = None
    try:
        test_case_name = extract_test_case_name_from_docstring(item, None)
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

    # Debug: print result being collected

    # Attach result to report for use in pytest_runtest_logreport
    # Only append to the correct collection once
    if hasattr(item.config, "workerinput"):
        # In worker process, store in config
        item.config.test_results_summary.append(result)
        # Always set workeroutput, even if empty
        item.config.workeroutput["test_results_summary"] = list(
            item.config.test_results_summary
        )
    else:
        # In main process (no xdist), store in global
        test_results_summary.append(result)


def pytest_runtest_logreport(report):
    """
    Called after each test phase to process the report.
    - Logs test result status and tracks successful proxies.
    - Useful for logging and custom reporting.
    """
    logger.info(f"HOOK: pytest_runtest_logreport ({report.when})")
    if report.when == "call":
        if report.passed:
            status = "✓ PASSED"
        elif report.failed:
            status = "✗ FAILED"
        elif report.skipped:
            status = "⊘ SKIPPED"
        else:
            status = "? UNKNOWN"
        logger.info(f"[{status}] {report.nodeid}")


def pytest_runtest_teardown(item, nextitem):
    """
    Called after test item execution for teardown.
    - Logs teardown phase for the test item.
    - Useful for debugging test cleanup.
    """
    logger.info(f"HOOK: pytest_runtest_teardown")
    logger.info(f"[TEARDOWN] {item.name}")


def pytest_testnodedown(node, error):
    """
    Called when a worker node goes down.
    - Logs the node going down and any error.
    - Correct and useful for monitoring node failures.
    """
    logger.info("HOOK: pytest_testnodedown")
    logger.info(f"Worker node down: {node.gateway.id}")
    if error:
        logger.error(f"Node error: {error}")
    # Use global _MASTER_CONFIG for aggregation
    config = _MASTER_CONFIG
    if config is None:
        return
    if not hasattr(config, "_test_results_from_workers"):
        config._test_results_from_workers = []
    results = node.workeroutput.get("test_results_summary", [])

    flatten_results(results, config)


def pytest_sessionfinish(session, exitstatus):
    """
    Called after the whole test run finishes, right before returning the exit status.
    - Exports online proxies and logs session end.
    - Useful for final cleanup and reporting.
    """
    logger.info("HOOK: pytest_sessionfinish")
    logger.info(f"{'Session Finish':^70}")
    logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Exit status: {exitstatus}")
    logger.info("=" * 70)


def pytest_unconfigure(config):
    """
    Called after all teardown and xdist worker aggregation is complete.
    Print the aggregated test results summary here.
    """
    # Only logger.warning in master process
    if hasattr(config, "workerinput"):
        return

    all_results = []
    # Always include results from config.test_results_summary (main process)
    if hasattr(config, "test_results_summary") and config.test_results_summary:
        all_results.extend(
            [r for r in config.test_results_summary if isinstance(r, dict)]
        )

    # If still empty, include global test_results_summary (for single test case runs)
    global test_results_summary
    if not all_results and test_results_summary:
        all_results.extend([r for r in test_results_summary if isinstance(r, dict)])

    # Also include results from xdist workers if present
    if (
        hasattr(config, "_test_results_from_workers")
        and config._test_results_from_workers
    ):
        for entry in config._test_results_from_workers:
            if isinstance(entry, dict):
                all_results.append(entry)
            elif isinstance(entry, list):
                all_results.extend([r for r in entry if isinstance(r, dict)])
            # else branch intentionally left empty (no action needed)

    # Place report in the 'report' folder at the project root (outside src)
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )

    print_results_summary(all_results)

    start_time = getattr(config, "_sessionstart_time", None)

    # Generate HTML report at the end of execution
    try:
        html_report_path = generate_and_save_html_report(all_results, start_time)
        print(f"HTML report generated: {html_report_path}")
    except Exception as e:
        print(f"Failed to generate HTML report: {e}")


# ============================================================================
# End Pytest Hooks
# ============================================================================


# ============================================================================
# Pytest-xdist Hooks (in execution order)
# ============================================================================

# Implemented Pytest-xdist Hooks (in execution order)
#
#     1. pytest_xdist_auto_num_workers(config) [xdist-specific]
#         Called to determine the number of workers for -n auto flag.
#         Logs the hook call. Returns None to use default behavior.
#         ✅ Useful for debugging parallel worker setup.
#
#     2. pytest_xdist_make_scheduler(config, log) [xdist-specific]
#         Called to create a custom test scheduler.
#         Logs the hook call and returns None to use default scheduler.
#         ✅ Useful for customizing test distribution strategy.
#
#     3. pytest_xdist_setupnodes(config, specs) [xdist-specific]
#         Called before any remote node is set up.
#         Logs the number of worker nodes being set up.
#         ✅ Useful for debugging parallel test setup.
#
#     4. pytest_xdist_newgateway(gateway) [xdist-specific]
#         Called when a new gateway (worker) is created.
#         Logs the creation of a new gateway.
#         ✅ Useful for tracking worker creation.
#
#     5. pytest_xdist_node_collection_finished(node, ids) [xdist-specific]
#         Called when a worker node finishes test collection.
#         Logs the number of tests collected by the worker.
#         ✅ Useful for monitoring collection progress.
#
# ============================================================================


def pytest_xdist_auto_num_workers(config):
    """
    Called to determine the number of workers for -n auto.
    - Logs the hook call.
    - Correct, though you do not return a value (default behavior).
    """
    logger.info("HOOK: pytest_xdist_auto_num_workers")

def pytest_xdist_make_scheduler(config, log):
    """
    Called to create a custom test scheduler.
    - Logs the hook call and returns None to use the default scheduler.
    - Correct, and returning None is the default/safe option.
    """
    logger.info("HOOK: pytest_xdist_make_scheduler")
    # Return None to use default LoadScheduling
    return None


def pytest_xdist_setupnodes(config, specs):
    """
    Called before any remote node is set up.
    - Logs the number of worker nodes being set up.
    - Correct and useful for debugging parallel test setup.
    """
    logger.info("HOOK: pytest_xdist_setupnodes")
    logger.info(f"Setting up {len(specs)} worker node(s)")


def pytest_xdist_newgateway(gateway):
    """
    Called when a new gateway (worker) is created.
    - Logs the creation of a new gateway.
    - Correct and useful for tracking worker creation.
    """
    logger.info("HOOK: pytest_xdist_newgateway")
    logger.info(f"New gateway created: {gateway.id}")


def pytest_xdist_node_collection_finished(node, ids):
    """
    Called when a worker node finishes test collection.
    - Logs the number of tests collected by the worker.
    """
    logger.info("HOOK: pytest_xdist_node_collection_finished")
    logger.info(f"Worker {node.gateway.id} collected {len(ids)} test(s)")


# ============================================================================
# End Pytest-xdist Hooks
# ============================================================================

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def row(request):
    return request.param


@pytest.fixture(scope="function")
def driver(request):
    """Fixture that provides a Chrome WebDriver instance with a unique profile."""
    # Create a temporary directory for the unique profile
    profile_dir = tempfile.mkdtemp(prefix="chrome_profile_")
    profile_name = os.path.basename(profile_dir)

    logger.info(f"Profile Name: {profile_name}")
    logger.info(f"Profile Directory: {profile_dir}")

    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Check HEADLESS environment variable (Y = headless, N = visible)
    headless = get_env("HEADLESS")
    if not headless:
        headless = "N"
    if headless.upper() == "Y":
        # Use --headless=new for Chrome 109+
        chrome_options.add_argument("--headless=new")
        logger.info("[HEADLESS MODE ENABLED]")
    else:
        logger.info("[HEADLESS MODE DISABLED]")

    driver = webdriver.Chrome(options=chrome_options)

    # Print profile information from driver
    logger.info(f"Driver Session ID: {driver.session_id}")
    logger.info(f"Driver Name: {driver.name}")
    logger.info(
        f"Driver Capabilities: {driver.capabilities.get('browserName', 'Unknown')}"
    )
    logger.info(f"Profile Name from Driver Context: {profile_name}")

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
        logger.info(f"Cleaned up profile directory: {profile_dir}")
        logger.info(f"Teardown complete for profile: {profile_name}")

    request.addfinalizer(finalizer)

    yield driver


@pytest.fixture()
def wait(driver):
    """Function-scoped WebDriverWait aligned with library usage (wait-first)."""
    timeout = int(os.getenv("WAIT_TIME", "15"))
    return WebDriverWait(driver, timeout)


# ============================================================================
# End Fixtures
# ============================================================================
