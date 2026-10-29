#!/usr/bin/env bash
# Day 4 check: store an investigation input for a seeded order from the real services.
#
# Needs: seed.sh already run; customer-service (:8083), order-service (:8085), payment-service (:8082)
# and recovery-agent (:8088) running locally, and the customer-db container up.
# Uses a local-only admin test account: registered through customer-service, then promoted to
# ROLE_ADMIN directly in the local customer-db (there is no admin sign-up flow). Token never printed.
#
# Usage: scripts/recovery/investigation_input_check.sh [orderId]   (default 800001 = S1)
set -euo pipefail

ORDER_ID="${1:-800001}"
CUSTOMER_URL="${CUSTOMER_URL:-http://localhost:8083}"
AGENT_URL="${AGENT_URL:-http://localhost:8088}"
CUSTOMER_DB_CONTAINER="${CUSTOMER_DB_CONTAINER:-customer-postgres-db}"

# Local dev admin test account — exists only in the local customer-db
ADMIN_EMAIL="recovery-admin@example.test"
ADMIN_PASSWORD="recovery-admin-local-only"

curl -s -o /dev/null -X POST "$CUSTOMER_URL/auth/register" -H 'Content-Type: application/json' \
  -d "{\"firstname\":\"Recovery\",\"lastname\":\"Admin\",\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" || true
docker exec -i "$CUSTOMER_DB_CONTAINER" psql -U customer_user -d customer_db -tAq -v ON_ERROR_STOP=1 \
  -c "UPDATE customer SET role='ROLE_ADMIN' WHERE email='$ADMIN_EMAIL'" >/dev/null

TOKEN=$(curl -sf -X POST "$CUSTOMER_URL/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["accessToken"])')

CREATED=$(curl -sf -X POST "$AGENT_URL/api/v1/recovery/investigation-inputs" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"orderId\":$ORDER_ID}")
INPUT_ID=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$CREATED")

STORED=$(curl -sf -H "Authorization: Bearer $TOKEN" "$AGENT_URL/api/v1/recovery/investigation-inputs/$INPUT_ID")

python3 - "$CREATED" "$STORED" <<'PY'
import json, sys
created, stored = json.loads(sys.argv[1]), json.loads(sys.argv[2])
print(f"input   {stored['id']}  order {stored['orderId']}  by {stored['requestedBy']}")
for name, src in stored["sources"].items():
    print(f"source  {name:<9} {src['status']}{'  ' + src['error'] if src.get('error') else ''}")
for eid in stored["evidenceIds"]:
    r = stored["records"][eid]
    print(f"record  {eid:<32} status={r.get('status', '-')}  intent={r.get('stripe_payment_intent_id') or '-'}")
ok = stored["evidenceIds"] == created["evidenceIds"] and stored["evidenceIds"]
print("INVESTIGATION INPUT STORED" if ok else "INVESTIGATION INPUT CHECK FAILED")
sys.exit(0 if ok else 1)
PY
