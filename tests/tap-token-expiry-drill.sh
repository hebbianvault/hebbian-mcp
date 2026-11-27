#!/usr/bin/env bash
# Drill for scripts/tap-token-expiry.sh (issue #90, ruling xg).
# Runs offline: header fixtures go through --from-headers, and the live and
# issue arms use fake curl and gh binaries on PATH.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
script="$repo_root/scripts/tap-token-expiry.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if [[ ! -f "$script" ]]; then
  echo "FAIL: $script is missing" >&2
  exit 1
fi

base_date="Fri, 27 Nov 2026 12:00:00 GMT"
base_epoch="$(date -u -d "$base_date" +%s)"

# expiry_in DAYS FORM -> expiration header value DAYS after base_date.
# FORM is UTC or a +HHMM/-HHMM offset; the wall clock is shifted to match.
expiry_in() {
  local days="$1" form="$2" t shift_s sign hh mm
  t=$((base_epoch + days * 86400))
  if [[ "$form" == "UTC" ]]; then
    echo "$(date -u -d "@$t" '+%Y-%m-%d %H:%M:%S') UTC"
    return
  fi
  sign="${form:0:1}" hh="${form:1:2}" mm="${form:3:2}"
  shift_s=$((10#$hh * 3600 + 10#$mm * 60))
  [[ "$sign" == "-" ]] && shift_s=$((-shift_s))
  echo "$(date -u -d "@$((t + shift_s))" '+%Y-%m-%d %H:%M:%S') $form"
}

# headers FILE STATUS [EXPIRATION] -> writes a raw header block with CRLFs.
headers() {
  local file="$1" status="$2" expiration="${3-}"
  {
    printf 'HTTP/2 %s\r\n' "$status"
    printf 'date: %s\r\n' "$base_date"
    printf 'content-type: application/json; charset=utf-8\r\n'
    if [[ -n "$expiration" ]]; then
      printf 'github-authentication-token-expiration: %s\r\n' "$expiration"
    fi
    printf 'x-github-request-id: 0000:1111:2222\r\n'
    printf '\r\n'
  } >"$file"
}

expect_ok() {
  local label="$1" file="$2" output
  if ! output="$(env -u GH_TOKEN bash "$script" --from-headers "$file" 2>&1)"; then
    echo "FAIL: expected exit 0 for ${label}, got:" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"ok:"* ]]; then
    echo "FAIL: ${label} exited 0 without an ok line:" >&2
    echo "$output" >&2
    exit 1
  fi
  echo "Verified arm: ${label} -> exit 0 (${output})"
}

expect_failure() {
  local label="$1" expected="$2" file="$3" output
  if output="$(env -u GH_TOKEN bash "$script" --from-headers "$file" 2>&1)"; then
    echo "FAIL: expected non-zero exit for ${label}, got:" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"$expected"* ]]; then
    echo "FAIL: ${label} failed without \"${expected}\":" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" == *"ok:"* ]]; then
    echo "FAIL: ${label} printed ok while failing:" >&2
    echo "$output" >&2
    exit 1
  fi
  echo "Verified arm: ${label} -> non-zero"
}

headers "$work/95" 200 "$(expiry_in 95 UTC)"
expect_ok "95 days left (UTC form)" "$work/95"

headers "$work/30" 200 "$(expiry_in 30 +0200)"
expect_ok "30 days left (+0200 form)" "$work/30"

headers "$work/11" 200 "$(expiry_in 11 -0500)"
expect_ok "11 days left (-0500 form)" "$work/11"

headers "$work/10" 200 "$(expiry_in 10 UTC)"
expect_failure "10 days left" "expires in 10 days" "$work/10"

headers "$work/3" 200 "$(expiry_in 3 +0000)"
expect_failure "3 days left" "expires in 3 days" "$work/3"

headers "$work/missing" 200
expect_failure "expiration header missing" "missing" "$work/missing"

headers "$work/garbage" 200 "next tuesday"
expect_failure "expiration header unparsable" "unparsable" "$work/garbage"

headers "$work/equal" 200 "$(date -u -d "$base_date" '+%Y-%m-%d %H:%M:%S') UTC"
expect_failure "expiry equal to Date" "go-github#3708" "$work/equal"

headers "$work/401" 401 "$(expiry_in 95 UTC)"
expect_failure "HTTP 401" "HTTP 401" "$work/401"

# Stdin form of --from-headers.
if ! out="$(env -u GH_TOKEN bash "$script" --from-headers - <"$work/95" 2>&1)" || [[ "$out" != *"ok: 95 days"* ]]; then
  echo "FAIL: --from-headers - (stdin) did not report 95 days: $out" >&2
  exit 1
fi
echo "Verified arm: --from-headers - reads stdin"

# Fake gh: logs argv, and answers `issue list` from $FAKE_GH_LIST.
bin="$work/bin"
mkdir -p "$bin"
cat >"$bin/gh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FAKE_GH_LOG"
if [[ "$1 $2" == "issue list" ]]; then
  [[ -n "${FAKE_GH_LIST-}" ]] && printf '%s\n' "$FAKE_GH_LIST"
fi
exit 0
EOF
# Fake curl: logs argv and stdin separately, writes the fixture to its -D path.
cat >"$bin/curl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FAKE_CURL_ARGV"
cat >>"$FAKE_CURL_STDIN"
out=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-D" ]]; then out="$2"; shift; fi
  shift
done
cp "$FAKE_CURL_FIXTURE" "$out"
EOF
chmod +x "$bin/gh" "$bin/curl"
export FAKE_GH_LOG="$work/gh.log"
export FAKE_CURL_ARGV="$work/curl.argv" FAKE_CURL_STDIN="$work/curl.stdin"

# Issue arm, first run: no open issue -> create with title and label.
: >"$FAKE_GH_LOG"
if PATH="$bin:$PATH" GH_TOKEN=dummy FAKE_GH_LIST="" bash "$script" --from-headers "$work/3" >"$work/out" 2>&1; then
  echo "FAIL: issue arm (create) exited 0" >&2
  exit 1
fi
if ! grep -q '^issue create .*--title HOMEBREW_TAP_TOKEN expires in 3 days .*--label lane:product' "$FAKE_GH_LOG"; then
  echo "FAIL: gh issue create not called with title and lane:product:" >&2
  cat "$FAKE_GH_LOG" "$work/out" >&2
  exit 1
fi
echo "Verified arm: <=10 days opens one issue (gh issue create, lane:product)"

# Issue arm, second run: #7 is open -> edit 7, no create.
: >"$FAKE_GH_LOG"
if PATH="$bin:$PATH" GH_TOKEN=dummy FAKE_GH_LIST="7" bash "$script" --from-headers "$work/3" >"$work/out" 2>&1; then
  echo "FAIL: issue arm (edit) exited 0" >&2
  exit 1
fi
if ! grep -q '^issue edit 7 .*--title HOMEBREW_TAP_TOKEN expires in 3 days' "$FAKE_GH_LOG" || grep -q '^issue create' "$FAKE_GH_LOG"; then
  echo "FAIL: expected gh issue edit 7 and no create:" >&2
  cat "$FAKE_GH_LOG" "$work/out" >&2
  exit 1
fi
echo "Verified arm: an open issue is updated, not duplicated (gh issue edit 7)"

# Live arm without a token: fails with the reason.
if out="$(env -u HOMEBREW_TAP_TOKEN PATH="$bin:$PATH" bash "$script" 2>&1)" || [[ "$out" != *"HOMEBREW_TAP_TOKEN is not set"* ]]; then
  echo "FAIL: live mode without HOMEBREW_TAP_TOKEN: $out" >&2
  exit 1
fi
echo "Verified arm: live mode without HOMEBREW_TAP_TOKEN -> non-zero"

# Token-leak arms: live mode through fake curl, ok path and issue path.
sentinel="sentinel-XYZ-$$"
for case in 95 3; do
  : >"$FAKE_CURL_ARGV" ; : >"$FAKE_CURL_STDIN" ; : >"$FAKE_GH_LOG"
  set +e
  PATH="$bin:$PATH" HOMEBREW_TAP_TOKEN="$sentinel" GH_TOKEN=dummy FAKE_GH_LIST="" \
    FAKE_CURL_FIXTURE="$work/$case" bash "$script" >"$work/out" 2>&1
  rc=$?
  set -e
  if [[ "$case" == 95 && $rc -ne 0 ]] || [[ "$case" == 3 && $rc -eq 0 ]]; then
    echo "FAIL: live mode (${case} days) exited ${rc}:" >&2
    cat "$work/out" >&2
    exit 1
  fi
  if grep -q "$sentinel" "$work/out" "$FAKE_CURL_ARGV" "$FAKE_GH_LOG"; then
    echo "FAIL: token value leaked into output, curl argv or gh argv (${case} days)" >&2
    exit 1
  fi
  if ! grep -q "Authorization: Bearer $sentinel" "$FAKE_CURL_STDIN"; then
    echo "FAIL: live mode did not send the token to curl via stdin config" >&2
    exit 1
  fi
  if ! grep -q 'api.github.com/repos/hebbianvault/homebrew-tap' "$FAKE_CURL_ARGV"; then
    echo "FAIL: live mode did not call the homebrew-tap repo endpoint" >&2
    exit 1
  fi
  echo "Verified arm: live mode (${case} days) never prints the token"
done

echo "All tap-token-expiry arms verified."
