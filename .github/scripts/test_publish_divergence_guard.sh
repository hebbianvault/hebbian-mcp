#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
guard="$repo_root/.github/scripts/publish_divergence_guard.py"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
version="$(python3 - "$repo_root/ts/package.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])
PY
)"
different_version="$(python3 - "$version" <<'PY'
import sys
major, minor, patch = map(int, sys.argv[1].split("-", 1)[0].split("+", 1)[0].split("."))
print(f"{major}.{minor}.{patch + 1}")
PY
)"

make_fixture() {
  rm -rf "$fixture/repo"
  mkdir -p "$fixture/repo/ts" "$fixture/repo/py"
  cp "$repo_root/ts/package.json" "$fixture/repo/ts/package.json"
  cp "$repo_root/ts/package-lock.json" "$fixture/repo/ts/package-lock.json"
  cp "$repo_root/py/pyproject.toml" "$fixture/repo/py/pyproject.toml"
  cp "$repo_root/py/uv.lock" "$fixture/repo/py/uv.lock"
}

expect_failure() {
  local label="$1"
  local expected="$2"
  shift 2
  local output
  if output="$("$@" 2>&1)"; then
    echo "Expected guard failure for ${label}" >&2
    exit 1
  fi
  if [[ "$output" != *"$expected"* ]]; then
    echo "${label} failed with an unexpected diagnostic:" >&2
    echo "$output" >&2
    exit 1
  fi
  echo "Verified guard arm: ${label}"
}

make_fixture
"$guard" --root "$fixture/repo" --tag "v${version}"
echo "Verified guard arm: matching metadata and tag"

make_fixture
python3 - "$fixture/repo/ts/package.json" <<'PY'
import json
import sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
data["version"] = "not-semver"
json.dump(data, open(path, "w", encoding="utf-8"))
PY
expect_failure "invalid TypeScript semantic version" "not a valid semantic version" "$guard" --root "$fixture/repo"

make_fixture
python3 - "$fixture/repo/ts/package-lock.json" "$different_version" <<'PY'
import json
import sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
data["version"] = sys.argv[2]
json.dump(data, open(path, "w", encoding="utf-8"))
PY
expect_failure "npm manifest-lock divergence" "does not match npm lockfile version" "$guard" --root "$fixture/repo"

make_fixture
python3 - "$fixture/repo/ts/package-lock.json" "$different_version" <<'PY'
import json
import sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
data["packages"][""]["version"] = sys.argv[2]
json.dump(data, open(path, "w", encoding="utf-8"))
PY
expect_failure "npm lock root-package divergence" "does not match its root package version" "$guard" --root "$fixture/repo"

make_fixture
python3 - "$fixture/repo/py/pyproject.toml" "$version" "$different_version" <<'PY'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(
    text.replace(f'version = "{sys.argv[2]}"', f'version = "{sys.argv[3]}"', 1)
)
PY
expect_failure "npm-Python divergence" "does not match Python package version" "$guard" --root "$fixture/repo"

make_fixture
python3 - "$fixture/repo/py/uv.lock" "$version" "$different_version" <<'PY'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
needle = f'name = "hebbianvault-mcp"\nversion = "{sys.argv[2]}"'
replacement = f'name = "hebbianvault-mcp"\nversion = "{sys.argv[3]}"'
open(path, "w", encoding="utf-8").write(text.replace(needle, replacement, 1))
PY
expect_failure "Python-uv-lock divergence" "does not match uv lockfile version" "$guard" --root "$fixture/repo"

make_fixture
expect_failure "malformed release tag" "must have the form v<semantic-version>" "$guard" --root "$fixture/repo" --tag 0.5.0

make_fixture
expect_failure "tag-package divergence" "does not match package version" "$guard" --root "$fixture/repo" --tag "v${different_version}"

echo "All publish-divergence guard arms were verified."
