"""Direct tests for dataclaw._workers worker count resolution."""

import pytest

from dataclaw._workers import DATACLAW_WORKERS_ENV, configured_workers


class TestConfiguredWorkers:
    def test_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv(DATACLAW_WORKERS_ENV, raising=False)
        assert configured_workers() is None

    def test_empty_string_returns_none(self, monkeypatch):
        monkeypatch.setenv(DATACLAW_WORKERS_ENV, "")
        assert configured_workers() is None

    def test_valid_int_returns_int(self, monkeypatch):
        monkeypatch.setenv(DATACLAW_WORKERS_ENV, "4")
        assert configured_workers() == 4

    def test_invalid_string_returns_none(self, monkeypatch):
        monkeypatch.setenv(DATACLAW_WORKERS_ENV, "not-a-number")
        assert configured_workers() is None

    def test_negative_int_returns_negative_int(self, monkeypatch):
        # configured_workers is a literal parser; sanity-check that it returns whatever int it parses.
        monkeypatch.setenv(DATACLAW_WORKERS_ENV, "-1")
        assert configured_workers() == -1
