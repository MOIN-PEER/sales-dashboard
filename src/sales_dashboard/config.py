"""Project paths and settings. DATABASE_PATH can be overridden with an environment variable."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.getenv("SALES_DB_PATH", ROOT / "data" / "sales.db"))
FRONTEND_DIR = ROOT / "frontend"
RESULTS_DIR = ROOT / "outputs" / "results"
FIGURES_DIR = ROOT / "outputs" / "figures"

RANDOM_SEED = 2026
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"
