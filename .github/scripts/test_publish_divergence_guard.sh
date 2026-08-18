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

# ── Arm: a hostile tag name must not reach the guard step's shell ─────────────
# github.ref_name is a git tag name, and git allows ; $ ` and " in one. Until
# 2026-08-18 the guard step pasted it in through ${{ inputs.tag }}, so a tag
# pushed by anyone with write access ran as shell in a job that goes on to
# publish. Both arms below are executed, so the RED one proves the hazard was
# real and the GREEN one proves this file's current shape closes it.
make_fixture
marker="$fixture/injected"
hostile_tag='v0.0.1"; touch '"$marker"'; :"'

rm -f "$marker"
# Unquoted heredoc on purpose: it substitutes the tag textually, which is what
# ${{ }} does before the shell ever sees the script.
cat >"$fixture/step-interpolated.sh" <<EOF
set -euo pipefail
if [ -n "$hostile_tag" ]; then
  python3 "$guard" --root "$fixture/repo" --tag "$hostile_tag"
else
  python3 "$guard" --root "$fixture/repo"
fi
EOF
bash "$fixture/step-interpolated.sh" >/dev/null 2>&1 || true
if [[ ! -f "$marker" ]]; then
  echo "RED arm did not reproduce the tag injection; this drill would pass vacuously." >&2
  exit 1
fi

rm -f "$marker"
cat >"$fixture/step-env.sh" <<'EOF'
set -euo pipefail
if [ -n "${TAG:-}" ]; then
  python3 "$GUARD" --root "$ROOT" --tag "$TAG"
else
  python3 "$GUARD" --root "$ROOT"
fi
EOF
TAG="$hostile_tag" GUARD="$guard" ROOT="$fixture/repo" bash "$fixture/step-env.sh" >/dev/null 2>&1 || true
if [[ -f "$marker" ]]; then
  echo "GREEN arm executed the injected command; the env-var form is not closing it." >&2
  exit 1
fi

# The arms above test a shape. This asserts the workflow still has that shape.
workflow="$repo_root/.github/workflows/publish-divergence-guard.yml"
if grep -nE '^\s*(python3|if).*\$\{\{\s*inputs\.tag' "$workflow" >/dev/null; then
  echo "publish-divergence-guard.yml interpolates inputs.tag into a run block again." >&2
  exit 1
fi
if ! grep -qE '^\s*TAG:\s*\$\{\{\s*inputs\.tag\s*\}\}\s*$' "$workflow"; then
  echo "publish-divergence-guard.yml no longer passes the tag through the TAG env var." >&2
  exit 1
fi

echo "Tag-injection arms verified: interpolated form executes, env form does not."
