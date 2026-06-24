# Massive Music — Data Engineering Pipeline
1. Extract.ipynb
Extracting Data from Youtube API. I apologize for the limitation regarding the Spotify Web API. I am unable to use it due to legal constraints, as it requires a Spotify Premium account through the official developer platform (https://developer.spotify.com/dashboard).

Technical test solution (**Tasks** section) for a music-publishing data pipeline that
ingests song & video metadata from **Spotify** and **YouTube** on top of an internal
catalogue of **699 songs**, and answers two business questions:

1. **How many videos does each song have on YouTube?**
2. **How many ISRC(s) does each song have on Spotify?**

> Scope note: this repo covers the **"Tasks"** deliverables (Pipeline Architecture,
> Data Quality, Storage Layer, Monitoring & Maintenance). API access uses a
> **deterministic mock** of the Spotify/YouTube responses so the whole pipeline runs
> offline with zero credentials — the focus is the architecture, model and data-quality
> design, which are identical for the real APIs (you swap one module).

## Result (reproducible)
```
songs : 699      ISRCs : 1266      videos : 2079
quarantined : 57 recordings (bad ISRC) + 22 videos (missing id)
status : SUCCESS
```

## How to run
Requires **Python 3.8+ only** (standard library — nothing to `pip install`).
```bash
python -m src.pipeline      # builds data/warehouse.db end to end
python verify.py            # smoke checks against the warehouse
```
Re-running is safe (idempotent upserts).

## Answering the business questions (SQL)
```sql
-- ISRCs per song (Spotify)
SELECT * FROM mart_song_isrc_count  ORDER BY isrc_count DESC;

-- Videos per song (YouTube)
SELECT * FROM mart_song_video_count ORDER BY video_count DESC;

-- Both, side by side (Power BI binds here)
SELECT * FROM mart_song_overview;
```

## Repository layout
```
massive-music-de/
├── data/
│   ├── seed/songs_catalog.csv     # the 699-song internal catalogue
│   ├── raw/                       # immutable raw API payloads (regenerated)
│   └── warehouse.db               # SQLite serving DB (regenerated)
├── src/
│   ├── ingest/                    # mock Spotify/YouTube clients + ingestion (RAW)
│   ├── transform/                 # cleaning + flattening (STAGING)
│   ├── quality/                   # validation, dedup, quarantine, anomaly checks
│   ├── load/                      # SQLite loader (GOLD) + marts
│   ├── config.py
│   └── pipeline.py                # orchestrator (RAW→STAGING→GOLD→marts)
├── sql/
│   ├── ddl.sql                    # star schema + quarantine + run log
│   └── marts.sql                  # the two business-answer views
├── docs/
│   ├── architecture.md            # Task: Data Pipeline Architecture
│   ├── erd.md                     # ERD (Mermaid)
│   ├── data_quality.md            # Task: Data Quality & Validation Strategy
│   ├── storage_design.md          # Task: Data Storage Layer Design
│   └── monitoring.md              # Task: Pipeline Monitoring & Maintenance
├── slides/outline.md              # presentation outline
└── verify.py
```

## How this maps to the test's "Tasks"
| Task | Where |
|------|-------|
| Data Pipeline Architecture (+ cleaned DB + ERD) | `docs/architecture.md`, `docs/erd.md`, `sql/`, running pipeline |
| Data Quality & Validation Strategy | `docs/data_quality.md`, `src/quality/`, `src/transform/clean.py` |
| Data Storage Layer Design | `docs/storage_design.md`, `sql/ddl.sql` |
| Pipeline Monitoring & Maintenance | `docs/monitoring.md`, `pipeline_run_log`, `quarantine_*` |

## Tech stack & rationale
**Python** (ingestion/transform), **SQL/SQLite → Azure SQL/Synapse** (warehouse),
**Azure Data Factory** (orchestration, the cloud evolution of SSIS), **Power BI**
(reporting). Chosen to match a SQL Server / SSIS / Azure / Power BI background, so the
production path is a direct extension of the demo rather than a different stack.

### Going from mock to real APIs
Replace `src/ingest/mock_spotify_client.py` / `mock_youtube_client.py` with `spotipy`
and `google-api-python-client` calls returning the same dict shape. Nothing downstream
changes. ISRC comes from Spotify's `track.external_ids.isrc`; video id/channel from the
YouTube `search.list` response. Mind the YouTube 10k-units/day quota (see
`docs/architecture.md` §1.5).
