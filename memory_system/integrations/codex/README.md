# Codex × memory_system 项目级集成

**挖洞不要走这套。** 实战记忆只经 `tools/src_memory.py` 读写 `experience.jsonl`。这里的 `/api/chat` 是遗留聊天层，不是挖洞账本。

本目录使用 Codex CLI 0.145.0 已实际支持的项目级 Lifecycle Hooks，不改动 `~/.codex/config.toml`、模型、中转地址或认证配置。Hook 只调用当前运行中的 `http://127.0.0.1:8765`，不会启动、停止或替换 memory_system。

## 生命周期

| Codex 事件 | 动作 |
| --- | --- |
| `SessionStart` | 读取近期会话中的结构化工作快照、短时记忆与长期图谱，最多注入 3–5 条、总计最多 4000 字符 |
| `UserPromptSubmit` | 保存本轮 prompt 的会话/回合关联，并按问题检索相关记忆 |
| `Stop` | 保存结构化工作进度快照；用户/会话/回合/内容哈希用于幂等去重 |
| 明确完成 | 由 `consolidate_lab.py` 或 Stop Hook 的成功条件执行一次巩固 |

服务不可达、超时、JSON 异常或集成被停用时，Hook 输出继续执行信号并以退出码 0 返回，不阻断 Codex。

## 文件

- `memory_client.py`：对源码确认的 HTTP API 的标准库客户端。
- `recall_memory.py`：本地相关性排序、长度限制和 Hook 上下文输出。
- `store_checkpoint.py`：prompt 关联、结构化进度快照、幂等写入和完成检测。
- `consolidate_lab.py`：完成条件校验与显式巩固。
- `redact.py`：写入和召回前替换凭据、Token、Cookie、密码等字段值。
- `settings.json`：端点、测试用户、召回数量和长度限制。
- `configure_hooks.py`：根据当前项目绝对路径重建 `.cmd` 包装器和 `.codex/hooks.json`。
- `hook_*.cmd`：Windows Hook 命令包装器。
- `start_codex.ps1`：启用集成并沿用当前 Codex 用户级模型配置启动 Codex。
- `stop_integration.ps1`：仅停用本项目的记忆 Hook；不结束任何进程。

## 已确认 API

- `GET /api/health`
- `GET /api/sessions?user_id=...`
- `GET /api/history?user_id=...&session_id=...`
- `GET /api/memories?user_id=...`
- `GET /api/events?user_id=...`
- `POST /api/chat`
- `POST /api/consolidate`
- `DELETE /api/memories?user_id=...`

现有 API 没有专门的“仅写 working”或“只读语义 recall”端点。集成使用 `/api/chat` 写入带结构的快照，因此服务会同时写 instant、working 和 short；召回使用只读 GET 端点在客户端本地排序，避免通过 `/api/chat` 检索时产生额外写入。

## 启动与停用

从项目根目录执行：

```powershell
.\memory_system\integrations\codex\start_codex.ps1
```

也可把 `exec` 参数传给启动器：

```powershell
.\memory_system\integrations\codex\start_codex.ps1 exec --skip-git-repo-check "动态 CSRF Token 应当如何处理？"
```

停用本项目自动连接，不结束 Codex 或 8765 服务：

```powershell
.\memory_system\integrations\codex\stop_integration.ps1
```

下次运行 `start_codex.ps1` 会重新启用。

## 手动调用

```powershell
# 只读召回
.\.venv\Scripts\python.exe .\memory_system\integrations\codex\recall_memory.py "动态 CSRF Token 应当如何处理？"

# 显式巩固；没有 --verified 或有效成功证据路径时不会巩固
.\.venv\Scripts\python.exe .\memory_system\integrations\codex\consolidate_lab.py `
  --session-id user_001 `
  --experience "动态 CSRF 场景中，每轮请求前应重新获取有效 Token。" `
  --verified

# 重建当前项目绝对路径的 Hook 配置
.\.venv\Scripts\python.exe .\memory_system\integrations\codex\configure_hooks.py
```

## 写入格式与巩固门槛

Stop Hook 写入字段：当前任务、平台、靶场名称、漏洞类别、已执行操作、实际观察、已确认结论、尚未确认内容、失败尝试及原因、下一步、证据路径、验证状态。字段被截断到配置上限；不会保存完整 Burp 流量、完整终端日志或整段聊天。

巩固仅在以下任一条件成立时执行：

1. 内容中存在明确 `Solved`；
2. 内容中存在“当前靶场已完成并验证”；
3. 提供的证据文件真实存在，且文件名包含 solved/success/proof/evidence/完成/成功/验证。

## 合并到原项目

复制以下路径到目标项目的对应位置：

- `memory_system/integrations/codex/`
- `.codex/config.toml` 中的 `[features] hooks = true`（合并键，不覆盖目标文件）

目标项目已有 `.git` 根标记时不需要复制本测试项目的占位 `.git`。在目标项目根目录创建 `.venv` 后运行：

```powershell
C:\Python\Python313\python.exe -m venv .venv
.\.venv\Scripts\python.exe .\memory_system\integrations\codex\configure_hooks.py
```

`configure_hooks.py` 会生成目标项目自己的绝对路径 `.codex/hooks.json` 与 `.cmd` 文件。启动时仍加载原有用户级模型/中转/认证配置。
