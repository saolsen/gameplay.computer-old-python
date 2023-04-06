import pytest


def test_testing():
    assert True


def test_no_web():
    with pytest.raises(ImportError):
        import fastapi

        assert fastapi
