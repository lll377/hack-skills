# 逻辑挖掘循环

先读 `knowledge/logic_first.md`。

观察 → 写入 map.md → 说出「怪在哪」→ Burp 只打一发 → 用报文证伪 → 再决定下一发。

工具：Playwright 走路，Burp 变形。对上某类洞时 `src_memory.py recall --skill <目录名>`，最多 5 条。`knowledge/patterns/` 是图书馆，不是检查表。本目录只读；打成/证伪只 `remember` 进 jsonl。

## 每个目标一份世界模型

写在 `works/<项目>/state/<target_id>/map.md`，四栏，只追加：

- **Actors**：匿名 / 账号A / 账号B / 还进不去的特权角色
- **Resources**：页面、接口、对象 ID、JS 里悄悄打的调用
- **Boundaries**：谁允许碰什么；两套系统说法不一致的缝
- **Anomalies / Dead**：奇怪的现象 + 下一步探针；证伪的写一行原因，避免下回再挖

写不出这四栏，等于还没观察过这个 URL。

## 硬规则

1. 假设来自这个目标上看到的缝，不是来自 47 个 skill 名称。
2. 一次只打一发探针，读完再决定下一发。
3. 证伪要有报文：403 是证伪，「大概服务端有校验」不是。
4. 调查阶段不要求先写出完整利用链；**交报告前**必须有钱/数据/权限，且在 Burp 原文里看得见。
5. 理论、推断、幻想不是洞。没有字节就没有 finding。
