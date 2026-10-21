#!/usr/bin/env python3
"""Fail if the client source stops being a thin client.

The client talks to the Hebbian API and nothing else. This check scans the shipped
source (ts/src, py/src) for two things:

1. Imports of database, graph, or object-storage clients.
2. http(s) hosts other than the allowed set below.

Usage: check_thin_client.py [ROOT ...]   (defaults to ts/src and py/src in the repo)
Exit code 0 when clean, 1 on any violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = [REPO / "ts" / "src", REPO / "py" / "src"]
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py"}

ALLOWED_HOSTS = {"api.hebbianvault.com", "localhost", "127.0.0.1"}

# Package names (or scope prefixes ending in "/") that must never be imported.
FORBIDDEN_PACKAGES = [
    "pg", "postgres", "psycopg", "psycopg2", "asyncpg", "@supabase/", "supabase",
    "neo4j", "neo4j-driver", "mongodb", "pymongo", "redis", "ioredis",
    "@aws-sdk/client-s3", "boto3", "prisma", "@prisma/", "drizzle-orm", "kysely",
    "knex", "sqlalchemy", "mysql", "mysql2", "better-sqlite3",
]

URL_RE = re.compile(r"https?://([A-Za-z0-9._-]+)", re.IGNORECASE)
TS_IMPORT_RE = re.compile(
    r"""(?:\bfrom\s+|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"]+)['"]"""
)
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", re.MULTILINE)


def _forbidden(name: str) -> bool:
    for pkg in FORBIDDEN_PACKAGES:
        if pkg.endswith("/"):
            if name.startswith(pkg):
                return True
        elif name == pkg or name.startswith(pkg + "/") or name.startswith(pkg + "."):
            return True
    return False


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    problems: list[str] = []
    if path.suffix == ".py":
        for m in PY_IMPORT_RE.finditer(text):
            names = [m.group(1)] if m.group(1) else [n.strip().split(" ")[0] for n in m.group(2).split(",")]
            for name in names:
                if name and _forbidden(name):
                    problems.append(f"{path}: forbidden import '{name}'")
    else:
        for m in TS_IMPORT_RE.finditer(text):
            if _forbidden(m.group(1)):
                problems.append(f"{path}: forbidden import '{m.group(1)}'")
    for m in URL_RE.finditer(text):
        host = m.group(1).lower()
        if host not in ALLOWED_HOSTS:
            problems.append(f"{path}: foreign host '{host}' (allowed: {sorted(ALLOWED_HOSTS)})")
    return problems


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or DEFAULT_ROOTS
    problems: list[str] = []
    scanned = 0
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES and "node_modules" not in path.parts:
                scanned += 1
                problems.extend(scan_file(path))
    for p in problems:
        print(f"THIN-CLIENT VIOLATION {p}")
    if problems:
        return 1
    print(f"thin-client check ok: {scanned} files, hosts limited to {sorted(ALLOWED_HOSTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
