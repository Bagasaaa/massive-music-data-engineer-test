# 3. Data Storage Layer Design

## 3.1 Demo vs production
- **Demo:** SQLite (`data/warehouse.db`) — a single portable file, zero setup, fully
  reviewable from the repo. Good enough to prove the model and the answers.
- **Production:** an Azure-native lakehouse, chosen to match the team's existing
  skill set (SQL Server / SSIS / Azure) and the "cloud data warehouse" requirement.

## 3.2 Proposed production architecture (Azure)

```
Spotify/YouTube APIs ─► Azure Data Factory ─► Azure Data Lake Gen2 (RAW, Parquet/JSON)
                                                     │
                                          ADF / Databricks (transform + DQ)
                                                     ▼
                                   Azure SQL Database  *or*  Synapse Analytics
                                          (dim_song, fact_recording, fact_video, marts)
                                                     ▼
                                              Power BI (DirectQuery / Import)
```

| Layer | Service | Why |
|-------|---------|-----|
| Raw | **Azure Data Lake Storage Gen2** | cheap, schema-on-read, immutable history, partition by `source`/`ingest_date`; enables replay without re-hitting API quota |
| Serving | **Azure SQL DB** (≤ this scale) or **Synapse dedicated/serverless** (if it grows to billions of rows) | columnstore indexes → fast `GROUP BY song_code`; familiar T-SQL; native Power BI connector |
| Secrets | **Azure Key Vault** | Spotify/YouTube API keys never in code |
| Orchestration | **Azure Data Factory** | scheduled triggers, retries, monitoring — the cloud evolution of SSIS |

## 3.3 Why this aligns with user access & analytical needs
- Analysts/data scientists consume **marts** (`mart_song_isrc_count`,
  `mart_song_video_count`, `mart_song_overview`) — already aggregated to one row per
  song, so reports are instant and the two business questions are first-class.
- **Power BI** connects directly to Azure SQL/Synapse; no data wrangling in the BI tool.
- The star schema (1 dimension + 2 facts) is the canonical shape BI engines optimise
  for, and `GROUP BY song_code` over indexed FKs scales linearly.

## 3.4 Performance & scalability choices
- **Indexes** on `fact_recording(song_code)` and `fact_video(song_code)` (present in
  the demo DDL) — the marts' aggregation path.
- **Primary keys** on `isrc` / `video_id` give idempotent upserts and free uniqueness.
- At larger scale: switch facts to **clustered columnstore** (Synapse), partition by
  `source` or load date, and distribute on `song_code` (hash) so per-song aggregation
  stays local to a node.
- Raw stays as **Parquet** in the lake for cheap reprocessing; only curated data lands
  in the warehouse.

## 3.5 Cost posture
- Lake storage is pennies; the warehouse is the main cost. For this volume (thousands
  of rows) **Azure SQL DB serverless** auto-pauses and is the cheapest fit; Synapse is
  reserved for when volume justifies it (millions+).
