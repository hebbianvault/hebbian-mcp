#!/usr/bin/env python3
"""Reject release inputs that would publish different package versions."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path


SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def fail(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        fail(f"Cannot read JSON metadata at {path}: {error}")


def read_toml(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
        fail(f"Cannot read TOML metadata at {path}: {error}")


def require_string(value: object, description: str) -> str:
    if not isinstance(value, str):
        fail(f"{description} must be a string.")
    return value


def require_semver(version: str, description: str) -> None:
    if not SEMVER.fullmatch(version):
        fail(f"{description} ({version!r}) is not a valid semantic version.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root (default: current directory)")
    parser.add_argument("--tag", help="Release tag to compare, for example v0.5.0")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    npm_manifest = read_json(root / "ts/package.json")
    npm_lock = read_json(root / "ts/package-lock.json")
    pyproject = read_toml(root / "py/pyproject.toml")
    uv_lock = read_toml(root / "py/uv.lock")

    npm_version = require_string(npm_manifest.get("version"), "TypeScript package manifest version")
    npm_lock_version = require_string(npm_lock.get("version"), "npm lockfile version")
    npm_lock_packages = npm_lock.get("packages")
    if not isinstance(npm_lock_packages, dict):
        fail("npm lockfile is missing its packages table.")
    npm_root_package = npm_lock_packages.get("")
    if not isinstance(npm_root_package, dict):
        fail("npm lockfile is missing its root package entry.")
    npm_root_version = require_string(npm_root_package.get("version"), "npm lockfile root package version")
    project = pyproject.get("project")
    if not isinstance(project, dict):
        fail("pyproject.toml is missing a [project] table.")
    pypi_version = require_string(project.get("version"), "Python package version")

    packages = uv_lock.get("package")
    if not isinstance(packages, list):
        fail("uv.lock is missing its package list.")
    matching_packages = [
        package
        for package in packages
        if isinstance(package, dict) and package.get("name") == "hebbianvault-mcp"
    ]
    if len(matching_packages) != 1:
        fail("uv.lock must contain exactly one hebbianvault-mcp package entry.")
    uv_version = require_string(matching_packages[0].get("version"), "uv lockfile version")

    require_semver(npm_version, "TypeScript package manifest version")
    require_semver(npm_lock_version, "npm lockfile version")
    require_semver(npm_root_version, "npm lockfile root package version")
    require_semver(pypi_version, "Python package version")
    require_semver(uv_version, "uv lockfile version")

    if npm_version != npm_lock_version:
        fail(
            "TypeScript package manifest version "
            f"({npm_version}) does not match npm lockfile version ({npm_lock_version})."
        )
    if npm_lock_version != npm_root_version:
        fail(
            "npm lockfile version "
            f"({npm_lock_version}) does not match its root package version ({npm_root_version})."
        )
    if npm_version != pypi_version:
        fail(
            "TypeScript package version "
            f"({npm_version}) does not match Python package version ({pypi_version})."
        )
    if pypi_version != uv_version:
        fail(
            "Python package version "
            f"({pypi_version}) does not match uv lockfile version ({uv_version})."
        )

    if args.tag is not None:
        if not args.tag.startswith("v") or not SEMVER.fullmatch(args.tag[1:]):
            fail(f"Release tag ({args.tag!r}) must have the form v<semantic-version>.")
        if args.tag[1:] != npm_version:
            fail(
                f"Release tag version ({args.tag[1:]}) does not match package version ({npm_version})."
            )

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(f"version={npm_version}\n")
    print(f"Publish divergence guard passed: all package metadata resolves to {npm_version}.")


if __name__ == "__main__":
    main()
