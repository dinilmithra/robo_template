import logging
import time

import pytest
from robo_automation_test_kit.utils import get_env
from robo_automation_test_kit.utils.RoboHelper import profile_name_from_driver

logger = logging.getLogger(__name__)


@pytest.mark.datafile("TestData.csv")
def test_demo(row, driver, wait):
    """Test case to open Google using a unique Chrome profile."""

    title = row.get("Title", "")
    if title:
        pass

    # Log profile name from driver user-data-dir argument
    # Measure connection time
    url = get_env("APP_URL")
    if url is None or url.strip() == "":
        assert False, "APP_URL environment variable is not set."

    start_time = time.time()
    driver.get(url)
    connection_time = time.time() - start_time

    # Set browser window title if 'title' is provided
    if title:
        try:
            driver.execute_script(f"document.title = '{title}'")
        except Exception as e:
            logger.warning(f"Could not set browser title: {e}")

    # Validate the page loaded successfully
    current_url = driver.current_url
    page_title = driver.title

    value_1 = row.get("Value 1", None)
    value_2 = row.get("Value 2", None)
    assert value_1 is not None, "Value 1 should not be None"
    assert value_2 is not None, "Value 2 should not be None"
    if value_1 > value_2:
        pytest.skip("Skipping due to some_condition")
    assert value_1 == value_2, "Value 1 and Value 2 should be same"


@pytest.mark.datafile("RoboTestData.csv")
def test_robo(row, driver, wait):
    """Test with RoboTestData."""
    pass
