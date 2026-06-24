"""Data-quality layer.

Validates candidate rows, deduplicates valid rows by primary key, and routes
rejected rows to a quarantine list with a human-readable reason instead of
silently dropping them. Returns a structured result the loader and the run
report consume.

Checks implemented:
  * not-null on primary / foreign keys (song_code, isrc, video_id)
  * ISRC format        -> ^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$  (12 chars)
  * referential integrity -> song_code must exist in the song dimension
  * uniqueness         -> dedup by PK, duplicates counted (not an error)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$")


@dataclass
class ValidationResult:
    valid: List[Dict] = field(default_factory=list)
    quarantine: List[Dict] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


def _quarantine(row: Dict, reason: str) -> Dict:
    q = dict(row)
    q["dq_reason"] = reason
    return q


def validate_recordings(rows: List[Dict], valid_song_codes: Set[str]) -> ValidationResult:
    res = ValidationResult()
    seen_isrc: Set[str] = set()
    dup = 0
    for row in rows:
        isrc = (row.get("isrc") or "").strip()
        if not isrc:
            res.quarantine.append(_quarantine(row, "missing_isrc"))
            continue
        if not ISRC_RE.match(isrc):
            res.quarantine.append(_quarantine(row, "invalid_isrc_format"))
            continue
        if row.get("song_code") not in valid_song_codes:
            res.quarantine.append(_quarantine(row, "orphan_song_code"))
            continue
        if isrc in seen_isrc:
            dup += 1
            continue
        seen_isrc.add(isrc)
        res.valid.append(row)

    res.stats = {
        "input": len(rows),
        "valid": len(res.valid),
        "duplicates_removed": dup,
        "quarantined": len(res.quarantine),
    }
    return res


def validate_videos(rows: List[Dict], valid_song_codes: Set[str]) -> ValidationResult:
    res = ValidationResult()
    seen_vid: Set[str] = set()
    dup = 0
    for row in rows:
        vid = (row.get("video_id") or "").strip()
        if not vid:
            res.quarantine.append(_quarantine(row, "missing_video_id"))
            continue
        if row.get("song_code") not in valid_song_codes:
            res.quarantine.append(_quarantine(row, "orphan_song_code"))
            continue
        if vid in seen_vid:
            dup += 1
            continue
        seen_vid.add(vid)
        res.valid.append(row)

    res.stats = {
        "input": len(rows),
        "valid": len(res.valid),
        "duplicates_removed": dup,
        "quarantined": len(res.quarantine),
    }
    return res


def anomaly_checks(report: Dict) -> List[str]:
    """Lightweight anomaly detection over the run's aggregate numbers.

    Returns a list of warnings (empty == healthy). In production these thresholds
    would compare against a rolling historical baseline and raise alerts.
    """
    warnings: List[str] = []
    rec = report.get("recordings", {})
    vid = report.get("videos", {})

    def rate(part, whole):
        return (part / whole) if whole else 0.0

    if rate(rec.get("quarantined", 0), rec.get("input", 0)) > 0.10:
        warnings.append("Recording quarantine rate >10% — possible source/format drift.")
    if rate(vid.get("quarantined", 0), vid.get("input", 0)) > 0.10:
        warnings.append("Video quarantine rate >10% — possible source/format drift.")
    if report.get("songs_loaded", 0) == 0:
        warnings.append("Zero songs loaded — catalogue ingestion likely failed.")
    return warnings
