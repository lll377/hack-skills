# PATTERN 2 — Race Condition (TOCTOU)

### The developer's assumption
*"Users won't send the same request twice in the same millisecond. Even if they do, the database transaction will serialize them correctly."*

In practice: checks happen in application code before the write, not atomically inside the database transaction. The window between check and write is exploitable under parallel load.

### Where the assumption breaks
- Single-use tokens (coupons, invite codes, gift cards) checked before update — not inside the same transaction
- Balance checks ("do you have enough credit?") that happen 50ms before the debit
- Rate-limit counters incremented after the action, not before
- "First come first served" slots that accept N+1 requests before incrementing

### Test sequence
```
# Use ~/work/Monte/tools/harness/race.py — NOT Caido Intruder
# race.py sends HTTP/2 synchronized frames; Intruder serializes

1. Identify the check-then-act pattern in Caido history:
   GET /api/coupon/validate?code=SAVE50 → 200 {"valid": true}
   POST /api/coupon/redeem {"code": "SAVE50"} → applies discount

2. race.py the redemption — 20 parallel requests, same coupon code, same session:
   python3 ~/work/Monte/tools/harness/race.py \
     --url https://target.com/api/coupon/redeem \
     --method POST \
     --body '{"code":"SAVE50"}' \
     --cookie "session=YOUR_SESSION" \
     --parallel 20

3. Inspect: how many returned 200? If >1, the coupon was applied N times.

4. Verify with a fresh account and a fresh code — confirm it is the race,
   not a per-user limit bug. Both must reproduce.
```

### Signal and chain
- **Positive**: >1 success response for a should-be-single-use action
- **False positive trap**: Some systems genuinely allow multiple uses — check the business intent (scope.md, terms, Phase A business model notes)
- **Chain**: Coupon race → financial loss (Medium→High). Balance race → double-spend (Critical on financial products). Slot race → unfair advantage (usually Low unless financial).

### High-value targets
Coupon/promo redemption, referral bonus claim, gift card redemption, crypto withdraw/transfer, limited inventory purchase, trial-to-paid conversion, account credit application.

---
