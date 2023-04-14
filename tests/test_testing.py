import os

import pytest


@pytest.mark.skipif(
    not os.getenv("GITHUB_ACTIONS"),
    reason="Only run in CI. Locally you'll have all deps so this will fail.",
)
def test_no_web() -> None:
    with pytest.raises(ImportError):
        import fastapi

        assert fastapi
