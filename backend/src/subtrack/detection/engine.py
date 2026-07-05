"""Subscription detection engine (architecture §2.4, §3.3).

Two phases:
  Phase 1 — heuristic: normalize merchant, group by merchant + amount cluster,
            analyze intervals against known cadences, score confidence.
  Phase 2 — AI-assisted: candidates below the confidence threshold are sent to
            the Claude API for structured classification (see detection/ai.py);
            a no-op when ANTHROPIC_API_KEY is unset.

Plaid amount convention: positive = money out (debit), so only amount > 0
transactions are considered.

User-set state is preserved: an existing DetectedSubscription with status
confirmed or dismissed keeps its status; only its data fields are refreshed.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.config import get_settings
from subtrack.db.models import Account, DetectedSubscription, Item, Transaction

_NORMALIZE_STRIP = re.compile(r"[0-9#*]+|\s{2,}")

# (name, expected gap in days, tolerance in days)
CADENCES: Sequence[Tuple[str, int, int]] = (
    ("weekly", 7, 2),
    ("biweekly", 14, 3),
    ("monthly", 30, 5),
    ("quarterly", 91, 10),
    ("yearly", 365, 20),
)

# Amounts within this relative tolerance are treated as the same charge
# (absorbs tax rounding and small price wobble, not tier changes).
AMOUNT_CLUSTER_TOLERANCE = 0.10


def normalize_merchant(raw: str) -> str:
    """Best-effort merchant normalization (e.g. 'NETFLIX.COM 8721938' -> 'netflix')."""
    cleaned = _NORMALIZE_STRIP.sub(" ", raw).strip().lower()
    return cleaned.split(".")[0].strip() if cleaned else cleaned


@dataclass
class Candidate:
    merchant_normalized: str
    account_id: Optional[int]
    amount: Decimal
    currency: Optional[str]
    cadence: str
    confidence: float
    next_expected_charge: Optional[date]
    # (posted_at ISO, amount as str) history for the AI pass
    history: List[Tuple[str, str]] = field(default_factory=list)
    source: str = "heuristic"  # heuristic | ai


def _match_cadence(gap_days: float) -> Optional[Tuple[str, int, int]]:
    for name, expected, tolerance in CADENCES:
        if abs(gap_days - expected) <= tolerance:
            return name, expected, tolerance
    return None


def _cluster_by_amount(txns: List[Transaction]) -> List[List[Transaction]]:
    """Greedy chaining of sorted amounts within the relative tolerance."""
    txns = sorted(txns, key=lambda t: t.amount)
    clusters: List[List[Transaction]] = []
    for txn in txns:
        if clusters and float(txn.amount) <= float(clusters[-1][-1].amount) * (
            1 + AMOUNT_CLUSTER_TOLERANCE
        ):
            clusters[-1].append(txn)
        else:
            clusters.append([txn])
    return clusters


def _analyze_group(merchant: str, txns: List[Transaction]) -> Optional[Candidate]:
    txns = sorted(txns, key=lambda t: t.posted_at)
    dates = [t.posted_at for t in txns]
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    if not gaps or any(g == 0 for g in gaps):
        # Same-day duplicates are not a cadence signal.
        return None

    median_gap = statistics.median(gaps)
    match = _match_cadence(median_gap)
    if match is None:
        return None
    cadence, _expected, tolerance = match

    consistency = sum(1 for g in gaps if abs(g - median_gap) <= tolerance) / len(gaps)
    if consistency < 0.6:
        return None

    # Confidence grows with interval consistency and evidence count, capped
    # below 1.0 so only user confirmation reaches full certainty.
    confidence = round(min(0.95, consistency * (0.5 + min(len(gaps), 5) * 0.09)), 2)

    median_amount = Decimal(
        str(statistics.median(float(t.amount) for t in txns))
    ).quantize(Decimal("0.01"))
    return Candidate(
        merchant_normalized=merchant,
        account_id=txns[-1].account_id,
        amount=median_amount,
        currency=txns[-1].currency,
        cadence=cadence,
        confidence=confidence,
        next_expected_charge=dates[-1] + timedelta(days=int(median_gap)),
        history=[(t.posted_at.isoformat(), str(t.amount)) for t in txns],
    )


def _heuristic_pass(txns: List[Transaction], min_occurrences: int) -> List[Candidate]:
    by_merchant: Dict[str, List[Transaction]] = {}
    for txn in txns:
        if txn.merchant_normalized:
            by_merchant.setdefault(txn.merchant_normalized, []).append(txn)

    candidates = []
    for merchant, group in by_merchant.items():
        for cluster in _cluster_by_amount(group):
            if len(cluster) < min_occurrences:
                continue
            candidate = _analyze_group(merchant, cluster)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def run_detection(session: Session, user_id: int) -> int:
    """Run detection for a user; returns the number of subscriptions upserted."""
    settings = get_settings()

    txns = list(
        session.scalars(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .join(Item, Account.item_id == Item.id)
            .where(
                Item.user_id == user_id,
                Transaction.removed.is_(False),
                Transaction.amount > 0,  # outflows only
            )
        )
    )

    # Preprocessing: fill merchant_normalized on rows that don't have it yet.
    for txn in txns:
        if not txn.merchant_normalized:
            txn.merchant_normalized = normalize_merchant(txn.merchant_raw)

    candidates = _heuristic_pass(txns, settings.detection_min_occurrences)

    # Phase 2: escalate low-confidence candidates to the AI pass. No-op
    # without an API key; never fails detection (ai.classify swallows errors).
    low_confidence = [
        c for c in candidates if c.confidence < settings.detection_confidence_threshold
    ]
    if low_confidence:
        from subtrack.detection.ai import classify_candidates

        verdicts = classify_candidates(low_confidence)
        kept: List[Candidate] = []
        for candidate in candidates:
            verdict = verdicts.get(candidate.merchant_normalized)
            if verdict is None:
                kept.append(candidate)
                continue
            if not verdict.is_recurring:
                continue  # AI rejected the candidate
            candidate.cadence = verdict.cadence or candidate.cadence
            candidate.confidence = verdict.confidence
            if verdict.clean_merchant_name:
                candidate.merchant_normalized = verdict.clean_merchant_name
            candidate.source = "ai"
            kept.append(candidate)
        candidates = kept

    written = 0
    for candidate in candidates:
        _upsert_subscription(session, user_id, candidate)
        written += 1
    session.flush()
    return written


def _upsert_subscription(session: Session, user_id: int, c: Candidate) -> None:
    existing = session.scalar(
        select(DetectedSubscription).where(
            DetectedSubscription.user_id == user_id,
            DetectedSubscription.merchant_normalized == c.merchant_normalized,
            DetectedSubscription.cadence == c.cadence,
        )
    )
    if existing is None:
        session.add(
            DetectedSubscription(
                user_id=user_id,
                account_id=c.account_id,
                merchant_normalized=c.merchant_normalized,
                amount=c.amount,
                currency=c.currency,
                cadence=c.cadence,
                confidence_score=c.confidence,
                status="detected",
                next_expected_charge=c.next_expected_charge,
                detection_source=c.source,
            )
        )
    else:
        # Refresh data fields but preserve user-set confirmed/dismissed status.
        existing.amount = c.amount
        existing.currency = c.currency
        existing.confidence_score = c.confidence
        existing.next_expected_charge = c.next_expected_charge
        existing.account_id = c.account_id
