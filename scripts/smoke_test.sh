#!/usr/bin/env bash
# Smoke test for a running stack (full stack containers, or dev servers).
# Used by the `Docker image` CI job and locally:  poetry run poe smoke-test [API_URL] [WEB_URL]
#   API_URL  default http://localhost:8000
#   WEB_URL  optional, e.g. http://localhost:8080: also checks the web frontend and its /api proxy
#
# Calls the real Open-Meteo API once (unlike the test suite), because its purpose is to
# prove the *deployed* container works end to end. curl retries transient errors.
# If Open-Meteo itself cannot be reached, the API answers 502/504 in our error format: that is
# reported as a warning and the checks that need weather data are skipped. Anything else that
# goes wrong in our own containers still fails the test.
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
WEB_URL="${2:-}"
# 20 s: longer than the API's own wait for Open-Meteo (retries included), so a slow upstream
# shows up as the API's 504 instead of curl giving up first.
CURL=(curl --silent --show-error --fail --max-time 20 --retry 3 --retry-delay 2)
ERROR_BODY=$(mktemp)
trap 'rm -f "$ERROR_BODY"' EXIT

step() { printf '\n==> %s\n' "$1"; }
warn() {  # a yellow annotation on GitHub Actions, a plain line elsewhere
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::warning::$1"; else echo "WARNING: $1"; fi
}
json_check() {  # json_check '<python expression on d>' <<< "$json"
    python3 -c "import json, sys; d = json.load(sys.stdin); sys.exit(0 if ($1) else 1)"
}

step "Readiness: API is up and reaches Redis and Postgres"
"${CURL[@]}" --retry 15 --retry-connrefused --retry-delay 1 "$BASE_URL/health/ready"
echo

step "OpenAPI schema is served"
"${CURL[@]}" "$BASE_URL/openapi.json" -o /dev/null && echo "ok"

step "Current weather (calls Open-Meteo)"
# Without --fail: a 502/504 is read and judged below. No retries: the API retries Open-Meteo itself.
status=$(curl --silent --show-error --max-time 20 --output "$ERROR_BODY" --write-out '%{http_code}' \
    "$BASE_URL/api/v1/weather/current?city=Prague&country=CZ")
if [[ "$status" == "200" ]]; then
    json_check 'd["location"]["name"] == "Prague" and "temperature" in d["current"]' < "$ERROR_BODY"
    echo "ok: Prague, cached=$(json_check 'd["cached"]' < "$ERROR_BODY" && echo true || echo false)"

    step "Same request again is served from Redis"
    second=$("${CURL[@]}" "$BASE_URL/api/v1/weather/current?city=Prague&country=CZ")
    json_check 'd["cached"] is True' <<< "$second" && echo "ok: cached=true"
elif [[ "$status" == "502" || "$status" == "504" ]] \
    && json_check 'd["error"]["code"] in ("UPSTREAM_ERROR", "UPSTREAM_TIMEOUT")' < "$ERROR_BODY"; then
    # Our container answered correctly; the weather provider did not.
    warn "Open-Meteo is unreachable (HTTP $status from the API): weather and cache checks skipped"
else
    echo "expected 200 (or 502/504 UPSTREAM_*), got $status:"
    cat "$ERROR_BODY"; echo
    exit 1
fi

step "Errors use the unified format"
status=$(curl --silent --output "$ERROR_BODY" --write-out '%{http_code}' \
    "$BASE_URL/api/v1/weather/forecast?city=Prague&days=40")
[[ "$status" == "422" ]] || { echo "expected 422, got $status"; exit 1; }
json_check 'd["error"]["code"] == "VALIDATION_ERROR"' < "$ERROR_BODY" && echo "ok: 422 VALIDATION_ERROR"

if [[ -n "$WEB_URL" ]]; then
    step "Web: the app page is served"
    page=$("${CURL[@]}" --retry 15 --retry-connrefused --retry-delay 1 "$WEB_URL/")
    grep -q '<div id="app">' <<< "$page" && echo "ok"

    step "Web: deep links fall back to the app (single-page app)"
    "${CURL[@]}" "$WEB_URL/some/deep/link" | grep -q '<div id="app">' && echo "ok"

    step "Web: /api is proxied to the API"
    # A guest asking who is logged in: answered by the API (our error format) without any
    # external service and without writing to the database.
    status=$(curl --silent --max-time 20 --output "$ERROR_BODY" --write-out '%{http_code}' \
        "$WEB_URL/api/v1/me")
    [[ "$status" == "401" ]] || { echo "expected 401, got $status"; exit 1; }
    json_check 'd["error"]["code"] == "UNAUTHORIZED"' < "$ERROR_BODY" && echo "ok: 401 UNAUTHORIZED"
fi

printf '\nSmoke test passed for %s %s\n' "$BASE_URL" "$WEB_URL"
