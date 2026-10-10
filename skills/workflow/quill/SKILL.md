---
name: quill
description: >-
  Report-writing quality only (impact-first, no hedging). Write the Word file by hand. One finding, one docx.
  Do not redact cookies in reports or evidence.
---

## Load Gate（hack-skills）

本篇从 Monte-Workshop **复制并适配**，不是默认开工 skill。硬规则在仓库根目录 `AGENTS.md`。本文件只读，经验只进 `experience.jsonl`。

- 默认开工仍是 `business-logic-vuln` + `knowledge/logic_first.md`。map.md 里已经有 Anomaly，才开本篇；同时 `bin/python tools/src_memory.py recall --skill quill`（≤5）。
- 工具：Burp 8080 + Playwright MCP（代理 http://127.0.0.1:8080，配置目录 works/.playwright-profile）。走路、登录、点击、截图用 Playwright MCP。截图必须能看见完整 URL。变形用 Burp Repeater / MCP。
- 出报告手写 Word，一洞一份，放到 `works/<项目>/reports/`。Burp 原文贴进报告，禁止打码。不要调用已删除的报告脚本。Monte `/remember` 对应 `src_memory.py remember`。资产已在 `works/<项目>/url.txt`。
- 只做读侧。禁止 PUT/DELETE/改密/下单/支付/webshell。查询 POST/JSON/GraphQL/导出可以。
- **未导入** `recon`、`web3`。禁止当子域扫描管线；禁止把 JS/CDN/GSLB 新主机自动入队（范围内且用户点头才能加）。
- 国内 SRC：范围看 `works/<项目>/规则.md`。报告门槛=他人数据 / 钱券积分库存 / 不该有的权限。对用户说话不贴 Cookie。
- 字典优先本仓库 `wordlist/`。密钥扫描脚本：`bin/python tools/secret_scan.py`。
- 何时开：`triage` 7 问过了，要写标题/危害/步骤文案。本篇只管文案质量。Word 手写。报告和 evidence **禁止打码** Cookie/Token/Host/参数（与 Monte 原文相反）。截图用 Playwright MCP，保存到 `works/<项目>/evidence/`，插入资产/复现/危害处。图内必须能看见完整 URL。国内 SRC 不用 H1/Bugcrowd 平台模板交稿。

---
# REPORT WRITING

Impact-first. Human tone. No theoretical language. Triagers are people.

---

## THE FIVE COMMANDMENTS — read before every report

1. **Short.** Report body < 400 words (excluding screenshots). One paragraph summary, numbered steps, impact. Done. A triager who needs to scroll past page 2 is already skeptical.
2. **Proved, not theorized.** Every claim in the report has a request+response pair behind it. If you write it but didn't capture it, delete the sentence. No "could", "may", "potentially", "theoretically".
3. **Visual evidence is non-negotiable.** Every key step gets a screenshot: the request being sent (Burp Repeater / Chrome DevTools), the response proving impact, the browser showing cross-tenant data. A report without screenshots is a report the triager closes.
4. **Reproducible in 3 minutes.** A triager who has never seen this target copies your curl, pastes it, and sees the bug. If your steps require guessing, the report fails. Each step ends with `Observe:` naming exactly what they should see.
5. **Plain language.** No "leveraging", "weaponizing", "attack surface", "threat actor". Say what happened in words a product manager understands. The triager is not impressed by jargon — they are impressed by clarity.

---

## THE MOST IMPORTANT RULE

> **Never use "could potentially" or "could be used to" or "may allow".**
> Either it does the thing or it doesn't. If you haven't proved it, don't claim it.

```
BAD:  "This vulnerability could potentially allow an attacker to access user data."
GOOD: "An attacker can access any user's order history by changing the user_id
       parameter to the target user's ID. I confirmed this using two test accounts:
       attacker@test.com (ID 123) successfully retrieved victim@test.com (ID 456)
       orders, including their shipping address and payment method last 4 digits."
```

---

## TITLE FORMULA

```
[Bug Class] in [Exact Endpoint/Feature] allows [attacker role] to [impact] [victim scope]
```

**Good titles (specific, impact-first):**
```
IDOR in /api/v2/invoices/{id} allows authenticated user to read any customer's invoice data
Missing auth on POST /api/admin/users allows unauthenticated attacker to create admin accounts
Stored XSS in profile bio field executes in admin panel — allows privilege escalation
SSRF via image import URL parameter reaches AWS EC2 metadata service
Race condition in coupon redemption allows same code to be used unlimited times
```

**Bad titles (vague, useless to triager):**
```
IDOR vulnerability found
Broken access control
XSS in user input
Security issue in API
Unauthorized access to user data
```

---

## HACKERONE REPORT TEMPLATE

```markdown
## Summary

[One paragraph: what the bug is, where it is, what an attacker can do. Be specific.
Include: endpoint, method, parameter, data exposed, required access level.]

Example: "The `/api/users/{user_id}/orders` endpoint does not verify that the
authenticated user owns the requested user_id. An attacker can enumerate any
user's order history, including PII (email, address, phone) and purchase history,
by incrementing the user_id parameter. No privileges beyond a standard free
account are required."

## Vulnerability Details

**Vulnerability Type:** IDOR / Broken Object Level Authorization
**CVSS 3.1 Score:** 6.5 (Medium) — AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N
**Affected Endpoint:** GET /api/users/{user_id}/orders

## Steps to Reproduce

**Environment:**
- Attacker account: attacker@test.com, user_id = 123
- Victim account: victim@test.com, user_id = 456
- Target: https://target.com

**Steps:**

1. Log in as attacker@test.com, obtain Bearer token

2. Send the following request:

```
GET /api/users/456/orders HTTP/1.1
Host: target.com
Authorization: Bearer ATTACKER_TOKEN_HERE
```

3. Observe response:

```json
{
  "orders": [
    {"id": 789, "items": [...], "email": "victim@test.com", "address": "123 Main St..."}
  ]
}
```

The response contains victim's full order history and PII despite being requested
by a different user.

## Impact

An authenticated attacker can enumerate all user orders by iterating user_id values.
This exposes: full name, email, shipping address, purchase history, and payment
method (last 4). With ~100K users, this represents a mass PII breach affecting
all registered users. Exploitation requires only a free account and takes minutes
with a simple loop.

## Recommended Fix

Add server-side ownership verification:
```python
if order.user_id != current_user.id:
    raise Forbidden()
```

## Supporting Materials

[Screenshot showing attacker's session returning victim's order data]
[Video walkthrough if available]
```

---

## BUGCROWD REPORT TEMPLATE

```markdown
# [IDOR] User order history accessible without authorization via /api/users/{id}/orders

**VRT Category:** Broken Access Control > IDOR > P2

## Description

[Same impact-first paragraph as HackerOne summary]

## Steps to Reproduce

[Same structured steps — exact HTTP requests, exact responses]

## Proof of Concept

[Screenshot/video showing the actual impact]

## Expected vs Actual Behavior

**Expected:** 403 Forbidden when user_id does not match authenticated user
**Actual:** 200 OK with victim's full order data

## Severity Justification

P2 (High) — Direct read access to other users' PII. Affects all user accounts.
No user interaction required. Exploitable by any authenticated user.
Automated enumeration could exfil all [N] user records in minutes.

## Remediation

Add ownership verification: `if order.user_id != current_user.id: raise 403`
```

---

## INTIGRITI REPORT TEMPLATE

```markdown
# [Bug Class]: [Exact Impact] in [Endpoint/Feature]

## Description

[Impact-first paragraph. Start with what an attacker can do, not with how you found it.
Include: endpoint, method, parameter, data exposed, required privileges.]

## Steps to Reproduce

**Environment:**
- Attacker: email=attacker@test.com (standard account, no special role)
- Victim: email=victim@test.com
- Tested: [date]

**Reproduction steps:**

1. [Login as attacker / visit URL / send request]

2. Send the following HTTP request:

\```http
METHOD /endpoint HTTP/1.1
Host: target.com
Authorization: Bearer ATTACKER_TOKEN
Content-Type: application/json

{"param": "victim_id_here"}
\```

3. Observe response contains victim's private data:

\```json
{"email": "victim@test.com", "address": "123 Main St", ...}
\```

## Impact

[Specific, quantified impact. What data, how many users, what can attacker do.]

CVSS 3.1 Score: X.X ([Severity]) — AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N

## Remediation

[1-3 sentence concrete fix. Include code if helpful.]

## Attachments

[Screenshot or Loom video showing the impact — Intigriti triagers prefer video for complex bugs]
```

**Intigriti-specific notes:**
- Title format: `[Bug Class]: [One-line impact]` (no formula required, but keep it specific)
- Severity is set by you: Critical/High/Medium/Low/Exceptional
- CVSS 3.1 is standard (CVSS 4.0 also accepted on newer programs)
- PoC video is valued much more than screenshot alone — record with Loom
- Safe harbor: Intigriti enforces it, be comfortable going slightly aggressive with testing

---

## IMMUNEFI REPORT TEMPLATE

```markdown
# [Bug Class] — [Protocol Name] — [Severity]

## Summary

[One paragraph with: root cause, affected function, economic impact, attack cost.
Include numbers where possible: "attacker can drain $X in Y transactions."]

## Vulnerability Details

**Contract:** `VulnerableContract.sol`
**Function:** `claimRedemption()`
**Bug Class:** Accounting State Desynchronization
**Severity:** Critical

### Root Cause

[Exact code snippet showing the vulnerable code with comments]

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
// Foundry PoC — run: forge test --match-test test_exploit -vvvv

contract ExploitTest is Test {
    // ... full working exploit
}
```

## Impact

[Quantified: "Attacker can drain X% of TVL = $Y at current rates.
Requires $Z gas. Attack is repeatable."]

## Recommended Fix

[Specific code change with before/after]
```

---

## CVSS / SEVERITY REFERENCE

CVSS 3.1 metric guide, severity tiers (Critical/High/Medium/Low), score examples by bug class, and downgrade counters all live in `triage` skill（`skills/triage/`） — load it alongside this one. Don't duplicate; derive the vector from OBSERVED ledger rows only.

---

## THE 60-SECOND PRE-SUBMIT CHECKLIST

```
[ ] Title follows formula: [Class] in [endpoint] allows [actor] to [impact]
[ ] First sentence states exact impact in plain English
[ ] Steps to Reproduce has exact HTTP request (copy-paste ready)
[ ] EVERY step ends with an "Observe:" block naming what the triager should see
[ ] Response showing the bug is included — screenshot of the HTTP response + the JSON/HTML body inline
[ ] Request screenshot included — Burp Repeater or Chrome DevTools Network showing what was sent
[ ] Browser screenshot included (if UI-visible bug) — URL bar visible, active session identified
[ ] Each screenshot caption says what it PROVES, not what it shows
[ ] Two test accounts used — never one account testing itself
[ ] Two-account proof shown for auth/IDOR-class: attacker request + victim data in response
[ ] CVSS score calculated, each metric backed by a captured artifact
[ ] Recommended fix is 1-2 sentences — not a security lecture
[ ] Report body < 400 words (excluding screenshots) — if longer, cut
[ ] Every sentence is a FACT backed by evidence — no speculation, no hedging
[ ] grep for "could", "may", "might", "potentially", "theoretically" — delete every hit
[ ] PoC reproduces from a FRESH state (logout, clear cookies, re-run)
[ ] 报告和 evidence 禁止打码 Cookie/Token/Host/参数；对用户说话不贴 Cookie
```

---

## CVSS 4.0 QUICK REFERENCE (newer programs)

CVSS 4.0 replaced CVSS 3.1 in November 2023. Some newer programs require it.

### Key Differences from CVSS 3.1

| Metric | CVSS 3.1 | CVSS 4.0 |
|---|---|---|
| Attack Vector | Network/Adjacent/Local/Physical | Same |
| Attack Complexity | Low/High | Low/High |
| **NEW**: Attack Requirements | (didn't exist) | None/Present (replaces some PR/UI) |
| Privileges Required | None/Low/High | Same |
| User Interaction | None/Required | None/Passive/Active |
| Scope | Unchanged/Changed | REMOVED |
| **NEW**: Sub-Impact metrics | (didn't exist) | Vulnerable/Subsequent system impact |

### CVSS 4.0 Score Examples

| Finding | CVSS 4.0 Score | Vector |
|---|---|---|
| Unauthenticated RCE | 10.0 | CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H |
| IDOR read PII, auth required | 6.9 | CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N |
| Stored XSS, admin views it | 8.2 | CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:P/VC:H/VI:H/VA:N/SC:H/SI:H/SA:N |
| SSRF → cloud metadata | 8.7 | CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:H/SI:H/SA:N |

### Quick CVSS 4.0 Calculator
```
Use: https://www.first.org/cvss/calculator/4.0
Key fields:
  VC/VI/VA = Vulnerable System Confidentiality/Integrity/Availability
  SC/SI/SA = Subsequent System (downstream impact)
  AT = None (no special condition) | Present (race/specific config needed)
  UI = None | Passive (victim visits URL) | Active (victim takes explicit action)
```

**Practical rule**: If program uses CVSS 4.0 and you don't know the vector, use the calculator and include the full string starting with `CVSS:4.0/AV:...`. Programs cannot dispute a valid vector string.

---

## HUMAN TONE GUIDELINES

**Write to a person, not a system:**
- Triagers are tired. Get to the impact in sentence 1.
- Use "I" not "the researcher" — you found it, own it
- Short paragraphs, bullet points for steps
- Hyperlink relevant docs if needed

**Escalation language (when payout is being downgraded):**
```
"This vulnerability does not require any special privileges — only a free account."
"The exposed data includes [PII type], which is subject to GDPR requirements."
"An attacker can automate this with a simple loop — all [N] records in minutes."
"This is exploitable externally without network access to any internal system."
"The impact is equivalent to a full data breach of [feature/data type]."
```

**Kill on sight:**
- Jargon the triager might not know ("attack surface", "threat vector", "lateral movement")
- Explaining what a bug class IS (they know what IDOR is — show the proof, skip the lecture)
- Theoretical chains ("could be combined with X to...") — if you chained it, show the chain; if you didn't, don't claim it
- Passive voice ("it was observed that...") — say who did what
- Qualifying language ("seems to," "appears to," "potentially") — prove it or delete the sentence
- Wall-of-text paragraphs — 3 sentences max per paragraph; prefer bullet points
- Describing what a screenshot shows ("Screenshot of Caido") — say what it PROVES ("attacker session reads victim invoice")

---

## STEPS TO REPRODUCE FORMAT (triager-optimized)

**Rule:** every numbered step ends with an `Observe:` block naming what the triager should see — a status code, a header, a JSON field, a UI element. A step the triager cannot verify in isolation is a step they will skip, and a skipped step is the one they'll dispute. Pair each step with a screenshot when a UI surface is involved.

```markdown
**Setup:**
- Account A (attacker): email=attacker@test.com, ID=111
- Account B (victim): email=victim@test.com, ID=222
- Both created via normal registration — no special access
- Browser: Firefox 128 (used for Account A in window 1, Account B in window 2)
- Proxy: Burp 8080 (request/response capture)
- Date tested: 2026-05-23

**Steps:**

1. Log in to https://target.com as Account A (attacker@test.com).
   Observe:
   - URL bar redirects to /dashboard after login
   - Network tab shows POST /api/auth/login → 200 with `Set-Cookie: session=...`
   - Top-right avatar shows "attacker@test.com"
   Screenshot: screenshots/01-attacker-logged-in.png

2. In the same browser, send this request (replace `111` with victim ID `222`):

\```
GET /api/v2/resource/222 HTTP/1.1
Host: target.com
Authorization: Bearer ACCOUNT_A_TOKEN
\```

   Observe:
   - Status line: `HTTP/1.1 200 OK` (not 403, not 404)
   - Response `Content-Type: application/json`
   - Response body field `id` equals `222` — the victim's ID, not the attacker's `111`
   - Response body field `email` equals `victim@test.com`
   Screenshot: screenshots/02-caido-cross-tenant-response.png

3. To prove the data belongs to Account B, log in to https://target.com as Account B (victim@test.com) in a private window. Open the same `/api/v2/resource/222` from B's session.
   Observe:
   - Response body field `email` matches step 2 exactly (`victim@test.com`)
   - Response body field `address` matches step 2 character for character
   - Conclusion: the data Account A saw in step 2 is verifiably Account B's private record.
   Screenshot: screenshots/03-victim-session-same-data.png

**Expected:** Step 2 returns 403 Forbidden (resource owned by user 222, requested by user 111).
**Actual:** Step 2 returns 200 OK with victim's private data — server does not check ownership before responding.
```

---

## BROWSER SCREENSHOT CAPTURE

A screenshot a triager can read in 5 seconds saves 5 paragraphs of prose. These are the conventions that make screenshots evidence rather than decoration.

### When to capture (per finding class)

| Finding class | Mandatory screenshots |
|---|---|
| IDOR / BOLA / auth bypass | (1) attacker session logged in, (2) request being sent with attacker token, (3) response showing victim data, (4) victim's own view of the same data (proves it's really theirs) |
| Stored XSS | (1) payload-injection request, (2) victim's browser executing the payload (alert / DOM mutation / cookie exfil destination) |
| Reflected XSS | (1) full URL in address bar, (2) DOM showing payload executed |
| CSRF | (1) attacker page hosting the form, (2) victim's logged-in tab after the click, (3) server-side state change confirmed (admin panel / DB view) |
| SSRF / RCE | (1) Caido request with the payload, (2) response containing the exfiltrated data (metadata creds, internal hostname, etc.) |
| Auth / MFA bypass | (1) bypassed auth gate, (2) authenticated-only resource now reachable |
| Race condition | (1) script output showing concurrent winners, (2) two independent state mutations both persisted (e.g. account balance, two valid tokens) |
| Information disclosure | (1) the public URL in the address bar, (2) the sensitive content rendered |
| GraphQL / API misconfig | (1) introspection / mass-assignment request, (2) response with the privileged field |
| Pure backend (SSRF blind / JWT / parser-diff) | (1) Burp Repeater frame showing request, response, timing — captured as image, not just pasted text |

### Capture method — Browser MCP first

**The `filename` is a path, not just a name.** Browser MCP resolves it against the output dir, which the Monte launcher roots at `works/<项目>/evidence` (never the repo / cwd). So pass the **full target-relative path** — `works/<项目>/evidence/NN-slug.png` — and the shot self-files into the correct hold; MCP `mkdir -p`'s the folder for you. A bare name (`01-foo.png`) is the old mistake: it dumps to the Targets root, unfiled. Captures **never** belong in the Monte workshop.

```
# Live capture (preferred — lossless, includes URL bar and dev tools)
# Pattern: filename = "works/<项目>/evidence/NN-slug.png"
Playwright MCP 打开页面并截图，保存到 works/<项目>/evidence/01-attacker-login.png。图内必须能看见完整 URL。

# Side-by-side proof (two-account / dual-tab)
Chrome tabs via CDP 9222                # confirm tab IDs
Playwright MCP 截图保存到 works/<项目>/evidence/02-attacker-tab.png
# switch tab
Playwright MCP 截图保存到 works/<项目>/evidence/03-victim-tab.png

# Network proof (use evaluate to render a banner so the screenshot identifies the session)
Chrome CDP evaluate(function="() => { document.title = 'SESSION: attacker@test.com'; }")
```

### Naming & storage

- Absolute home: `works/<项目>/evidence/<finding-name>/screenshots/`. The path **passed to MCP** is the slice relative to `works/<项目>/evidence`: `<target>/works/<项目>/evidence/NN-slug.png`. (Set by `--output-dir` in `tools/stealth/playwright-mcp-vps.sh` — see that script's comment.)
- Never pass a bare filename or a path into the Monte repo — captures live in the target's hold, not the workshop.
- Prefix with two-digit step number: `01-`, `02-`, ... so the directory listing matches the reproduction order.
- Filename pattern: `NN-<one-or-two-word-slug>.png` — e.g. `02-caido-cross-tenant-response.png`, `03-admin-panel-after-csrf.png`.
- Always `.png` for stills, `.gif` only for tiny loops, `.mp4` (or Loom link) for flows > 5 steps.

### Annotation rules

1. **Circle the parameter that was tampered.** Red box around `user_id=222` in the request, red box around `victim@example` in the response.
2. **Always include the URL bar.** A response screenshot without the URL bar can be claimed to be from a different host.
3. **Identify the active session.** Either a visible logged-in avatar/email in the corner, or inject a banner via `browser_evaluate` before capture.
4. **Redact unrelated PII** of real users. Black-box other rows of data, real email addresses of accounts you don't own, partial card numbers.
5. **Show the timestamp** when timing matters (race conditions, expiry-based bugs). DevTools Network panel shows request time; include it in the frame.

### Embedding in the report

```markdown
![Step 2 — Caido response shows victim's email returned to attacker's session](screenshots/02-caido-cross-tenant-response.png)
*Caption explains what this **proves**, not what the image **shows**.*
```

Bad caption: "Screenshot of Caido showing a response."
Good caption: "Attacker session (token `eyJ...attacker`) receives victim's email and address — proves ownership check is missing."

### One-screenshot test

For each screenshot, ask: *"If a triager closed every other screenshot and only saw this one, would they still understand which step it proves?"* If no, add a banner via `browser_evaluate` or annotate the image, then re-capture.

---
