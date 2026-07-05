"""Phase-2 AI-assisted classification via the Claude API (architecture §2.4).

Low-confidence heuristic candidates are batched into a single structured-output
request. Graceful no-op when ANTHROPIC_API_KEY is unset; any API failure falls
back to the heuristic result (never fails detection).

Model comes from settings (ANTHROPIC_MODEL, default claude-opus-4-8); the
choice is architecture open question §6.5 and is overridable via env.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel

from subtrack.config import get_settings

if TYPE_CHECKING:
    from subtrack.detection.engine import Candidate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You classify candidate recurring payments detected in bank \
transaction data. For each candidate you receive the normalized merchant name \
and its (date, amount) charge history. Decide whether it is a genuine recurring \
subscription, its billing cadence, your confidence (0.0-1.0), and a clean \
human-readable merchant name (e.g. 'NETFLIX.COM 8721938' -> 'Netflix'). \
Cadence must be one of: weekly, biweekly, monthly, quarterly, yearly. \
Return a verdict for every candidate, keyed by the exact merchant string given."""


class Verdict(BaseModel):
    merchant: str
    is_recurring: bool
    cadence: Optional[str] = None
    confidence: float
    clean_merchant_name: Optional[str] = None


class VerdictList(BaseModel):
    verdicts: List[Verdict]


def classify_candidates(candidates: "List[Candidate]") -> Dict[str, Verdict]:
    """Classify candidates; returns verdicts keyed by merchant_normalized.

    Empty dict (leaving heuristic results untouched) when no API key is
    configured or the API call fails.
    """
    settings = get_settings()
    if not settings.anthropic_api_key or not candidates:
        return {}

    payload = [
        {
            "merchant": c.merchant_normalized,
            "history": [
                {"date": posted, "amount": amount} for posted, amount in c.history
            ],
        }
        for c in candidates
    ]

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.parse(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
            output_format=VerdictList,
        )
        parsed = response.parsed_output
        if parsed is None:
            return {}
        return {v.merchant: v for v in parsed.verdicts}
    except Exception:
        # AI pass is best-effort; heuristic results stand on any failure.
        logger.exception("AI classification pass failed; keeping heuristic results")
        return {}
