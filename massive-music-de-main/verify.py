"""Quick verification / smoke checks against the built warehouse."""
import sqlite3

from src import config

c = sqlite3.connect(config.WAREHOUSE_DB)
cur = c.cursor()

print("songs :", cur.execute("SELECT COUNT(*) FROM dim_song").fetchone()[0])
print("ISRCs :", cur.execute("SELECT COUNT(*) FROM fact_recording").fetchone()[0])
print("videos:", cur.execute("SELECT COUNT(*) FROM fact_video").fetchone()[0])
print("quarantine recordings:", cur.execute(
    "SELECT dq_reason, COUNT(*) FROM quarantine_recording GROUP BY dq_reason").fetchall())
print("quarantine videos    :", cur.execute(
    "SELECT dq_reason, COUNT(*) FROM quarantine_video GROUP BY dq_reason").fetchall())
print("songs w/ 0 ISRC :", cur.execute(
    "SELECT COUNT(*) FROM mart_song_isrc_count WHERE isrc_count=0").fetchone()[0])
print("songs w/ 0 video:", cur.execute(
    "SELECT COUNT(*) FROM mart_song_video_count WHERE video_count=0").fetchone()[0])
print("run log :", cur.execute(
    "SELECT run_date, songs_loaded, recordings_valid, videos_valid, status "
    "FROM pipeline_run_log ORDER BY rowid DESC LIMIT 2").fetchall())
c.close()
