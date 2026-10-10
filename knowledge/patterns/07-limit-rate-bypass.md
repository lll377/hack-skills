# PATTERN 7 — Limit and Rate Bypass

### The developer's assumption
*"We check the count before allowing the action. If it exceeds the limit, we block."*

In practice: limits are checked at the application layer, not enforced atomically at the data layer. Or: the same action is available through multiple endpoints, only one of which checks the limit. Or: the limit resets under predictable conditions.

### Where the assumption breaks
- The limit counter is in a cache (Redis) that is separate from the database — race condition between cache check and database write
- Endpoint A checks limits, endpoint B (legacy or internal) does not — same underlying action
- The limit is per-day, and the day boundary is in UTC but the frontend shows local time — exploitable in the transition window
- Deleting a resource decrements the counter; re-creating it does not increment if deletion event was not processed
- Trial limits are enforced on the UI only — the API accepts calls beyond the limit

### Test sequence
```
1. Identify the limit: what is the cap? (Phase A business model analysis)
   Common limits: API calls/day, seats/org, file uploads/month, exports/week

2. Find ALL endpoints that perform the limited action:
   (Phase B JS analysis — search for the action name in all bundles)
   Often: /api/v1/export AND /api/v2/export AND /internal/export

3. Test the limit on the primary endpoint: reach N-1 uses.
   On the Nth call: does it block correctly?

4. On the (N+1)th call: try the alternative endpoint, or add/remove a header,
   or change the Content-Type, or switch from POST to PUT.

5. Race test: simultaneously send N+5 requests at the N-1 state.
   How many succeed?

6. Deletion test: use 5 of 5 slots. Delete all 5 resources.
   Re-create 5. Are they counted again from 0 or is the lifetime limit enforced?
```

### Signal and chain
- **Positive**: action succeeds beyond the stated limit
- **Business impact anchor**: a "5 seats" limit bypass → an analyst can invite 500 users for free; the vendor loses 495 seats of revenue. Quantify this in the impact statement.
- **Chain**: Limit bypass on trial → full Enterprise tier access without payment (High). API rate bypass → scraping protection eliminated, often pairs with IDOR for mass data extraction (Critical).

### High-value targets
SaaS with seat limits, API-as-a-product (pay-per-call), storage-limited plans, export/download gating on analytics platforms, anti-abuse features (OTP rate limiting, login attempt caps).

---
