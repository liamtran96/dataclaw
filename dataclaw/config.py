"""Persistent config for DataClaw - stored at ~/.dataclaw/config.json"""

import logging
import os
import tempfile
from pathlib import Path
from typing import TypedDict, cast

from . import _json as json

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".dataclaw"
CONFIG_FILE = CONFIG_DIR / "config.json"


class LastExport(TypedDict, total=False):
    """Bookkeeping written to config after each successful export run."""

    file: str
    timestamp: str
    sessions: int
    bytes: int


class ReviewAttestations(TypedDict, total=False):
    """Free-text attestations collected during `dataclaw confirm`."""

    asked_full_name: str
    asked_sensitive_entities: str
    manual_scan_done: str


class ReviewVerification(TypedDict, total=False):
    """Concrete verification evidence captured during `dataclaw confirm`."""

    full_name: str
    full_name_scan_skipped: bool
    manual_scan_sessions: int


class LastConfirm(TypedDict, total=False):
    """Pointer to the most recent confirmed export file."""

    file: str
    timestamp: str


class DataClawConfig(TypedDict, total=False):
    """Expected shape of the config dict."""

    repo: str | None
    source: str | None  # "claude" | "codex" | "gemini" | "all"
    excluded_projects: list[str]
    redact_strings: list[str]
    redact_usernames: list[str]
    last_export: LastExport
    stage: str | None  # "auth" | "configure" | "review" | "confirmed" | "done"
    projects_confirmed: bool  # True once user has addressed folder exclusions
    review_attestations: ReviewAttestations
    review_verification: ReviewVerification
    last_confirm: LastConfirm
    publish_attestation: str


DEFAULT_CONFIG: DataClawConfig = {
    "repo": None,
    "source": None,
    "excluded_projects": [],
    "redact_strings": [],
}


def load_config() -> DataClawConfig:
    if CONFIG_FILE.exists():
        try:
            stored = json.loads(CONFIG_FILE.read_bytes())
            return cast(DataClawConfig, {**DEFAULT_CONFIG, **stored})
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read %s: %s", CONFIG_FILE, e)
    return cast(DataClawConfig, dict(DEFAULT_CONFIG))


def save_config(config: DataClawConfig) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = json.dumps_bytes(config, indent=2)
        # Atomic write: temp file in the same directory, then rename.
        fd, tmp_path = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=CONFIG_DIR)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp_path, CONFIG_FILE)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        logger.warning("Could not save %s: %s", CONFIG_FILE, e)
