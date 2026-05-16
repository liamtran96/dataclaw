"""CLI facade for DataClaw."""

import argparse
import os
import subprocess  # nosec B404
import sys
from pathlib import Path

from . import _json as json
from ._cli import commands, exporting, review
from ._cli.common import DEFAULT_SOURCE, CLIBlockedError, _has_session_sources
from ._cli.exporting import push_to_huggingface, summarize_export_jsonl, update_skill
from .anonymizer import Anonymizer
from .config import CONFIG_FILE, load_config, save_config
from .jsonl_tools import DiffResult, diff_jsonl_files, jsonl_to_yaml_file
from .parser import discover_projects, iter_project_sessions


def list_projects(source_filter: str = "auto") -> None:
    commands.list_projects(
        source_filter,
        discover_projects_fn=discover_projects,
        load_config_fn=load_config,
    )


def configure(
    repo: str | None = None,
    source: str | None = None,
    exclude: list[str] | None = None,
    redact: list[str] | None = None,
    redact_usernames: list[str] | None = None,
    confirm_projects: bool = False,
):
    commands.configure(
        repo=repo,
        source=source,
        exclude=exclude,
        redact=redact,
        redact_usernames=redact_usernames,
        confirm_projects=confirm_projects,
        load_config_fn=load_config,
        save_config_fn=save_config,
        config_file=CONFIG_FILE,
    )


def export_to_jsonl(
    selected_projects: list[dict],
    output_path: Path,
    anonymizer: Anonymizer,
    include_thinking: bool = True,
    custom_strings: list[str] | None = None,
) -> dict:
    return exporting.export_to_jsonl(
        selected_projects,
        output_path,
        anonymizer,
        parse_project_sessions_fn=iter_project_sessions,
        default_source=DEFAULT_SOURCE,
        include_thinking=include_thinking,
        custom_strings=custom_strings,
    )


def status() -> None:
    commands.status(load_config_fn=load_config)


def confirm(
    file_path: Path | None = None,
    full_name: str | None = None,
    attest_asked_full_name: str | None = None,
    attest_asked_sensitive: str | None = None,
    attest_manual_scan: str | None = None,
    skip_full_name_scan: bool = False,
    accept_full_name_matches: str | None = None,
    accept_session_shrink: str | None = None,
    accept_redaction_drift: str | None = None,
) -> None:
    review.confirm(
        file_path=file_path,
        full_name=full_name,
        attest_asked_full_name=attest_asked_full_name,
        attest_asked_sensitive=attest_asked_sensitive,
        attest_manual_scan=attest_manual_scan,
        skip_full_name_scan=skip_full_name_scan,
        accept_full_name_matches=accept_full_name_matches,
        accept_session_shrink=accept_session_shrink,
        accept_redaction_drift=accept_redaction_drift,
        load_config_fn=load_config,
        save_config_fn=save_config,
    )


def prep(source_filter: str = "auto") -> None:
    commands.prep(
        source_filter,
        load_config_fn=load_config,
        save_config_fn=save_config,
        discover_projects_fn=discover_projects,
        has_session_sources_fn=_has_session_sources,
    )


def jsonl_to_yaml(input_path: Path, output_path: Path | None = None) -> Path:
    return jsonl_to_yaml_file(input_path, output_path)


def diff_jsonl(
    old_path: Path,
    new_path: Path,
    output_path: Path | None = None,
    include_records_for_modified: bool = False,
) -> DiffResult:
    return diff_jsonl_files(
        old_path,
        new_path,
        output_path,
        include_records_for_modified=include_records_for_modified,
    )


def _handle_config(args: argparse.Namespace) -> None:
    commands.handle_config(
        args,
        load_config_fn=load_config,
        save_config_fn=save_config,
        configure_fn=configure,
    )


def _run_export(args: argparse.Namespace) -> None:
    commands.run_export(
        args,
        load_config_fn=load_config,
        save_config_fn=save_config,
        discover_projects_fn=discover_projects,
        has_session_sources_fn=_has_session_sources,
        export_to_jsonl_fn=export_to_jsonl,
        summarize_jsonl_fn=summarize_export_jsonl,
        push_to_huggingface_fn=push_to_huggingface,
    )


def _run_jsonl_to_yaml(args: argparse.Namespace) -> None:
    commands.run_jsonl_to_yaml(args, jsonl_to_yaml_fn=jsonl_to_yaml)


def _run_diff_jsonl(args: argparse.Namespace) -> None:
    commands.run_diff_jsonl(args, diff_jsonl_fn=diff_jsonl)


def main() -> None:
    if not getattr(sys, "frozen", False) and not sys.flags.utf8_mode and "pytest" not in sys.modules:
        os.environ["PYTHONUTF8"] = "1"
        ret = subprocess.run(  # nosec B603
            [sys.executable, "-m", "dataclaw.cli"] + sys.argv[1:], timeout=86400
        ).returncode
        sys.exit(ret)

    try:
        commands.main_impl(
            prep_fn=prep,
            status_fn=status,
            confirm_fn=confirm,
            update_skill_fn=update_skill,
            list_projects_fn=list_projects,
            load_config_fn=load_config,
            handle_config_fn=_handle_config,
            run_export_fn=_run_export,
            run_jsonl_to_yaml_fn=_run_jsonl_to_yaml,
            run_diff_jsonl_fn=_run_diff_jsonl,
        )
    except CLIBlockedError as exc:
        print(json.dumps(exc.payload, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
