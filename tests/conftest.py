from __future__ import annotations

from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.fixture
def samples() -> Path:
    return SAMPLES
