---
name: recon-for-sec
description: >-
  Entry P1 category router for reconnaissance and methodology. Use when mapping
  scope, discovering assets, fingerprinting technology, building endpoint
  inventory, and choosing the first high-value security testing path.
---

# Recon and Methodology Router

分类路由，**不是**默认开工。默认挖洞按 AGENTS.md。  
本仓库**未导入** Monte `recon` / `web3`。资产来自 `works/<项目>/url.txt`，禁止把 JS/CDN 新主机自动入队。

## When to Use

- 当前 URL 需要应用内指纹、泄露路径、接口清点（不是子域扫描管线）
- 用户明确要 OSINT / 资产归属判断
- 你想把后续测试建立在结构化方法论上，而不是随机枚举 payload

## Skill Map

- [Recon and Methodology](../recon-and-methodology/SKILL.md) — 应用内方法论、中间件指纹、泄露清单
- [OSINT methodology](../osint/SKILL.md) — 按需 OSINT 怎么想
- [OSINT probes](../osint-offensive/SKILL.md) — 按需路径/正则/dork；`tools/secret_scan.py`
- [Methodology mindset](../../workflow/methodology/SKILL.md) — map 已有后卡住才开
- [Insecure Source Code Management](../insecure-source-code-management/SKILL.md) — .git/.svn/.hg exposure detection
- [Dependency Confusion](../dependency-confusion/SKILL.md) — Supply chain reconnaissance for internal package names

## Recommended Flow

1. 先读 `规则.md` 和本轮 `url.txt`，确认范围内
2. Playwright 走路 + Burp History 做应用内指纹和端点收集
3. 按收集到的现象再路由到 [api-sec](../../api/api-sec/SKILL.md)、[auth-sec](../../auth/auth-sec/SKILL.md)、[injection-checking](../../injection/injection-checking/SKILL.md) 或 [business-logic-vuln](../../workflow/business-logic-vuln/SKILL.md)
4. 需要 OSINT 时再开 `osint` + `osint-offensive`，同时 `recall --skill <同名>`