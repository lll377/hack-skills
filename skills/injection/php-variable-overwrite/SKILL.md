---
name: php-variable-overwrite
description: >-
  PHP variable overwrite. Use when extract(), parse_str(), or variable variables import request data.
---

# PHP External Variable Modification


When PHP applications use `extract()` or `import_request_variables()` on untrusted input:

### extract() Variable Overwrite

```php
// Vulnerable:
extract($_GET);
// Attacker: ?auth=true&is_admin=1
// Now $auth = "true" and $is_admin = "1" in the application scope

// Combined with include:
extract($_GET);
include($template . ".php");
// Attacker: ?template=../../../../etc/passwd%00
```

### EXTR_OVERWRITE vs EXTR_SKIP

```php
// Default: EXTR_OVERWRITE — overwrites existing variables (dangerous!)
extract($_POST);  // Overwrites even $db_password if POST has it

// Safer but still risky:
extract($_POST, EXTR_SKIP);  // Won't overwrite existing, but creates new globals
```

### $GLOBALS Overwrite (PHP < 8.1)

```php
// In PHP < 8.1, $GLOBALS could be modified:
// Attacker: ?GLOBALS[admin]=1
extract($_GET);  // $GLOBALS['admin'] = 1 if EXTR_OVERWRITE

// PHP 8.1+ made $GLOBALS read-only — this attack no longer works
```

### Detection

```text
# Look for:
# - extract($_GET), extract($_POST), extract($_REQUEST)
# - parse_str($query) without second parameter (imports to current scope)
# - import_request_variables() (removed in PHP 5.4)
# - $$variable (variable variables with user input)
```
