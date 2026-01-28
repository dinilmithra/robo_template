import logging
from pathlib import Path
import zipfile
import os

logger = logging.getLogger(__name__)


def profile_name_from_driver(driver) -> str:

    # Log profile name from driver user-data-dir argument
    profile_name: str = ""
    for arg in driver.options.arguments:
        if arg.startswith("--user-data-dir="):
            profile_dir = arg.split("=", 1)[1]
            import os

            profile_name = os.path.basename(profile_dir)
            break

    return profile_name


def get_excel_rows(path: Path, logger=None):
    """Load rows from the BrowserTitle file using pandas.
    The file may be a true CSV (with various encodings) or an Excel workbook
    stored with a .csv name. Returns a list of dict rows suitable for
    parametrization.
    """
    try:
        import pandas as pd
    except ImportError:
        if logger:
            logger.warning("pandas not installed; unable to load Excel/CSV rows.")
        return []
    try:
        if zipfile.is_zipfile(path):
            df = pd.read_excel(
                path, engine="openpyxl", dtype=str, keep_default_na=False
            )
        else:
            df = None
            for enc in ("utf-8-sig", "latin-1"):
                try:
                    df = pd.read_csv(
                        path, encoding=enc, dtype=str, keep_default_na=False
                    )
                    break
                except UnicodeDecodeError:
                    df = None
            if df is None:
                df = pd.read_csv(
                    str(path),
                    encoding="utf-8",
                    dtype=str,
                    keep_default_na=False,
                )
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception as exc:
        if logger:
            logger.warning(f"failed to load rows with pandas: {exc}")
        return []


def get_env(key: str) -> str:
    return os.getenv(key, "").strip()
