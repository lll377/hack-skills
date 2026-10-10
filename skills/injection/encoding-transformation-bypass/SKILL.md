---
name: encoding-transformation-bypass
description: >-
  Encoding and normalization bypass. Use when filters run before Unicode, punycode, collation, or double decoding.
---

# Encoding Transformation Bypass


Unicode normalization and encoding differences can bypass security filters:

### Unicode Normalization Exploits

```text
# NFC/NFD/NFKC/NFKD normalization can change characters:
# NFKC normalizes: ﬀ (U+FB00, LATIN SMALL LIGATURE FF) → "ff"
# Fullwidth characters: Ａ (U+FF21) → "A"

# Attack: Register username "ⓐdmin" → normalizes to "admin" after filter check
# Password reset: request for "Ａdmin" (fullwidth A) → matches "admin" in DB
```

### Punycode / Homograph Attacks

```text
# IDN domains: аpple.com (Cyrillic а) looks like apple.com
# xn--pple-43d.com → displays as аpple.com in browsers

# Used for: phishing, open redirect filter bypass, SSRF domain validation bypass
```

### MySQL Collation Tricks

```sql
-- Default utf8_general_ci treats certain Unicode chars as equivalent:
-- 'a' = 'ᵃ' (U+1D43, MODIFIER LETTER SMALL A)
SELECT * FROM users WHERE username = 'ᵃdmin'  -- matches 'admin'!

-- Exploitation: Register as 'ᵃdmin', system treats as 'admin'
```

### Base64 Ambiguity

```text
# Same base64 string can decode differently depending on charset/padding:
# Some WAFs decode base64 for inspection but use different decoder than app
# Malformed base64 padding may bypass WAF but still decode in app
```

### Double Encoding

```text
%252e%252e%252f  → %2e%2e%2f (after first decode) → ../ (after second decode)
# If WAF decodes once but app decodes twice → filter bypass
```

---
