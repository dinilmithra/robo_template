# AI Coding Agent Instructions - robo_template

## Project Overview

**robo_template** is a pytest plugin for comprehensive test automation reporting. It extracts test execution data from pytest and generates interactive HTML reports with chart visualizations (status summaries, category breakdowns, phase analysis). The plugin supports parallel test execution via pytest-xdist and reads test data from CSV/Excel files for parameterized testing.

## Architecture & Key Components

### Core Plugin Structure (`robo_reporter/`)
- **plugin.py**: Pytest hook implementations (pytest_addoption, pytest_configure, pytest_configure_node, pytest_collection, pytest_runtest_makereport, pytest_testnodedown, pytest_unconfigure)
- **report_generator.py**: HTML report generation using Jinja2 templates with result flattening/aggregation; contains `flatten_results()` and `generate_and_save_html_report()`
- **utils/RoboTemplateHelper.py**: Utilities including `get_excel_rows()` (handles CSV/Excel with encoding fallbacks), `get_env()`, `extract_test_case_name_from_docstring()`, `profile_name_from_driver()`, `print_results_summary()`
- **utils/reports/HtmlReportUtils.py**: HTML generation helpers including `get_html_template()`, `get_report_summary()`, `get_report_data()`
- **templates/**: Jinja2 HTML templates (html_report/ and email_report/) with chart components and result tables

### Data Flow
1. Tests execute via pytest (isolated or parallel with xdist)
2. `pytest_configure` initializes `config.test_results_summary` list and stores `_MASTER_CONFIG` globally
3. `pytest_runtest_makereport` hook captures each test result (status, duration, title from docstring via `extract_test_case_name_from_docstring()`)
4. For xdist workers: `pytest_configure_node` initializes per-worker result lists; worker results passed back via `pytest_testnodedown`
5. Master aggregates worker results via `flatten_results()` into `config._test_results_from_workers`
6. On `pytest_unconfigure`: `generate_and_save_html_report()` combines all results, renders templates, saves to `reports/test_report_<timestamp>.html`

### Critical Patterns
- **Result Collection**: Results in `config.test_results_summary` as dict list with keys: `test_status` (PASSED/FAILED/ERROR/SKIPPED), `test_name`, `test_title`, `duration`, `error_log`, plus custom fields (Row Name, Phase, Request Category, Center, etc.)
- **xdist Aggregation**: Master config stored in global `_MASTER_CONFIG`; workers' results flattened into `config._test_results_from_workers` via `flatten_results()` which recursively handles nested lists/dicts
- **Template Rendering**: Uses `FileSystemLoader` (project root → templates/html_report/) NOT PackageLoader; templates at project root level, not package-nested
- **Environment Configuration**: Read via `os.getenv()` for `PROJECT_NAME`, `APP_ENV`, `TEST_FRAMEWORK`, `REPORT_TITLE`, `LOG_LEVEL`
- **Status Mapping**: ERROR status treated as FAILED in summary calculations (see `get_report_summary()`)

## Common Workflows & Commands

### Setup & Installation
```powershell
# Local dev install (editable mode)
pip install -e .

# Run tests with default HTML report (parallel via xdist by default)
pytest

# Run tests serially (disable xdist -n logical default)
pytest -n 1

# Run with custom report path and title
pytest --robo-report=custom_report.html --robo-report-title="Smoke Tests"

# Run specific test file or test
pytest tests/test_Template.py
pytest tests/test_Template.py::test_name

# Control log level dynamically (PowerShell)
$env:LOG_LEVEL="DEBUG"; pytest --log-cli-level=$env:LOG_LEVEL
```

### Test Data Integration
- CSV/Excel files in `data/` directory (TestData.csv, RoboTestData.csv)
- Data accessed via `row` fixture parameter; `get_excel_rows()` handles loading
- Encoding fallback chain: utf-8-sig → latin-1 → utf-8; handles .csv and .xlsx via zipfile/openpyxl detection
- Access datafile via `@pytest.mark.datafile("filename.csv")` marker (pytest.ini has custom marker registered)

### Test Naming & Reporting
- Test titles from docstring extracted via `extract_test_case_name_from_docstring()`; falls back to pytest nodeid
- Custom test data fields (Row Name, Phase, Request Category, Center) added to result dict and displayed in summary table
- Use `print_results_summary()` to view console summary before HTML report

### Debugging & Verification
- HTML reports saved to `reports/` with timestamp; check browser logs for rendering issues
- Console shows test status, duration, and custom fields via `print_results_summary()`
- For xdist issues: Check `config._test_results_from_workers` populated and worker node configs initialized
- Log level via environment: `$env:LOG_LEVEL="DEBUG"`

## Project-Specific Conventions

1. **Test Naming**: Docstrings provide human-readable test titles in reports; fallback to pytest nodeid if missing
2. **Report Organization**: Results grouped by status (PASSED/FAILED/SKIPPED/RERUN); ERROR status treated as FAILED in summaries
3. **Parallel Safety**: Global state (`_MASTER_CONFIG`, `test_results_summary`) isolated per worker; aggregation happens only in master
4. **Fixture Pattern**: Tests receive `row` (from CSV), `driver` (Selenium), `wait` (WebDriverWait) fixtures
5. **Template Inheritance**: Base template includes component partials via Jinja2 `{% include %}` for modular report structure

## Key Files & Their Roles

| File | Purpose |
|------|---------|
| robo_reporter/plugin.py | Pytest hooks - initialization, result capture, xdist aggregation |
| robo_reporter/report_generator.py | flatten_results() and generate_and_save_html_report() main entry point |
| robo_reporter/utils/RoboTemplateHelper.py | CSV/Excel loading, docstring extraction, environment config |
| robo_reporter/utils/reports/HtmlReportUtils.py | get_html_template(), get_report_summary(), HTML rendering |
| templates/html_report/html_template.html | Main Jinja2 template rendering summary and results table |
| templates/html_report/components/ | Chart partials (summary-chart, category-chart, phase-chart, etc.) |
| conftest.py | Minimal fixture setup - delegates to plugin hooks |
| pytest.ini | pytest config: xdist -n logical default, markers, logging format |
| data/ | CSV/Excel test data files (TestData.csv, RoboTestData.csv) |
| reports/ | Output directory for generated HTML reports with timestamp naming |

## Critical Integration Points

- **pytest Hook Execution Order**: `pytest_configure` (init) → `pytest_collection` (discover) → `pytest_runtest_makereport` (per test) → `pytest_testnodedown` (workers finish) → `pytest_unconfigure` (report generation)
- **Global State for xdist**: `_MASTER_CONFIG` stores master process reference; workers initialize own `config.test_results_summary`; master aggregates via `flatten_results()` which recursively processes nested lists/dicts from workers
- **Jinja2 Template Loading**: Uses `FileSystemLoader(template_dir)` pointing to project root `templates/html_report/` directory (NOT PackageLoader which assumes package-nested templates)
- **Result Dict Structure**: Results passed to template must include: `test_status`, `test_name`, `test_title`, `duration` (seconds as float, formatted to HH:MM:SS by template), `error_log`, plus custom fields from CSV (Row Name, Phase, Request Category, Center)
- **CSV Encoding Handling**: `get_excel_rows()` tries utf-8-sig, then latin-1, then utf-8; detects .xlsx via zipfile check and uses openpyxl; always converts to dict records via pandas

## Typical Extension Scenarios

- **Adding Report Metrics**: Modify `get_report_summary()` in HtmlReportUtils.py; update template to display new fields
- **Custom Chart Types**: Add new component HTML file in `templates/html_report/components/`; include in main template
- **Test Result Filtering**: Extend `flatten_results()` to apply predicates before aggregation
- **Email Notifications**: Template structure exists in `templates/email_report/`; hook into `pytest_unconfigure` to send via SMTP

## Gotchas & Debugging Tips

- **Missing Results in xdist**: Verify `pytest_testnodedown` hook is called and `flatten_results()` receives worker results
- **Template Not Found**: Check `PackageLoader` vs `FileSystemLoader`; ensure templates/ in MANIFEST.in for package builds
- **Encoding Errors**: CSV loading may fail silently; check `get_excel_rows()` exception handling and log fallbacks
- **Report Path Issues**: Default path is `reports/test_report_<timestamp>.html`; ensure reports/ directory is writable
