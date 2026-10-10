# PATTERN 6 — Account Linkage and OAuth Interception

### The developer's assumption
*"When the user authenticates via Google/GitHub/SSO, we match them to an existing account by email. If no account exists, we create one."*

In practice: the matching-or-creation step has a window where the email is trusted from the OAuth provider before the account is confirmed. Or: the pre-linking step accepts an email that the analyst controls.

### Where the assumption breaks
- Pre-linking vulnerability: The app allows a logged-in user to "add a social login" to their account. The pre-link state (before OAuth completes) is stored as a session variable. The analyst can start a link for email `subject@target.com`, then complete the OAuth flow from their own Google account — if the server uses the pre-link email instead of the OAuth-returned email, they link their Google identity to the subject's account
- `state` parameter in OAuth is not validated — CSRF allows an analyst to bind their OAuth token to a subject's session
- Merge-on-email: The app merges accounts when emails match. Analyst creates an account with `subject@target.com`, then initiates OAuth with a Google account that has a different email but changes the profile email mid-flow
- The `redirect_uri` in the OAuth initiation is user-controllable and not validated against a whitelist

### Test sequence
```
1. Map all OAuth flows in the app (Phase B JS analysis usually surfaces these):
   - /auth/google, /auth/github, /auth/saml, /auth/oidc
   - Any "connect account" feature in settings

2. Test state parameter: complete OAuth flow. Note the `state` value.
   Start a new OAuth flow. Swap in the first flow's `state` at the callback step.
   Do the two accounts get merged?

3. Test pre-linking:
   Log in as userA. Navigate to Settings > Connect Google Account.
   Copy the pre-link initiation URL. Open in incognito with userB's session.
   Complete the Google OAuth with userB's Google account.
   Check: is userB's Google now linked to userA's account?

4. Test redirect_uri manipulation:
    GET /oauth/authorize?redirect_uri=https://analyst.example.com
    Does it redirect? (Logs the code to analyst's server)
    Try: redirect_uri=https://legitimate.target.com%40analyst.example.com (confusable)

5. Test email-merge timing:
    Create account with subject@target.com via email/password.
    Initiate OAuth with a provider where you control an account
    with subject@target.com (or a lookalike). Does it merge?
```

### Signal and chain
- **Positive on state CSRF**: two accounts merged → full ATO of subject's account
- **Positive on redirect_uri**: OAuth code intercepted → ATO
- **Chain**: OAuth ATO → if the subject is an admin, chain to full org compromise. Always Critical on direct ATO.

### High-value targets
Any application with social login ("Login with Google/GitHub/Apple"). Especially valuable on targets where SSO is used for internal tools.

---
