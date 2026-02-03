# Report generation utilities and helpers
from .reports.HtmlReportUtils import get_html_template
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import zipfile
import os
import logging
import shutil


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


def load_test_data(path: Path):
    """Load test data rows from CSV or Excel file using pandas.

    Supports multiple file formats and encodings:
    - CSV files with utf-8-sig, latin-1, or utf-8 encoding
    - Excel workbooks (.xlsx)

    Returns a list of dict rows suitable for pytest parametrization.
    """

    # Print to stderr to ensure visibility in xdist mode
    import sys

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
                    break
                except UnicodeDecodeError:
                    df = None
            if df is None:
                logger.error(
                    f"Could not load CSV file {path} with any supported encoding"
                )
                return []
        df = df.fillna("")

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
    """Flatten and aggregate test results from workers."""
    if cfg is None:
        return
    if isinstance(res, dict):
        cfg._test_results_from_workers.append(res)
    elif isinstance(res, list):
        for x in res:
            flatten_results(x, cfg)
    else:
        pass


def build_test_data(item):
    """
    Build test result data dictionary from test execution information.

    Args:
        item: pytest Item object containing test metadata
        custom_attribute_data: Optional dict with custom attributes from robo_custom_attribute_data hook

    Returns:
        Dictionary containing test result data:
        - test_status: PASSED, FAILED, or SKIPPED
        - test_id: Test name/nodeid
        - error_log: Exception message if test failed
        - duration: Total execution time in seconds (sum of all phases)
        - Any additional fields from custom_attributes dict
    """

    # Get stored call phase exception info
    call_excinfo = getattr(item, "_call_excinfo", None)

    # Determine test status and error log from call phase
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

    test_id = getattr(item, "name", item.nodeid)

    data_row = {
        # "test_case_name": test_case_name,
        "test_status": status,
        "test_id": test_id,
        "error_log": error_log,
        "duration": total_duration,
    }

    return data_row


# ============================================================================
# Report Generation Functions (merged from report_generator.py)
# ============================================================================


def aggregate_test_results(config):
    """
    Aggregate test results from master process and xdist workers.

    Collects results from config.test_results_summary (master process)
    and config._test_results_from_workers (aggregated worker results).

    Args:
        config: Pytest config object

    Returns:
        List of aggregated test result dictionaries
    """
    report_rows = []

    # Include results from config.test_results_summary (initialized in pytest_configure)
    if hasattr(config, "test_results_summary") and config.test_results_summary:
        master_results = [r for r in config.test_results_summary if isinstance(r, dict)]
        report_rows.extend(master_results)

    # Include results from xdist workers (aggregated via pytest_testnodedown)
    if (
        hasattr(config, "_test_results_from_workers")
        and config._test_results_from_workers
    ):
        for entry in config._test_results_from_workers:
            if isinstance(entry, dict):
                report_rows.append(entry)
            elif isinstance(entry, list):
                worker_results = [r for r in entry if isinstance(r, dict)]
                report_rows.extend(worker_results)
    
    return report_rows


def create_report_summary(report_rows, start_time=None):
    """
    Create summary object for HTML report template.

    Args:
        report_rows: List of test result dictionaries
        start_time: Datetime object for test session start

    Returns:
        Dictionary containing summary statistics for the report
    """
    # Calculate test duration
    if start_time:
        end_time = datetime.now()
        duration = end_time - start_time
        duration_str = str(duration).split(".")[0]  # Remove microseconds
    else:
        duration_str = ""

    # Calculate summary statistics
    total = len(report_rows)
    passed = sum(1 for r in report_rows if r.get("test_status") == "PASSED")
    failed = sum(1 for r in report_rows if r.get("test_status") in ["ERROR", "FAILED"])
    skipped = sum(1 for r in report_rows if r.get("test_status") == "SKIPPED")

    return {
        "env_name": os.getenv("APP_ENV", "").upper(),
        "project_name": os.getenv("PROJECT_NAME", ""),
        "test_framework": os.getenv("TEST_FRAMEWORK", "Robo Automation Framework"),
        "total": total,
        "duration": duration_str,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "rerun": 0,  # Not tracked in current implementation
        "generated_date": datetime.now().strftime("%m-%d-%Y"),
        "generated_time": datetime.now().strftime("%I:%M:%S %p"),
    }


def format_duration(seconds):
    """
    Convert duration in seconds to HH:MM:SS format string.

    Args:
        seconds: Duration in seconds (float or int)

    Returns:
        Formatted duration string as HH:MM:SS
    """
    if isinstance(seconds, (float, int)):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return str(seconds)


def get_report_path():
    """
    Determine and create the report path from environment configuration.

    Returns:
        Path object for the HTML report file location
    """
    report_path = get_env("REPORT_PATH", "reports")
    report_dir = Path(report_path)
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir / "test_report.html"


def generate_report(report_rows, report_summary, start_time):
    """
    Generate and save HTML report with test results.

    Args:
        report_rows: List of test result dictionaries
        report_summary: Summary dictionary for the report
        start_time: Datetime object for test session start

    Returns:
        Path to the generated HTML report
    """

    # Prepare template data with raw numeric durations
    report_title = get_env("REPORT_TITLE", "Test Execution Report")
    template_data = {
        "report_title": report_title,
        "summary": report_summary,
        "report_rows": report_rows,
    }

    # Load CSS and JS files for embedding
    try:
        scripts_dir = Path(__file__).parent.parent / "templates" / "html_report" / "scripts"

        # Read CSS files
        css_path = scripts_dir / "css" / "report.css"
        css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

        material_icons_path = scripts_dir / "css" / "material-icons.css"
        material_icons_content = (
            material_icons_path.read_text(encoding="utf-8")
            if material_icons_path.exists()
            else ""
        )

        robo_fonts_path = scripts_dir / "css" / "robo-fonts.css"
        robo_fonts_content = (
            robo_fonts_path.read_text(encoding="utf-8")
            if robo_fonts_path.exists()
            else ""
        )

        # Read Chart.js library
        chart_js_path = scripts_dir / "js" / "chart.js"
        chart_js_content = (
            chart_js_path.read_text(encoding="utf-8")
            if chart_js_path.exists()
            else ""
        )

        # Read merged JS file
        report_js_path = scripts_dir / "js" / "report.js"

        report_js_content = (
            report_js_path.read_text(encoding="utf-8")
            if report_js_path.exists()
            else ""
        )

        # Add to template data
        template_data["embedded_css"] = css_content
        template_data["embedded_material_icons"] = material_icons_content
        template_data["embedded_robo_fonts"] = robo_fonts_content
        template_data["embedded_chart_js"] = chart_js_content
        template_data["embedded_report_js"] = report_js_content
    except Exception as e:
        # If reading fails, use empty strings
        template_data["embedded_css"] = ""
        template_data["embedded_material_icons"] = ""
        template_data["embedded_robo_fonts"] = ""
        template_data["embedded_chart_js"] = ""
        template_data["embedded_report_js"] = ""

    # Load template using get_html_template() which checks source first
    template = get_html_template()
    
    # Register custom Jinja2 filter for duration formatting
    template.globals['format_duration'] = format_duration

    # Render and save report
    try:
        html_content = template.render(**template_data)

        report_path = get_report_path()

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"\nHTML report generated: {report_path.absolute()}", flush=True)
        return str(report_path.absolute())
    except Exception as e:
        print(f"\nError generating HTML report: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return None
