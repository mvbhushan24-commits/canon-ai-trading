"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def sample_symbol() -> str:
    return "XAUUSD"
