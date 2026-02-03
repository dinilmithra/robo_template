"""
HTML Report Generator
Generates HTML reports with chart visualizations using Jinja2 templates.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from robo_reporter.utils.RoboHelper import get_env
from robo_reporter.utils.reports.HtmlReportUtils import get_html_template


def flatten_results(results, config):
    """
    Flatten and aggregate test results from workers.

    Args:
        results: List of test results from worker
        config: Pytest config object
    """
    if not hasattr(config, "_test_results_from_workers"):
        config._test_results_from_workers = []

    for entry in results:
        if isinstance(entry, dict):
            config._test_results_from_workers.append(entry)
        elif isinstance(entry, list):
            config._test_results_from_workers.extend(
                [r for r in entry if isinstance(r, dict)]
            )


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


def format_test_durations(report_rows):
    """
    Format test case durations from seconds to HH:MM:SS format.

    Args:
        report_rows: List of test result dictionaries with duration in seconds

    Returns:
        List of test result dictionaries with duration formatted as HH:MM:SS
    """
    formatted_results = []
    for result in report_rows:
        duration_val = result.get("duration", "")
        if isinstance(duration_val, (float, int)):
            hours = int(duration_val // 3600)
            minutes = int((duration_val % 3600) // 60)
            seconds = int(duration_val % 60)
            duration_formatted = f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            duration_formatted = str(duration_val)
        result_copy = dict(result)
        result_copy["duration"] = duration_formatted
        formatted_results.append(result_copy)
    return formatted_results


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

    # Format each test case duration as HH:MM:SS
    formatted_results = format_test_durations(report_rows)

    # Prepare template data
    report_title = get_env("REPORT_TITLE", "Test Execution Report")
    template_data = {
        "report_title": report_title,
        "summary": report_summary,
        "report_rows": formatted_results,
    }

    # Load CSS and JS files for embedding
    try:
        scripts_dir = Path(__file__).parent / "templates" / "html_report" / "scripts"

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
