"""Mock YouTube Data API v3 client.

Mimics the subset of ``GET /youtube/v3/search`` (+ a touch of ``videos.list``)
that the pipeline needs. Shape mirrors the real API:

    {
      "items": [
        {
          "id": {"videoId": "<11-char id>"},
          "snippet": {
            "channelId": "UC...",
            "channelTitle": "<channel>",
            "title": "<video title>"
          }
        },
        ...
      ]
    }

A song maps to MANY videos (official MV, lyric video, covers, live, reactions).
The number of videos per song is what answers business question #1.

Deliberately injected data-quality issues for a deterministic fraction of songs:
  * duplicate videoIds (search pagination returning the same video)
  * a missing/empty videoId (corrupt record the validator must quarantine)
  * zero results (song has no video presence)
"""
from __future__ import annotations

from typing import Dict, List

from ._seed import seeded_rng

_VIDEO_KINDS = [
    "Official Music Video", "Official Lyric Video", "(Official Audio)",
    "Live at Synchronize Fest", "Cover", "Lyrics", "Reaction", "Acoustic Session",
]
_ID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _make_video_id(rng) -> str:
    return "".join(rng.choice(_ID_CHARS) for _ in range(11))


def _make_channel_id(rng) -> str:
    return "UC" + "".join(rng.choice(_ID_CHARS) for _ in range(22))


def search_videos(song_code: str, song_title: str, original_artist: str) -> Dict:
    """Return a mock YouTube search response for one catalogue song."""
    rng = seeded_rng("youtube", song_code)

    has_artist = bool(original_artist.strip())
    if rng.random() < (0.05 if has_artist else 0.12):
        return {"items": []}  # no videos found

    n_videos = rng.choices(
        population=[1, 2, 3, 5, 8, 12],
        weights=[18, 22, 25, 18, 12, 5] if has_artist else [40, 25, 18, 10, 5, 2],
        k=1,
    )[0]

    artist = original_artist.strip() or "Various Artists"
    items: List[Dict] = []
    for _ in range(n_videos):
        kind = rng.choice(_VIDEO_KINDS)
        items.append({
            "id": {"videoId": _make_video_id(rng)},
            "snippet": {
                "channelId": _make_channel_id(rng),
                "channelTitle": rng.choice([artist, f"{artist} Official", "MyMusic Records", "Trinity"]),
                "title": f"{artist} - {song_title} | {kind}",
            },
        })

    # ~7% duplicate a video (pagination overlap) -> dedup must collapse.
    if items and rng.random() < 0.07:
        items.append(dict(items[0]))

    # ~3% inject a corrupt record with an empty videoId -> must be quarantined.
    if rng.random() < 0.03:
        items.append({
            "id": {"videoId": ""},
            "snippet": {"channelId": "", "channelTitle": "", "title": f"{artist} - {song_title}"},
        })

    return {"items": items}
