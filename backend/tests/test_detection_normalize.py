from __future__ import annotations

import pytest

from subtrack.detection.engine import normalize_merchant


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NETFLIX.COM 8721938", "netflix"),
        ("SPOTIFY P1234ABCD", "spotify p abcd"),  # crude for now; Phase 1 will refine
        ("Tim Hortons #1234", "tim hortons"),
        ("", ""),
    ],
)
def test_normalize_merchant(raw: str, expected: str) -> None:
    assert normalize_merchant(raw) == expected
