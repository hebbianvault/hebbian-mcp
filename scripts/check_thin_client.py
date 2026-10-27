#!/usr/bin/env python3
"""Fail if the client source stops being a thin client.

The client talks to the Hebbian API and nothing else. This check scans the shipped
source (ts/src, py/src) for four things:

1. Imports of database, graph, or object-storage clients.
2. http(s) hosts other than the allowed set below.
3. Endpoint allowlist: every string that is wholly an API path must be listed in
   scripts/thin_client_endpoints.txt (so /vault/graph and /vault/company-graph fail).
4. Banned constructs (DEC #268: no ranking, traversal, graph cache or scope logic in
   the client): score/rank functions, `visited` sets, graph caches with a TTL, and
   sorts in tool code.

Logic findings (3 and 4) are matched against scripts/thin_client_baseline.txt, one key
per line: `<relpath>:<symbol> <rule>[ <detail>]`. A finding missing from the baseline
fails (NEW), and a baseline line with no matching finding fails too (STALE), so the
baseline only shrinks. There is deliberately no flag that writes the baseline.

The logic checks are name and shape heuristics. They catch the patterns we know about,
not logic hidden behind innocent names or paths built by concatenation.

Usage: check_thin_client.py [--repo DIR] [--baseline FILE] [ROOT ...]
Roots default to <repo>/ts/src and <repo>/py/src. Exit code 0 when clean, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_contract_drift import path_shape  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py"}
ENDPOINTS_FILE = REPO / "scripts" / "thin_client_endpoints.txt"

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

PATH_RE = re.compile(r"^/[a-z][\w\-/{}$.]*$")


def endpoint_path(value: str) -> str | None:
    """Return the endpoint path of a string literal, or None when it is not one.

    The query string is stripped first: PATH_RE rejects '?' and '=', so without
    this a call such as "/vault/graph?limit=5" would never be checked against
    the allowlist.
    """
    path = value.split("?", 1)[0]
    return path if PATH_RE.match(path) else None
RANK_RE = re.compile(r"score|rank", re.IGNORECASE)
VISITED_RE = re.compile(r"visited", re.IGNORECASE)
CACHE_RE = re.compile(r"graph_?cache|cache_?ttl", re.IGNORECASE)

TS_TOP_RE = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?|const|let|var|class)\s+(\w+)",
    re.MULTILINE,
)
TS_FN_DECL_RE = re.compile(
    r"\b(?:function\*?\s+(\w+)"
    r"|(?:const|let|var)\s+(\w+)(?:\s*:[^=]+)?\s*=\s*"
    r"(?:async\s+)?(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|\w+\s*=>))"
)
TS_VISITED_RE = re.compile(r"\b(\w*visited\w*)\s*(?::[^=;]+)?=\s*new\s+Set\b", re.IGNORECASE)
TS_CACHE_DECL_RE = re.compile(
    r"\b(?:const|let|var|function|class)\s+(\w*(?:graph_?cache|cache_?ttl)\w*)", re.IGNORECASE
)
TS_CACHE_ATTR_RE = re.compile(r"\bthis\.(\w*(?:graph_?cache|cache_?ttl)\w*)\s*=[^=]", re.IGNORECASE)
TS_SORT_RE = re.compile(r"\.(?:sort|toSorted)\s*\(")


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


def ts_strip(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Blank out comments (keeping newlines). Return code and (offset, string value) literals.

    Template literals keep their constant parts, with each ${...} replaced by {}.
    """
    out: list[str] = []
    strings: list[tuple[int, str]] = []
    i, n = 0, len(text)
    # Stack entries: "code", "brace" (inside ${ } or a plain { }), or a template state tuple.
    stack: list = ["code"]
    while i < n:
        top = stack[-1]
        c = text[i]
        if isinstance(top, tuple):  # inside a template literal
            _, start, parts = top
            if c == "\\":
                parts.append(text[i : i + 2])
                out.append(text[i : i + 2])
                i += 2
            elif c == "`":
                strings.append((start, "".join(parts)))
                out.append(c)
                stack.pop()
                i += 1
            elif text.startswith("${", i):
                parts.append("{}")
                out.append("${")
                stack.append("brace")
                i += 2
            else:
                parts.append(c)
                out.append(c)
                i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            strings.append((i, text[i + 1 : j]))
            out.append(text[i : j + 1])
            i = j + 1
        elif c == "`":
            stack.append(("tpl", i, []))
            out.append(c)
            i += 1
        elif c == "{":
            stack.append("brace")
            out.append(c)
            i += 1
        elif c == "}" and top == "brace":
            stack.pop()
            out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out), strings


def ts_findings(text: str, tool_code: bool) -> set[tuple[str, str, str]]:
    """Return (symbol, rule, detail) triples for a TypeScript source."""
    code, strings = ts_strip(text)
    tops = [(m.start(), m.group(1)) for m in TS_TOP_RE.finditer(code)]
    found: set[tuple[str, str, str]] = set()

    def add(pos: int, rule: str, detail: str = "") -> None:
        sym = "<module>"
        for start, name in tops:
            if start > pos:
                break
            sym = name
        found.add((sym, rule, "" if detail == sym else detail))

    for offset, value in strings:
        path = endpoint_path(value)
        if path is not None:
            add(offset, "endpoint", path_shape(path))
    for m in TS_FN_DECL_RE.finditer(code):
        name = m.group(1) or m.group(2)
        if RANK_RE.search(name):
            add(m.start(), "rank-fn", name)
    for m in TS_VISITED_RE.finditer(code):
        add(m.start(), "visited-set")
    for rx in (TS_CACHE_DECL_RE, TS_CACHE_ATTR_RE):
        for m in rx.finditer(code):
            add(m.start(), "graph-cache")
    if tool_code:
        for m in TS_SORT_RE.finditer(code):
            add(m.start(), "sort")
    return found


def _py_target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for elt in target.elts for n in _py_target_names(elt)]
    return []


def _py_skip_ids(tree: ast.AST) -> set[int]:
    """Docstrings and the constant fragments of f-strings are not path literals."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
        elif isinstance(node, ast.JoinedStr):
            ids.update(id(v) for v in node.values if isinstance(v, ast.Constant))
    return ids


def _py_fstring_text(node: ast.JoinedStr) -> str:
    return "".join(
        v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
        for v in node.values
    )


def _py_is_set_value(value: ast.AST | None) -> bool:
    if isinstance(value, ast.Set):
        return True
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in ("set", "frozenset")
    )


def py_findings(text: str, tool_code: bool) -> set[tuple[str, str, str]]:
    """Return (symbol, rule, detail) triples for a Python source."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    skip = _py_skip_ids(tree)
    found: set[tuple[str, str, str]] = set()
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            sym = top.name
        else:
            names: list[str] = []
            if isinstance(top, ast.Assign):
                names = [n for t in top.targets for n in _py_target_names(t)]
            elif isinstance(top, (ast.AnnAssign, ast.AugAssign)):
                names = _py_target_names(top.target)
            sym = names[0] if names else "<module>"

        def add(rule: str, detail: str = "") -> None:
            found.add((sym, rule, "" if detail == sym else detail))

        for node in ast.walk(top):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not isinstance(node, ast.ClassDef) and RANK_RE.search(node.name):
                    add("rank-fn", node.name)
                if CACHE_RE.search(node.name):
                    add("graph-cache")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for name in [n for t in targets for n in _py_target_names(t)]:
                    if CACHE_RE.search(name):
                        add("graph-cache")
                    if VISITED_RE.search(name) and _py_is_set_value(node.value):
                        add("visited-set")
            elif isinstance(node, ast.JoinedStr):
                value = _py_fstring_text(node)
                path = endpoint_path(value)
                if path is not None:
                    add("endpoint", path_shape(path))
            elif isinstance(node, ast.Constant):
                path = endpoint_path(node.value) if isinstance(node.value, str) and id(node) not in skip else None
                if path is not None:
                    add("endpoint", path_shape(path))
            elif tool_code and isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr in ("sort", "sorted"):
                    add("sort")
                elif isinstance(fn, ast.Name) and (
                    fn.id == "sorted"
                    or (fn.id in ("min", "max") and any(k.arg == "key" for k in node.keywords))
                ):
                    add("sort")
    return found


def logic_findings(path: Path, repo: Path) -> set[str]:
    try:
        rel = path.resolve().relative_to(repo.resolve())
    except ValueError:
        rel = Path(path.name)
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".py":
        triples = py_findings(text, tool_code=path.name == "tools.py")
    else:
        triples = ts_findings(text, tool_code="tools" in rel.parts)
    keys = set()
    for sym, rule, detail in triples:
        key = f"{rel.as_posix()}:{sym} {rule}"
        keys.add(f"{key} {detail}" if detail else key)
    return keys


def read_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines = (ln.strip() for ln in path.read_text(encoding="utf-8").splitlines())
    return [ln for ln in lines if ln and not ln.startswith("#")]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Thin-client guard")
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--baseline", type=Path, default=None)
    ap.add_argument("--endpoints", type=Path, default=None)
    ap.add_argument("roots", nargs="*", type=Path)
    args = ap.parse_args(argv)
    repo = args.repo
    roots = args.roots or [repo / "ts" / "src", repo / "py" / "src"]
    baseline_path = args.baseline or (REPO / "scripts" / "thin_client_baseline.txt")
    allowed = {path_shape(p) for p in read_lines(args.endpoints or ENDPOINTS_FILE)}

    problems: list[str] = []
    findings: set[str] = set()
    scanned = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES and "node_modules" not in path.parts:
                scanned += 1
                problems.extend(scan_file(path))
                findings |= logic_findings(path, repo)

    def allowed_endpoint(key: str) -> bool:
        parts = key.split(" ", 2)
        return len(parts) == 3 and parts[1] == "endpoint" and parts[2] in allowed

    findings = {k for k in findings if not allowed_endpoint(k)}
    baseline = set(read_lines(baseline_path))
    new = sorted(findings - baseline)
    stale = sorted(baseline - findings)
    for p in problems:
        print(f"THIN-CLIENT VIOLATION {p}")
    for key in sorted(findings):
        print(f"THIN-CLIENT LOGIC {key}")
    for key in new:
        print(f"THIN-CLIENT NEW (not in baseline): {key}")
    for key in stale:
        print(f"THIN-CLIENT STALE (violation is gone, delete this baseline line): {key}")
    if problems or new or stale:
        return 1
    print(
        f"thin-client check ok: {scanned} files, hosts limited to {sorted(ALLOWED_HOSTS)}, "
        f"{len(findings)} baselined logic violations"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
