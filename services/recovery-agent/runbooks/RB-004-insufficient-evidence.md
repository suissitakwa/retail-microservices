---
id: RB-004-insufficient-evidence
title: Not enough evidence to diagnose
applies_to: INSUFFICIENT_EVIDENCE
---

# Not enough evidence to diagnose

## When this applies
- A source did not answer (timeout, 5xx, malformed response). Its records are unknown — not absent.
- The question is about something no service records, e.g. "inventory was not decremented for this order":
  no service keeps order-linked stock movements, and current stock levels cannot show what one order did.
- A record the recovery depends on is missing, e.g. the order has no Stripe payment intent ID.

## What to do
1. Say exactly which evidence is missing and why it matters.
2. If a source was unavailable, retry the investigation once the service is healthy. Freshly started services
   can time out on their first requests.
3. Do not infer a cause from missing data, and do not propose an action.

## Do not
- Treat "no event observed" as "no event happened" — the observer only sees events after it started.
- Guess an inventory diagnosis from current stock levels.
