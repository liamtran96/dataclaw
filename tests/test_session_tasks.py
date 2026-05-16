"""Direct tests for dataclaw.session_tasks task dispatch."""

from unittest.mock import MagicMock

import pytest

from dataclaw.anonymizer import Anonymizer
from dataclaw.export_tasks import ExportSessionTask
from dataclaw.session_tasks import build_export_session_tasks, parse_export_session_task


class TestBuildExportSessionTasks:
    def test_uses_provider_for_each_project(self, monkeypatch):
        fake_task = ExportSessionTask(
            source="claude",
            project_index=0,
            task_index=0,
            project_dir_name="proj",
            project_display_name="claude:proj",
            estimated_bytes=10,
            kind="file",
            file_path="/tmp/session.jsonl",
        )
        fake_provider = MagicMock()
        fake_provider.build_export_session_tasks.return_value = [fake_task]
        monkeypatch.setattr(
            "dataclaw.session_tasks.get_provider",
            lambda source: fake_provider if source == "claude" else None,
        )

        tasks = build_export_session_tasks([{"source": "claude", "dir_name": "proj"}], default_source="claude")
        assert tasks == [fake_task]
        fake_provider.build_export_session_tasks.assert_called_once()

    def test_unknown_source_is_skipped(self, monkeypatch):
        monkeypatch.setattr("dataclaw.session_tasks.get_provider", lambda source: None)
        tasks = build_export_session_tasks([{"source": "nope", "dir_name": "proj"}], default_source="claude")
        assert tasks == []


class TestParseExportSessionTask:
    def test_returns_none_for_unknown_source(self, monkeypatch):
        monkeypatch.setattr("dataclaw.session_tasks.get_provider", lambda source: None)
        task = ExportSessionTask(
            source="nope",
            project_index=0,
            task_index=0,
            project_dir_name="proj",
            project_display_name="nope:proj",
            estimated_bytes=10,
            kind="file",
            file_path="/tmp/session.jsonl",
        )
        assert parse_export_session_task(task, Anonymizer(), include_thinking=True) is None

    def test_delegates_to_provider(self, monkeypatch):
        expected = {"session_id": "s1", "messages": []}
        fake_provider = MagicMock()
        fake_provider.parse_export_session_task.return_value = expected
        monkeypatch.setattr("dataclaw.session_tasks.get_provider", lambda source: fake_provider)

        task = ExportSessionTask(
            source="claude",
            project_index=0,
            task_index=0,
            project_dir_name="proj",
            project_display_name="claude:proj",
            estimated_bytes=10,
            kind="file",
            file_path="/tmp/session.jsonl",
        )
        anon = Anonymizer()
        result = parse_export_session_task(task, anon, include_thinking=False)
        assert result is expected
        fake_provider.parse_export_session_task.assert_called_once_with(task, anon, False)
