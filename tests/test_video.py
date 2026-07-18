import os
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _replicate() -> Any:
    replicate = pytest.importorskip("replicate")
    if not os.getenv("REPLICATE_API_TOKEN", "").strip():
        pytest.skip("REPLICATE_API_TOKEN is not configured")
    return replicate


def test_replicate_initialization() -> None:
    replicate = _replicate()
    assert replicate is not None


def test_replicate_account_is_reachable() -> None:
    replicate = _replicate()
    model = replicate.models.get("stability-ai/stable-diffusion")
    assert model is not None
