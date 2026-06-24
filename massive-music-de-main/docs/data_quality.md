# 2. Data Quality & Validation Strategy

The catalogue is messy real-world data. This section describes the concrete issues,
the checks that catch them, and how anomalies/corruption are managed. All checks are
implemented in `src/transform/clean.py` (standardisation) and
`src/quality/validators.py` (validation, dedup, quarantine).

## 2.1 Issues observed in the source catalogue

| Issue | Example (real rows) | Handling |
|-------|--------------------|----------|
| Missing artist | 279 *BE FREE*, 18185 *THE GUIDING LIGHTS* (≈ half of catalogue) | match on title only; flag `has_artist=0`; lower match confidence |
| Invisible/zero-width chars | 14522 `⁠SEROTONIN 6 AM` (U+2060 prefix) | `strip_invisible` + NFKC normalise |
| Version/feature noise | 13719 *WARTEG (WARGA TEGAR)*, 12493 *LET ME (FEAT. RIFKA RACHMAN)* | strip parentheticals into `match_key` |
| Multi-language alternates | 11479 *PUJA PAU SEN TA TI / PAU SEN TA TI SUNG KE* | `split_title_alternates` on ` / ` |
| Multi-artist strings | 3827 *... FEAT TEZA SUMENDRA*, 4729 *... & BRIGITTA TIFANNY*, 15645 comma-separated | `parse_artists` (feat/ft/&/,/x) |
| Duplicate titles ≠ duplicate songs | *AMPUNI AKU* (4580, 3459); *DOA*; *BUNGA* | dedup on `song_code`, never on title |

## 2.2 Validation checks (serving layer gate)

| Check | Rule | On failure |
|-------|------|-----------|
| Not-null keys | `song_code`, `isrc`, `video_id` must be present | quarantine |
| ISRC format | `^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$` (12 chars) | quarantine (`invalid_isrc_format`) |
| Referential integrity | fact `song_code` must exist in `dim_song` | quarantine (`orphan_song_code`) |
| Uniqueness | dedup by PK (`isrc` / `video_id`) | duplicate dropped, **counted** |

## 2.3 Deduplication
- **Recordings:** unique by `isrc`. API pagination/overlap can return the same
  recording twice — collapsed on load. *(Demo run: 23 duplicate recordings removed.)*
- **Videos:** unique by `video_id`. *(Demo run: 40 duplicate videos removed.)*
- **Songs:** unique by `song_code` (catalogue PK).

## 2.4 Handling missing / inconsistent data
- Songs not found on a platform legitimately get **count = 0** (demo: 82 songs with
  0 ISRC, 61 with 0 video) — they remain in `dim_song` via a `LEFT JOIN`, so "no data"
  is visible rather than silently absent.
- Bad rows are **quarantined, not dropped**: `quarantine_recording` /
  `quarantine_video` store the offending payload + reason + run_date for triage and
  potential re-processing. *(Demo run: 57 bad ISRCs, 22 missing video ids.)*

## 2.5 Corruption / anomaly detection (`anomaly_checks`)
Run-level guards compare aggregate numbers against expectations:
- **Quarantine-rate threshold** (>10% per source) → warns of schema/format drift.
- **Zero-rows guard** → catches a failed catalogue ingest.
- **Idempotency** → upserts mean a re-run is safe and self-healing.

In production these thresholds compare against a **rolling historical baseline**
(e.g. "today's video count is within ±3σ of the 30-day mean") and raise alerts
rather than just print warnings.

## 2.6 Production hardening (roadmap)
- Replace bespoke checks with a **Great Expectations** suite versioned in git, run as
  an ADF activity that fails the pipeline on breach.
- **Schema contract** on the API responses (fail fast if Spotify/YouTube change shape).
- **Fuzzy matching confidence score** (token-set ratio on `match_key` + artist) with a
  manual-review queue for low-confidence matches — the biggest accuracy lever given
  the high rate of missing artists.
