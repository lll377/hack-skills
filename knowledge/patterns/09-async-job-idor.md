# PATTERN 9 — Insecure Direct Object Reference in Async/Background Jobs

### The developer's assumption
*"The user requests an export/report generation. The job runs in the background. When it finishes, only that user can download the result."*

In practice: background job IDs are sequential or predictable. The download endpoint does not re-check ownership. Or: the job is triggered by one user but the callback URL contains the ID — if that URL is guessable, anyone can poll it.

### Where the assumption breaks
- `GET /api/jobs/12345/result` does not verify that `12345` was requested by the current user
- The job ID is a sequential integer (12345, 12346...) — enumerable
- The callback URL is `https://target.com/api/export/download?token=base64(job_id)` — the token is just a base64, not a signed value
- The status polling endpoint leaks information about other users' jobs (what export they requested, which records, timing)

### Test sequence
```
1. Trigger a background job as userA. Note the returned job_id or token.

2. As userB, poll the job status endpoint with userA's job_id:
   GET /api/jobs/<userA_job_id>/status

3. As userB, attempt download:
   GET /api/jobs/<userA_job_id>/result
   or  GET /api/export/download?token=<userA_token>

4. If job IDs are numeric, enumerate adjacent IDs (userA's ID ± 5):
   GET /api/jobs/12340/result through /api/jobs/12350/result
   as userB.

5. Check what the status endpoint leaks even without the full result:
   Does it reveal what data was exported? Query parameters? Record counts?
   Even metadata disclosure is a finding on sensitive platforms.
```

### Signal and chain
- **Positive**: userB can download userA's job result
- **Scale**: if IDs are sequential and the platform is high-volume, this is mass data extraction (Critical). Even a single read is High if the export contains PII.
- **Chain**: Job IDOR → if export contains all-user data (admin export job), chain to full database read. Job IDOR on financial exports → transaction history disclosure.

### High-value targets
Analytics platforms, BI tools, CRM export functions, billing history downloads, GDPR data export ("download your data") features, bulk email list exports.

---
