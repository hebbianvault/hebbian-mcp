#!/usr/bin/env python3
"""Check the Hebbian MCP client's API surface against the public OpenAPI contract.

Run without arguments to download and validate the current contract. Use --lint to
also check that statically visible MCP client request paths are represented in the
committed manifest.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any


CONTRACT_URL = (
    "https://raw.githubusercontent.com/hebbianvault/Hebbian/main/"
    "apps/api/openapi/openapi-v1.json"
)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "contract" / "client-paths.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
VALID_HTTP_METHODS = {method.upper() for method in HTTP_METHODS}
PLACEHOLDER = re.compile(r"\{[^}]+\}")

# This deliberately only recognises quoted first arguments to get/post request
# helpers. It will not see paths assembled in variables, concatenated strings, or
# helper methods other than get/post; keep those call sites simple or add them to
# this heuristic when they are introduced.
REQUEST_CALL = re.compile(
    r"""\b(?:client\.)?(?P<method>get|post)\(\s*
        (?:
            \"(?P<double>/[^\"]*)\"
          | '(?P<single>/[^']*)'
          | `(?P<template>/[^`]*)`
          | f\"(?P<fdouble>/[^\"]*)\"
          | f'(?P<fsingle>/[^']*)'
        )
    """,
    re.VERBOSE,
)
TS_TEMPLATE_EXPRESSION = re.compile(r"\$\{[^}]+\}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to the client operation manifest",
    )
    parser.add_argument(
        "--url",
        default=CONTRACT_URL,
        help="OpenAPI JSON URL (ignored when --contract is supplied)",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        help="read OpenAPI JSON from a local file instead of downloading it",
    )
    parser.add_argument(
        "--lint",
        action="store_true",
        help="fail if statically visible client request paths are absent from the manifest",
    )
    parser.add_argument(
        "--lint-only",
        action="store_true",
        help="run the client-path manifest lint without downloading the OpenAPI contract",
    )
    return parser.parse_args()


def read_json(path: Path, description: str) -> Any:
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not parse {description} at {path}: {exc}") from exc


def download_contract(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "hebbian-mcp-contract-drift"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not download or parse OpenAPI contract from {url}: {exc}") from exc


def load_manifest(path: Path) -> set[tuple[str, str]]:
    data = read_json(path, "manifest")
    if not isinstance(data, list):
        raise ValueError(f"manifest at {path} must be a JSON array")

    operations: set[tuple[str, str]] = set()
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"manifest entry {index} must be an object")
        method = entry.get("method")
        path_value = entry.get("path")
        if not isinstance(method, str) or method.upper() not in VALID_HTTP_METHODS:
            raise ValueError(f"manifest entry {index} has an invalid HTTP method: {method!r}")
        if not isinstance(path_value, str) or not path_value.startswith("/"):
            raise ValueError(f"manifest entry {index} has an invalid path: {path_value!r}")
        operation = (method.upper(), path_value)
        if operation in operations:
            raise ValueError(f"manifest contains duplicate operation: {method.upper()} {path_value}")
        operations.add(operation)
    return operations


def contract_operations(contract: Any) -> tuple[set[tuple[str, str]], dict[str, set[str]]]:
    if not isinstance(contract, dict) or not isinstance(contract.get("paths"), dict):
        raise ValueError("OpenAPI contract has no object-valued 'paths' field")

    operations: set[tuple[str, str]] = set()
    methods_by_path: dict[str, set[str]] = {}
    for path_value, item in contract["paths"].items():
        if not isinstance(path_value, str) or not isinstance(item, dict):
            continue
        methods = {method.upper() for method in item if method.lower() in HTTP_METHODS}
        methods_by_path[path_value] = methods
        operations.update((method, path_value) for method in methods)
    return operations, methods_by_path


def format_missing(
    missing: Iterable[tuple[str, str]], methods_by_path: dict[str, set[str]]
) -> list[str]:
    lines: list[str] = []
    known_paths = list(methods_by_path)
    for method, path_value in sorted(missing):
        if path_value in methods_by_path:
            available = ", ".join(sorted(methods_by_path[path_value])) or "no HTTP operations"
            lines.append(f"  - {method} {path_value} (path exists, methods: {available})")
            continue
        renamed = difflib.get_close_matches(path_value, known_paths, n=3, cutoff=0.45)
        if renamed:
            lines.append(
                f"  - {method} {path_value} (path missing; possible renamed path(s): "
                + ", ".join(renamed)
                + ")"
            )
        else:
            lines.append(f"  - {method} {path_value} (path missing)")
    return lines


def path_shape(path_value: str) -> str:
    """Compare parameterized paths without coupling linting to local variable names."""
    path_value = TS_TEMPLATE_EXPRESSION.sub("{}", path_value)
    return PLACEHOLDER.sub("{}", path_value)


def client_source_files() -> list[Path]:
    ts_files = sorted((ROOT / "ts" / "src").rglob("*.ts"))
    py_files = sorted((ROOT / "py" / "src" / "hebbianvault_mcp").rglob("*.py"))
    return ts_files + py_files


def lint_manifest(manifest: set[tuple[str, str]]) -> list[str]:
    expected_shapes = {(method, path_shape(path_value)) for method, path_value in manifest}
    missing: list[str] = []
    for source_file in client_source_files():
        contents = source_file.read_text(encoding="utf-8")
        for match in REQUEST_CALL.finditer(contents):
            path_value = next(value for value in match.groupdict().values() if value and value.startswith("/"))
            method = match.group("method").upper()
            if (method, path_shape(path_value)) not in expected_shapes:
                line = contents.count("\n", 0, match.start()) + 1
                relative = source_file.relative_to(ROOT)
                missing.append(f"  - {relative}:{line}: {method} {path_value}")
    return missing


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
    except ValueError as exc:
        print(f"contract-drift: {exc}", file=sys.stderr)
        return 2

    if args.lint_only:
        lint_missing = lint_manifest(manifest)
        if lint_missing:
            print("Client-path manifest lint failed. Unlisted request path(s):", file=sys.stderr)
            print("\n".join(lint_missing), file=sys.stderr)
            return 1
        print("Client-path manifest lint passed.")
        return 0

    try:
        contract = read_json(args.contract, "OpenAPI contract") if args.contract else download_contract(args.url)
        available, methods_by_path = contract_operations(contract)
    except ValueError as exc:
        print(f"contract-drift: {exc}", file=sys.stderr)
        return 2

    failed = False
    missing = manifest - available
    if missing:
        failed = True
        print("Contract drift detected. Manifest operations absent from OpenAPI:", file=sys.stderr)
        print("\n".join(format_missing(missing, methods_by_path)), file=sys.stderr)
    else:
        source = args.contract if args.contract else args.url
        print(f"Contract check passed: {len(manifest)} manifest operation(s) match {source}.")

    if args.lint:
        lint_missing = lint_manifest(manifest)
        if lint_missing:
            failed = True
            print("Client-path manifest lint failed. Unlisted request path(s):", file=sys.stderr)
            print("\n".join(lint_missing), file=sys.stderr)
        else:
            print("Client-path manifest lint passed.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
