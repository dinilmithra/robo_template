# HTML report generation using Jinja2
from .reports.HtmlReportUtils import generate_html_report
from pathlib import Path
import zipfile
import os
import logging


logger = logging.getLogger(__name__)
logger.propagate = True


def profile_name_from_driver(driver) -> str:

    # Log profile name from driver user-data-dir argument
    profile_name: str = ""
    for arg in driver.options.arguments:
        if arg.startswith("--user-data-dir="):
            profile_dir = arg.split("=", 1)[1]
            profile_name = os.path.basename(profile_dir)
            break

    return profile_name


def get_excel_rows(path: Path):
    """Load rows from the data file using pandas.
    The file may be a true CSV (with various encodings) or an Excel workbook
    stored with a .csv name. Returns a list of dict rows suitable for
    parametrization.
    """

    # Print to stderr to ensure visibility in xdist mode
    import sys

    logger.info(f"Loading data file: {path}" )

    # Validate file exists
    if not os.path.exists(path):
        logger.error(f"Data file not found: {path}")
        return []

    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas not installed; cannot load data file")
        return []

    try:
        if zipfile.is_zipfile(path):
            df = pd.read_excel(
                path, engine="openpyxl", dtype=str, keep_default_na=False
            )
        else:
            df = None
            for enc in ("utf-8-sig", "latin-1", "utf-8"):
                try:
                    df = pd.read_csv(
                        path, encoding=enc, dtype=str, keep_default_na=False
                    )
                    logger.debug(f"Successfully loaded CSV with encoding: {enc}")
                    break
                except UnicodeDecodeError:
                    logger.debug(f"Failed to load CSV with encoding: {enc}")
                    df = None
            if df is None:
                logger.error(f"Could not load CSV file {path} with any supported encoding")
                return []
        df = df.fillna("")
        logger.info(f"Loaded {len(df)} rows from data file: {path}")
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.error(f"Error loading data file {path}: {exc}", exc_info=True)
        return []


def get_env(key: str, default: str = "") -> str:
    value = os.getenv(key, default).strip()
    return value if value else default


def extract_test_case_name_from_docstring(item, report):
    """Extract test case name from function docstring or nodeid."""
    docstring = str(item.function.__doc__)
    if docstring:
        return docstring.strip()
    else:
        return report.nodeid


def print_results_summary(all_results):

    header = "{:<10} {:<30} {:<10} {:<10} {:<20} {:<20} {:<10} {:<10} {:<20}".format(
        "Status",
        "Title",
        "Phase",
        "Request Category",
        "Request Sub Category",
        "Center",
        "Duration",
        "Error Log",
        "Test Name",
    )
    sep = "-" * 150
    print("\nTest Results Summary:")
    print(header)
    print(sep)
    if not all_results:
        print(sep)
        return
    for result in all_results:
        # If duration is a float or int, format as HH:MM:SS
        duration_val = result.get("duration", "")
        if isinstance(duration_val, (float, int)):
            hours = int(duration_val // 3600)
            minutes = int((duration_val % 3600) // 60)
            seconds = int(duration_val % 60)
            duration_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            duration_str = str(duration_val)
        row = "{:<10} {:<30} {:<10} {:<10} {:<20} {:<20} {:<10} {:<10} {:<20}".format(
            result.get("test_status", ""),
            result.get("title", ""),
            result.get("Phase", ""),
            result.get("Request Category", ""),
            result.get("Request Sub Category", ""),
            result.get("Center", ""),
            duration_str,
            result.get("error_log", ""),
            result.get("test_name", ""),
        )
        print(row)
    print(sep)


# Flatten if results is a list of lists or dicts
def flatten_results(res, cfg):
    if cfg is None:
        return
    if isinstance(res, dict):
        cfg._test_results_from_workers.append(res)
    elif isinstance(res, list):
        for x in res:
            flatten_results(x, cfg)
    else:
        pass
