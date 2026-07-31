#!/usr/bin/env bash
set -euo pipefail

fixture_dir=".github/scripts/fixtures/runner-guard"
empty_allowlist="$(mktemp)"
trap 'rm -f "$empty_allowlist"' EXIT

# This is the pre-change matcher. It must miss these quoted and flow-form
# runners, proving the fixture would have passed the old guard.
old_regex='^[[:space:]]*runs-on:[[:space:]]*(ubuntu-latest|ubuntu-[0-9][0-9]*\.[0-9][0-9]*|windows-[[:alnum:]._-]+|macos-[[:alnum:]._-]+)([[:space:]]*(#.*)?)?$'
if grep -RInE --include='*.yml' --include='*.yaml' "$old_regex" "$fixture_dir"; then
  printf 'Fixture unexpectedly matches the pre-change runner-guard regex.\n' >&2
  exit 1
fi

printf 'Old runner guard passes fixture: its matcher finds no hosted runner.\n'

if bash .github/scripts/runner_guard.sh "$fixture_dir" "$empty_allowlist"; then
  printf 'Fixture unexpectedly passed the runner guard.\n' >&2
  exit 1
fi

printf 'New runner guard rejects fixture as expected.\n'
