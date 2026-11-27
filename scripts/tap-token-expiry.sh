#!/usr/bin/env bash
# Warn before the 90-day HOMEBREW_TAP_TOKEN lapses (ruling xg, issue #90).
#
# Reads the github-authentication-token-expiration header GitHub returns for
# a fine-grained PAT and fails when 10 days or fewer are left (day 80 of 90),
# opening or updating one "HOMEBREW_TAP_TOKEN expires in N days" issue.
# Every doubt fails too: a non-200, a missing or unparsable header, or an
# expiry within 1 minute of Date (go-github#3708). Only the days left and
# the expiry date are printed, never the token.
#
# Usage:
#   scripts/tap-token-expiry.sh                      live: HOMEBREW_TAP_TOKEN from env
#   scripts/tap-token-expiry.sh --from-headers FILE  offline: raw header block (- = stdin)
#
# With GH_TOKEN set, the <=10 days case opens or edits the issue with `gh`
# in ${GITHUB_REPOSITORY:-hebbianvault/hebbian-mcp}. Needs GNU date.
set -euo pipefail

api_url="https://api.github.com/repos/hebbianvault/homebrew-tap"
repo="${GITHUB_REPOSITORY:-hebbianvault/hebbian-mcp}"
title_prefix="HOMEBREW_TAP_TOKEN expires in"
warn_days=10

fail() {
  echo "tap-token-expiry: $*" >&2
  exit 1
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
raw="$work/headers"

case "${1-}" in
  --from-headers)
    [[ $# -eq 2 ]] || fail "usage: $0 [--from-headers FILE]"
    if [[ "$2" == "-" ]]; then
      cat >"$raw"
    else
      [[ -r "$2" ]] || fail "cannot read header file $2"
      cat -- "$2" >"$raw"
    fi
    ;;
  "")
    [[ -n "${HOMEBREW_TAP_TOKEN-}" ]] || fail "HOMEBREW_TAP_TOKEN is not set"
    # The token goes in through curl's config on stdin, never argv.
    if ! printf 'header = "Authorization: Bearer %s"\n' "$HOMEBREW_TAP_TOKEN" |
      curl -sS --max-time 30 -o /dev/null -D "$raw" \
        -H "Accept: application/vnd.github+json" -K - "$api_url"; then
      fail "request to $api_url failed (curl error above)"
    fi
    ;;
  *)
    fail "usage: $0 [--from-headers FILE]"
    ;;
esac

# Keep only the last response block (redirects or 1xx come first), drop CRs.
tr -d '\r' <"$raw" | awk '/^HTTP\// { block = "" } { block = block $0 "\n" } END { printf "%s", block }' >"$work/last"

status="$(awk 'NR == 1 && /^HTTP\// { print $2 }' "$work/last")"
[[ -n "$status" ]] || fail "no HTTP status line in the response"
[[ "$status" == "200" ]] || fail "HTTP $status from api.github.com, cannot read the token expiry"

header() {
  awk -v name="$1" '{
    i = index($0, ":")
    if (i > 0 && tolower(substr($0, 1, i - 1)) == name) {
      v = substr($0, i + 1); sub(/^[ \t]+/, "", v); sub(/[ \t]+$/, "", v); print v; exit
    }
  }' "$work/last"
}

expiration="$(header github-authentication-token-expiration)"
[[ -n "$expiration" ]] ||
  fail "github-authentication-token-expiration header missing: token has no expiry or is not a fine-grained PAT"
# GNU date accepts almost anything, so the shape is checked first.
[[ "$expiration" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ (UTC|[+-][0-9]{4})$ ]] ||
  fail "github-authentication-token-expiration header unparsable: '$expiration'"
exp_epoch="$(date -u -d "$expiration" +%s 2>/dev/null)" ||
  fail "github-authentication-token-expiration header unparsable: '$expiration'"

date_header="$(header date)"
[[ -n "$date_header" ]] || fail "Date header missing, cannot check the expiry against GitHub's clock"
now_epoch="$(date -u -d "$date_header" +%s 2>/dev/null)" ||
  fail "Date header unparsable: '$date_header'"

left=$((exp_epoch - now_epoch))
if ((left <= 60)); then
  fail "expiry $expiration is within 1 minute of Date ($date_header): known fine-grained header bug (go-github#3708), cannot trust it"
fi

days=$((left / 86400))
expires_on="$(date -u -d "@$exp_epoch" +%Y-%m-%d)"

if ((days > warn_days)); then
  echo "ok: $days days left, expires $expires_on"
  exit 0
fi

title="$title_prefix $days days"
echo "$title ($expires_on)" >&2

if [[ -z "${GH_TOKEN-}" ]]; then
  echo "tap-token-expiry: GH_TOKEN not set, no issue opened" >&2
  exit 1
fi

body="$(cat <<EOF
\`HOMEBREW_TAP_TOKEN\` expires in $days days, on $expires_on (UTC).

Ruling (xg), \`RULING-homebrew-a-90-day-tap-token-20261127.md\` (hebbianvault/Hebbian#5583), makes it a 90-day fine-grained PAT. If it lapses, the Homebrew bump in the release workflow stops and Homebrew users stay on an old version (see #76).

Rotate it before $expires_on:
1. Create a new fine-grained PAT: repository access \`hebbianvault/homebrew-tap\` only, permission Contents read/write, 90-day expiry.
2. Store it in Infisical and as the \`HOMEBREW_TAP_TOKEN\` repository secret of hebbianvault/hebbian-mcp.
3. Re-run the tap-token-expiry workflow; it goes green and this issue can be closed.

Opened by \`scripts/tap-token-expiry.sh\`.
EOF
)"

if ! existing="$(gh issue list --repo "$repo" --state open --label lane:product \
  --search "in:title \"$title_prefix\"" --json number,title \
  --jq ".[] | select(.title | startswith(\"$title_prefix\")) | .number")"; then
  fail "gh issue list failed, could not open the expiry issue ($title)"
fi
number="$(printf '%s\n' "$existing" | head -n 1)"

if [[ -n "$number" ]]; then
  gh issue edit "$number" --repo "$repo" --title "$title" --body "$body" >/dev/null ||
    fail "gh issue edit $number failed ($title)"
  echo "tap-token-expiry: updated issue #$number" >&2
else
  gh issue create --repo "$repo" --title "$title" --label lane:product --body "$body" >/dev/null ||
    fail "gh issue create failed ($title)"
  echo "tap-token-expiry: opened issue '$title'" >&2
fi
exit 1
