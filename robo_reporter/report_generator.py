"""
HTML Report Generator
Generates HTML reports with chart visualizations using Jinja2 templates.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
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


def generate_and_save_html_report(
    all_results, start_time=None, custom_path=None, report_title="Test Execution Report"
):
    """
    Generate and save HTML report with test results.

    Args:
        all_results: List of test result dictionaries
        start_time: Datetime object for test session start
        custom_path: Optional custom path for the report file
        report_title: Title for the HTML report

    Returns:
        Path to the generated HTML report
    """
    # Calculate test duration
    if start_time:
        end_time = datetime.now()
        duration = end_time - start_time
        duration_str = str(duration).split(".")[0]  # Remove microseconds
    else:
        duration_str = ""

    # Calculate summary statistics
    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("test_status") == "PASSED")
    failed = sum(1 for r in all_results if r.get("test_status") in ["ERROR", "FAILED"])
    skipped = sum(1 for r in all_results if r.get("test_status") == "SKIPPED")

    # Format each test case duration as HH:MM:SS
    formatted_results = []
    for result in all_results:
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

    # Determine report path
    if custom_path:
        report_path = Path(custom_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Default to reports directory with fixed name
        report_dir = Path("reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "test_report.html"

    # Create summary object matching template expectations
    summary = {
        "env_name": os.getenv("APP_ENV", ""),
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

    # Prepare template data
    template_data = {
        "report_title": report_title,
        "summary": summary,
        "all_results": formatted_results,
    }

    # Load CSS and JS files for embedding
    try:
        scripts_dir = Path(__file__).parent / "templates" / "html_report" / "scripts"

        # Read CSS file
        css_path = scripts_dir / "css" / "report.css"
        css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

        # Read JS files
        report_js_path = scripts_dir / "js" / "report.js"

        report_js_content = (
            report_js_path.read_text(encoding="utf-8")
            if report_js_path.exists()
            else ""
        )

        # Add to template data
        template_data["embedded_css"] = css_content
        template_data["embedded_report_js"] = report_js_content
    except Exception as e:
        # If reading fails, use empty strings
        template_data["embedded_css"] = ""
        template_data["embedded_report_js"] = ""

    # Load template using get_html_template() which checks source first
    template = get_html_template()

    # Render and save report
    try:
        html_content = template.render(**template_data)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"\nHTML report generated: {report_path.absolute()}", flush=True)
        return str(report_path.absolute())
    except Exception as e:
        print(f"\nError generating HTML report: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None
