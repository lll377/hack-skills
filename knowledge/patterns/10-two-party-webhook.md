# PATTERN 10 — Business Logic in Two-Party Flows (Webhooks, Callbacks)

### The developer's assumption
*"When Stripe/PayPal/Twilio sends us a webhook, we verify the signature and then process the event. The event data is trustworthy."*

In practice: the signature is verified but the event *type* or *amount* within the event is not cross-referenced against the expected state. Or: the webhook endpoint is reachable from the internet without signature verification on some paths.

### Where the assumption breaks
- Webhook replays: a legitimate `payment.succeeded` event can be replayed after a refund to re-credit the account
- Amount mismatch: the webhook says `amount: 1000` (cents) but the platform uses it directly as `amount: 1000` (dollars). Or an analyst can craft their own webhook if signature verification is skippable
- Event type forgery: if verification uses HMAC-SHA256 but the key is found in a JS bundle or `.env`, an analyst can craft any event
- Status promotion: `payment.pending` event processed before `payment.succeeded` arrives, and the system trusts the first event it sees (no state machine check)
- Idempotency key bypass: the platform deduplicates by idempotency key, but the key is derived from analyst-controlled input

### Test sequence
```
1. Identify all webhook endpoints from Phase B JS analysis and Phase D Wayback:
   /api/webhooks/stripe, /api/webhooks/paypal, /api/callbacks/twilio

2. Verify if the endpoint enforces signature validation:
   Send a POST with no signature header → does it process or reject?
   Send a POST with a malformed signature → does it process or reject?

3. If validation is present, check for the secret in Phase B secrets scan:
   python3 ~/work/Monte/tools/secret_scan.py loots/js/<host>/
   Look for: STRIPE_WEBHOOK_SECRET, WEBHOOK_KEY, HMAC_SECRET

4. If secret is found, craft a valid `payment.succeeded` event:
   Compute HMAC-SHA256(payload, secret) and send.
   Set amount to 1, observe if full access/credit is granted.

5. Test event replay:
   Capture a real webhook event (if you can complete a real payment).
   Re-send it with a new timestamp. Does the platform re-process it?

6. Test amount trust:
   If the payment amount comes from the webhook body (not looked up in DB),
   try sending a `payment.succeeded` with amount=1 for a $100 product.
```

### Signal and chain
- **Positive on signature bypass**: arbitrary event injection → full fraud capability (Critical)
- **Positive on replay**: duplicate credit → financial loss (High-Critical depending on value)
- **Chain**: Webhook bypass with valid secret → if the platform grants account upgrades on payment events, chain to free premium access for all accounts.

### High-value targets
E-commerce, SaaS subscriptions, fintech platforms, any application integrating Stripe/PayPal/Braintree/Twilio/SendGrid.

---
