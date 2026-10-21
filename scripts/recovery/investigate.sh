#!/usr/bin/env bash
# Runs one read-only investigation against the live stack and prints the result and its trace.
#
# Needs the same stack as investigation_input_check.sh; for a model-backed result, recovery-agent must
# run with OPENAI_API_KEY set (otherwise it returns the rules baseline).
#
# Usage: scripts/recovery/investigate.sh <orderId> [PAYMENT|INVENTORY]
set -euo pipefail

ORDER_ID="${1:?usage: $0 <orderId> [PAYMENT|INVENTORY]}"
CONCERN="${2:-PAYMENT}"
CUSTOMER_URL="${CUSTOMER_URL:-http://localhost:8083}"
AGENT_URL="${AGENT_URL:-http://localhost:8088}"
CUSTOMER_DB_CONTAINER="${CUSTOMER_DB_CONTAINER:-customer-postgres-db}"

# Local dev admin test account — same one the other check scripts use
ADMIN_EMAIL="recovery-admin@example.test"
ADMIN_PASSWORD="recovery-admin-local-only"

curl -s -o /dev/null -X POST "$CUSTOMER_URL/auth/register" -H 'Content-Type: application/json' \
  -d "{\"firstname\":\"Recovery\",\"lastname\":\"Admin\",\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" || true
docker exec -i "$CUSTOMER_DB_CONTAINER" psql -U customer_user -d customer_db -tAq -v ON_ERROR_STOP=1 \
  -c "UPDATE customer SET role='ROLE_ADMIN' WHERE email='$ADMIN_EMAIL'" >/dev/null
TOKEN=$(curl -sf -X POST "$CUSTOMER_URL/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["accessToken"])')

ID=$(curl -sf -X POST "$AGENT_URL/api/v1/recovery/investigations" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"orderId\":$ORDER_ID,\"concern\":\"$CONCERN\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')


BODY=$(curl -sf -H "Authorization: Bearer $TOKEN" "$AGENT_URL/api/v1/recovery/investigations/$ID?include_trace=true")

python3 - "$BODY" <<'PY'
import json, sys
b = json.loads(sys.argv[1]); t = b["trace"]; m = t.get("model") or {}
fallback = f"  fallback={b['fallbackReason']}" if b.get("fallbackReason") else ""
print(f"investigation {b['id']}  order {b['orderId']}  concern {b['concern']}  {b['latencyMs']} ms")
print(f"finding       {b['finding']}   source={b['source']}{fallback}")
print(f"action        {b['recommendedAction']}   manualReview={b['requiresManualReview']}")
print(f"runbook       {b['runbookId']}")
print(f"evidence      {b['evidenceIds']}")
print(f"explanation   {b['explanation']}")
if b.get("uncertainty"):
    print(f"uncertainty   {b['uncertainty']}")
print(f"retrieved     {[(r['runbook_id'][:6], r['section'], round(r['score'], 3)) for r in t['retrieved']]}")
print(f"model         {m.get('name')}  in={m.get('inputTokens')} out={m.get('outputTokens')}  error={m.get('error')}")
print(f"validation    {t['validationErrors'] or 'ok'}")
print(f"timings ms    {t['timingsMs']}")
PY
