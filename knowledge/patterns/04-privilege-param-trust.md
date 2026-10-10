# PATTERN 4 — Privilege Escalation via Parameter Trust

### The developer's assumption
*"The role parameter in this request is just a hint for the UI — the server re-validates permissions from the JWT."*

In practice: during rapid feature development, a role parameter leaks from the prototype UI and never gets removed from the backend validation path. Or: the backend uses the JWT role for one check and the request parameter for another.

### Where the assumption breaks
- A `role=admin` or `is_admin=true` parameter in the request body that the backend reads and trusts
- The JWT contains a `plan: "free"` but the endpoint also accepts a `plan` parameter in the body — body wins
- An invitation link carries `role=editor` — changing to `role=admin` during acceptance gives admin access
- The `X-User-Role` or `X-Internal` header is forwarded by a misconfigured CDN and trusted by the backend

### Test sequence
```
1. Intercept the login/session-establishment request in Caido.
   Look for: role, plan, tier, is_admin, group, permission in the response JWT payload
   (decode with: echo "<jwt_payload>" | base64 -d)

2. On every subsequent privileged-feature API call, check the request:
   Does it send a role/plan parameter in the body or URL? Note it.

3. As a low-priv user, call a high-priv endpoint and add:
   {"role": "admin"}  or  ?plan=enterprise  or  X-User-Role: admin
   One parameter at a time. State the hypothesis before each probe.

4. Test invitation/onboarding flows specifically:
   Generate an invite link. Capture the link's parameters.
   Accept the invite after modifying role/permission parameters.

5. Test internal-header trust:
   X-Forwarded-For: 127.0.0.1
   X-Original-URL: /admin/dashboard
   X-Rewrite-URL: /admin/dashboard
   (Only if the WAF fingerprint suggests a proxy layer that might forward these)
```

### Signal and chain
- **Positive**: endpoint returns admin-level data or performs admin-level action after parameter injection
- **Chain**: Role escalation → if admin panel has user management, chain to mass ATO. If admin panel has API key management, chain to credential theft. These are Critical.

### High-value targets
SaaS applications with a free/paid tier distinction, invitation-based onboarding flows, corporate apps with role-based feature gates, anything using JWT with role claims.

---
