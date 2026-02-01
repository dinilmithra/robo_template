def get_report_data(start_time):
    """
    Build the report_data dictionary for report generation, using config and environment variables.
    """
    import os
    from datetime import datetime

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    report_dir = os.path.join(project_root, "reports")
    return {
        "project_name": os.getenv("PROJECT_NAME", "N/A"),
        "environment": os.getenv("APP_ENV", "N/A"),
        "test_framework": os.getenv("TEST_FRAMEWORK", "N/A"),
        "start_time": start_time,
        "end_time": datetime.now(),
        "report_dir": report_dir,
    }


import os


def get_html_template():
    """
    Returns the Jinja2 template object for the HTML report.
    """
    import os
    from jinja2 import Environment, FileSystemLoader

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    template_dir = os.path.join(project_root, "templates", "html_report")
    env = Environment(loader=FileSystemLoader(template_dir))
    return env.get_template("html_template.html")


def get_report_summary(all_results, report_data):
    """
    Create the summary object for the report, including environment, project, test framework, total, and duration.
    """
    from datetime import datetime
    start_time = report_data.get("start_time", None)
    end_time = report_data.get("end_time", None)
    if start_time is not None and end_time is not None:
        total_seconds = int((end_time - start_time).total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        duration_str = f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        duration_str = "-"

    # Count test statuses for summary chart, treating 'ERROR' as 'FAILED'
    status_counts = {"PASSED": 0, "FAILED": 0, "SKIPPED": 0, "RERUN": 0}
    for result in all_results:
        status = str(result.get("test_status", "")).upper()
        if status == "ERROR":
            status = "FAILED"
        if status in status_counts:
            status_counts[status] += 1
    return {
        "environment": report_data.get("environment", "N/A"),
        "project_name": report_data.get("project_name", "N/A"),
        "test_framework": report_data.get("test_framework", "N/A"),
        "total": len(all_results),
        "duration": duration_str,
        "passed": status_counts["PASSED"],
        "failed": status_counts["FAILED"],
        "skipped": status_counts["SKIPPED"],
        "rerun": status_counts["RERUN"],
        "generated_date": datetime.now().strftime('%m-%d-%Y'),
        "generated_time": datetime.now().strftime('%I:%M:%S %p'),
    }


def generate_and_save_html_report(all_results, start_time):
    """
    Generate and save the HTML report in the report directory with a timestamped filename.
    Returns the path to the generated report.
    """

    report_data = get_report_data(start_time)

    report_title = report_data.get("project_name", "NA")
    report_dir = report_data.get("report_dir", None)

    if report_dir is None:
        # Use the project root (three levels up from this file)
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        report_dir = os.path.join(project_root, "reports")
    os.makedirs(report_dir, exist_ok=True)

    # Sanitize report_title for filename (remove/replace problematic characters)
    import re
    from datetime import datetime

    safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", report_title)
    now_str = datetime.now().strftime("_%Y%m%d_%H%M%S")
    html_report_path = os.path.join(report_dir, f"{safe_title}{now_str}.html")
    generate_html_report(all_results, html_report_path, report_data)
    return html_report_path


def generate_html_report(all_results, output_path, report_data=None):
    """
    Generate an HTML report using the Jinja2 template and all_results.
    """

    # Defensive: allow report_data to be None
    if report_data is None:
        report_data = {}
    report_title = os.getenv("REPORT_TITLE", "Test Report")
    from datetime import datetime
    summary = get_report_summary(all_results, report_data)

    template = get_html_template()

    # Format each test case duration as HH:MM:SS
    formatted_results = []
    for result in all_results:
        duration_val = result.get("duration", "")
        if isinstance(duration_val, (float, int)):
            hours = int(duration_val // 3600)
            minutes = int((duration_val % 3600) // 60)
            seconds = int(duration_val % 60)
            duration_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            duration_str = str(duration_val)
        result_copy = dict(result)
        result_copy["duration"] = duration_str
        formatted_results.append(result_copy)

    html_content = template.render(
        report_title=report_title,
        summary=summary,
        all_results=formatted_results,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
