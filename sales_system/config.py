from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DATASET_FILENAME = "retail_synthetic_dataset.csv"
DATASET_PATH = DATA_DIR / DATASET_FILENAME
LEGACY_DATASET_PATH = Path.home() / "Downloads" / "retail_synthetic_dataset.xls"


def ensure_project_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_dataset_file() -> Path:
    ensure_project_directories()

    if DATASET_PATH.exists():
        return DATASET_PATH

    if LEGACY_DATASET_PATH.exists():
        shutil.copy2(LEGACY_DATASET_PATH, DATASET_PATH)
        print(f"[DEBUG] Bootstrapped canonical dataset from: {LEGACY_DATASET_PATH}")
        print(f"[DEBUG] Canonical dataset created at: {DATASET_PATH}")
        return DATASET_PATH

    raise FileNotFoundError(
        f"Missing dataset. Expected either {DATASET_PATH} or legacy source {LEGACY_DATASET_PATH}."
    )