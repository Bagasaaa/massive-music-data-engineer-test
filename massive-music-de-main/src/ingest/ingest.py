"""Ingestion layer (RAW / Bronze).

Reads the internal song catalogue (the Google Sheets export), calls the Spotify
and YouTube clients for every song, and persists the *raw, untransformed*
responses to ``data/raw/``. Persisting raw payloads first means we can replay
transformations without re-hitting the APIs — important for auditability and for
not burning YouTube quota on every code change.
"""
from __future__ import annotations

import csv
import json
import os
from typing import Dict, List

from .. import config
from . import mock_spotify_client, mock_youtube_client


def load_catalog(path: str = config.SEED_CATALOG) -> List[Dict[str, str]]:
    """Load the internal song catalogue CSV into a list of dicts."""
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [
            {
                "song_code": (r.get("song_code") or "").strip(),
                "original_artist": (r.get("original_artist") or "").strip(),
                "song_title": (r.get("song_title") or ""),
            }
            for r in reader
        ]
    return rows


def ingest_spotify(catalog: List[Dict[str, str]]) -> List[Dict]:
    """Call the (mock) Spotify API per song; tag each raw response with song_code."""
    raw = []
    for song in catalog:
        resp = mock_spotify_client.search_track(
            song["song_code"], song["song_title"], song["original_artist"]
        )
        raw.append({"song_code": song["song_code"], "response": resp})
    return raw


def ingest_youtube(catalog: List[Dict[str, str]]) -> List[Dict]:
    """Call the (mock) YouTube API per song; tag each raw response with song_code."""
    raw = []
    for song in catalog:
        resp = mock_youtube_client.search_videos(
            song["song_code"], song["song_title"], song["original_artist"]
        )
        raw.append({"song_code": song["song_code"], "response": resp})
    return raw


def _write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def run_ingestion() -> Dict:
    """Full ingestion: load catalogue, hit both sources, persist raw zone."""
    catalog = load_catalog()
    spotify_raw = ingest_spotify(catalog)
    youtube_raw = ingest_youtube(catalog)

    _write_json(config.SPOTIFY_RAW, spotify_raw)
    _write_json(config.YOUTUBE_RAW, youtube_raw)

    return {"catalog": catalog, "spotify_raw": spotify_raw, "youtube_raw": youtube_raw}
