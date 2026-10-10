# 逻辑优先（hack-skills）

参考 Monte 的挖法，改成我们的工具：Playwright 观察，Burp 重放。  
原则：扫描器找「代码做了什么」；逻辑洞找「代码以为用户会怎么走」和「实际能不能走另外一条」。

## 什么叫逻辑洞

要靠推断「系统打算怎样」，不是靠丢 payload。  
缝是行为不变量被打破：顺序、归属、租户、原子性、信任来源。  
对不上下面任何一行的新缝，更要挖，不要丢掉。

| 不变量 | 开发者以为 | 破法（只读） |
|---|---|---|
| 归属 | 只能碰自己的对象 | 换 pin/userId/memberPin/orderId，或换 Cookie |
| 租户 | JWT 里的 org 会过滤一切 | body/URL 另带 tenant，服务端听请求不听 JWT |
| 步骤 | 第 N 步一定经过第 N-1 步 | 直接打确认页/结果页 |
| 身份来源 | role 只是前端提示 | 查询 POST 多塞 role/isAdmin/pin=* |
| 登录 | 没 Cookie 进不去 | 去掉 Cookie 重放 |
| 任务归属 | 导出任务只有发起人能取 | 换 jobId 读别人的结果 |
| 回调 | Webhook 只接受已校验事件 | 看回调是否信 client 的 success |

国内高频名字：`pin` `erp` `memberPin` `userId` `tenantId` `orderId` `uid`。

## 调查 vs 报告

- **调查**：只要能说出「哪里怪」和「可能意味着什么」就可以打一发。不必先写出完整利用链。
- **报告**：Burp 原文里必须看见他人数据、权限或可利用密钥。只有 200、只有长度变化、只有内部端口 → 不写。  
  泄露了 userId 但没读到内容 → 继续接到读接口，不要单独交。

## 怎么发现缝

读 JS、source map、Burp History 里悄悄发出的请求。  
前端路由守卫 `step>=2`、管理接口没有鉴权注解、total 在前端算完 POST 上去——这些是缝，不是「再试一个 XSS payload」。

## 禁止

把 `knowledge/patterns/` 或 47 个 skill 当成检查表轮询。  
它们是图书馆：map 里已经有异常了，才打开对应那一篇。  
本目录只读。经验只经 `src_memory.py remember` 进 jsonl，不要改这里的文件。
