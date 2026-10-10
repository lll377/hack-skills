# PATTERN 3 — Cross-Tenant IDOR (Multi-Tenant Boundary Failure)

### The developer's assumption
*"The user's org_id is in their JWT/session. We always filter queries by org_id, so they can only see their own data."*

In practice: junior developers use the org_id from the JWT for read endpoints (safe) but forget it on write, bulk-export, or async/background endpoints. GraphQL resolvers are particularly prone to per-field inconsistency.

### Where the assumption breaks
- The tenant identifier is passed in the request body or URL, not the JWT — and the server trusts the one from the request
- Bulk export endpoints accept a list of IDs and validate the first but not all
- The `include` / `expand` query parameter on a resource returns nested objects that belong to other tenants
- WebSocket subscriptions that push updates don't re-check tenant at message delivery time
- Admin APIs that were meant to be internal-only but are reachable from the public facing domain

### Test sequence
```
1. Establish two accounts in different orgs: userA (org_id=ORG_A), userB (org_id=ORG_B).
   (Use personas.json to track cookies)

2. As userA, create a resource. Note its ID (e.g. report_id=500).

3. As userB, attempt to read that resource:
   GET /api/reports/500
   Cookie: [userB's session]
   Expected: 403 or 404. If 200 with data → IDOR confirmed.

4. As userB, attempt to mutate: PUT/DELETE /api/reports/500
   Higher impact than read — confirm separately.

5. Test the expand/include vector:
   GET /api/orders/MY_ORDER?include=customer
   Does the nested "customer" object respect tenant isolation?

6. Test bulk operations:
   POST /api/reports/export {"ids": [MY_ID, THEIR_ID_500]}
   Does the response include data for THEIR_ID?

7. GraphQL: query for fields across resolvers using a single query.
   Some resolvers check tenant, some don't — field-level inconsistency is common.
```

### Signal and chain
- **Positive**: userB receives userA's data with a 200 response and full body
- **Near-miss to dismiss**: userB gets a 200 but with empty/null body — server knows to filter, just responds 200 instead of 403
- **Chain**: Read IDOR → if leaked object contains PII, chain to mass data breach. Write IDOR → data integrity violation (often Critical on SaaS). Delete IDOR → availability impact (DoS-adjacent, usually High).

### High-value targets
SaaS platforms (CRM, HR tools, project management, analytics dashboards), multi-tenant APIs, platforms with "teams" or "organizations" model, any system with a shared data layer.

---
