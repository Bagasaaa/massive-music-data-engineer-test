"""Load layer (Gold / serving).

Builds the SQLite warehouse from the DDL, loads the dimension and fact tables
with idempotent upserts (re-running the pipeline never duplicates rows), persists
quarantined rows and the run log, and (re)creates the analytical marts.

The SQL here is intentionally close to ANSI so the same logic ports to Azure SQL
/ Synapse with minimal change (mainly the upsert syntax and index hints).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Dict, List

from .. import config


def _exec_script(conn: sqlite3.Connection, path: str) -> None:
    with open(path, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())


def init_schema(conn: sqlite3.Connection) -> None:
    _exec_script(conn, config.DDL_FILE)


def load_songs(conn: sqlite3.Connection, rows: List[Dict]) -> int:
    conn.executemany(
        """
        INSERT INTO dim_song
            (song_code, song_title, song_title_raw, original_artist,
             artist_primary, match_key, has_artist)
        VALUES (:song_code, :song_title, :song_title_raw, :original_artist,
                :artist_primary, :match_key, :has_artist)
        ON CONFLICT(song_code) DO UPDATE SET
            song_title=excluded.song_title,
            song_title_raw=excluded.song_title_raw,
            original_artist=excluded.original_artist,
            artist_primary=excluded.artist_primary,
            match_key=excluded.match_key,
            has_artist=excluded.has_artist
        """,
        rows,
    )
    return len(rows)


def load_recordings(conn: sqlite3.Connection, rows: List[Dict]) -> int:
    conn.executemany(
        """
        INSERT INTO fact_recording
            (isrc, song_code, artist_name, recording_title, album,
             release_date, label, source)
        VALUES (:isrc, :song_code, :artist_name, :recording_title, :album,
                :release_date, :label, :source)
        ON CONFLICT(isrc) DO UPDATE SET
            song_code=excluded.song_code,
            artist_name=excluded.artist_name,
            recording_title=excluded.recording_title,
            album=excluded.album,
            release_date=excluded.release_date,
            label=excluded.label
        """,
        rows,
    )
    return len(rows)


def load_videos(conn: sqlite3.Connection, rows: List[Dict]) -> int:
    conn.executemany(
        """
        INSERT INTO fact_video
            (video_id, song_code, channel_id, channel_title, video_title, source)
        VALUES (:video_id, :song_code, :channel_id, :channel_title, :video_title, :source)
        ON CONFLICT(video_id) DO UPDATE SET
            song_code=excluded.song_code,
            channel_id=excluded.channel_id,
            channel_title=excluded.channel_title,
            video_title=excluded.video_title
        """,
        rows,
    )
    return len(rows)


def load_quarantine(conn: sqlite3.Connection, recs: List[Dict], vids: List[Dict]) -> None:
    conn.executemany(
        "INSERT INTO quarantine_recording (song_code, isrc, payload, dq_reason, run_date) "
        "VALUES (?, ?, ?, ?, ?)",
        [(r.get("song_code"), r.get("isrc"), json.dumps(r, ensure_ascii=False),
          r.get("dq_reason"), config.RUN_DATE) for r in recs],
    )
    conn.executemany(
        "INSERT INTO quarantine_video (song_code, video_id, payload, dq_reason, run_date) "
        "VALUES (?, ?, ?, ?, ?)",
        [(v.get("song_code"), v.get("video_id"), json.dumps(v, ensure_ascii=False),
          v.get("dq_reason"), config.RUN_DATE) for v in vids],
    )


def write_run_log(conn: sqlite3.Connection, report: Dict) -> None:
    rec, vid = report["recordings"], report["videos"]
    conn.execute(
        """
        INSERT INTO pipeline_run_log
            (run_date, songs_loaded, recordings_input, recordings_valid,
             recordings_dupes, recordings_quarantined, videos_input, videos_valid,
             videos_dupes, videos_quarantined, warnings, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            config.RUN_DATE, report["songs_loaded"],
            rec["input"], rec["valid"], rec["duplicates_removed"], rec["quarantined"],
            vid["input"], vid["valid"], vid["duplicates_removed"], vid["quarantined"],
            "; ".join(report.get("warnings", [])) or "none",
            report.get("status", "SUCCESS"),
        ),
    )


def build_marts(conn: sqlite3.Connection) -> None:
    _exec_script(conn, config.MARTS_FILE)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.WAREHOUSE_DB)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
