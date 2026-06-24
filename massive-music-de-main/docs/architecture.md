# 1. Data Pipeline Architecture

## 1.1 Goal
Automate retrieval, processing and storage of song & video metadata from Spotify
and YouTube, on top of an internal catalogue of **699 songs**, so analysts can
answer two questions reliably:

1. **How many videos does each song have on YouTube?**
2. **How many ISRC(s) does each song have on Spotify?**

## 1.2 High-level design (Medallion: Raw → Staging → Serving)

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                    ORCHESTRATION                           │
                 │   Demo: src/pipeline.py   ·   Prod: Azure Data Factory     │
                 └──────────────────────────────────────────────────────────┘
 SOURCES                 RAW (Bronze)          STAGING (Silver)        SERVING (Gold)
┌─────────────┐      ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐
│ Internal    │      │ data/raw/*.json  │   │ flatten + clean  │   │ dim_song           │
│ catalogue   ├────► │ (immutable,      ├──►│ standardise      ├──►│ fact_recording     │
│ (CSV/Sheets)│      │  append-only,    │   │ dedup            │   │ fact_video         │
├─────────────┤      │  partition by    │   │ validate ──┐     │   │ quarantine_*       │
│ Spotify API ├────► │  source+date)    │   │            ▼     │   │ pipeline_run_log   │
├─────────────┤      │                  │   │       quarantine │   │ + marts (views)    │
│ YouTube API ├────► │                  │   │                  │   │                    │
└─────────────┘      └──────────────────┘   └──────────────────┘   └─────────┬──────────┘
                                                                              ▼
                                                                    ┌────────────────────┐
                                                                    │ Power BI / SQL      │
                                                                    │ (analysts)          │
                                                                    └────────────────────┘
```

### Why three layers?
- **Raw (Bronze)** keeps the *exact* API payloads. We can replay transformations
  without re-calling the APIs — critical because the YouTube Data API has a hard
  daily quota (see §1.5) and re-hitting it on every code change is wasteful.
- **Staging (Silver)** is where cleaning, standardisation and deduplication happen.
  It is fully deterministic and unit-testable (`src/transform`, `src/quality`).
- **Serving (Gold)** is the query-optimised star schema plus the marts the business
  reads. Analysts never touch raw JSON.

## 1.3 Components (demo ↔ production mapping)

| Stage | Demo implementation | Production equivalent |
|-------|--------------------|------------------------|
| Catalogue source | `data/seed/songs_catalog.csv` | Google Sheets API export to Data Lake |
| API clients | `src/ingest/mock_*_client.py` | `spotipy` + `google-api-python-client` |
| Raw storage | `data/raw/*.json` | Azure Data Lake Gen2 (`/raw/source=.../date=...`) |
| Transform | `src/transform/*` (stdlib) | PySpark / pandas in ADF or Databricks |
| Quality | `src/quality/validators.py` | Great Expectations suite |
| Warehouse | SQLite `data/warehouse.db` | Azure SQL DB / Synapse Analytics |
| Orchestration | `src/pipeline.py` | Azure Data Factory pipeline (scheduled) |
| Reporting | SQL views (marts) | Power BI on the marts |

## 1.4 Data flow & matching logic
1. Read the catalogue (`song_code`, `original_artist`, `song_title`).
2. For each song, query Spotify (track search) and YouTube (video search) using a
   **cleaned title + parsed artist** query (see `docs/data_quality.md`).
3. Land raw responses, then flatten:
   - Spotify track → `fact_recording` (PK = **ISRC**).
   - YouTube item → `fact_video` (PK = **video_id**).
4. Each fact row carries `song_code`, preserving the **Song → Recording (1:N)** and
   **Song → Video (1:N)** relationships.
5. Counting per `song_code` answers both business questions (the `mart_*` views).

## 1.5 Scalability notes
- **YouTube quota:** default 10,000 units/day; `search.list` = 100 units, so 699
  songs ≈ 70k units → exceeds one day. Strategies: request a quota increase, spread
  ingestion across days, cache results in the Raw zone, and only re-query songs
  whose catalogue entry changed (incremental load keyed on `song_code`).
- **Incremental & idempotent:** all loads are upserts keyed on the PK, so re-runs
  never duplicate data (verified: two consecutive runs both yield 699 / 1266 / 2079).
- **Parallelism:** API calls are independent per song → trivially parallelisable
  with a thread pool (demo keeps it sequential for determinism).

## 1.6 Demo run result (reproducible)
```
songs loaded : 699
ISRCs        : 1266   (Spotify recordings, post-dedup)
videos       : 2079   (YouTube videos, post-dedup)
quarantined  : 57 recordings (bad ISRC) + 22 videos (missing id)
status       : SUCCESS
```
