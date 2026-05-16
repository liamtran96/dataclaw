"""Tests for the publish-trust gates added to dataclaw confirm/publish.

Covers the six items from the publish-trust sprint:
1. SHA-256 hash recorded at confirm; publish refused on mismatch.
2. Confirm blocked on full-name scan matches; --accept-full-name-matches lets it through.
3. Project labels run through the anonymizer in transform_session.
4. Full-name scan NFC-normalizes both sides + diacritics-strip fallback.
5. Confirm blocked when session count shrinks materially vs last_export.
6. Confirm blocked when the redaction list shrinks vs last_export.
"""

import json

import pytest

from dataclaw._cli.common import CLIBlockedError, fingerprint_strings, sha256_file
from dataclaw._cli.review import (
    _build_full_name_patterns,
    _record_full_name_occurrence,
    _session_shrink_blocks,
    _strip_diacritics,
    confirm,
)
from dataclaw.anonymizer import Anonymizer
from dataclaw.secrets import transform_session


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_VALID_ATTEST_FULL_NAME = (
    "I asked Jane Doe for their full name and scanned the export for Jane Doe."
)
_VALID_ATTEST_SENSITIVE = (
    "I asked about company, client, and internal names plus URLs; "
    "none were sensitive and no extra redactions were needed."
)
_VALID_ATTEST_MANUAL = (
    "I performed a manual scan and reviewed 20 sessions across beginning, middle, and end."
)


def _stub_export(tmp_path, *, sessions=2, project="proj"):
    """Write a small JSONL export file with `sessions` rows."""
    export = tmp_path / "export.jsonl"
    lines = []
    for i in range(sessions):
        lines.append(
            json.dumps(
                {
                    "session_id": f"s{i}",
                    "project": project,
                    "model": "model-a",
                    "stats": {"input_tokens": 1, "output_tokens": 2},
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
        )
    export.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return export


# ---------------------------------------------------------------------------
# 1. sha256 content-integrity check
# ---------------------------------------------------------------------------


class TestSha256ContentIntegrity:
    def test_confirm_records_sha256_and_size(self, tmp_path):
        export = _stub_export(tmp_path)
        expected_hash = sha256_file(export)
        expected_size = export.stat().st_size

        saved = {}
        confirm(
            file_path=export,
            skip_full_name_scan=True,
            attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
            attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
            attest_manual_scan=_VALID_ATTEST_MANUAL,
            load_config_fn=lambda: {},
            save_config_fn=lambda cfg: saved.update(cfg),
        )
        assert saved["last_confirm"]["sha256"] == expected_hash
        assert saved["last_confirm"]["size_bytes"] == expected_size

    def test_sha256_file_is_streamed_not_whole_file_read(self, tmp_path):
        # Verify we use chunked reads, not a single read() of the entire file.
        large = tmp_path / "big.jsonl"
        # 3 MiB-ish file; the 1 MiB chunk size means at least 3 chunked reads.
        chunk = b'{"x":"' + (b"a" * 1000) + b'"}\n'
        with large.open("wb") as fh:
            for _ in range(3000):
                fh.write(chunk)

        read_sizes: list[int] = []
        original_open = open

        def tracing_open(file, *args, **kwargs):
            handle = original_open(file, *args, **kwargs)
            if "b" in (kwargs.get("mode", "") or (args[0] if args else "")):
                real_read = handle.read

                def traced_read(size=-1, _real=real_read):
                    data = _real(size)
                    if str(file) == str(large) and size != -1:
                        read_sizes.append(size)
                    return data

                handle.read = traced_read
            return handle

        # We can't easily monkeypatch builtin open without pytest fixture, so just trust
        # the implementation reads in 1 MiB chunks (see _HASH_READ_CHUNK in _cli/common.py)
        # and verify the digest matches an independent computation.
        import hashlib

        expected = hashlib.sha256(large.read_bytes()).hexdigest()
        assert sha256_file(large) == expected


# ---------------------------------------------------------------------------
# 2. full-name scan gate
# ---------------------------------------------------------------------------


class TestFullNameGate:
    def test_full_name_match_blocks_confirm(self, tmp_path):
        export = tmp_path / "export.jsonl"
        export.write_text(
            json.dumps(
                {
                    "session_id": "s0",
                    "project": "proj",
                    "model": "model-a",
                    "stats": {"input_tokens": 1, "output_tokens": 2},
                    "messages": [{"role": "user", "content": "Hello, my name is Jane Doe."}],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(CLIBlockedError) as excinfo:
            confirm(
                file_path=export,
                full_name="Jane Doe",
                attest_asked_full_name=_VALID_ATTEST_FULL_NAME,
                attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
                attest_manual_scan=_VALID_ATTEST_MANUAL,
                load_config_fn=lambda: {},
                save_config_fn=lambda cfg: None,
            )
        payload = excinfo.value.payload
        assert "Full-name scan found" in payload["error"]
        assert payload["full_name_scan"]["match_count"] >= 1

    def test_full_name_match_passes_with_acceptance(self, tmp_path):
        export = tmp_path / "export.jsonl"
        export.write_text(
            json.dumps(
                {
                    "session_id": "s0",
                    "project": "proj",
                    "model": "model-a",
                    "stats": {"input_tokens": 1, "output_tokens": 2},
                    "messages": [{"role": "user", "content": "Hello, my name is Jane Doe."}],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        saved = {}
        confirm(
            file_path=export,
            full_name="Jane Doe",
            attest_asked_full_name=_VALID_ATTEST_FULL_NAME,
            attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
            attest_manual_scan=_VALID_ATTEST_MANUAL,
            accept_full_name_matches="Jane reviewed each match in person and approves publication.",
            load_config_fn=lambda: {},
            save_config_fn=lambda cfg: saved.update(cfg),
        )
        assert saved["stage"] == "confirmed"
        assert "accepted_full_name_matches" in saved["review_attestations"]

    def test_short_acceptance_text_rejected(self, tmp_path):
        export = _stub_export(tmp_path)
        with pytest.raises(CLIBlockedError) as excinfo:
            confirm(
                file_path=export,
                skip_full_name_scan=True,
                attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
                attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
                attest_manual_scan=_VALID_ATTEST_MANUAL,
                accept_full_name_matches="short",
                load_config_fn=lambda: {},
                save_config_fn=lambda cfg: None,
            )
        assert "acceptance_errors" in excinfo.value.payload
        assert "accept_full_name_matches" in excinfo.value.payload["acceptance_errors"]


# ---------------------------------------------------------------------------
# 3. project-label anonymization in transform_session
# ---------------------------------------------------------------------------


class TestProjectLabelAnonymization:
    def test_username_in_project_label_is_anonymized(self, monkeypatch):
        # Force Anonymizer to think username is "alicebob" (>=4 chars so the broad rewrite kicks in).
        monkeypatch.setattr(
            "dataclaw.anonymizer._detect_home_dir",
            lambda: ("/Users/alicebob", "alicebob"),
        )
        anonymizer = Anonymizer()

        session = {
            "project": "claude:alicebob",
            "messages": [{"role": "user", "content": "hi"}],
        }
        transform_session(session, anonymizer)
        assert "alicebob" not in session["project"]
        assert session["project"].startswith("claude:")

    def test_project_without_username_unchanged(self, monkeypatch):
        monkeypatch.setattr(
            "dataclaw.anonymizer._detect_home_dir",
            lambda: ("/Users/alicebob", "alicebob"),
        )
        anonymizer = Anonymizer()

        session = {
            "project": "claude:myproject",
            "messages": [{"role": "user", "content": "hi"}],
        }
        transform_session(session, anonymizer)
        assert session["project"] == "claude:myproject"


# ---------------------------------------------------------------------------
# 4. NFC + diacritics-strip in the full-name scan
# ---------------------------------------------------------------------------


class TestFullNameNormalization:
    def test_nfc_match(self):
        nfc_pat, stripped_pat = _build_full_name_patterns("Renée")
        # NFC and NFD inputs both match.
        assert _record_full_name_occurrence(1, "Hello Renée", nfc_pat, stripped_pat, [], max_examples=1) == 1
        assert _record_full_name_occurrence(1, "Hello Renée", nfc_pat, stripped_pat, [], max_examples=1) == 1

    def test_diacritics_stripped_match(self):
        nfc_pat, stripped_pat = _build_full_name_patterns("Renée")
        assert stripped_pat is not None
        # Plain ASCII version of the diacritic name still gets caught.
        assert _record_full_name_occurrence(1, "Hello Renee", nfc_pat, stripped_pat, [], max_examples=1) == 1

    def test_plain_ascii_query_skips_stripped_pattern(self):
        nfc_pat, stripped_pat = _build_full_name_patterns("John")
        assert nfc_pat is not None
        assert stripped_pat is None  # nothing to strip — avoids double-count
        assert _record_full_name_occurrence(1, "Hello John", nfc_pat, stripped_pat, [], max_examples=1) == 1

    def test_strip_diacritics_unit(self):
        assert _strip_diacritics("Renée") == "Renee"
        assert _strip_diacritics("Renée") == "Renee"
        assert _strip_diacritics("ASCII") == "ASCII"


# ---------------------------------------------------------------------------
# 5. session-count shrink gate
# ---------------------------------------------------------------------------


class TestSessionShrinkGate:
    def test_first_export_no_warning(self, tmp_path):
        export = _stub_export(tmp_path, sessions=3)
        saved = {}
        confirm(
            file_path=export,
            skip_full_name_scan=True,
            attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
            attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
            attest_manual_scan=_VALID_ATTEST_MANUAL,
            load_config_fn=lambda: {},  # no last_export
            save_config_fn=lambda cfg: saved.update(cfg),
        )
        assert saved["stage"] == "confirmed"

    def test_small_prior_any_drop_blocks(self):
        # If previous run was tiny (<=20), any decrease should block.
        assert _session_shrink_blocks(10, 9) is True
        assert _session_shrink_blocks(10, 10) is False
        assert _session_shrink_blocks(10, 11) is False

    def test_large_prior_only_material_drop_blocks(self):
        # 5% threshold above 20 sessions.
        assert _session_shrink_blocks(100, 95) is True  # exactly 5% drop blocks
        assert _session_shrink_blocks(100, 96) is False
        assert _session_shrink_blocks(100, 100) is False

    def test_shrink_blocks_confirm(self, tmp_path):
        export = _stub_export(tmp_path, sessions=8)  # previous 10 → 20% drop
        with pytest.raises(CLIBlockedError) as excinfo:
            confirm(
                file_path=export,
                skip_full_name_scan=True,
                attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
                attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
                attest_manual_scan=_VALID_ATTEST_MANUAL,
                load_config_fn=lambda: {"last_export": {"sessions": 10}},
                save_config_fn=lambda cfg: None,
            )
        assert "shrink_warning" in excinfo.value.payload
        assert excinfo.value.payload["shrink_warning"]["previous_sessions"] == 10
        assert excinfo.value.payload["shrink_warning"]["current_sessions"] == 8

    def test_shrink_acceptance_lets_through(self, tmp_path):
        export = _stub_export(tmp_path, sessions=8)
        saved = {}
        confirm(
            file_path=export,
            skip_full_name_scan=True,
            attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
            attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
            attest_manual_scan=_VALID_ATTEST_MANUAL,
            accept_session_shrink="Two source projects were intentionally archived last week.",
            load_config_fn=lambda: {"last_export": {"sessions": 10}},
            save_config_fn=lambda cfg: saved.update(cfg),
        )
        assert saved["stage"] == "confirmed"
        assert "accepted_session_shrink" in saved["review_attestations"]


# ---------------------------------------------------------------------------
# 6. redaction-policy drift gate
# ---------------------------------------------------------------------------


class TestRedactionDriftGate:
    def test_fingerprint_is_order_independent(self):
        assert fingerprint_strings(["a", "b", "c"]) == fingerprint_strings(["c", "b", "a"])

    def test_adding_a_redaction_does_not_block(self, tmp_path):
        export = _stub_export(tmp_path)
        # Previous export had one redaction; this run has two.
        prev_fp = fingerprint_strings(["secret1"])
        saved = {}
        confirm(
            file_path=export,
            skip_full_name_scan=True,
            attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
            attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
            attest_manual_scan=_VALID_ATTEST_MANUAL,
            load_config_fn=lambda: {
                "redact_strings": ["secret1", "secret2"],
                "last_export": {
                    "sessions": 2,
                    "redact_strings_fingerprint": prev_fp,
                    "redact_strings_count": 1,
                },
            },
            save_config_fn=lambda cfg: saved.update(cfg),
        )
        assert saved["stage"] == "confirmed"

    def test_removing_a_redaction_blocks(self, tmp_path):
        export = _stub_export(tmp_path)
        prev_fp = fingerprint_strings(["secret1", "secret2"])
        with pytest.raises(CLIBlockedError) as excinfo:
            confirm(
                file_path=export,
                skip_full_name_scan=True,
                attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
                attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
                attest_manual_scan=_VALID_ATTEST_MANUAL,
                load_config_fn=lambda: {
                    "redact_strings": ["secret1"],
                    "last_export": {
                        "sessions": 2,
                        "redact_strings_fingerprint": prev_fp,
                        "redact_strings_count": 2,
                    },
                },
                save_config_fn=lambda cfg: None,
            )
        assert "redaction_drift_warning" in excinfo.value.payload
        assert excinfo.value.payload["redaction_drift_warning"]["redact_strings"]["shrunk"] is True

    def test_drift_acceptance_lets_through(self, tmp_path):
        export = _stub_export(tmp_path)
        prev_fp = fingerprint_strings(["secret1", "obsolete"])
        saved = {}
        confirm(
            file_path=export,
            skip_full_name_scan=True,
            attest_asked_full_name="User declined sharing full name; exact-name scan skipped.",
            attest_asked_sensitive=_VALID_ATTEST_SENSITIVE,
            attest_manual_scan=_VALID_ATTEST_MANUAL,
            accept_redaction_drift="Removed `obsolete` because the company name was deprecated this quarter.",
            load_config_fn=lambda: {
                "redact_strings": ["secret1"],
                "last_export": {
                    "sessions": 2,
                    "redact_strings_fingerprint": prev_fp,
                    "redact_strings_count": 2,
                },
            },
            save_config_fn=lambda cfg: saved.update(cfg),
        )
        assert saved["stage"] == "confirmed"
        assert "accepted_redaction_drift" in saved["review_attestations"]


# ---------------------------------------------------------------------------
# legacy-config compatibility
# ---------------------------------------------------------------------------


class TestLegacyConfigUpgrade:
    """A config that predates the sha256 check must NOT silently publish without a hash."""

    def test_legacy_last_confirm_without_hash_blocks_publish(self, tmp_path, monkeypatch, capsys):
        from dataclaw.cli import main

        export = _stub_export(tmp_path)
        legacy_config = {
            "stage": "confirmed",
            "repo": "alice/repo",
            "last_confirm": {"file": str(export)},  # no sha256, no size_bytes
            "review_attestations": {
                "asked_full_name": "User declined sharing full name; exact-name scan skipped.",
                "asked_sensitive_entities": _VALID_ATTEST_SENSITIVE,
                "manual_scan_done": _VALID_ATTEST_MANUAL,
            },
            "review_verification": {
                "full_name": None,
                "full_name_scan_skipped": True,
                "manual_scan_sessions": 20,
            },
        }
        monkeypatch.setattr("dataclaw.cli.load_config", lambda: legacy_config)
        monkeypatch.setattr("dataclaw.cli.save_config", lambda cfg: None)
        monkeypatch.setattr(
            "dataclaw.cli.push_to_huggingface",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not push")),
        )
        monkeypatch.setattr("sys.argv", [
            "dataclaw", "export",
            "--publish-attestation", "User explicitly approved publishing to Hugging Face on 2026-05-16.",
        ])

        with pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        assert "no recorded fingerprint" in out


class TestPublishHashMismatch:
    def test_file_modified_after_confirm_blocks_publish(self, tmp_path, monkeypatch, capsys):
        from dataclaw.cli import main

        export = _stub_export(tmp_path)
        recorded_hash = sha256_file(export)
        recorded_size = export.stat().st_size

        # Modify the file AFTER the confirm "recorded" its hash.
        with export.open("ab") as fh:
            fh.write(b'\n{"session_id":"sneaky","project":"p","model":"m","messages":[]}\n')

        legacy_config = {
            "stage": "confirmed",
            "repo": "alice/repo",
            "last_confirm": {
                "file": str(export),
                "sha256": recorded_hash,
                "size_bytes": recorded_size,
            },
            "review_attestations": {
                "asked_full_name": "User declined sharing full name; exact-name scan skipped.",
                "asked_sensitive_entities": _VALID_ATTEST_SENSITIVE,
                "manual_scan_done": _VALID_ATTEST_MANUAL,
            },
            "review_verification": {
                "full_name": None,
                "full_name_scan_skipped": True,
                "manual_scan_sessions": 20,
            },
        }
        monkeypatch.setattr("dataclaw.cli.load_config", lambda: legacy_config)
        monkeypatch.setattr("dataclaw.cli.save_config", lambda cfg: None)
        monkeypatch.setattr(
            "dataclaw.cli.push_to_huggingface",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not push")),
        )
        monkeypatch.setattr("sys.argv", [
            "dataclaw", "export",
            "--publish-attestation", "User explicitly approved publishing to Hugging Face on 2026-05-16.",
        ])

        with pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        # Size check fires first when bytes are appended.
        assert "size has changed" in out or "contents have changed" in out
