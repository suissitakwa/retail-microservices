#!/usr/bin/env bash
# Seeds recovery scenarios S1–S5 (see SCENARIOS.md) directly into order-db and payment-db.
#
# Idempotent: every run deletes and re-creates its own rows (references RCV-S1..RCV-S5,
# order IDs 800001–800005), so eval cases can refer to stable IDs. No service needs to be
# running — only the two DB containers, with tables already created by each service once.
#
# Usage: scripts/recovery/seed.sh
set -euo pipefail

ORDER_DB_CONTAINER="${ORDER_DB_CONTAINER:-order-postgres-db}"
PAYMENT_DB_CONTAINER="${PAYMENT_DB_CONTAINER:-payment-postgres-db}"

order_sql()   { docker exec -i "$ORDER_DB_CONTAINER"   psql -U order_user   -d order_db   -tAq -v ON_ERROR_STOP=1 -c "$1"; }
payment_sql() { docker exec -i "$PAYMENT_DB_CONTAINER" psql -U payment_user -d payment_db -tAq -v ON_ERROR_STOP=1 -c "$1"; }

# ── Preconditions ────────────────────────────────────────────────────────────
[[ "$(order_sql "SELECT to_regclass('public.retail_order') IS NOT NULL")" == "t" ]] \
  || { echo "retail_order table missing — start order-service once so Hibernate creates it" >&2; exit 2; }
[[ "$(payment_sql "SELECT to_regclass('public.payments') IS NOT NULL")" == "t" ]] \
  || { echo "payments table missing — start payment-service once so Hibernate creates it" >&2; exit 2; }

# ── Reset this script's rows only ────────────────────────────────────────────
order_sql "DELETE FROM order_item WHERE order_id IN (SELECT id FROM retail_order WHERE reference LIKE 'RCV-S%');
           DELETE FROM retail_order WHERE reference LIKE 'RCV-S%'"
payment_sql "DELETE FROM payments WHERE order_reference LIKE 'RCV-S%'"

# seed <scenario> <order_status> <order_total> <order_intent|NULL> <payment_status> <payment_amount> <payment_intent|NULL>
seed() {
  local s="$1" order_status="$2" order_total="$3" order_pi="$4" pay_status="$5" pay_amount="$6" pay_pi="$7"
  local n="${s#S}" id=$((800000 + ${s#S})) ref="RCV-$s"
  local opi="NULL" ppi="NULL"
  [[ "$order_pi" != NULL ]] && opi="'$order_pi'"
  [[ "$pay_pi"   != NULL ]] && ppi="'$pay_pi'"

  order_sql "INSERT INTO retail_order (id, reference, customer_id, total_amount, stripe_session_id,
               stripe_payment_intent_id, payment_method, status, created_date)
             VALUES ($id, '$ref', 1, $order_total, 'cs_rcv_s$n', $opi, 'STRIPE', '$order_status', now());
             INSERT INTO order_item (id, order_id, product_id, product_name, quantity, price)
             VALUES ($id, $id, 1, 'Recovery scenario item', 1, $order_total)"

  payment_sql "INSERT INTO payments (order_id, customer_id, amount, currency, status, stripe_session_id,
                 stripe_payment_intent_id, order_reference, customer_email, created_at, updated_at)
               VALUES ($id, 1, $pay_amount, 'usd', '$pay_status', 'cs_rcv_s$n', $ppi, '$ref',
                       'recovery-$n@example.test', now(), now())" >/dev/null
}

# S1: confirm call lost after the order committed — the payment never learned the intent ID
seed S1 COMPLETED 42.50 pi_rcv_s1   PENDING 42.50 NULL
# S2: payment ahead of order — agent must not act on the order side
seed S2 PENDING   30.00 pi_rcv_s2   PAID    30.00 pi_rcv_s2
# S3: consistent end state after a duplicate webhook delivery (replay itself is tested on Day 9)
seed S3 COMPLETED 25.00 pi_rcv_s3   PAID    25.00 pi_rcv_s3
# S4: consistent payment state; the "inventory not decremented" claim lives in the eval case
seed S4 COMPLETED 18.00 pi_rcv_s4   PAID    18.00 pi_rcv_s4
# S5: conflicting records — intent IDs and amounts disagree
seed S5 COMPLETED 60.00 pi_rcv_s5_a PENDING 55.00 pi_rcv_s5_b

# ── Read back and verify ─────────────────────────────────────────────────────
expected=(
  "S1|800001|COMPLETED|42.50|pi_rcv_s1|PENDING|42.50|"
  "S2|800002|PENDING|30.00|pi_rcv_s2|PAID|30.00|pi_rcv_s2"
  "S3|800003|COMPLETED|25.00|pi_rcv_s3|PAID|25.00|pi_rcv_s3"
  "S4|800004|COMPLETED|18.00|pi_rcv_s4|PAID|18.00|pi_rcv_s4"
  "S5|800005|COMPLETED|60.00|pi_rcv_s5_a|PENDING|55.00|pi_rcv_s5_b"
)

printf '%-4s %-8s %-10s %-8s %-12s %-8s %-9s %-8s %s\n' \
  scen order_id order total order_pi pay_id payment amount payment_pi
failed=0
for row in "${expected[@]}"; do
  IFS='|' read -r s id exp_os exp_ot exp_opi exp_ps exp_pa exp_ppi <<<"$row"
  IFS='|' read -r os ot opi <<<"$(order_sql "SELECT status, total_amount, coalesce(stripe_payment_intent_id,'') FROM retail_order WHERE id=$id")"
  IFS='|' read -r pid ps pa ppi <<<"$(payment_sql "SELECT id, status, amount, coalesce(stripe_payment_intent_id,'') FROM payments WHERE order_id=$id AND order_reference='RCV-$s'")"
  printf '%-4s %-8s %-10s %-8s %-12s %-8s %-9s %-8s %s\n' "$s" "$id" "$os" "$ot" "${opi:--}" "$pid" "$ps" "$pa" "${ppi:--}"
  if [[ "$os|$ot|$opi|$ps|$pa|$ppi" != "$exp_os|$exp_ot|$exp_opi|$exp_ps|$exp_pa|$exp_ppi" ]]; then
    echo "  ^ $s does not match expected seed" >&2; failed=1
  fi
done

[[ $failed -eq 0 ]] && echo "seeded S1–S5" || { echo "seed verification FAILED" >&2; exit 1; }
