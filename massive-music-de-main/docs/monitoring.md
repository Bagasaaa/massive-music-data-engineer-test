# 4. Pipeline Monitoring & Maintenance Plan

## 4.1 What we monitor

| Dimension | Signal | Source in this repo | Production tool |
|-----------|--------|---------------------|-----------------|
| **Reliability** | run status (SUCCESS / WARN / FAIL), per-stage row counts | `pipeline_run_log` table | ADF run history + Azure Monitor |
| **Performance** | stage duration, rows/sec, API latency | (extend run log with timings) | ADF metrics, Log Analytics |
| **Data quality** | quarantine rate, dedup rate, % songs with 0 results | `pipeline_run_log` + `quarantine_*` | Great Expectations data docs |
| **Freshness** | last successful `run_date` vs SLA | `pipeline_run_log.run_date` | Azure Monitor alert |
| **API quota** | YouTube units consumed / 10k daily cap | counter around the client | custom metric + alert at 80% |

Every run writes one row to `pipeline_run_log` with songs loaded, valid/dup/quarantine
counts per source, warnings and status — the table any dashboard or alert reads.

## 4.2 Error management
- **Retries with exponential backoff** on transient API errors (429/5xx). On 429
  (quota), pause and resume next window rather than fail the whole run.
- **Quarantine, don't crash:** a malformed record never aborts the batch; it is parked
  in `quarantine_*` with a reason for later triage/replay.
- **Idempotent upserts:** a failed run can be safely re-run from the start (verified:
  consecutive runs are stable at 699 / 1266 / 2079).
- **Alerting:** on FAIL or on a DQ threshold breach (e.g. quarantine rate >10%, or 0
  rows loaded), Azure Monitor raises an alert (email/Teams).

## 4.3 Maintenance processes
- **Schema-change resilience:** API response parsing is isolated in the client +
  `transform` modules; a Spotify/YouTube field change is a one-file fix. A schema
  contract check fails fast if shapes drift.
- **Re-matching unmatched songs:** the 82 songs with 0 ISRC / 61 with 0 video are a
  backlog; a periodic job retries them (better query, alternate title, fuzzy match)
  and the manual-review queue handles low-confidence matches.
- **Backfill:** because Raw is immutable and loads are idempotent, we can reprocess any
  historical window by replaying the lake — no API calls needed.
- **Secret rotation:** API keys live in Key Vault and are rotated on schedule.
- **Cost & quota review:** monthly check of warehouse spend and YouTube quota
  utilisation; tune incremental scope (only changed `song_code`s) accordingly.

## 4.4 Operational runbook (summary)
| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Status FAIL, 0 songs | catalogue source unavailable | check Sheets/Lake connectivity; re-run |
| Quarantine rate spike | API schema change / encoding issue | inspect `quarantine_*`; patch parser |
| YouTube 429 storm | quota exhausted | resume next quota window; request increase |
| Stale freshness | trigger missed | check ADF schedule; manual trigger |
| Duplicate counts off | dedup key wrong | confirm PKs (`isrc`, `video_id`) intact |
