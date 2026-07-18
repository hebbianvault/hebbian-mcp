"""Directory scanners that turn local Markdown files into absorb items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .secrets import redact_secrets, should_skip_file

StoreKind = Literal["claude-code", "markdown"]
SUPPORTED_STORES: tuple[StoreKind, ...] = ("claude-code", "markdown")
SKIP_DIRS = frozenset(
    {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".cache"}
)


@dataclass(frozen=True)
class AbsorbItem:
    """One redacted local-memory item ready for the absorb API."""

    store_kind: str
    source_id: str
    title: str
    content: str
    created_at: str | None
    updated_at: str

    def as_dict(self) -> dict[str, str]:
        """Return the API payload representation with its snake_case keys."""
        payload = {
            "store_kind": self.store_kind,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "updated_at": self.updated_at,
        }
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        return payload


@dataclass(frozen=True)
class ScanResult:
    """Items found and the security actions taken while scanning."""

    items: list[AbsorbItem]
    skipped_secret_files: list[str]
    skipped_symlinks: list[str]
    redacted_items: int
    redacted_secrets: int


def is_supported_store(kind: str) -> bool:
    """Return whether ``kind`` names an available local importer."""
    return kind in SUPPORTED_STORES


def supported_stores() -> tuple[str, ...]:
    """Return the supported store tags in CLI-display order."""
    return SUPPORTED_STORES


def _collect_markdown_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Collect Markdown files below ``root`` and report skipped symlinks."""
    output: list[Path] = []
    skipped_symlinks: list[Path] = []

    def walk(directory: Path) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            try:
                if entry.is_symlink():
                    skipped_symlinks.append(entry.relative_to(root))
                    continue
                if entry.is_dir():
                    if entry.name not in SKIP_DIRS:
                        walk(entry)
                elif entry.is_file() and entry.name.lower().endswith(".md"):
                    output.append(entry.relative_to(root))
            except OSError:
                continue

    walk(root)
    return (
        sorted(output, key=lambda path: path.as_posix()),
        sorted(skipped_symlinks, key=lambda path: path.as_posix()),
    )


def _derive_title(content: str, relative_path: Path) -> str:
    """Use the first Markdown heading, falling back to the filename stem."""
    for raw in content.split("\n"):
        match = re.fullmatch(r"#{1,6}\s+(.+?)\s*#*", raw.strip())
        if match and match.group(1):
            return match.group(1).strip()
    return relative_path.stem


def _iso_timestamp(timestamp: float) -> str:
    """Format a filesystem timestamp as an ISO-8601 UTC value."""
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def _birthtime_iso(stat: object) -> str | None:
    """Return a filesystem birthtime when the platform exposes one."""
    birthtime = getattr(stat, "st_birthtime", None)
    return _iso_timestamp(birthtime) if birthtime is not None else None


def scan_directory(root: str | Path, store_kind: str) -> ScanResult:
    """Walk a local store and produce redacted items for a supported store kind."""
    root_path = Path(root)
    items: list[AbsorbItem] = []
    skipped_secret_files: list[str] = []
    relative_symlinks: list[Path]
    redacted_items = 0
    redacted_secrets = 0

    relative_paths, relative_symlinks = _collect_markdown_files(root_path)
    for relative_path in relative_paths:
        source_id = relative_path.as_posix()
        if should_skip_file(relative_path.name):
            skipped_secret_files.append(source_id)
            continue
        try:
            path = root_path / relative_path
            raw = path.read_text(encoding="utf-8")
            stat = path.stat()
        except OSError:
            continue
        redaction = redact_secrets(raw)
        if redaction.redacted_count:
            redacted_items += 1
            redacted_secrets += redaction.redacted_count
        items.append(
            AbsorbItem(
                store_kind=store_kind,
                source_id=source_id,
                title=_derive_title(redaction.content, relative_path),
                content=redaction.content,
                created_at=_birthtime_iso(stat),
                updated_at=_iso_timestamp(stat.st_mtime),
            )
        )

    return ScanResult(
        items=items,
        skipped_secret_files=skipped_secret_files,
        skipped_symlinks=[path.as_posix() for path in relative_symlinks],
        redacted_items=redacted_items,
        redacted_secrets=redacted_secrets,
    )
