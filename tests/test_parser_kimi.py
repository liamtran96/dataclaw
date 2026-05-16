"""Direct tests for dataclaw.parsers.kimi project discovery and hashing."""

import pytest

from dataclaw.parsers.kimi import SOURCE, get_project_hash


class TestKimiProjectHash:
    def test_is_md5_hex_digest(self):
        h = get_project_hash("/home/user/project")
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_is_deterministic(self):
        assert get_project_hash("/foo") == get_project_hash("/foo")

    def test_different_cwds_differ(self):
        assert get_project_hash("/foo") != get_project_hash("/bar")


class TestKimiSource:
    def test_source_constant(self):
        assert SOURCE == "kimi"
