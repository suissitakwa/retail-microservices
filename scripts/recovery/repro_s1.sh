#!/usr/bin/env bash
# Reproduces scenario S1: order COMPLETED while payment stays PENDING.
#
# Seeds a PENDING order + PENDING payment, then delivers a signed payment_intent.succeeded
# webhook to order-service while payment-service is down. No Stripe API call is made.
#
# Usage: scripts/recovery/repro_s1.sh <env-file>
#   <env-file> must define STRIPE_WEBHOOK_SECRET (the same value order-service runs with).
set -euo pipefail

ENV_FILE="${1:?usage: $0 <env-file>}"
ORDER_SERVICE_URL="${ORDER_SERVICE_URL:-http://localhost:8085}"
PAYMENT_SERVICE_URL="${PAYMENT_SERVICE_URL:-http://localhost:8082}"
ORDER_DB_CONTAINER="${ORDER_DB_CONTAINER:-order-postgres-db}"
PAYMENT_DB_CONTAINER="${PAYMENT_DB_CONTAINER:-payment-postgres-db}"

# Read only the signing secret, literally (no sourcing: other values may contain spaces); never echo it.
WEBHOOK_SECRET="$(sed -n 's/^STRIPE_WEBHOOK_SECRET=//p' "$ENV_FILE" | tail -1 | tr -d '"'"'"'\r')"
[[ -n "$WEBHOOK_SECRET" ]] || { echo "STRIPE_WEBHOOK_SECRET missing in $ENV_FILE" >&2; exit 2; }

order_sql()   { docker exec -i "$ORDER_DB_CONTAINER"   psql -U order_user   -d order_db   -tAq -v ON_ERROR_STOP=1 -c "$1"; }
payment_sql() { docker exec -i "$PAYMENT_DB_CONTAINER" psql -U payment_user -d payment_db -tAq -v ON_ERROR_STOP=1 -c "$1"; }

# ── Preconditions ────────────────────────────────────────────────────────────
curl -sf "$ORDER_SERVICE_URL/actuator/health" >/dev/null \
  || { echo "order-service not reachable at $ORDER_SERVICE_URL" >&2; exit 2; }
if curl -s -o /dev/null --max-time 2 "$PAYMENT_SERVICE_URL/actuator/health"; then
  echo "payment-service is up at $PAYMENT_SERVICE_URL — stop it first, S1 needs it down" >&2; exit 2
fi
[[ "$(payment_sql "SELECT to_regclass('public.payments') IS NOT NULL")" == "t" ]] \
  || { echo "payments table missing — start payment-service once so Hibernate creates it" >&2; exit 2; }

# ── Seed ─────────────────────────────────────────────────────────────────────
TS="$(date +%s)"
ORDER_ID=$(( 900000 + TS % 90000 ))        # outside Hibernate's sequence range
REF="REPRO-S1-$TS"
PI_ID="pi_repro_s1_$TS"
AMOUNT="42.50"

order_sql "INSERT INTO retail_order (id, reference, customer_id, total_amount, stripe_session_id,
             stripe_payment_intent_id, payment_method, status, created_date)
           VALUES ($ORDER_ID, '$REF', 1, $AMOUNT, 'cs_repro_s1_$TS', '$PI_ID', 'STRIPE', 'PENDING', now())"

PAYMENT_ID=$(payment_sql "INSERT INTO payments (order_id, customer_id, amount, currency, status,
             stripe_session_id, order_reference, customer_email, created_at, updated_at)
           VALUES ($ORDER_ID, 1, $AMOUNT, 'usd', 'PENDING', 'cs_repro_s1_$TS', '$REF',
                   'repro@example.test', now(), now()) RETURNING id" | head -1)

echo "seeded order=$ORDER_ID payment=$PAYMENT_ID paymentIntent=$PI_ID"

# ── Deliver a signed payment_intent.succeeded ───────────────────────────────
PAYLOAD=$(cat <<JSON
{"id":"evt_repro_s1_$TS","object":"event","api_version":"2024-06-20","created":$TS,"livemode":false,"type":"payment_intent.succeeded","data":{"object":{"id":"$PI_ID","object":"payment_intent","amount":4250,"currency":"usd","status":"succeeded","livemode":false,"metadata":{"orderId":"$ORDER_ID"}}}}
JSON
)
SIG=$(printf '%s' "$TS.$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -hex | awk '{print $NF}')

HTTP=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$ORDER_SERVICE_URL/api/v1/orders/stripe/webhook" \
  -H 'Content-Type: application/json' -H "Stripe-Signature: t=$TS,v1=$SIG" --data-binary "$PAYLOAD")
echo "webhook -> HTTP $HTTP"

# ── Verify ───────────────────────────────────────────────────────────────────
ORDER_STATUS=$(order_sql "SELECT status FROM retail_order WHERE id=$ORDER_ID")
PAYMENT_STATUS=$(payment_sql "SELECT status FROM payments WHERE id=$PAYMENT_ID")
echo "order $ORDER_ID status=$ORDER_STATUS | payment $PAYMENT_ID status=$PAYMENT_STATUS"

if [[ "$HTTP" == "200" && "$ORDER_STATUS" == "COMPLETED" && "$PAYMENT_STATUS" == "PENDING" ]]; then
  echo "S1 REPRODUCED"
else
  echo "S1 NOT reproduced" >&2; exit 1
fi
