---


name: recon-and-methodology


description: >-


  Reconnaissance and methodology playbook. Use when mapping assets, discovering endpoints, fingerprinting technology, and building a structured testing plan for a new target.


---


# SKILL: Recon and Methodology — Expert Bug Bounty Playbook


> **AI LOAD INSTRUCTION**: Systematic recon and bug-finding methodology from top bug hunters. Covers subdomain enumeration, endpoint discovery, tech fingerprinting, and the hunter's mental model for finding bugs that others miss. Key insight: most high-severity bugs are found through systematic coverage, not just clever payloads.


---


## 1. RECON HIERARCHY


```


Target Selection


└── Scope Definition (in-scope assets)


    └── Asset Discovery (subdomains, IPs, domains)


        └── Tech Fingerprinting (what's running)


            └── Endpoint Discovery (attack surface)


                └── Vulnerability Testing (per vulnerability type)


```


---


## 2. SUBDOMAIN ENUMERATION (CRITICAL FIRST STEP)


### Passive (no DNS queries to target)


```bash


# Subfinder (aggregates multiple sources):


subfinder -d target.com -o subdomains.txt


# Amass passive:


amass enum -passive -d target.com


# Certsh (certificate transparency):


curl -s "https://crt.sh/?q=%.target.com&output=json" | jq -r '.[].name_value' | sort -u


# SecurityTrails API, Shodan:


# Web: https://securitytrails.com/list/apex_domain/target.com


```


### Active (DNS brute force + resolution)


```bash


# Massdns + wordlist:


massdns -r /path/to/resolvers.txt -t A -o S -w output.txt \


  <(cat wordlist.txt | sed 's/$/.target.com/')


# ffuf for subdomain brute:


ffuf -w subdomains-wordlist.txt -u https://FUZZ.target.com \


  -mc 200,301,302,403 -H "Host: FUZZ.target.com"


# DNSx for bulk resolution:


cat subdomains.txt | dnsx -a -resp -o resolved.txt


# Recommended wordlist: SecLists/Discovery/DNS/


```


### Virtual Host Discovery


```bash


# ffuf vhost mode:


ffuf -w wordlist.txt -u https://target.com \


  -H "Host: FUZZ.target.com" -mc 200,301,403


# gobuster vhost:


gobuster vhost -u https://target.com -w wordlist.txt


```


---


## 3. SERVICE AND PORT DISCOVERY


```bash


# Fast port scan (common ports):


nmap -T4 -F target.com -oN ports.txt


# Comprehensive scan on resolved subdomains:


cat resolved_ips.txt | nmap -iL - --open -p 80,443,8080,8443,8888,3000,5000 -oG scan.txt


# httpx for HTTP probing:


cat subdomains.txt | httpx -title -tech-detect -status-code -o live_hosts.txt


# masscan for speed on large IP ranges:


masscan -p 80,443,8080,8443 10.0.0.0/8 --rate=1000


```


---


## 4. WEB TECHNOLOGY FINGERPRINTING


```bash


# Wappalyzer (browser extension) or:


whatweb https://target.com


# httpx with tech detection:


httpx -u https://target.com -tech-detect


# Check headers manually:


curl -sI https://target.com | grep -i "server\|x-powered-by\|x-generator\|cf-ray"


# Fingerprint from:


- Server header: nginx/1.18, Apache/2.4, IIS/10.0


- X-Powered-By: PHP/7.4, ASP.NET


- Cookies: PHPSESSID (PHP), JSESSIONID (Java), _rails_session (Rails)


- HTML comments: <!-- Drupal 9 -->


- Meta generator: <meta name="generator" content="WordPress 6.2">


- JS framework files: /static/js/angular.min.js


```


---


## 5. ENDPOINT DISCOVERY


### Directory Brute Force


```bash


# ffuf (fastest):


ffuf -u https://target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-files.txt \


  -mc 200,301,302,403 -t 50 -o dirs.txt


# Gobuster:


gobuster dir -u https://target.com -w wordlist.txt -x php,html,js,json


# feroxbuster (recursive):


feroxbuster -u https://target.com -w wordlist.txt -x php,html,txt -r


```


### Parameter Discovery


```bash


# Arjun (hidden parameter finder):


arjun -u https://target.com/api/endpoint


# x8:


x8 -u https://target.com/api/endpoint -w params-wordlist.txt


```


### JavaScript Source Mining


```bash


# Extract endpoints from JS files:


gau target.com | grep '\.js$' | httpx -mc 200 | xargs -I{} curl -s {} | \


  grep -oE '"/[a-zA-Z0-9/_-]+"' | sort -u


# LinkFinder:


python3 linkfinder.py -i https://target.com -d -o output.html


# GetAllURLs (gau):


gau target.com | sort -u > all_urls.txt


# Wayback URLs:


waybackurls target.com | sort -u > wayback_urls.txt


```


### API Endpoint Discovery


```bash


# Common API paths:


ffuf -u https://target.com/FUZZ -w /SecLists/Discovery/Web-Content/api/api-endpoints.txt


# Swagger/OpenAPI:


test: /swagger.json /api-docs /openapi.json /v2/api-docs /.well-known/ /docs/


# GraphQL:


test: /graphql /gql /v1/graphql /api/graphql


```


---


## 6. SOURCE CODE RECON


### GitHub / GitLab Exposure


```bash


# trufflehog (secret scanner in git history):


trufflehog git https://github.com/target-org/target-repo


# gitleaks:


gitleaks detect --source /path/to/cloned/repo


# Manual GitHub search:


# site:github.com "target.com" "api_key" OR "secret" OR "password"


# site:github.com "target.com" ".env" OR "config.php" OR "db_password"


# GitHub dorks:


# "target.com" extension:env


# "target.com" filename:*.config password


# org:target-org secret OR password OR apikey


```


### Exposed Environment Files


```


# Check common paths:


https://target.com/.env


https://target.com/.git/config


https://target.com/config.json


https://target.com/config.yaml


https://target.com/credentials.json


https://target.com/secrets.json


https://target.com/wp-config.php


https://target.com/backup.sql


https://target.com/backup.zip


```


---


## 7. ZSEANO'S TESTING METHODOLOGY


### Core Philosophy


1. **Go deep on one program** rather than spread across many — learn the application thoroughly


2. **Build a profile of the company** — tech stack, developers, processes


3. **Look where others don't** — check error pages, admin paths, old versions, mobile API


4. **Follow the filter** — if input is filtered somewhere, that functionality exists and may be bypassed


### Testing Sequence (One Page / Feature)


```


For each input point:


1. Non-malicious HTML tags (<h2>, <img>) → are they reflected?


2. Incomplete tags → what happens? (<iframe src=//evil.com )


3. Encoding tests → %0d, %0a, %09, <%00


4. Observe the OUTPUT too (not just response) — where does your input appear?


5. Test same input in ALL similarly-structured pages (shared code → shared vuln)


6. Check if the same parameter exists in mobile/API endpoint (less protected)


```


### Parameter Insights


```


- Each parameter tells a story: "what does this do server-side?"


- Filename → OS interaction → Path Traversal / CMDi


- URL/location → HTTP fetch → SSRF


- Template/HTML parameter → render function → SSTI


- XML field → parser → XXE


- SQL filter → query → SQLi


- User-content → storage → Stored XSS


```


---


## 8. BUG BOUNTY PROGRAM TRIAGE (WHERE TO SPEND TIME)


### High-Value Target Selection


```


✓ Programs with large scope (*.target.com)


✓ Programs that pay for P2/P3 (not just RCE)


✓ Programs with recent tech changes (migrations = new bugs)


✓ Programs with active development (new features = new attack surface)


× Avoid: frozen/old codebases with well-known CVEs (already claimed)


× Avoid: strict programs with narrow scope (less surface)


```


### High-Value Feature Focus (by bug probability)


```


Priority 1: Authentication, password reset, 2FA → account takeover


Priority 2: File upload, profile edit, API endpoints → stored XSS, IDOR


Priority 3: Admin panels, user management → BFLA, privilege escalation


Priority 4: Payment flows, subscription → business logic


Priority 5: Import/export, template rendering → XXE, SSTI


```


---


## 9. NUCLEI TEMPLATES (AUTOMATED SCANNING)


```bash


# Run all on target:


nuclei -u https://target.com -t /nuclei-templates/ -o nuclei-results.txt


# Specific categories:


nuclei -u https://target.com -t cves/ -severity critical,high


nuclei -u https://target.com -t exposures/


nuclei -u https://target.com -t misconfiguration/


# On subdomain list:


cat subdomains.txt | nuclei -t exposures/ -t misconfiguration/ -o exposed.txt


```


---


## 10. COMMON MISCONFIGURATIONS (QUICK WINS)


```


□ CORS: Access-Control-Allow-Origin: * with credentials → CSRF + data theft


□ S3 bucket public: curl https://target.s3.amazonaws.com/


□ Directory listing: response contains "Index of /"


□ .git exposed: curl https://target.com/.git/config


□ .env exposed: curl https://target.com/.env


□ Debug mode: stack traces in production (source code exposure)


□ Default credentials: admin:admin, admin:password on admin panels


□ phpinfo.php: curl https://target.com/phpinfo.php


□ Backup files: config.bak, database.sql.gz, app.zip


□ GraphQL introspection enabled: POST /graphql {"query":"{__schema{types{name}}}"}


□ Admin panels: /admin /manager /console /phpmyadmin /wp-admin


```


---


## 11. QUICK REFERENCE TOOLS


| Category | Tool |


|---|---|


| Subdomain enum | subfinder, amass, massdns |


| Port scan | nmap, masscan |


| HTTP probe | httpx |


| Dir brute | ffuf, feroxbuster, gobuster |


| JS mining | LinkFinder, gau, waybackurls |


| Secret scan | trufflehog, gitleaks |


| Parameter fuzz | arjun, x8 |


| Vuln scan | nuclei |


| Proxy/intercept | Burp Suite Pro |


| JWT attacks | jwt_tool |


| SQLi | sqlmap |


| XSS | dalfox, XSStrike |


| SSRF | SSRFmap, Gopherus |


---


## 12. JAVA MIDDLEWARE FINGERPRINT MATRIX


| Middleware | Detection Path | Key Indicators |


|---|---|---|


| Apache Tomcat | `/manager/html`, `/manager/status` | Default creds: `tomcat:tomcat`, `admin:admin` |


| JBoss / WildFly | `/jmx-console/`, `/web-console/` | JMX MBean access, WAR deployment |


| WebLogic | `/console/`, `/wls-wsat/` | T3 protocol on 7001/7002, IIOP |


| Spring Boot Actuator | `/actuator/`, `/actuator/env`, `/actuator/heapdump` | JSON endpoint listing, heap dump contains secrets |


| Spring Boot (alt paths) | `/actuator/jolokia`, `/actuator/gateway/routes` | Jolokia JMX bridge, Gateway route injection |


| Jenkins | `/script`, `/manage` | Groovy console, API token in cookie |


| GlassFish | `/common/`, `/theme/` | Admin on 4848, default empty password |


| Jetty | `/jolokia/` | JMX access |


| Resin | `/resin-admin/` | Admin panel |


### Spring Boot Actuator Exploitation Priority


```


/actuator/env          → Leak environment variables (DB creds, API keys)


/actuator/heapdump     → Download JVM heap → search for passwords in memory


/actuator/jolokia      → JMX → possible RCE via MBean manipulation


/actuator/gateway/routes → Spring Cloud Gateway → SpEL injection (CVE-2022-22947)


/actuator/configprops  → All configuration properties


/actuator/mappings     → All URL mappings (hidden endpoints)


/actuator/beans        → All Spring beans


/actuator/shutdown     → POST to shutdown application (DoS)


```


---


## 13. INFORMATION LEAK DETECTION CHECKLIST


### Version Control & Backup Leaks


```


/.git/HEAD                    → Git repository exposed


/.svn/entries                 → SVN metadata


/.svn/wc.db                   → SVN SQLite database


/.hg/requires                 → Mercurial


/.bzr/README                  → Bazaar


/.DS_Store                    → macOS directory listing


```


### Backup File Patterns


```


/backup.zip    /backup.tar.gz    /backup.sql


/wwwroot.rar   /www.zip          /web.zip


/db.sql        /database.sql     /dump.sql


/config.php.bak    /config.php~    /config.php.swp


/.config.php.swp   /wp-config.php.bak


/.env          /.env.bak         /.env.production


```


### API Documentation & Debug


```


/swagger-ui.html              → Swagger/OpenAPI


/swagger-ui/                  → Swagger UI


/api-docs                     → API documentation


/graphql                      → GraphQL playground


/graphiql                     → GraphQL IDE


/debug/                       → Debug endpoints


/phpinfo.php                  → PHP configuration


/server-status                → Apache status


/server-info                  → Apache info


/nginx_status                 → Nginx status


```


### Cloud & Infrastructure


```


/.aws/credentials             → AWS credentials


/.docker/config.json          → Docker registry auth


/robots.txt                   → Disallowed paths (hint list)


/sitemap.xml                  → Full URL listing


/crossdomain.xml              → Flash cross-domain policy


/.well-known/                 → Various well-known URIs


```


## SRC_NOTE_RECON_FRONTEND_HARDCODED_SECRETS_20260816
- Targets: https://mprocess-joysky.jd-ex.com/ and https://usmart.jd-ex.com/
- Verified on Sunday, August 16, 2026.
- Real pattern: production SPA build artifacts referenced from the in-scope homepage contained hardcoded environment values: `REACT_APP_ASSISTANT_AGENT_ID=40520`, `REACT_APP_ASSISTANT_AGENT_TOKEN=a72ed437837d4dd082df6840a23f824a` in `main.34a6a39f.js`, and `VUE_APP_ERP_APPKEY=test3`, `VUE_APP_ERP_APPTOKEN=347c6161e79f4b6a8873202dd5fe7e8f`, `VUE_APP_BASE_API=http://uat-api.jdl.com` in `chunk-vendors.2e19f92c.js`.
- Real extraction path: GET the homepage, extract every `<script src>` and preload URL, download each JS asset, then regex for `REACT_APP_*`, `VUE_APP_*`, `APPKEY`, `APPTOKEN`, `AGENT_TOKEN`, and `chatInfo`.
- Real verification path: re-request the exact public JS URL and record status 200 plus the surrounding code snippet; do not use or test the credentials against out-of-scope services.
- Reusable cue: always mine JS assets for build-time env vars, not only API paths. Secrets in frontend bundles are high-signal SRC findings even when the backend endpoints themselves require auth or are out of scope.

## SRC_NOTE_RECON_DEFAULT_VERSION_PAGES_20260816
- Targets: https://shj-wms.jd.com/, http://tea.chanchuang.jdcloud.com.jcloudlb.com/, https://qf-ai.jd.com/
- Verified on Sunday, August 16, 2026.
- Real pattern: three exposed hosts leaked deployment metadata: Apache Tomcat/8.5.73 default page plus `/docs/`, nginx/1.18.0 Ubuntu welcome page, and a self-hosted Sentry login page disclosing `version.current=25.10.0`, `supportEmail`, DSN, and `userIdentity.ip_address`.
- Real extraction path: GET `/`, `/docs/`, `/manager/html`, and the login HTML; capture server header, title, version strings, and the `window.__initialData` block.
- Real verification path: confirm each page with direct GET status 200 and matching body/header evidence; classify as low/informational information disclosure, not authentication bypass.
- Reusable cue: default Tomcat/nginx pages and framework metadata are fast wins for SRC initial reporting, but always pair them with a concrete exposure statement and evidence path rather than a version number alone.


## SRC_NOTE_RECON_API_REDIRECT_INTERNAL_PORT_20260817
- Target: https://pi.jd.com/
- Verified on Sunday, August 17, 2026.
- Real pattern: an SPA gateway did not expose its backend API directly at the public `/pi/api` prefix, but the exact no-trailing-slash path `/pi/api` returned `301 Moved Permanently` with `Location: http://pi.jd.com:8080/pi/api/`, disclosing internal HTTP port 8080 and `nginx/1.24.0`.
- Real extraction path: download the main JS from the in-scope homepage, extract API prefixes (`/pi/api`), then test both `/prefix` and `/prefix/` while preserving redirects. Record the 301 body and all relevant headers (`Location`, `Server`, `Access-Control-*`).
- Real verification path: re-request `/pi/api` and confirm the same 301 `Location`; do not connect to the leaked `:8080` endpoint because that port is outside the URL-list scope.
- Reusable cue: trailing-slash and prefix-only probes are cheap and can reveal reverse-proxy/back-end port mapping. Treat them as low-severity internal infrastructure disclosure, and never claim the backend port is exploitable without an in-scope reachability test.

## NEGATIVE_SIGNAL_INTERNAL_PORT_REDIRECT_20260817
- User feedback: the finding documented as `??_04_pi.jd.com??????.docx` is not a valid vulnerability.
- Reason: a 301/302 redirect that merely exposes an internal port (e.g. `Location: http://pi.jd.com:8080/pi/api/`) or a Server/version string has no proven exploitability and no business impact.
- Rule: do not treat prefix/trailing-slash 301s that reveal internal ports or nginx versions as reportable findings unless the same in-scope target demonstrates reachability plus an actual abuse/impact chain.
- Action for future scans: classify as `informational/no-value` and skip reporting; do not spend time generating DOCX reports for this pattern.

