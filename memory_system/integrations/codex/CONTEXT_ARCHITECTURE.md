# 北山AI第二步：上下文系统架构决策

- 形成日期：2026-07-30
- 正式项目：`C:\Users\Administrator\Desktop\hack-skills`
- 保留后端：现有 `memory_system` 与正式 `memory.db`
- 决策：只借鉴成熟生命周期，不安装 Cognee，不引入第二数据库或第二记忆平台。

## 官方依据

1. OpenAI Codex Hooks：`https://developers.openai.com/codex/hooks`
2. OpenAI Codex Advanced Configuration：`https://developers.openai.com/codex/config-advanced`
3. Cognee Codex Integration：`https://docs.cognee.ai/integrations/codex-integration`

截至 2026-07-30 的官方 Codex 文档确认：项目层可以使用 `.codex/hooks.json`；同一层同时配置 `hooks.json` 与内联 `[hooks]` 会被合并并产生警告，因此本项目固定只用 `hooks.json`。非托管命令 Hook 的信任绑定当前内容哈希，内容改变后需要通过 `/hooks` 重新审核。命令 Hook 从 stdin 接收 JSON；SessionStart 与 UserPromptSubmit 可通过 `additionalContext` 注入上下文；PreCompact 在压缩前运行；SessionEnd 是建议性、短时 Hook，当前支持的超时上限为 3 秒。

## 1. 当前已经实现什么

现有正式合并已经实现三类生命周期入口：

- `SessionStart`：从 short、long、近期 session 历史和本地 checkpoint 索引中召回有限条目。
- `UserPromptSubmit`：先捕获并脱敏 prompt，再按词项、时间、层级和重要性召回相关记忆。
- `Stop`：按 `session_id + turn_id` 保存结构化工作进度，并以内容哈希辅助去重。

现有能力还包括：

- 正式服务固定为 `http://127.0.0.1:8765`；
- 正式用户固定为 `user_001`；
- Cookie、Authorization、Bearer、CSRF、密码、API Key、JWT、嵌套 JSON 与 URL 编码字段脱敏；
- HTTP 短超时与服务不可用时 fail-open；
- instant、working、short、long entity、long relation 五类存储视图；
- 只有显式完成条件才允许长期巩固；
- 本地原子状态文件用于远端不可用时的恢复与幂等。

当前缺口是：没有 PostToolUse 结构化进度、没有压缩前任务锚点、没有 SessionEnd 最终恢复位置，以及 checkpoint 字段和状态值尚未统一为严格 schema。

## 2. Cognee 生命周期解决什么

Cognee 官方 Codex 集成采用六点生命周期：SessionStart、UserPromptSubmit、PostToolUse、Stop、PreCompact、SessionEnd。其设计目标分别是会话身份准备、按问题召回、工具轨迹、回答配对、压缩前锚点和会话结束同步。

其主要价值不是某个特定数据库，而是把“输入—行动—阶段结论—压缩—退出—新会话恢复”连接成闭环，尤其解决：

- 工具执行后只有终端输出、没有结构化进度的问题；
- 压缩后丢失已完成步骤和下一步的问题；
- 退出时未保存最终恢复点的问题；
- 新 session 只凭模糊历史检索、缺少当前任务高权重锚点的问题。

## 3. 适合现有 memory_system 的设计

适合直接吸收：

1. 固定六类 Hook，不增加低价值事件。
2. SessionStart 只恢复当前任务、最近 checkpoint 和 3–5 条相关经验。
3. UserPromptSubmit 把当前任务 checkpoint 置于最高权重。
4. PostToolUse 只保存结构化摘要，不保存完整工具输出。
5. Stop 形成严格 schema 的回合 checkpoint，但不每轮长期巩固。
6. PreCompact 生成唯一任务锚点并原子落盘。
7. SessionEnd 区分完成与未完成，只有 VERIFIED/SOLVED 允许巩固。
8. Hook 失败不阻断 Codex；远端不可用时保留本地恢复状态。

## 4. 不适合现有 memory_system 的设计

本次不采用：

- 安装 Cognee、Mem0、Letta、Graphiti 或其他第二套平台；
- 创建第二数据库或迁移正式数据；
- 把完整 prompt、完整 assistant 对话、完整工具输出和完整 transcript 同步到长期图谱；
- 每次 Stop 都执行重型知识图谱巩固；
- SessionEnd 启动一个未受管理、不可追踪的独立后台 worker；
- 依赖 Hook 作为耐久队列并假设失败事件稍后会自动重放；
- 使用 `async` Hook 配置，因为 OpenAI 官方文档说明该选项当前只解析、尚未支持异步命令 Hook。

原因是现有 `memory_system` 已完成四层/图谱/跨会话能力验收；重复平台会增加数据分叉、凭据面、运维面和恢复复杂度。

## 5. 本次增加和调整的 Hook

| Hook | 本次动作 | 输出/存储 |
|---|---|---|
| SessionStart | 强化 | 任务锚点、最近 checkpoint、3–5 条相关经验；可输出 additionalContext |
| UserPromptSubmit | 合并捕获与召回语义 | 脱敏 prompt 关联、相关上下文；可输出 additionalContext |
| PostToolUse | 新增 | 仅保存有进度意义的结构化工具摘要 |
| Stop | 强化 | schema 校验后的回合 checkpoint，默认 working/instant |
| PreCompact | 新增 | 唯一任务上下文锚点，写入 working 与本地原子状态 |
| SessionEnd | 新增 | 最终 checkpoint、恢复位置、完成状态；仅 VERIFIED/SOLVED 可巩固 |

## 6. 非阻塞与可恢复设计

### SessionStart

- HTTP 超时短于 Hook 总超时；最多 3–5 条、固定字符上限。
- 服务不可用时从本地 anchor/checkpoint 恢复；两者都不可用则返回 `continue: true`。
- 不扫描整个数据库，不读取完整 transcript。

### UserPromptSubmit

- prompt 先脱敏，再本地原子暂存；远端召回失败不影响问题提交。
- `session_id + turn_id` 做幂等键；同一上下文内容合并。
- 无关目标、低相关条目不注入。

### PostToolUse

- 只计算受限长度摘要和输入/输出摘要哈希。
- 相同工具、输入摘要、输出摘要去重；轮询和无进度调用跳过。
- 不把完整 stdout、Burp 流量、网页源码或扫描器原始结果送入记忆。

### Stop

- 只做轻量 schema 归一化、脱敏、原子落盘和短 HTTP 写入。
- 普通回合不触发长期巩固。
- 服务失败时保留本地 checkpoint，返回合法 JSON 且退出码 0。

### PreCompact

- 基于最新有效 checkpoint 生成一个唯一 anchor；已完成步骤作为恢复约束。
- 先原子写本地文件，再尝试写 working；任一失败都不阻断压缩。
- 压缩后的 SessionStart(source=compact) 优先恢复该 anchor。

### SessionEnd

- 按 OpenAI 当前限制把命令超时设为 3 秒。
- 仅完成轻量最终 checkpoint；重型巩固通过现有本机 memory service 请求触发，不启动新的 PowerShell 后台进程。
- 未完成任务保存恢复位置但不进入长期事实；服务不可用时本地状态仍可供下一 session 恢复。

## 最终架构决策

正式第二步采用：`Codex 六类 Hook → 统一安全上下文 schema → 本地原子状态 + 现有 memory_system HTTP API → 原有五层存储视图`。

边界固定为：短超时、fail-open、幂等、有限召回、摘要而非原文、证据保存路径、未验证不长期化、已完成步骤不自动重跑。
