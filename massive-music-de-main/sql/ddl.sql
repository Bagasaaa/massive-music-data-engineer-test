-- ============================================================================
-- Massive Music — Serving layer schema (Gold)
-- Demo engine: SQLite. Production target: Azure SQL Database / Synapse.
-- Star-style model: dim_song (1) --< fact_recording (N), dim_song (1) --< fact_video (N)
-- ============================================================================

DROP VIEW  IF EXISTS mart_song_isrc_count;
DROP VIEW  IF EXISTS mart_song_video_count;
DROP VIEW  IF EXISTS mart_song_overview;
DROP TABLE IF EXISTS fact_recording;
DROP TABLE IF EXISTS fact_video;
DROP TABLE IF EXISTS quarantine_recording;
DROP TABLE IF EXISTS quarantine_video;
DROP TABLE IF EXISTS pipeline_run_log;
DROP TABLE IF EXISTS dim_song;

-- ----------------------------------------------------------------------------
-- Dimension: one row per internal composition (the catalogue Song Code).
-- ----------------------------------------------------------------------------
CREATE TABLE dim_song (
    song_code        TEXT PRIMARY KEY,
    song_title       TEXT NOT NULL,        -- cleaned, human-facing
    song_title_raw   TEXT,                 -- original value (audit)
    original_artist  TEXT,                 -- may be empty in source
    artist_primary   TEXT,                 -- first parsed artist
    match_key        TEXT,                 -- normalised key for matching
    has_artist       INTEGER DEFAULT 0     -- 1 if source had an artist
);

-- ----------------------------------------------------------------------------
-- Fact: Spotify recordings. One song -> many recordings (each a unique ISRC).
-- ----------------------------------------------------------------------------
CREATE TABLE fact_recording (
    isrc             TEXT PRIMARY KEY,     -- International Standard Recording Code
    song_code        TEXT NOT NULL,
    artist_name      TEXT,
    recording_title  TEXT,
    album            TEXT,
    release_date     TEXT,
    label            TEXT,
    source           TEXT DEFAULT 'spotify',
    FOREIGN KEY (song_code) REFERENCES dim_song(song_code)
);

-- ----------------------------------------------------------------------------
-- Fact: YouTube videos. One song -> many videos.
-- ----------------------------------------------------------------------------
CREATE TABLE fact_video (
    video_id         TEXT PRIMARY KEY,
    song_code        TEXT NOT NULL,
    channel_id       TEXT,
    channel_title    TEXT,
    video_title      TEXT,
    source           TEXT DEFAULT 'youtube',
    FOREIGN KEY (song_code) REFERENCES dim_song(song_code)
);

-- ----------------------------------------------------------------------------
-- Quarantine: rejected rows are kept (never silently dropped) for triage.
-- ----------------------------------------------------------------------------
CREATE TABLE quarantine_recording (
    song_code   TEXT,
    isrc        TEXT,
    payload     TEXT,        -- JSON of the offending row
    dq_reason   TEXT,
    run_date    TEXT
);

CREATE TABLE quarantine_video (
    song_code   TEXT,
    video_id    TEXT,
    payload     TEXT,
    dq_reason   TEXT,
    run_date    TEXT
);

-- ----------------------------------------------------------------------------
-- Observability: one row per pipeline run with stage row counts.
-- ----------------------------------------------------------------------------
CREATE TABLE pipeline_run_log (
    run_date              TEXT,
    songs_loaded          INTEGER,
    recordings_input      INTEGER,
    recordings_valid      INTEGER,
    recordings_dupes      INTEGER,
    recordings_quarantined INTEGER,
    videos_input          INTEGER,
    videos_valid          INTEGER,
    videos_dupes          INTEGER,
    videos_quarantined    INTEGER,
    warnings              TEXT,
    status                TEXT
);

-- Indexes for the FK / aggregation paths the marts use.
CREATE INDEX idx_recording_song ON fact_recording(song_code);
CREATE INDEX idx_video_song     ON fact_video(song_code);
