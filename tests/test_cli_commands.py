"""Direct tests for dataclaw._cli.commands helper logic."""

from dataclaw import _json as json
from dataclaw._cli.commands import list_projects, status
from dataclaw._cli.common import CLIBlockedError, DEFAULT_SOURCE


class TestListProjects:
    def test_prints_empty_message_when_no_projects(self, capsys):
        list_projects(
            "all",
            discover_projects_fn=lambda: [],
            load_config_fn=lambda: {"excluded_projects": []},
        )
        out = capsys.readouterr().out
        assert "No" in out and "sessions" in out

    def test_prints_filtered_projects_json(self, capsys):
        projects = [
            {
                "dir_name": "proj1",
                "display_name": "claude:proj1",
                "session_count": 2,
                "total_size_bytes": 100,
                "source": "claude",
            },
            {
                "dir_name": "proj2",
                "display_name": "codex:proj2",
                "session_count": 1,
                "total_size_bytes": 50,
                "source": "codex",
            },
        ]
        list_projects(
            "all",
            discover_projects_fn=lambda: projects,
            load_config_fn=lambda: {"excluded_projects": ["claude:proj1"]},
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        assert {row["name"] for row in data} == {"claude:proj1", "codex:proj2"}
        excluded_rows = [row for row in data if row["excluded"]]
        assert {row["name"] for row in excluded_rows} == {"claude:proj1"}

    def test_source_filter_narrows_results(self, capsys):
        projects = [
            {
                "dir_name": "proj1",
                "display_name": "claude:proj1",
                "session_count": 2,
                "total_size_bytes": 100,
                "source": "claude",
            },
            {
                "dir_name": "proj2",
                "display_name": "codex:proj2",
                "session_count": 1,
                "total_size_bytes": 50,
                "source": "codex",
            },
        ]
        list_projects(
            "claude",
            discover_projects_fn=lambda: projects,
            load_config_fn=lambda: {"excluded_projects": []},
        )
        data = json.loads(capsys.readouterr().out)
        assert {row["name"] for row in data} == {"claude:proj1"}


class TestStatus:
    def test_prints_status_payload(self, capsys):
        status(load_config_fn=lambda: {"repo": "user/repo", "source": "claude"})
        out = capsys.readouterr().out
        # status emits JSON; sanity-check that some expected key is present.
        assert "repo" in out or "stage" in out


class TestCLIBlockedError:
    def test_carries_payload(self):
        err = CLIBlockedError({"error": "boom", "hint": "do X"})
        assert err.payload == {"error": "boom", "hint": "do X"}
        assert "boom" in str(err)
