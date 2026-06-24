"""Mock Spotify Web API client.

Mimics the subset of the Spotify ``GET /v1/search?type=track`` response that the
pipeline cares about. The shape mirrors the real API so that swapping in a real
``requests``-based client later only touches this file:

    {
      "tracks": {
        "items": [
          {
            "name": "<recording title>",
            "artists": [{"name": "<artist>"}],
            "album": {"name": "<album>", "release_date": "YYYY-MM-DD", "label": "<label>"},
            "external_ids": {"isrc": "<ISRC>"}
          },
          ...
        ]
      }
    }

A song (composition) maps to MANY recordings, each with its own ISRC — this is
the one-to-many relationship from the study case (a song covered by multiple
artists yields multiple ISRCs).

To exercise the data-quality layer the mock deliberately injects, for a small
deterministic fraction of songs:
  * duplicate ISRCs within the same response (API returns the same recording twice)
  * malformed ISRCs (wrong length / illegal characters)
  * an empty result set (song not found on Spotify)
"""
from __future__ import annotations

from typing import Dict, List

from ._seed import seeded_rng

# Realistic-looking ISRC country codes and labels for fabricated recordings.
_COUNTRIES = ["ID", "US", "GB", "QZ", "TC", "SE", "FR", "DE"]
_LABELS = [
    "Musica Studios", "Aquarius Musikindo", "Warner Music Indonesia",
    "Sony Music Indonesia", "Universal Music Indonesia", "Trinity Optima",
    "DKSI", "Independent",
]
_VERSION_SUFFIXES = [
    "", "", "", "",  # weight towards no suffix
    " (Acoustic Version)", " - Remastered", " (Live)", " (Radio Edit)",
]


def _make_isrc(rng, valid: bool = True) -> str:
    """Build an ISRC. Valid form: CC + 3 alnum registrant + 2-digit year + 5-digit code."""
    country = rng.choice(_COUNTRIES)
    registrant = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(3))
    year = f"{rng.randint(0, 25):02d}"
    designation = f"{rng.randint(0, 99999):05d}"
    isrc = f"{country}{registrant}{year}{designation}"
    if not valid:
        # Corrupt it in one of a few ways the validator must catch.
        mode = rng.choice(["short", "lower", "symbol"])
        if mode == "short":
            isrc = isrc[:9]
        elif mode == "lower":
            isrc = isrc.lower()
        else:
            isrc = isrc[:4] + "-" + isrc[5:]
    return isrc


def search_track(song_code: str, song_title: str, original_artist: str) -> Dict:
    """Return a mock Spotify search response for one catalogue song."""
    rng = seeded_rng("spotify", song_code)

    # Songs with a known artist are more likely to be found and to have more
    # recordings; blank-artist songs are sometimes not found at all.
    has_artist = bool(original_artist.strip())
    if not has_artist and rng.random() < 0.18:
        return {"tracks": {"items": []}}  # not found on Spotify

    n_recordings = rng.choices(
        population=[1, 2, 3, 4, 5],
        weights=[40, 25, 18, 12, 5] if has_artist else [60, 22, 10, 6, 2],
        k=1,
    )[0]

    base_artist = original_artist.strip() or song_title.split()[0].title()
    cover_artists = [
        base_artist, "Noah", "Andmesh", "Ruth Sahanaya", "Tulus", "Raisa",
        "Hindia", "Pamungkas", base_artist,
    ]

    items: List[Dict] = []
    for i in range(n_recordings):
        valid = not (rng.random() < 0.04)  # ~4% malformed ISRC
        isrc = _make_isrc(rng, valid=valid)
        artist = cover_artists[i % len(cover_artists)] if i else base_artist
        suffix = rng.choice(_VERSION_SUFFIXES)
        items.append({
            "name": f"{song_title}{suffix}",
            "artists": [{"name": artist}],
            "album": {
                "name": song_title if i == 0 else f"{song_title} - Single",
                "release_date": f"{rng.randint(1975, 2025)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                "label": rng.choice(_LABELS),
            },
            "external_ids": {"isrc": isrc},
        })

    # ~6% of responses duplicate a recording (dedup must collapse these).
    if items and rng.random() < 0.06:
        items.append(dict(items[0]))

    return {"tracks": {"items": items}}
