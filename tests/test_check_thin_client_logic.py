"""Tests for the logic checks in scripts/check_thin_client.py (DEC #268)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "check_thin_client.py"
FIXTURES = REPO / "tests" / "fixtures" / "thin_client"
BASELINE = REPO / "scripts" / "thin_client_baseline.txt"


def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


@pytest.fixture
def empty_baseline(tmp_path: Path) -> Path:
    path = tmp_path / "baseline.txt"
    path.write_text("")
    return path


def test_ts_fixture_fails_with_both_findings(empty_baseline: Path) -> None:
    result = run("--repo", FIXTURES / "bad", "--baseline", empty_baseline)
    assert result.returncode != 0
    assert "bad_tool.ts:" in result.stdout
    assert "endpoint /vault/graph" in result.stdout
    assert "bad_tool.ts:scoreNode rank-fn" in result.stdout
    assert "bad_tool.ts:handleBad visited-set" in result.stdout
    assert "bad_tool.ts:handleBad sort" in result.stdout


def test_py_fixture_fails_with_both_findings(empty_baseline: Path) -> None:
    result = run("--repo", FIXTURES / "bad", "--baseline", empty_baseline)
    assert result.returncode != 0
    assert "tools.py:_score rank-fn" in result.stdout
    assert "tools.py:handle_bad endpoint /vault/graph" in result.stdout
    assert "tools.py:handle_bad visited-set" in result.stdout
    assert "tools.py:handle_bad sort" in result.stdout


def test_comments_docstrings_and_allowed_paths_are_not_flagged(empty_baseline: Path) -> None:
    result = run("--repo", FIXTURES / "ok", "--baseline", empty_baseline)
    assert result.returncode == 0, result.stdout
    assert "THIN-CLIENT LOGIC" not in result.stdout


def test_baseline_covering_fixture_passes(tmp_path: Path, empty_baseline: Path) -> None:
    first = run("--repo", FIXTURES / "bad", "--baseline", empty_baseline)
    keys = [ln.removeprefix("THIN-CLIENT LOGIC ") for ln in first.stdout.splitlines() if ln.startswith("THIN-CLIENT LOGIC ")]
    assert keys
    covered = tmp_path / "covered.txt"
    covered.write_text("\n".join(keys) + "\n")
    assert run("--repo", FIXTURES / "bad", "--baseline", covered).returncode == 0


def test_stale_baseline_line_fails(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("ts/src/tools/gone.ts:scoreNode rank-fn\n")
    result = run("--repo", FIXTURES / "ok", "--baseline", baseline)
    assert result.returncode == 1
    assert "STALE" in result.stdout


def test_repo_passes_with_committed_baseline() -> None:
    result = run()
    assert result.returncode == 0, result.stdout


def test_deleting_any_baseline_line_fails(tmp_path: Path) -> None:
    lines = [ln for ln in BASELINE.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    assert lines
    for i, line in enumerate(lines):
        trimmed = tmp_path / f"baseline_{i}.txt"
        trimmed.write_text("\n".join(lines[:i] + lines[i + 1 :]) + "\n")
        result = run("--baseline", trimmed)
        assert result.returncode == 1, f"deleting {line!r} did not fail the check"
        assert "NEW" in result.stdout
