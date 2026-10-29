#!/usr/bin/env bash
# Day 5 check: the deterministic rules classify every seeded scenario correctly — no model call.
#
# Needs the same stack as investigation_input_check.sh and seed.sh already run.
# For each of S1–S5 it stores a fresh investigation input from the live services, asks the agent for
# the rules baseline, and compares the finding and action with SCENARIOS.md.
set -euo pipefail

CUSTOMER_URL="${CUSTOMER_URL:-http://localhost:8083}"
AGENT_URL="${AGENT_URL:-http://localhost:8088}"
CUSTOMER_DB_CONTAINER="${CUSTOMER_DB_CONTAINER:-customer-postgres-db}"

# Local dev admin test account — same one investigation_input_check.sh uses
ADMIN_EMAIL="recovery-admin@example.test"
ADMIN_PASSWORD="recovery-admin-local-only"

curl -s -o /dev/null -X POST "$CUSTOMER_URL/auth/register" -H 'Content-Type: application/json' \
  -d "{\"firstname\":\"Recovery\",\"lastname\":\"Admin\",\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" || true
docker exec -i "$CUSTOMER_DB_CONTAINER" psql -U customer_user -d customer_db -tAq -v ON_ERROR_STOP=1 \
  -c "UPDATE customer SET role='ROLE_ADMIN' WHERE email='$ADMIN_EMAIL'" >/dev/null
TOKEN=$(curl -sf -X POST "$CUSTOMER_URL/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["accessToken"])')

# scenario  orderId  concern    expected finding          expected action
cases=(
  "S1 800001 PAYMENT   ORDER_PAYMENT_MISMATCH   RECONCILE_PAYMENT_CONFIRMATION"
  "S2 800002 PAYMENT   PAYMENT_AHEAD_OF_ORDER   -"
  "S3 800003 PAYMENT   CONSISTENT               -"
  "S4 800004 INVENTORY INSUFFICIENT_EVIDENCE    -"
  "S5 800005 PAYMENT   CONFLICTING_EVIDENCE     -"
)

failed=0
printf '%-3s %-7s %-10s %-24s %-31s %s\n' scen order concern finding action result
for c in "${cases[@]}"; do
  read -r s oid concern exp_finding exp_action <<<"$c"
  input_id=$(curl -sf -X POST "$AGENT_URL/api/v1/recovery/investigation-inputs" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"orderId\":$oid}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
  read -r finding action < <(curl -sf -H "Authorization: Bearer $TOKEN" \
    "$AGENT_URL/api/v1/recovery/investigation-inputs/$input_id/baseline?concern=$concern" \
    | python3 -c 'import json,sys; b=json.load(sys.stdin); print(b["finding"], b["recommendedAction"] or "-")')
  result=ok
  [[ "$finding" == "$exp_finding" && "$action" == "$exp_action" ]] || { result="EXPECTED $exp_finding/$exp_action"; failed=1; }
  printf '%-3s %-7s %-10s %-24s %-31s %s\n' "$s" "$oid" "$concern" "$finding" "$action" "$result"
done

[[ $failed -eq 0 ]] && echo "RULES OK — S1–S5 classified as expected" || { echo "RULES CHECK FAILED" >&2; exit 1; }
