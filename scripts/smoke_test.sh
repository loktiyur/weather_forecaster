#!/usr/bin/env bash
# Smoke test for a running API (full stack container, or a dev server).
# Used by the `Docker image` CI job and locally:  poetry run poe smoke-test [BASE_URL]
#
# Calls the real Open-Meteo API once (unlike the test suite), because its purpose is to
# prove the *deployed* container works end to end. curl retries transient errors.
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
CURL=(curl --silent --show-error --fail --max-time 10 --retry 3 --retry-delay 2)
ERROR_BODY=$(mktemp)
trap 'rm -f "$ERROR_BODY"' EXIT

step() { printf '\n==> %s\n' "$1"; }
json_check() {  # json_check '<python expression on d>' <<< "$json"
    python3 -c "import json, sys; d = json.load(sys.stdin); sys.exit(0 if ($1) else 1)"
}

step "Readiness: API is up and reaches Redis"
"${CURL[@]}" --retry 15 --retry-connrefused --retry-delay 1 "$BASE_URL/health/ready"
echo

step "OpenAPI schema is served"
"${CURL[@]}" "$BASE_URL/openapi.json" -o /dev/null && echo "ok"

step "Current weather (calls Open-Meteo)"
first=$("${CURL[@]}" "$BASE_URL/api/v1/weather/current?city=Prague&country=CZ")
json_check 'd["location"]["name"] == "Prague" and "temperature" in d["current"]' <<< "$first"
echo "ok: Prague, cached=$(json_check 'd["cached"]' <<< "$first" && echo true || echo false)"

step "Same request again is served from Redis"
second=$("${CURL[@]}" "$BASE_URL/api/v1/weather/current?city=Prague&country=CZ")
json_check 'd["cached"] is True' <<< "$second" && echo "ok: cached=true"

step "Errors use the unified format"
status=$(curl --silent --output "$ERROR_BODY" --write-out '%{http_code}' \
    "$BASE_URL/api/v1/weather/forecast?city=Prague&days=40")
[[ "$status" == "422" ]] || { echo "expected 422, got $status"; exit 1; }
json_check 'd["error"]["code"] == "VALIDATION_ERROR"' < "$ERROR_BODY" && echo "ok: 422 VALIDATION_ERROR"

printf '\nSmoke test passed for %s\n' "$BASE_URL"
