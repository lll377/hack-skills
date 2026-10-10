# PATTERN 1 — State Machine Skip (Workflow Bypass)

### The developer's assumption
*"Users will always arrive at step N through step N-1. The state is persisted server-side and validated at each transition."*

In practice: deadline pressure means developers validate the *entry* to a flow but not the *re-entry* at each step. They also often trust a client-side indicator (a cookie, a body parameter, a URL segment) as proof that prior steps completed.

### Where the assumption breaks
- Step 2 is skippable if step 3's endpoint does not verify that step 2's server-side record exists
- A completed flow can be re-entered at step 3 without re-completing step 2 — useful if step 2 is an identity check or payment
- Replaying step 1's response (status 200 + redirect token) while the flow is in step 3 causes the server to reset to step 1's state, bypassing step 2–3's guards

### Test sequence
```
1. Complete the flow legitimately once. Capture every request in Caido.
   Map: step → endpoint → required params → server-side state created

2. Start the flow fresh. Complete only step 1.

3. Directly POST to step 3's endpoint with the params from your legitimate run.
   Q: Does the server require step 2's state, or does it proceed?

4. If step 3 proceeds — replay step 3's final request with a fresh account
   that has never started the flow. Does it work?

5. Reorder test: complete 1 → 3 → 2 → 4 (swapping two middle steps).
   Some flows validate only "did you do step N-1" not "did you do all prior steps."
```

### Signal and chain
- **Positive**: Step N succeeds without step N-1's server-side record
- **False positive trap**: Some flows are stateless by design (idempotent APIs) — verify the skip *matters* (e.g. step 2 was an MFA check or a payment)
- **Chain**: If skipped step was payment → financial impact (Critical). If skipped step was identity verification → ATO chain. If skipped step was admin approval → privilege escalation.

### High-value targets
Checkout flows, KYC/identity verification, multi-step MFA enrollment, email confirmation gates, subscription upgrade flows, corporate approval workflows.

---
