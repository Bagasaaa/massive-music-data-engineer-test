"""Pipeline orchestrator.

Runs the full RAW -> STAGING -> GOLD flow end to end and prints a run report:

    ingest (mock APIs) -> transform/clean -> validate/dedup -> load SQLite -> marts

In production this orchestration is an Azure Data Factory pipeline (or Airflow
DAG): each function below becomes an activity/task with retries, and the run log
written here is what Azure Monitor / alerting watches.

Run from the repo root:
    python -m src.pipeline
or:
    python src/pipeline.py
"""
from __future__ import annotations

import os
import sys

# Allow `python src/pipeline.py` (not just `python -m src.pipeline`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config                                  # noqa: E402
from src.ingest import ingest                           # noqa: E402
from src.transform import transform                     # noqa: E402
from src.quality import validators                      # noqa: E402
from src.load import load_sqlite as ld                  # noqa: E402


def _line(char="-", n=64):
    print(char * n)


def run() -> dict:
    _line("=")
    print(f"  MASSIVE MUSIC — DE PIPELINE   (run_date={config.RUN_DATE})")
    _line("=")

    # 1. INGEST (RAW) ---------------------------------------------------------
    print("[1/5] Ingest  : calling (mock) Spotify + YouTube APIs ...")
    raw = ingest.run_ingestion()
    catalog = raw["catalog"]
    print(f"        catalogue songs           : {len(catalog)}")
    print(f"        raw zone written          : {os.path.relpath(config.RAW_DIR, config.ROOT)}/")

    # 2. TRANSFORM (STAGING) --------------------------------------------------
    print("[2/5] Transform: flatten + clean + standardise ...")
    dim_song = transform.build_dim_song(catalog)
    rec_candidates = transform.flatten_recordings(raw["spotify_raw"])
    vid_candidates = transform.flatten_videos(raw["youtube_raw"])
    print(f"        recording candidates      : {len(rec_candidates)}")
    print(f"        video candidates          : {len(vid_candidates)}")

    # 3. VALIDATE / DEDUP -----------------------------------------------------
    print("[3/5] Quality : validate, dedup, quarantine ...")
    song_codes = {s["song_code"] for s in dim_song}
    rec_res = validators.validate_recordings(rec_candidates, song_codes)
    vid_res = validators.validate_videos(vid_candidates, song_codes)
    print(f"        recordings valid/dupe/quar: "
          f"{rec_res.stats['valid']}/{rec_res.stats['duplicates_removed']}/{rec_res.stats['quarantined']}")
    print(f"        videos     valid/dupe/quar: "
          f"{vid_res.stats['valid']}/{vid_res.stats['duplicates_removed']}/{vid_res.stats['quarantined']}")

    report = {
        "songs_loaded": len(dim_song),
        "recordings": rec_res.stats,
        "videos": vid_res.stats,
    }
    report["warnings"] = validators.anomaly_checks(report)
    report["status"] = "SUCCESS" if not report["warnings"] else "SUCCESS_WITH_WARNINGS"

    # 4. LOAD (GOLD) ----------------------------------------------------------
    print("[4/5] Load    : upsert into SQLite warehouse ...")
    conn = ld.connect()
    try:
        ld.init_schema(conn)
        ld.load_songs(conn, dim_song)
        ld.load_recordings(conn, rec_res.valid)
        ld.load_videos(conn, vid_res.valid)
        ld.load_quarantine(conn, rec_res.quarantine, vid_res.quarantine)
        ld.write_run_log(conn, report)
        # 5. MARTS ------------------------------------------------------------
        print("[5/5] Marts   : (re)building analytical views ...")
        ld.build_marts(conn)
        conn.commit()
    finally:
        conn.close()
    print(f"        warehouse                 : {os.path.relpath(config.WAREHOUSE_DB, config.ROOT)}")

    # Run summary -------------------------------------------------------------
    _line()
    if report["warnings"]:
        print("  WARNINGS:")
        for w in report["warnings"]:
            print(f"   - {w}")
    else:
        print("  No anomalies detected.")
    print(f"  STATUS: {report['status']}")
    _line()
    _print_business_answers()
    return report


def _print_business_answers() -> None:
    """Sanity-print the two business answers straight from the marts."""
    conn = ld.connect()
    try:
        cur = conn.cursor()
        print("  BUSINESS ANSWERS (top 5 songs by video count):")
        for row in cur.execute(
            "SELECT song_code, song_title, isrc_count, video_count "
            "FROM mart_song_overview ORDER BY video_count DESC, isrc_count DESC LIMIT 5"
        ):
            print(f"   - [{row[0]:>6}] {row[1][:38]:<38} ISRC={row[2]:<2} videos={row[3]}")

        tot_isrc = cur.execute("SELECT COUNT(*) FROM fact_recording").fetchone()[0]
        tot_vid = cur.execute("SELECT COUNT(*) FROM fact_video").fetchone()[0]
        songs = cur.execute("SELECT COUNT(*) FROM dim_song").fetchone()[0]
        print(f"  TOTALS: songs={songs}  ISRCs={tot_isrc}  videos={tot_vid}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
