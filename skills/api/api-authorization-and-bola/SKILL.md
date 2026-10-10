---
name: api-authorization-and-bola
description: >-
  API authorization and BOLA testing playbook. Use when APIs expose object identifiers, nested resources, hidden writable fields, or weak function-level authorization.
---

# SKILL: API Authorization and BOLA — Object Access, Function Access, and Mass Assignment

> **AI LOAD INSTRUCTION**: Use this skill when an API exposes object IDs, nested resources, or role-sensitive functions and you need a focused authorization test path: BOLA, BFLA, method abuse, and hidden field control.

## 1. CORE TEST LOOP

1. Create Account A and Account B.
2. As Account A, capture create, read, update, and delete flows.
3. Replay with Account B's token.
4. Test sibling endpoints, nested endpoints, and alternate HTTP verbs.

## 2. TEST SURFACES

| Surface | Example |
|---|---|
| object read | `/api/v1/orders/123` |
| nested object | `/api/v1/users/1/invoices/9` |
| admin or internal function | `/api/v1/admin/users` |
| update path | `PUT`, `PATCH`, `DELETE` variants |
| hidden JSON fields | `role`, `org`, `verified`, `tier` |

## 3. QUICK PAYLOADS

```json
{"role":"admin"}
{"isAdmin":true}
{"org":"target-company"}
{"verified":true}
```

## 4. WHAT TESTERS MISS

- object IDs in headers, cookies, GraphQL args, and nested objects
- alternate methods sharing the same route but weaker authz
- parent check present, child resource check missing
- admin docs revealing extra writable fields

## 5. NEXT ROUTING

- For JWT or token-layer abuse: [jwt oauth token attacks](../../auth/jwt-oauth-token-attacks/SKILL.md)
- For GraphQL and hidden parameter discovery: [graphql and hidden parameters](../graphql-and-hidden-parameters/SKILL.md)
- For broader IDOR patterns outside APIs: [idor broken object authorization](../../auth/idor-broken-object-authorization/SKILL.md)

## 6. REAL SRC CHAIN: USER-ID LIST TO SESSION-HISTORY READ

- Reusable trigger: an API helper contains a user-controlled list query such as /api/sessions?userId=..., while the authenticated identity is also available from /currentUser.
- Minimal A/B verification: query the endpoint with the current user ID, then with one unrelated user ID exposed by a separate authorized leak. A 200 response whose objects contain the unrelated userId, session IDs, titles, timestamps, and message counts proves horizontal enumeration without any write action.
- Escalate only through read-only derived objects: take one returned session ID and test /api/history/{id}, /api/history/{id}/messages, and /api/images/session/{id}/all with both credentials include and credentials omit.
- Strong proof pattern: the derived endpoints return the target object under an authenticated unrelated account, and a separate no-cookie HTTP client also returns 200 with the same sensitive content and response length; store hashes rather than saving unnecessary full victim data.
- Report gate: require demonstrated cross-account access to another user private prompt/message/image history. Do not report the user-ID enumeration alone if it only exposes metadata without a sensitive read chain.

## 7. REAL SRC CASE

- Target: `https://9.jd.com/`
- Verified finding: anonymous `GET /super-api/api/v1/admin/toolbox/cards` returned `HTTP 200` with `code=200` and the full internal toolbox card config.
- Data exposed: `whitelistUsers` contained 137 unique internal whitelist identities, including phone-shaped IDs; `createBy`/`updateBy` exposed internal ERP logins.
- Verification signals: no Cookie needed; `GET /super-api/api/portal/currentUser` returned `isLogin=0`; arbitrary `Origin` still returned data.
- Key takeaway: after extracting JS API strings, directly probe `/api/v1/admin/*` and `/admin-api/*` anonymously; then inspect `whitelistUsers`, `createBy`, `updateBy`, `owner`, and similar identity-bearing fields instead of only looking for object-ID substitution.

## 8. ANONYMOUS API BASELINE BEFORE A/B TESTING

- Before setting up two accounts, run every JS-discovered profile, wallet, order, or admin GET through a fresh cookieless HTTP session. Clear the session, explicitly confirm no `Cookie` request header, and do not follow redirects.
- Repeat the request at least twice and compare status, content type, body length, body hash, and JSON field names. A stable 200 response with identity or asset fields is stronger than a single anomaly.
- A response can set a CSRF or session cookie after the request; that does not prove the request was authenticated. Do not replay that cookie unless explicitly testing a separate hypothesis.
- Classify the result separately: fixed-account data exposure, current-session data exposure, public configuration, or generic SPA content. Report fixed-account exposure only when fields such as real name, account identity, balances, order history, or tenant membership create business impact.
- Keep write methods out of this baseline. If the value of a field is unclear, record the field name and type for evidence and continue only with safe GET/OPTIONS validation.
