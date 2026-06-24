# Entity Relationship Diagram (ERD)

The model follows the study-case definition: a **Song** (composition) has many
**Recordings** (each uniquely identified by an **ISRC**), and many **Videos** on
YouTube. Both are one-to-many from the song.

```mermaid
erDiagram
    DIM_SONG ||--o{ FACT_RECORDING : "has (1:N)"
    DIM_SONG ||--o{ FACT_VIDEO     : "has (1:N)"

    DIM_SONG {
        TEXT    song_code PK
        TEXT    song_title
        TEXT    song_title_raw
        TEXT    original_artist
        TEXT    artist_primary
        TEXT    match_key
        INTEGER has_artist
    }

    FACT_RECORDING {
        TEXT isrc PK
        TEXT song_code FK
        TEXT artist_name
        TEXT recording_title
        TEXT album
        TEXT release_date
        TEXT label
        TEXT source
    }

    FACT_VIDEO {
        TEXT video_id PK
        TEXT song_code FK
        TEXT channel_id
        TEXT channel_title
        TEXT video_title
        TEXT source
    }
```

## Supporting (operational) tables

```mermaid
erDiagram
    QUARANTINE_RECORDING {
        TEXT song_code
        TEXT isrc
        TEXT payload
        TEXT dq_reason
        TEXT run_date
    }
    QUARANTINE_VIDEO {
        TEXT song_code
        TEXT video_id
        TEXT payload
        TEXT dq_reason
        TEXT run_date
    }
    PIPELINE_RUN_LOG {
        TEXT    run_date
        INTEGER songs_loaded
        INTEGER recordings_valid
        INTEGER videos_valid
        INTEGER recordings_quarantined
        INTEGER videos_quarantined
        TEXT    status
    }
```

## Marts (views) on top of the model

| View | Answers | Grain |
|------|---------|-------|
| `mart_song_isrc_count`  | ISRCs per song (Spotify)  | one row per song |
| `mart_song_video_count` | Videos per song (YouTube) | one row per song |
| `mart_song_overview`    | both, side by side        | one row per song |

### Why this shape
- **`song_code` is the join key**, never the title. The catalogue contains the same
  title for different compositions (e.g. *AMPUNI AKU* appears under codes `4580` and
  `3459`; *DOA*, *BUNGA*, *SELAMAT TINGGAL*, *HUJAN* repeat too). Deduplicating on
  title would wrongly merge distinct songs.
- **ISRC and video_id are natural primary keys** — they guarantee idempotent upserts
  and make "count distinct" trivially correct.
- A star schema (one dimension, two fact tables) keeps the two business aggregations
  as simple, index-friendly `GROUP BY song_code` queries that port directly to a
  columnar warehouse.
