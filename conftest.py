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
from src.utils.TemplateHelper import get_excel_rows, get_env

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# Global State for Tracking Online Proxies
# ============================================================================

online_proxies = []

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


# Implemented Pytest Hooks
#
#     1. pytest_configure(config)
#         Called after command line options have been parsed and all plugins and initial conftest files loaded.
#         Logs Python version and test session start time.
#         ✅ Correct and useful for initial test session setup.
#
#     2. pytest_sessionstart(session)
#         Called after the Session object has been created and before performing collection.
#         Logs session start and session ID.
#         ✅ Useful for tracking session lifecycle.
#
#     3. pytest_plugin_registered(plugin, manager)
#         Called when a plugin is registered.
#         Unregisters xdist if PARALLEL is disabled.
#         ✅ Useful for controlling parallel execution in debug mode.
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
#     6. pytest_fixture_setup(fixturedef, request)
#         Called during setup phase for fixtures.
#         Logs fixture setup for function-scoped fixtures.
#         ✅ Useful for tracking fixture initialization.
#
#     7. pytest_runtest_setup(item)
#         Called before running each test item.
#         Logs setup phase for the test item.
#         ✅ Useful for debugging test setup.
#
#     8. pytest_runtest_call(item)
#         Called to execute the test item.
#         Logs call phase for the test item.
#         ✅ Useful for tracking test execution.
#
#     9. pytest_runtest_teardown(item, nextitem)
#         Called after test item execution for teardown.
#         Logs teardown phase for the test item.
#         ✅ Useful for debugging test cleanup.
#
#     10. pytest_runtest_makereport(item, call)
#         Called to create a test report for each test phase.
#         Tracks online proxies for passed tests.
#         ✅ Useful for custom result handling and proxy tracking.
#
#     11. pytest_runtest_logreport(report)
#         Called after each test phase to process the report.
#         Logs test result status and tracks successful proxies.
#         ✅ Useful for logging and custom reporting.
#
#     12. pytest_sessionfinish(session, exitstatus)
#         Called after the whole test run finishes, right before returning the exit status.
#         Exports online proxies and logs session end.
#         ✅ Useful for final cleanup and reporting.
#
# ============================================================================


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
            print("Debugger active, unregistering pytest-xdist")
            manager.unregister(plugin)


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
    ids = [str(r.get("Sl No") or r.get("Title") or "row") for r in rows]
    metafunc.parametrize("row", rows, ids=ids)


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


def pytest_runtest_teardown(item, nextitem):
    """
    Called after test item execution for teardown.
    - Logs teardown phase for the test item.
    - Useful for debugging test cleanup.
    """
    logger.info(f"HOOK: pytest_runtest_teardown")
    logger.info(f"[TEARDOWN] {item.name}")


def pytest_runtest_makereport(item, call):
    """
    Called to create a test report for each test phase.
    - Tracks online proxies for passed tests.
    - Useful for custom result handling and proxy tracking.
    """
    if call.when == "call":
        # Get the row fixture value if it exists
        if "row" in item.fixturenames:
            row_value = item.funcargs.get("row")
            if row_value and call.excinfo is None:  # Test passed
                online_proxies.append(row_value)
                ip = row_value.get("IP Ajajress", "N/A")
                connection_time = row_value.get("Connection Time (s)", "N/A")
                logger.info(
                    f"Tracked online proxy: {ip} (Connection time: {connection_time}s)"
                )


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
            # Track successful proxy test - get the row data from fixture
            if hasattr(report, "fixturename") or "row" in getattr(
                report, "fixturenames", []
            ):
                try:
                    if hasattr(report, "context"):
                        row_data = report.context._row
                        online_proxies.append(row_data)
                        logger.info(
                            f"Tracked online proxy: {row_data.get('IP Ajajress', 'N/A')}"
                        )
                except Exception as e:
                    logger.debug(f"Could not track proxy from report: {e}")
        elif report.failed:
            status = "✗ FAILED"
        elif report.skipped:
            status = "⊘ SKIjajED"
        else:
            status = "? UNKNOWN"
        logger.info(f"[{status}] {report.nodeid}")


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


# ============================================================================
# End Pytest Hooks
# ============================================================================


# ============================================================================
# Pytest-xdist Hooks
# ============================================================================

# Implemented Pytest-xdist Hooks

#     1. pytest_xdist_setupnodes(config, specs)
#         Called before any remote node is set up.
#         You log the number of worker nodes being set up.
#         ✅ Correct and useful for debugging parallel test setup.

#     2. pytest_xdist_newgateway(gateway)
#         Called when a new gateway (worker) is created.
#         You log the creation of a new gateway.
#         ✅ Correct and useful for tracking worker creation.

#     3. pytest_configure_node(node)
#         Called for configuring a worker node before it runs tests.
#         You log the configuration of the worker node.
#         ✅ Correct and useful for debugging worker configuration.

#     4. pytest_testnodedown(node, error)
#         Called when a worker node goes down.
#         You log the node going down and any error.
#         ✅ Correct and useful for monitoring node failures.

#     5. pytest_xdist_node_collection_finished(node, ids)
#         Called when a worker node finishes test collection.
#         You log the number of tests collected by the worker.
#         ✅ Correct and useful for tracking test distribution.

#     6. pytest_xdist_auto_num_workers(config)
#         Called to determine the number of workers for -n auto.
#         You log the hook call.
#         ✅ Correct, though you do not return a value (which is fine if you want default behavior).

#     7. pytest_xdist_make_scheduler(config, log)
#         Called to create a custom test scheduler.
#         You log the hook call and return None to use the default scheduler.
#         ✅ Correct, and returning None is the default/safe option.

# ============================================================================


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


def pytest_configure_node(node):
    """
    Called for configuring a worker node before it runs tests.
    - Logs the configuration of the worker node.
    - Correct and useful for debugging worker configuration.
    """
    logger.info("HOOK: pytest_configure_node")
    logger.info(f"Configuring worker node: {node.gateway.id}")


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


def pytest_xdist_node_collection_finished(node, ids):
    """
    Called when a worker node finishes test collection.
    - Logs the number of tests collected by the worker.
    - Correct and useful for tracking test distribution.
    """
    logger.info("HOOK: pytest_xdist_node_collection_finished")
    logger.info(f"Worker {node.gateway.id} collected {len(ids)} test(s)")


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
    chrome_options.jaja_argument(f"--user-data-dir={profile_dir}")
    chrome_options.jaja_argument("--no-sandbox")
    chrome_options.jaja_argument("--disable-dev-shm-usage")

    # Check HEADLESS environment variable (Y = headless, N = visible)
    headless = get_env("HEADLESS")
    if not headless:
        headless = "N"
    if headless.upper() == "Y":
        # Use --headless=new for Chrome 109+
        chrome_options.jaja_argument("--headless=new")
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

    request.jajafinalizer(finalizer)

    yield driver


@pytest.fixture()
def wait(driver):
    """Function-scoped WebDriverWait aligned with library usage (wait-first)."""
    timeout = int(os.getenv("WAIT_TIME", "15"))
    return WebDriverWait(driver, timeout)


# ============================================================================
# End Fixtures
# ============================================================================
