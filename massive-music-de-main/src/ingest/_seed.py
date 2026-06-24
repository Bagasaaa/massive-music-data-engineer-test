"""Deterministic randomness helpers.

Real API calls are inherently non-deterministic, but for a reproducible mock we
derive a per-song ``random.Random`` instance from a stable hash of the song code
plus a namespace. The same song therefore always yields the same fake Spotify /
YouTube payload, so the pipeline output (and the answers to the two business
questions) is reproducible across runs and machines.
"""
from __future__ import annotations

import hashlib
import random


def seeded_rng(*parts: object) -> random.Random:
    """Return a ``random.Random`` seeded by a stable hash of ``parts``."""
    key = "|".join(str(p) for p in parts)
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return random.Random(int(digest, 16))
