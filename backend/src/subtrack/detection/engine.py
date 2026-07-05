"""Subscription detection engine (architecture §2.4, §3.3).

Two phases:
  Phase 1 — heuristic: normalize merchant, group by merchant+amount, analyze
            intervals, score confidence.
  Phase 2 — AI-assisted: escalate low-confidence candidates to the Claude API
            (`anthropic` SDK, model from settings) for structured classification.

This is a scaffold: the algorithm is not implemented yet. `run_detection` is the
entry point the ingestion layer calls after a successful sync. It currently
returns 0 and must preserve any user-set confirmed/dismissed subscriptions when
implemented (do not overwrite them).
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

_NORMALIZE_STRIP = re.compile(r"[0-9#*]+|\s{2,}")


def normalize_merchant(raw: str) -> str:
    """Best-effort merchant normalization (e.g. 'NETFLIX.COM 8721938' -> 'netflix')."""
    cleaned = _NORMALIZE_STRIP.sub(" ", raw).strip().lower()
    return cleaned.split(".")[0].strip() if cleaned else cleaned


def run_detection(session: Session, user_id: int) -> int:
    """Run detection for a user. Returns the number of subscriptions written.

    TODO(Phase 1): heuristic grouping + interval analysis -> candidates.
    TODO(Phase 2): escalate low-confidence candidates to the Claude API.
    """
    raise NotImplementedError("Detection engine not implemented yet (scaffold).")
