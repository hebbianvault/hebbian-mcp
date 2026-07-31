#!/usr/bin/env bash
set -euo pipefail

workflows_dir="${1:-.github/workflows}"
allowlist="${2:-.github/runner-allowlist.txt}"
status=0

while IFS=: read -r workflow line declaration; do
  label="$(printf '%s\n' "$declaration" | sed -E 's/^[[:space:]]*runs-on:[[:space:]]*//; s/[[:space:]]*(#.*)?$//')"
  label="${label#\"${label%%[![:space:]]*}\"}"
  label="${label%\"${label##*[![:space:]]}\"}"
  label="${label#[}"
  label="${label%]}"
  label="${label#\"${label%%[![:space:]]*}\"}"
  label="${label%\"${label##*[![:space:]]}\"}"
  label="${label#\"}"
  label="${label%\"}"
  label="${label#\'}"
  label="${label%\'}"
  job="$(awk -v target="$line" '
    NR <= target && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {
      job = $1
      sub(/:$/, "", job)
    }
    END { print job }
  ' "$workflow")"
  key="${workflow}:${job}:${label}"
  if ! grep -Fqx "$key" "$allowlist"; then
    printf '::error file=%s,line=%s::%s is not allowlisted for job %s\n' "$workflow" "$line" "$label" "$job" >&2
    status=1
  fi
done < <(grep -RInE --include='*.yml' --include='*.yaml' \
  "^[[:space:]]*runs-on:[[:space:]]*(['\"]?(ubuntu-latest|ubuntu-[0-9][0-9]*\\.[0-9][0-9]*|windows-[[:alnum:]._-]+|macos-[[:alnum:]._-]+)['\"]?|\\[[[:space:]]*['\"]?(ubuntu-latest|ubuntu-[0-9][0-9]*\\.[0-9][0-9]*|windows-[[:alnum:]._-]+|macos-[[:alnum:]._-]+)['\"]?[[:space:]]*\\])([[:space:]]*(#.*)?)?$" \
  "$workflows_dir" || true)

if [ "$status" -ne 0 ]; then
  exit "$status"
fi

printf 'Runner guard passed: every hosted runner use is explicitly allowlisted.\n'
