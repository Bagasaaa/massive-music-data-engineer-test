"""Standardisation / cleaning helpers (pure functions, easy to unit-test).

These encode the concrete data-quality issues we found in the real catalogue:
  * invisible / zero-width characters (e.g. U+2060 before "SEROTONIN 6 AM")
  * inconsistent whitespace and casing
  * version / feature noise in titles  -> "WARTEG (WARGA TEGAR)", "(FEAT. ...)"
  * multi-language alternates split by " / "
  * multi-artist strings joined by feat / ft / & / "," / " x "
"""
from __future__ import annotations

import re
import unicodedata
from typing import List

# Zero-width / invisible code points seen in real-world spreadsheet exports.
_INVISIBLE = dict.fromkeys(
    map(ord, ["​", "‌", "‍", "⁠", "﻿", " ", "᠎"]),
    None,
)

_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")      # (...) or [...]
_FEAT_RE = re.compile(r"\s*[-/|]\s*$")                  # trailing separators
_ARTIST_SPLIT_RE = re.compile(
    r"\s*(?:\bfeat\.?\b|\bft\.?\b|\bfeaturing\b|&|,|\bx\b)\s*",
    flags=re.IGNORECASE,
)


def strip_invisible(text: str) -> str:
    """Remove zero-width / non-breaking characters."""
    return (text or "").translate(_INVISIBLE)


def normalize_text(text: str) -> str:
    """NFKC-normalise, drop invisibles, collapse whitespace, trim."""
    text = unicodedata.normalize("NFKC", text or "")
    text = strip_invisible(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_title(raw_title: str) -> str:
    """Human-facing cleaned title (keeps real casing & meaningful punctuation)."""
    return normalize_text(raw_title)


def match_key(title: str) -> str:
    """Aggressive normalised key used ONLY for fuzzy matching / grouping.

    Lower-cased, parentheticals removed, punctuation stripped. Never displayed.
    """
    t = normalize_text(title).lower()
    t = _PAREN_RE.sub("", t)
    t = _FEAT_RE.sub("", t)
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_title_alternates(raw_title: str) -> List[str]:
    """Split multi-language alternates joined by ' / ' into separate strings."""
    cleaned = normalize_text(raw_title)
    parts = [p.strip() for p in cleaned.split(" / ") if p.strip()]
    return parts or [cleaned]


def parse_artists(raw_artist: str) -> List[str]:
    """Split a multi-artist string into individual normalised artist names."""
    cleaned = normalize_text(raw_artist)
    if not cleaned:
        return []
    parts = [p.strip() for p in _ARTIST_SPLIT_RE.split(cleaned) if p.strip()]
    # De-dup while preserving order.
    seen, out = set(), []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def primary_artist(raw_artist: str) -> str:
    """First / lead artist, or empty string when unknown."""
    artists = parse_artists(raw_artist)
    return artists[0] if artists else ""
