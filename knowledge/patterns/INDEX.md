# Logic Patterns — Quick Index

> Load this file first. Then load **only** the pattern(s) matching your direction's class.
> Read-only library. Do not append cases here. Reusable methods go to `experience.jsonl` via `src_memory.py remember`.

| # | Pattern | File | When it fires |
|---|---------|------|---------------|
| 1 | State Machine Skip | `patterns/01-state-machine-skip.md` | multi-step flows where step N doesn't verify step N-1 |
| 2 | Race Condition (TOCTOU) | `patterns/02-race-toctou.md` | balance/coupon/quota + concurrent submits |
| 3 | Cross-Tenant IDOR | `patterns/03-cross-tenant-idor.md` | tenant ID in JWT but resolver trusts body |
| 4 | Privilege Escalation | `patterns/04-privilege-param-trust.md` | role/isAdmin in body trusted server-side |
| 5 | Price/Quantity Manipulation | `patterns/05-price-quantity.md` | negative qty, decimal price, currency swap |
| 6 | OAuth/Account Linkage | `patterns/06-oauth-linkage.md` | link-account trusts unverified email/sub |
| 7 | Limit/Rate Bypass | `patterns/07-limit-rate-bypass.md` | rate limit keyed on raw input |
| 8 | Coupon/Referral Abuse | `patterns/08-coupon-reward.md` | re-apply after refund, self-referral |
| 9 | Async Job IDOR | `patterns/09-async-job-idor.md` | job re-reads without re-auth |
| 10 | Webhook Two-Party | `patterns/10-two-party-webhook.md` | webhook trusts callback payload |
| 11 | LLM Passive Trust [EXP] | `patterns/11-llm-passive-trust.md` | agent treats retrieved content as instruction |

## Class → Pattern mapping

| Direction class | Load patterns |
|---|---|
| auth, auth-bypass, mfa-bypass | 1, 4, 6 |
| idor | 3, 9 |
| race, toctou | 2 |
| logic, business-logic | 1, 5, 7, 8 |
| oauth, sso, saml | 6 |
| price, economic | 5, 8 |
| webhook, callback | 10 |
| ai-llm, prompt-injection | 11 |
| privilege-escalation, authz | 4 |

## Cross-Pattern Chain Map

```
Pattern                    → Often chains to
──────────────────────────────────────────────────────────────────
State Machine Skip (1)     → Coupon Abuse (8), Limit Bypass (7)
Race Condition (2)         → Price Manipulation (5), Limit Bypass (7)
Cross-Tenant IDOR (3)      → Async Job IDOR (9)
Privilege Escalation (4)   → all patterns [now as admin]
Price Manipulation (5)     → Reward Abuse (8)
OAuth Interception (6)     → Privilege Escalation (4)
Limit Bypass (7)           → Async Job IDOR (9)
Webhook Logic (10)         → Price Manipulation (5)
```
