# 仿生人类四层记忆系统

**挖洞账本不在这里。** 实战记忆只有 `data/experience.jsonl`，读写走仓库根目录的 `tools/src_memory.py`。本目录的 8765 网页是同一份 jsonl 的查看器。下面的 SQLite 四层和 `POST /api/chat` 是遗留聊天层，**不要当挖洞记忆用，也不要往里面写经验**。

这是根据《仿生人类四层记忆模型 AI 记忆系统设计方案》完成的可运行实现。系统默认仅依赖 Python 3.11+，以 SQLite 持久化四层数据；配置 OpenAI 兼容接口后会启用语义分析和完整对话能力，不配置密钥也能完成记忆编码、召回、巩固与可视化。

## 已实现

| 认知层 | 工程实现 | 生命周期 |
| --- | --- | --- |
| 瞬时感官记忆 | 会话消息流、字符预算裁剪 | 当前会话上下文 |
| Baddeley 工作记忆 | 文本环路、视觉通道、情景缓冲、中央调度 | 最近 15 条重要信息 |
| 短时向量记忆 | 本地哈希向量、相似度/时效/重要度混合排序、召回强化 | 默认 7 天，过期后真实删除 |
| 长时联结记忆 | 实体关系图、重复事实增强、回忆强化 | 持久保存，按用户隔离 |

额外包含 LOP 深浅加工、每日海马式巩固任务、手动巩固、多用户隔离、审计事件、跨会话召回、数据清除 API 和响应式中文控制台。

## 快速启动

需要 Python 3.11 或更高版本，不需要安装任何第三方包。

```powershell
cd memory_system
python run.py
```

浏览器访问 `http://127.0.0.1:8765`。也可以执行：

```powershell
.\start.ps1
```

Docker 部署：

```powershell
docker compose up --build
```

聊天层数据默认写入 `memory_system/data/memory.db`（清空不影响挖洞账本）。挖洞真源是 `data/experience.jsonl`。服务只监听本机地址；需要容器或局域网访问时设置 `MEMORY_HOST=0.0.0.0`。

## 启用模型

复制 `.env.example` 中的变量到当前终端或部署环境。服务支持 OpenAI Chat Completions 兼容端点：

```powershell
$env:MEMORY_OPENAI_API_KEY="your-key"
$env:MEMORY_OPENAI_MODEL="gpt-4.1-mini"
python run.py
```

没有密钥时，系统使用确定性的本地深浅分类、中文事实抽取和记忆型回答。密钥只从环境变量读取，不会保存到数据库或返回给前端。

## API

`POST /api/chat`

```json
{
  "user_id": "user_001",
  "session_id": "session_001",
  "message": "我叫张三，今年25岁，职业是程序员",
  "image_description": null
}
```

主要端点：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/health` | 服务和模型状态 |
| `GET` | `/api/history?user_id=...&session_id=...` | 瞬时层会话历史 |
| `GET` | `/api/memories?user_id=...` | 四层统计、短时记忆和长期图谱 |
| `GET` | `/api/events?user_id=...` | 深浅加工与召回日志 |
| `POST` | `/api/consolidate` | 立即执行指定用户的记忆巩固 |
| `DELETE` | `/api/memories?user_id=...` | 清空指定用户的全部记忆 |

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试覆盖事实抽取、浅层过滤、跨会话召回、长期巩固、用户隔离、TTL 真实删除、用户清除和 HTTP 端到端流程。

## 与原方案的关键修正

- 短时过期会删除完整记录和向量，不会只删时间字典。
- 所有层以 `user_id` 隔离，不共享全局 FAISS 索引。
- 长期查询全部参数化，不拼接 Cypher 或 SQL。
- 巩固线程在服务级只启动一次，并支持优雅退出。
- 时间全部使用 UTC，避免默认参数固化和时区漂移。
- SQLite 使用 WAL、事务和外键；重启后四层记忆不会丢失。
- 模型异常会降级到本地加工，不会让记忆链路中断。

## 目录

```text
memory_system/
  memory_app/
    agent.py          顶层调度与回答生成
    memory_layers.py  四层记忆、巩固和遗忘
    processor.py      LOP 深浅加工与事实提取
    embeddings.py     本地向量编码与相似度
    db.py             SQLite 模式和事务
    server.py         HTTP API 与静态资源服务
    static/           中文控制台
  tests/              单元和端到端测试
  run.py              启动入口
```
