"""Central configuration: paths and tunables.

Kept deliberately simple (no external config lib) so the demo runs with a bare
Python install. In production these would come from environment variables /
Azure Key Vault (API keys) and a settings file per environment.
"""
from __future__ import annotations

import os

# Repo root = two levels up from this file (src/config.py -> repo root).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(ROOT, "data")
SEED_CATALOG = os.path.join(DATA_DIR, "seed", "songs_catalog.csv")
RAW_DIR = os.path.join(DATA_DIR, "raw")
SPOTIFY_RAW = os.path.join(RAW_DIR, "spotify_raw.json")
YOUTUBE_RAW = os.path.join(RAW_DIR, "youtube_raw.json")

WAREHOUSE_DB = os.path.join(DATA_DIR, "warehouse.db")
DDL_FILE = os.path.join(ROOT, "sql", "ddl.sql")
MARTS_FILE = os.path.join(ROOT, "sql", "marts.sql")

# A fixed run timestamp keeps the demo reproducible. In production this is the
# orchestrator's logical run date (e.g. Azure Data Factory pipeline trigger time).
RUN_DATE = "2026-06-24"
