#!/usr/bin/env bash
# Day 3 check: recovery-agent is reachable through api-gateway and accepts customer-service tokens.
#
# Needs: config-server, customer-service, api-gateway and recovery-agent running locally.
# Registers a local-only test customer (ignored if it already exists), logs in through the gateway,
# then calls the recovery endpoint with and without the token. The token is never printed.
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8090}"

# Local dev test account — exists only in the local customer-db
TEST_EMAIL="recovery-check@example.test"
TEST_PASSWORD="recovery-check-local-only"

curl -s -o /dev/null -X POST "$GATEWAY_URL/auth/register" -H 'Content-Type: application/json' \
  -d "{\"firstname\":\"Recovery\",\"lastname\":\"Check\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}" || true

TOKEN=$(curl -sf -X POST "$GATEWAY_URL/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["accessToken"])')
[[ -n "$TOKEN" ]] || { echo "login through gateway failed" >&2; exit 2; }

without=$(curl -s -o /dev/null -w '%{http_code}' "$GATEWAY_URL/api/v1/recovery/health")
with_body=$(curl -s -w '\n%{http_code}' -H "Authorization: Bearer $TOKEN" "$GATEWAY_URL/api/v1/recovery/health")
with=$(tail -1 <<<"$with_body")

echo "GET /api/v1/recovery/health without token -> $without"
echo "GET /api/v1/recovery/health with token    -> $with  $(head -1 <<<"$with_body")"

if [[ "$without" == "401" && "$with" == "200" ]]; then
  echo "GATEWAY AUTH OK"
else
  echo "GATEWAY AUTH FAILED" >&2; exit 1
fi
