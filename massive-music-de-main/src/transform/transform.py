"""Transformation layer (STAGING / Silver).

Flattens the nested raw API payloads into tabular candidate rows and applies
standardisation (via ``clean``). Deduplication and validation happen in the
quality layer, so this module stays a pure, side-effect-free mapping from raw
JSON to flat dicts.
"""
from __future__ import annotations

from typing import Dict, List

from . import clean


def build_dim_song(catalog: List[Dict[str, str]]) -> List[Dict]:
    """Build the song dimension from the internal catalogue."""
    rows = []
    for s in catalog:
        title_clean = clean.clean_title(s["song_title"])
        rows.append({
            "song_code": s["song_code"],
            "song_title": title_clean,
            "song_title_raw": s["song_title"],
            "original_artist": clean.normalize_text(s["original_artist"]),
            "artist_primary": clean.primary_artist(s["original_artist"]),
            "match_key": clean.match_key(s["song_title"]),
            "has_artist": 1 if s["original_artist"].strip() else 0,
        })
    return rows


def flatten_recordings(spotify_raw: List[Dict]) -> List[Dict]:
    """Flatten Spotify search responses into candidate recording rows."""
    rows = []
    for entry in spotify_raw:
        song_code = entry["song_code"]
        items = entry.get("response", {}).get("tracks", {}).get("items", [])
        for it in items:
            album = it.get("album", {}) or {}
            artists = it.get("artists", []) or []
            rows.append({
                "isrc": (it.get("external_ids", {}) or {}).get("isrc", ""),
                "song_code": song_code,
                "artist_name": clean.normalize_text(artists[0]["name"] if artists else ""),
                "recording_title": clean.clean_title(it.get("name", "")),
                "album": clean.normalize_text(album.get("name", "")),
                "release_date": (album.get("release_date") or "").strip(),
                "label": clean.normalize_text(album.get("label", "")),
                "source": "spotify",
            })
    return rows


def flatten_videos(youtube_raw: List[Dict]) -> List[Dict]:
    """Flatten YouTube search responses into candidate video rows."""
    rows = []
    for entry in youtube_raw:
        song_code = entry["song_code"]
        items = entry.get("response", {}).get("items", [])
        for it in items:
            vid = (it.get("id", {}) or {}).get("videoId", "")
            snip = it.get("snippet", {}) or {}
            rows.append({
                "video_id": (vid or "").strip(),
                "song_code": song_code,
                "channel_id": (snip.get("channelId") or "").strip(),
                "channel_title": clean.normalize_text(snip.get("channelTitle", "")),
                "video_title": clean.normalize_text(snip.get("title", "")),
                "source": "youtube",
            })
    return rows
