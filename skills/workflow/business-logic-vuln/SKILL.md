---
name: business-logic-vuln
description: >-
  SRC logic hunting for this repo. Find the intended invariant, name the seam,
  fire one Burp replay, refute on the wire. Do not run a payload checklist.
---

# SRC 逻辑挖掘（本仓库默认）

本篇是默认开工 skill，**不是**万能合集。硬规则在 `AGENTS.md`。本文件只读，不要追加 Method。  
开工先 `src_memory.py recall --skill business-logic-vuln`（≤5）。打成或证伪只 `remember` 进 jsonl。  
先读 `knowledge/logic_first.md` 和 `knowledge/loop.md`。  
pattern 目录：`knowledge/patterns/INDEX.md`（只加载命中的一篇）。  
同名的 `business-logic-vulnerabilities/` 不要同时打开。

工具：Playwright MCP 走路、登录、点击、截图（图内必须能看见完整 URL）。Burp 收包和重放。禁止 PUT/DELETE，禁止下单支付、改密、webshell。

## 每个 URL：先建模，再打

写进 `works/<项目>/state/<id>/map.md`，只追加：

1. **Actors**：这页上有谁（匿名 / A / B）
2. **Resources**：看见的对象和接口（订单、发票、导出任务、JS 里的私有 API）
3. **Boundaries**：这个对象按理该谁能读
4. **Anomaly**：一句话「怪在哪」+ 一句话「若是真的会怎样」

写不出 Boundaries，就还没开始挖逻辑。

## 探针（不是清单，是打破不变量的一发）

History 里出现对象 ID、身份字段、隐藏接口或可跳过的步骤，就按「一发一个假设」打。表是例子不是检查表，读完报文再打下一发。同一 URL 多发可以，禁止只 GET 首页就走。

| 看见什么 | 开发者以为 | 你打什么（只改一个变量） | 命中 |
|---|---|---|---|
| path/query/json 里有 pin、userId、orderId、memberPin | 只能读自己的 | A 的包 + B 的 Cookie，或 A 的 Cookie + B 的 ID | 出现对方姓名/手机/订单/金额/地址 |
| JWT/Cookie 有租户，body 又有 orgId/tenantId/erp | 以登录态为准 | 登录 A，body 改成 B 的租户 | 出 B 租户数据 |
| 多步：填表 → 确认 → 结果 | 第 3 步会检查第 2 步已完成 | 直接打结果/确认 URL | 没付款/没审批也出业务结果 |
| JSON 里已有 pin/role 或根本没有 | 服务端会忽略客户端身份字段 | 查询 POST 多塞 `pin`/`userId`/`role`/`isAdmin`/`pin=*` | 出他人或越权字段 |
| 无 Cookie | 一定 401/登录页 | 原请求去掉 Cookie | 仍返回上述敏感字段 |
| 导出/异步任务 jobId | 只有发起人能下载 | B 的 Cookie 去拉 A 的 job 结果（只读） | 下到 A 的文件或 PII |
| 回调/Webhook URL | 会验签 | 只读：看是否信 client 的 status=success（不要真伪造支付成功去落单） | 能证明服务端信了客户端状态再停 |

打完：命中就按报告模板写（Burp 原文，禁止打码）。  
未命中：在 map.md 的 Dead 写一行原因。  
对上 INDEX 里某一类：只打开那一个 pattern 再补一发。

## 不要做的

- 每个 URL 把上表当扫描器全跑一遍，或反过来只 GET 一下就标完成。
- 看见 History 里的查询 POST / GraphQL / 导出 / 隐藏 API 却不重放。
- 先打开 47 个 skill 再决定测什么。
- 200 或 body 变长就报。
- 泄露 ID 却不去读内容就报。
- 无假设地对整站 ffuf / 同一套字典打所有 URL。

## 国内优先对象

订单、发票、账单、优惠券、积分、地址、售后、绑定手机、商家/云控制台。  
参数：`pin` `memberPin` `erp` `userId` `tenantId` `orderId` `uid` `accountId`。

## 报告

`{系统名称}_{漏洞名称}.docx`。手写 Word。Burp 原文贴进报告，禁止打码。
