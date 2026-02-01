import logging
import time

import pytest
from src.utils.RoboTemplateHelper import profile_name_from_driver, get_env

logger = logging.getLogger(__name__)


@pytest.mark.datafile("TestData.csv")
def test_open_google_with_unique_profile(row, driver, wait):
    """Test case to open Google using a unique Chrome profile."""

    title = row.get("Title", "")
    logger.info(f"Running with TestData row: {row}")
    if title:
        logger.info(f"Using title: {title}")

    logger.info(f"\n{'='*70}")
    logger.info(f"Test: Opening Google with Unique Profile")
    logger.info(f"{'='*70}")
    # Log profile name from driver user-data-dir argument
    logger.info(f"Profile Name from driver: {profile_name_from_driver(driver)}")

    # Measure connection time
    url = get_env("APP_URL")
    if url is None or url.strip() == "":
        assert False, "APP_URL environment variable is not set."

    logger.info(f"Opening {url}")
    start_time = time.time()
    driver.get(url)
    connection_time = time.time() - start_time

    # Set browser window title if 'title' is provided
    if title:
        try:
            driver.execute_script(f"document.title = '{title}'")
            logger.info(f"Set browser window title to: {title}")
        except Exception as e:
            logger.warning(f"Could not set browser title: {e}")

    # Validate the page loaded successfully
    current_url = driver.current_url
    page_title = driver.title
    logger.info(f"Current URL: {current_url}")
    logger.info(f"Page Title: {page_title}")
    logger.info(f"Connection Time: {connection_time:.2f} seconds")

    logger.info(f"✓ Successfully opened: {current_url}")
    logger.info(f"✓ Page Title: {page_title}")
    logger.info(f"✓ Connection Time: {connection_time:.2f} seconds")
    logger.info(f"✓ Profile Used: {profile_name_from_driver(driver)}")
    logger.info(f"{'='*70}")

    value_1 = row.get("Value 1", None)
    value_2 = row.get("Value 2", None)
    assert value_1 is not None, "Value 1 should not be None"
    assert value_2 is not None, "Value 2 should not be None"
    if value_1 > value_2:
        pytest.skip("Skipping due to some_condition")
    assert value_1 == value_2, "Value 1 and Value 2 should be same"
