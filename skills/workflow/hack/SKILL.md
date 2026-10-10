---
name: hack
description: >-
  Entry P0 primary router for HackSkills. Use when the task involves web
  application testing, API security assessment, recon, vulnerability triage,
  exploit path planning, or choosing the right next category skill before any
  deep topic skill.
---

# HACKING SKILLS / HackSkills

## Load Gate（换 AI 也要守）

本文件是**路由表**，不是挖洞说明书，更不是万能 Skill。

- 默认挖洞只开 `../business-logic-vuln/SKILL.md` + `knowledge/logic_first.md`。
- map.md 里已经有 Anomaly 后，按现象打开对口专题，同时 `recall --skill <该专题目录名> --q '<看见的参数或现象>' --limit 5`。需要对口就开，禁止当检查表把库读完。
- Monte 适配篇（`methodology` / `arsenal` / `vulns` / `triage` / `quill` / `osint` / `osint-offensive`）**不是**默认开工。未导入 `recon`、`web3`。
- 禁止一上来把技能库全读完。禁止把本文件扩成合集。
- 本文件只读。硬规则只在 `AGENTS.md`（人改）。经验只进 `experience.jsonl`，不要往本文件追加路由行。

## Overview

这是一个面向 **漏洞赏金、Web 安全、API 安全、授权渗透测试** 的总入口技能。

它的核心作用不是替代所有专题技巧，而是帮助 Agent：

1. 先确定测试阶段（Recon / 验证 / 提权 / 组合链）
2. 再选择正确的漏洞类别
3. 避免只依赖基础训练数据，优先使用结构化方法论
4. 优先关注 AI 容易忽略但在实战里很重要的边界条件

## Trust Model

- 本知识库强调内容安全与可审查性。
- 使用时应限定在 **授权目标**、**合法研究**、**防御验证**、**漏洞赏金规则允许** 的范围内。
- 不要把这里的技巧用于未授权攻击。

## When to Use This Skill

在以下场景优先使用本技能：

- 你刚接手一个新的漏洞赏金目标，不知道先测什么
- 你需要决定应该加载 XSS / SQLi / SSRF / IDOR / JWT / API 等哪类思路
- 你想让 Agent 按更稳定的方法论进行 Web/API 安全测试
- 你需要把零散的现象路由到合适的攻击面
- 你希望 AI 在安全领域少漏掉关键测试点

## Operating Model

### Step 1: 先做 Recon 和上下文确认

优先收集：

- 目标类型：传统 Web、REST API、移动端后端、管理后台、支付流程、文件上传、GraphQL
- 身份与权限模型：匿名、普通用户、管理员、多租户
- 输入位置：URL、查询参数、JSON、Header、Cookie、文件名、导入文件、模板、回显点
- 输出位置：HTML、属性、JS、PDF、邮件、日志、后台任务、移动端接口

### Step 2: 按现象开主技能；判定类型后必须打开专题

不要把本表当检查表全开。只开对上的那几行。判定类型后必须打开专题并用对口部分；禁止停在 vulns/arsenal 摘要。

**主技能（按现象）**

| 现象 | 打开 |
|---|---|
| 独立后台账密登录（非 SSO） | 爆破技能已删除，待重写。本次不要套旧流程 |
| map 已有，卡住下一步 | [methodology](../methodology/SKILL.md)（不要当开工） |
| 已有假设，要 payload / 什么不该报 | [arsenal](../arsenal/SKILL.md) |
| 已点名某类洞，要对根因 | [vulns](../vulns/SKILL.md)，然后立刻下钻下表专题 |
| 准备出报告 | [triage](../triage/SKILL.md)；文案 [quill](../quill/SKILL.md)。手写 Word |
| 用户要 OSINT | [osint](../../recon/osint/SKILL.md) + [osint-offensive](../../recon/osint-offensive/SKILL.md)；禁止自动入队新主机 |

**判定类型后必须打开（未判定不开）**

| 判定是 | 打开 |
|---|---|
| 越权 / 对象 ID | `idor-broken-object-authorization` |
| 登录 / 重置 / 验证码 | `authbypass-authentication-flaws` |
| 服务端拉 URL | `ssrf-server-side-request-forgery` |
| 反射 / DOM | `xss-cross-site-scripting` |
| SQL | `sqli-sql-injection` |
| 模板 | `ssti-server-side-template-injection` |
| 上传 | `upload-insecure-files` |
| 其它已判定的类型 | `skills/` 下对应专题那一篇 |

### Step 3: 使用最可能命中的测试顺序

1. Recon：页面、JS、真实 Burp 流量里的对象 ID
2. 匿名未授权：admin / inner / super-api
2b. 独立后台账密登录：爆破技能已删除，待重写。本次不要套旧流程；打进去再转逻辑
3. 双账号 IDOR / BOLA / BFLA（只改 ID 或 cookie）
4. 业务逻辑：跳步骤、查询字段 mass assignment、一次性操作
5. 表面上的 SSRF（URL 拉取/PDF/Webhook）或 RCE 入口（模板/转换器）立刻下钻
6. 最后短过传统洞：XSS / SQLi / CSRF / 上传 / LFI / CORS。有点再深挖，没点就走。不打满字典。

## High-Value Expert Intuitions

这些点是很多基础模型容易忽略，但在真实漏洞赏金里经常有效：

1. **同一套过滤逻辑往往复用在多个页面**：一个点可绕过，类似页面通常也能绕过。
2. **参数名本身也是攻击面**：WAF 经常只盯参数值，不盯参数名。
3. **二阶漏洞非常常见**：存储时安全，不代表读取后进入危险上下文时也安全。
4. **BOLA 的本质是“有认证、无授权”**：A/B 账号切换重放非常关键。
5. **老版本接口最容易漏补丁**：v2 修了不代表 v1 下线了。
6. **业务逻辑漏洞往往回报最高**：它们难以被扫描器发现，也更容易长期存在。
7. **Race Condition 应优先测试“一次性”操作**：优惠券、领取、重置、邀请、试用、库存扣减。
8. **JWT 攻击先看密钥与算法上下文**：不要盲目试 payload，要先确认 `alg`、`kid`、JWKS、密钥来源。

## Suggested Prompts

可把本技能当作路由器来用，先让 Agent 明确阶段和目标：

- “先按漏洞赏金方法论帮我做这个目标的测试路线规划。”
- “这是一个 REST API，请优先从 BOLA、BFLA、Mass Assignment、JWT 角度审视。”
- “这个参数会触发服务端请求，请按 SSRF 思路列出关键验证点。”
- “这个功能是支付/优惠券/库存流程，请优先考虑业务逻辑和竞态。”
- “我只看到登录和找回密码流程，请按 Auth Bypass + OAuth/JWT + CSRF 路线分析。”

## Installation Notes

推荐 skill 名称：

- `hack`

推荐检索关键词：

- `HackSkills`
- `HACKING SKILLS`
- `bug bounty`
- `赏金猎人`

## Guidelines

- 优先按目标类型与现象路由，而不是随机枚举 payload。
- 需要 payload 时，优先使用对应主 skill 里的 quick start / first-pass 样本，而不是再跳一个中间入口。
- 优先寻找可复用的过滤器、共享组件和跨页面复现路径。
- 先确认认证边界、授权边界、版本边界，再深入利用。
- 优先保留可解释、可审查、可复现的测试过程。
- 当完整仓库可用时，优先回到专题文档获取更细的攻击细节。

## Historical SRC / Evidence Validation Notes

- Use a minimal reproducible chain: baseline request/response -> one-variable differential -> impact proof -> application result and time order, recording each layer separately.
- Keep HTTP status/response, browser or CDP execution, parser behavior, and success detection as separate evidence; navigation text, reflection, or a confirmation page alone is insufficient.
- Classify failures as session, length, quoting/encoding, wait timing, dependency, protocol, or detector problems before changing the vulnerability hypothesis.
- SRC records should retain reproducible steps, input types, key outputs, and evidence paths while redacting credentials, tokens, hosts, lab-only data, and final payloads.
- Cross-check independent observers such as proxy replay and browser behavior, and preserve the baseline, differential, and impact-proof order.

## Exploitability Gate (User Rule 2026-08-17)
- Only pursue vulnerabilities that can be actually exploited and demonstrated with impact.
- Skip informational-only findings (internal ports, version strings, 301 Location, harmless header differences) unless they can be chained into a real impact.
- A report is allowed only when there is a minimal reproducible exploit or attack chain, not a guess.

