-- ============================================================================
-- Analytical marts — these directly answer the two business questions.
-- Implemented as views so they always reflect the current warehouse state.
-- ============================================================================

-- Business question #2: "How many ISRC(s) does each song have in Spotify?"
DROP VIEW IF EXISTS mart_song_isrc_count;
CREATE VIEW mart_song_isrc_count AS
SELECT
    s.song_code,
    s.song_title,
    s.original_artist,
    COUNT(r.isrc) AS isrc_count
FROM dim_song s
LEFT JOIN fact_recording r ON r.song_code = s.song_code
GROUP BY s.song_code, s.song_title, s.original_artist;

-- Business question #1: "How many videos does each song have in YouTube?"
DROP VIEW IF EXISTS mart_song_video_count;
CREATE VIEW mart_song_video_count AS
SELECT
    s.song_code,
    s.song_title,
    s.original_artist,
    COUNT(v.video_id) AS video_count
FROM dim_song s
LEFT JOIN fact_video v ON v.song_code = s.song_code
GROUP BY s.song_code, s.song_title, s.original_artist;

-- Convenience: both answers side by side (what a Power BI report binds to).
DROP VIEW IF EXISTS mart_song_overview;
CREATE VIEW mart_song_overview AS
SELECT
    s.song_code,
    s.song_title,
    s.original_artist,
    COUNT(DISTINCT r.isrc)     AS isrc_count,
    COUNT(DISTINCT v.video_id) AS video_count
FROM dim_song s
LEFT JOIN fact_recording r ON r.song_code = s.song_code
LEFT JOIN fact_video     v ON v.song_code = s.song_code
GROUP BY s.song_code, s.song_title, s.original_artist;
