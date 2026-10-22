# MY-AICODING 阿里云多容器部署与并发架构方案

本文说明 MY-AICODING 从“本地课程版”升级到“阿里云服务器 + 多 Docker 容器节点 + Nginx 负载均衡”的生产化部署方案。

当前本地版本的核心技术栈是：

- FastAPI / Uvicorn 提供后端服务。
- DeepAgents 负责 Agent 编排。
- Vue + JavaScript 提供 Dashboard 前端。
- SQLite 保存业务 Store 和 checkpoint。
- 本地工作区 `<AI_WORKSPACE_ROOT>` 保存项目、skills、policies、reviews、runtimes 等目录。
- POST SSE 返回 Agent 实时输出。

如果部署到阿里云并启用多个 ASGI 容器节点，必须重点解决这些问题：

- 多个容器不能各自使用本地 SQLite 保存全局状态。
- 多个容器不能各自维护进程内锁来保护同一个 Gitee 仓库。
- 多个容器不能依赖本机内存中的 `_BACKENDS` 缓存保存长期状态。
- SSE 长连接可能被 Nginx 缓冲或超时。
- coding 任务会修改工作区代码，必须避免多个 Agent 同时修改同一个仓库。
- Agent 任务耗时较长，不应该完全绑死在 Web 容器线程里。

最终推荐目标是：

> Web 层多 ASGI 容器无状态化；Agent 执行层由独立 Worker 负责；PostgreSQL 保存业务数据和 checkpoint；Redis 负责队列、分布式锁和实时事件总线；Nginx 负责负载均衡和 SSE 代理。

---

## 1. 总体目标

### 1.1 部署目标

| 目标 | 说明 |
| --- | --- |
| 多容器部署 | 支持多个 ASGI 容器节点横向扩展 |
| Nginx 负载均衡 | 前端请求进入 Nginx，再分发到后端容器 |
| 状态共享 | 多容器共享 PostgreSQL、Redis 和工作区存储 |
| 并发可控 | 同一会话串行、同一仓库写任务串行、模型调用限流 |
| SSE 稳定 | 关闭 Nginx 缓冲，支持长连接实时输出 |
| Agent 可恢复 | 任务状态、历史消息、业务摘要不依赖某一个容器进程 |
| 安全可控 | API Key、Gitee Token、私钥不写入镜像，使用环境变量或 Secret 注入 |

### 1.2 不建议直接照搬本地结构

本地教学版适合单机、单用户、低并发：

```mermaid
flowchart TD
    U["浏览器"] --> F["FastAPI + Uvicorn"]
    F --> A["DeepAgent"]
    F --> S["SQLite"]
    A --> W["<AI_WORKSPACE_ROOT>"]
```

云端多容器不能简单变成：

```mermaid
flowchart TD
    U["浏览器"] --> N["Nginx"]
    N --> A1["ASGI 容器 1 + SQLite"]
    N --> A2["ASGI 容器 2 + SQLite"]
    N --> A3["ASGI 容器 3 + SQLite"]
```

原因是：

- 每个容器的 SQLite 文件不同，状态不一致。
- 每个容器的内存锁不同，不能保护跨容器并发。
- SSE 连接在哪个容器上，Agent 就必须在哪个容器里跑，容器重启会中断任务。
- 如果多个容器挂载同一个 SQLite 文件，并发写会更容易触发锁冲突。

---

## 2. 推荐目标架构

### 2.1 完整架构图

```mermaid
flowchart TD
    U["浏览器 / Vue Dashboard"] --> N["Nginx 负载均衡"]

    N --> A1["ASGI Web 容器 1<br/>FastAPI"]
    N --> A2["ASGI Web 容器 2<br/>FastAPI"]
    N --> A3["ASGI Web 容器 N<br/>FastAPI"]

    A1 --> PG["PostgreSQL<br/>业务 Store + checkpoint"]
    A2 --> PG
    A3 --> PG

    A1 --> R["Redis<br/>队列 + 分布式锁 + 事件流"]
    A2 --> R
    A3 --> R

    R --> W1["Agent Worker 1"]
    R --> W2["Agent Worker 2"]
    R --> W3["Agent Worker N"]

    W1 --> PG
    W2 --> PG
    W3 --> PG

    W1 --> WS["共享工作区<br/>NFS / 云盘 / OSS 缓存 / 独立卷"]
    W2 --> WS
    W3 --> WS

    W1 --> G["Gitee"]
    W2 --> G
    W3 --> G

    W1 --> LLM["大模型 API"]
    W2 --> LLM
    W3 --> LLM
```

### 2.2 各组件职责

| 组件 | 职责 | 是否保存状态 |
| --- | --- | --- |
| Nginx | 静态资源、反向代理、负载均衡、SSE 长连接代理 | 不保存业务状态 |
| ASGI Web 容器 | 接收 HTTP 请求、校验参数、创建任务、提供 SSE 接口、查询历史 | 不保存本地关键状态 |
| Agent Worker | 执行 DeepAgent、读写仓库、调用工具、运行测试、push/PR | 不保存不可恢复状态 |
| PostgreSQL | 保存 thread、run、review findings、checkpoint、仓库记忆等持久化数据 | 保存核心状态 |
| Redis | 保存任务队列、分布式锁、实时事件流、限流计数 | 保存短期运行状态 |
| 共享工作区 | 保存仓库源码、skills、policies、reviews、runtimes | 保存文件状态 |
| Gitee | 代码仓库、PR、评论 | 外部状态 |
| 大模型服务 | deepseek-v4-pro 等模型调用 | 外部状态 |

### 2.3 数据流总览

```mermaid
sequenceDiagram
    autonumber
    participant V as Vue 前端
    participant N as Nginx
    participant API as ASGI Web 容器
    participant R as Redis
    participant W as Agent Worker
    participant PG as PostgreSQL
    participant G as Gitee

    V->>N: POST /dashboard/api/threads/{id}/stream-message
    N->>API: 转发请求
    API->>PG: 创建 thread/run，状态 queued
    API->>R: 写入任务队列
    API-->>V: SSE user_message / queued
    W->>R: 领取任务
    W->>R: 获取 thread 锁和 repo 写锁
    W->>PG: 更新 run 状态 running
    W->>G: clone/pull/push/PR
    W->>PG: 写 checkpoint / Store
    W->>R: 发布 text_delta / todo_delta / thread_done
    API->>R: 读取当前 run 事件流
    API-->>V: SSE 增量输出
    W->>R: 释放锁
    W->>PG: 更新 run 状态 completed/failed
    API-->>V: SSE done
```

---

## 3. 分阶段落地方案

不建议一次性把本地版本直接改造成完整分布式。建议分三阶段。

### 3.1 第一阶段：单容器云部署

目标：先让项目在阿里云 Linux 服务器上稳定跑起来。

架构：

```mermaid
flowchart TD
    U["浏览器"] --> N["Nginx"]
    N --> A["单个 ASGI 容器"]
    A --> DB["SQLite"]
    A --> W["Linux 本地工作区 /data/ai_workspace"]
```

改造点：

| 项目 | 处理 |
| --- | --- |
| Windows 路径 | 改成 Linux 路径，例如 `/data/ai_workspace` |
| `.env` | 通过 Docker env 或挂载 Secret 注入 |
| SQLite | 暂时保留，但只允许单容器 |
| Nginx | 配置 SSE 关闭 buffering |
| 工作区 | 挂载 Docker volume 到 `/data/ai_workspace` |
| 日志 | 输出到容器 stdout，同时挂载日志目录 |

适用场景：

- 讲课演示。
- 单人或少量用户使用。
- 验证 Linux 环境兼容性。

限制：

- 不能横向扩展。
- 容器重启会中断正在运行的 Agent。
- SQLite 不适合多容器并发。

### 3.2 第二阶段：多 ASGI 容器 + PostgreSQL + Redis 锁

目标：支持多个 Web 容器，先不拆 Worker。

架构：

```mermaid
flowchart TD
    U["浏览器"] --> N["Nginx"]
    N --> A1["ASGI 容器 1"]
    N --> A2["ASGI 容器 2"]
    N --> A3["ASGI 容器 N"]
    A1 --> PG["PostgreSQL"]
    A2 --> PG
    A3 --> PG
    A1 --> R["Redis 分布式锁"]
    A2 --> R
    A3 --> R
    A1 --> WS["共享工作区"]
    A2 --> WS
    A3 --> WS
```

改造点：

| 项目 | 处理 |
| --- | --- |
| Store | SQLite 迁移 PostgreSQL |
| checkpoint | LangGraph checkpointer 迁移 PostgreSQL |
| 锁 | 使用 Redis 分布式锁替代进程内 `threading.Lock` |
| 工作区 | 多容器共享同一个工作区，或每仓库独立目录 |
| SSE | 请求在哪个 Web 容器，Agent 暂时也在哪个容器内跑 |
| Nginx | 可以不强制 sticky session，因为一次 SSE 连接本身会固定到一个 upstream |

适用场景：

- 内部小团队使用。
- 多用户查看历史、生成方案、代码审查。
- coding 任务数量不高。

限制：

- Agent 仍然在 Web 容器里跑，Web 层和执行层没有完全解耦。
- Web 容器重启仍会影响当前任务。
- SSE 连接和 Agent 执行仍绑定在同一个容器进程。

### 3.3 第三阶段：多 ASGI 容器 + 独立 Agent Worker + Redis Stream

目标：正式支持多人、多任务、可横向扩展的生产形态。

架构：

```mermaid
flowchart TD
    U["浏览器"] --> N["Nginx"]
    N --> API1["ASGI Web 1"]
    N --> API2["ASGI Web 2"]

    API1 --> PG["PostgreSQL"]
    API2 --> PG
    API1 --> R["Redis Queue / Stream / Lock"]
    API2 --> R

    R --> W1["Agent Worker 1"]
    R --> W2["Agent Worker 2"]
    R --> W3["Agent Worker N"]

    W1 --> PG
    W2 --> PG
    W3 --> PG
    W1 --> WS["共享工作区"]
    W2 --> WS
    W3 --> WS
```

核心变化：

| 当前本地/第二阶段 | 第三阶段 |
| --- | --- |
| ASGI 容器直接执行 Agent | ASGI 只入队，Worker 执行 Agent |
| event_sink 直接进入当前 SSE queue | event_sink 写 Redis Stream |
| SSE 从本地 queue 读 | SSE 从 Redis Stream 读 |
| 进程内 run 状态 | PostgreSQL + Redis 共享状态 |
| 容器重启任务中断风险高 | Worker 可做任务恢复或失败标记 |

适用场景：

- 多学生同时访问。
- 企业内部多人使用。
- 需要水平扩容。
- 需要更稳定的任务排队、运行保护和观测能力。

---

## 4. 数据层改造方案

### 4.1 SQLite 为什么不适合多容器

SQLite 是本地文件数据库，适合单机低并发。多容器场景下问题明显：

| 问题 | 说明 |
| --- | --- |
| 文件锁冲突 | 多进程/多容器同时写更容易 `database is locked` |
| 状态不一致 | 如果每个容器各有 SQLite，数据天然分裂 |
| 连接管理弱 | 不适合大量并发长任务写入 |
| 运维能力不足 | 缺少成熟连接池、权限、备份、监控、复制能力 |

### 4.2 PostgreSQL 保存哪些数据

建议 PostgreSQL 同时承载两类数据：

| 数据类型 | 原本位置 | 云端建议 |
| --- | --- | --- |
| thread 列表 | SQLite Store | PostgreSQL |
| run 记录 | SQLite Store | PostgreSQL |
| run_events | SQLite Store | PostgreSQL 或 Redis Stream 归档 |
| review_findings | SQLite Store | PostgreSQL |
| settings | SQLite Store | PostgreSQL |
| checkpoint | SQLite / 本地 saver | LangGraph Postgres checkpointer |
| 仓库记忆 | LangGraph Store / SQLite | LangGraph Store on PostgreSQL |

推荐原则：

- **长期持久化数据** 放 PostgreSQL。
- **实时短期事件** 先放 Redis Stream，必要时异步归档到 PostgreSQL。
- **聊天正文历史** 仍以 checkpoint 为准。
- **业务 Store** 不参与聊天正文拼接。

### 4.3 PostgreSQL 表设计方向

业务 Store 可以继续沿用当前 SQLite Store 的概念，只是实现换成 PostgreSQL。

核心表：

| 表 | 作用 |
| --- | --- |
| `threads` | 会话摘要、仓库、分支、PR、最新状态 |
| `runs` | 每轮运行记录 |
| `run_events` | 结构化过程事件归档 |
| `review_findings` | reviewer 子 Agent 的结构化审查发现 |
| `settings` | 系统配置 |
| `repo_memories` 或 LangGraph Store 表 | 仓库长期记忆 |
| LangGraph checkpoint 表 | thread state 和消息历史 |

注意：

> checkpoint 的表结构尽量使用 LangGraph 官方 saver 提供的结构，不建议手写一套兼容表。

---

## 5. Redis 的使用方案

### 5.1 Redis 承担三类职责

| 职责 | Redis 功能 |
| --- | --- |
| 任务队列 | List / Stream / Celery broker / RQ queue |
| 分布式锁 | `SET key value NX EX seconds` |
| 实时事件总线 | Redis Stream 或 Pub/Sub |

### 5.2 任务队列

当用户提交任务时，ASGI 容器不直接运行 Agent，而是：

1. 在 PostgreSQL 中创建 `run`，状态为 `queued`。
2. 把任务写入 Redis 队列。
3. SSE 先返回 `queued` 事件。
4. Agent Worker 从队列取任务执行。

任务消息示例：

```json
{
  "run_id": "run-uuid",
  "thread_id": "thread-uuid",
  "repo_url": "https://gitee.com/owner-example/efg-test.git",
  "prompt": "用户输入",
  "task_kind": "coding",
  "created_at": "2026-08-16T12:00:00+08:00"
}
```

### 5.3 分布式锁

必须有两类锁。

#### 5.3.1 会话锁

同一个 `thread_id` 同一时间只允许一轮任务运行。

Redis key：

```text
lock:thread:{thread_id}
```

作用：

- 防止用户连续点击发送导致同一会话两轮任务并发。
- 防止第二轮任务计划插到第一轮输出中。
- 防止 checkpoint 同一 thread 被同时写入。

#### 5.3.2 仓库写锁

同一个 Gitee 仓库同一时间只允许一个写任务。

Redis key：

```text
lock:repo-write:{owner}/{repo}
```

需要加写锁的任务：

| 任务类型 | 是否需要仓库写锁 |
| --- | --- |
| `coding` | 需要 |
| `sync` / `pull` / `push` | 需要 |
| 创建 PR | 需要 |
| `planning` | 通常不需要 |
| `qa` | 不需要 |
| `analysis` | 不需要 |
| `review` | 通常不需要，除非要发布 PR 评论 |

### 5.4 实时事件总线

第三阶段建议把当前 `event_sink(event, data)` 改成写 Redis Stream。

Redis Stream key：

```text
stream:run:{run_id}
```

事件示例：

```json
{
  "event": "text_delta",
  "thread_id": "thread-uuid",
  "run_id": "run-uuid",
  "message_id": "thread-live-assistant-run-1",
  "content": "正在读取项目结构...",
  "mode": "replace"
}
```

SSE 接口不再等待本进程队列，而是读 Redis Stream：

```mermaid
sequenceDiagram
    autonumber
    participant W as Agent Worker
    participant R as Redis Stream
    participant API as 任意 ASGI 容器
    participant V as Vue 前端

    W->>R: XADD stream:run:{run_id} text_delta
    API->>R: XREAD stream:run:{run_id}
    API-->>V: SSE text_delta
    W->>R: XADD stream:run:{run_id} done
    API-->>V: SSE done
```

这样前端连接到任意 ASGI 容器，都能读取同一个 run 的事件。

---

## 6. Agent Worker 设计

### 6.1 为什么要拆 Worker

如果 ASGI 容器直接运行 Agent，会有几个问题：

| 问题 | 说明 |
| --- | --- |
| Web 请求被长时间占用 | Agent 运行可能几分钟甚至更久 |
| 容器重启影响任务 | Web 容器重启会直接中断 Agent |
| 扩容职责混乱 | Web 扩容和 Agent 执行扩容绑在一起 |
| 并发控制困难 | 每个 Web 容器都要维护任务执行状态 |

拆出 Worker 后：

- Web 容器负责短请求和 SSE。
- Worker 负责长任务。
- Worker 数量可以按模型额度、CPU、内存、工作区 IO 单独扩容。

### 6.2 Worker 主循环伪代码

```python
def worker_loop():
    while True:
        task = redis_queue.pop()
        if task is None:
            sleep(1)
            continue

        run_id = task["run_id"]
        thread_id = task["thread_id"]
        repo_url = task["repo_url"]

        with acquire_thread_lock(thread_id):
            with acquire_repo_lock_if_needed(task):
                try:
                    mark_run_running(run_id)
                    run_agent_task(
                        repo_url=repo_url,
                        prompt=task["prompt"],
                        thread_id=thread_id,
                        event_sink=redis_stream_event_sink(run_id),
                    )
                    mark_run_completed(run_id)
                except Exception as exc:
                    mark_run_failed(run_id, exc)
                    publish_error_event(run_id, exc)
                finally:
                    publish_done_event(run_id)
```

### 6.3 Worker 数量建议

Worker 不是越多越好，因为每个 Agent 会占用：

- 模型调用额度；
- git / pytest / pip 等系统资源；
- 工作区文件 IO；
- Redis / PostgreSQL 连接；
- CPU 和内存。

建议：

| 场景 | Web 容器 | Worker 容器 | 模型并发 |
| --- | --- | --- | --- |
| 讲课演示 | 1 | 1 | 1-2 |
| 小团队 | 2 | 2 | 2-4 |
| 多学生实验 | 2-4 | 3-6 | 3-8 |
| 企业内部平台 | 4+ | 6+ | 根据模型额度动态调整 |

---

## 7. 工作区设计

### 7.1 本地工作区到 Linux 工作区

当前本地路径：

```text
<AI_WORKSPACE_ROOT>
```

云端建议：

```text
/data/ai_workspace
```

目录结构保持一致：

```text
/data/ai_workspace
├── projects/
├── skills/
├── policies/
├── reviews/
├── runtimes/
├── logs/
└── tmp/
```

### 7.2 共享工作区的几种方案

| 方案 | 说明 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 单机 Docker volume | 所有容器挂载同一宿主机目录 | 简单 | 只能单机 |
| 阿里云 NAS / NFS | 多台机器共享目录 | 支持多机 | IO 延迟和文件锁要测试 |
| 每任务独立工作区 | Worker 为每个 run clone 独立目录 | 隔离最好 | 占空间，clone 慢 |
| 每仓库独立工作区 | `/projects/{owner}/{repo}` | 复用仓库，较省空间 | 同仓库写任务必须加锁 |

第一版建议：

> 每仓库独立工作区 + Redis 仓库写锁。

示例：

```text
/data/ai_workspace/projects/owner-example/efg-test
/data/ai_workspace/projects/owner-example/abc-test
```

### 7.3 coding 任务工作区保护

同一个仓库 coding 时必须串行：

```mermaid
flowchart TD
    A["coding 任务进入"] --> B["解析 owner/repo"]
    B --> C["获取 lock:repo-write:owner/repo"]
    C -->|成功| D["pull / checkout / edit / test / push / PR"]
    C -->|失败| E["任务排队或返回等待提示"]
    D --> F["释放 repo 写锁"]
```

只读任务可以不拿写锁，但如果读取过程中需要保证一致性，可以读取当前分支快照或最近 commit。

---

## 8. Nginx 配置

### 8.1 基础负载均衡

示例：

```nginx
upstream lx_aicoding_backend {
    server my-aicoding-api-1:8000;
    server my-aicoding-api-2:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }

    location /dashboard/api/ {
        proxy_pass http://lx_aicoding_backend;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

### 8.2 SSE 必须关闭缓冲

SSE 接口必须关闭 Nginx buffering：

```nginx
location /dashboard/api/ {
    proxy_pass http://lx_aicoding_backend;
    proxy_http_version 1.1;

    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;

    chunked_transfer_encoding on;
    add_header X-Accel-Buffering no;
}
```

如果不关闭 buffering，前端会出现：

- Agent 后端已经在输出日志；
- 浏览器一直看不到 token；
- 等到缓冲区满或请求结束才一次性显示。

这和本项目之前遇到的“一次性展示技术方案”现象非常类似。

### 8.3 是否需要 sticky session

如果还停留在第二阶段，Agent 在接收 SSE 的 Web 容器里直接运行，那么一次 SSE 请求本身会固定在某个 upstream 连接上，通常不需要额外 sticky session。

但如果页面还会额外通过 GET 轮询同一任务的本地内存状态，则需要 sticky session。当前推荐方案不依赖本地内存状态，所以不需要。

第三阶段使用 Redis Stream 后：

> 不需要 sticky session。任意 ASGI 容器都可以从 Redis Stream 读取同一个 run 的事件。

---

## 9. Docker Compose 参考结构

### 9.1 服务拆分

建议拆成这些容器：

| 服务 | 说明 |
| --- | --- |
| `nginx` | 前端静态资源 + API 反向代理 |
| `api` | FastAPI ASGI Web 服务，可多副本 |
| `worker` | Agent Worker，可多副本 |
| `postgres` | PostgreSQL |
| `redis` | Redis |

### 9.2 示例 docker-compose

```yaml
services:
  nginx:
    image: nginx:1.27
    ports:
      - "80:80"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ui/dist:/usr/share/nginx/html:ro
    depends_on:
      - api

  api:
    build:
      context: .
      dockerfile: Dockerfile
    command: uvicorn agent.app:app --host 0.0.0.0 --port 8000
    environment:
      APP_ENV: production
      WORKSPACE_ROOT: /data/ai_workspace
      DATABASE_URL: postgresql+psycopg://lx:${POSTGRES_PASSWORD}@postgres:5432/lx_aicoding
      REDIS_URL: redis://redis:6379/0
      MAIN_MODEL: deepseek-v4-pro
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL}
      GITEE_WEBHOOK_SECRET: ${GITEE_WEBHOOK_SECRET}
    volumes:
      - ai_workspace:/data/ai_workspace
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: python -m agent.worker
    environment:
      APP_ENV: production
      WORKSPACE_ROOT: /data/ai_workspace
      DATABASE_URL: postgresql+psycopg://lx:${POSTGRES_PASSWORD}@postgres:5432/lx_aicoding
      REDIS_URL: redis://redis:6379/0
      MAIN_MODEL: deepseek-v4-pro
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL}
      GITEE_WEBHOOK_SECRET: ${GITEE_WEBHOOK_SECRET}
    volumes:
      - ai_workspace:/data/ai_workspace
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: lx_aicoding
      POSTGRES_USER: lx
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  ai_workspace:
  postgres_data:
  redis_data:
```

说明：

- 上面是架构参考，不是当前项目可直接运行的最终配置。
- 当前项目需要先实现 PostgreSQL Store、Redis 队列、Redis Stream event sink、Worker 入口。
- Docker Swarm 的 `deploy.replicas` 在普通 `docker compose up` 下不生效，如果不用 Swarm，需要手动 scale。

---

## 10. 环境变量和密钥管理

### 10.1 不要把密钥写进镜像

这些内容不能写入 Dockerfile 或提交到 Git：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `GITEE_WEBHOOK_SECRET`
- Gitee 私人令牌
- 数据库密码
- Redis 密码
- SSH 私钥

建议方式：

| 场景 | 推荐 |
| --- | --- |
| 单机 Docker Compose | `.env` 文件放服务器，不提交 Git |
| Docker Swarm | Docker secrets |
| Kubernetes | Secret / ConfigMap |
| 阿里云生产 | KMS / 环境变量 / 容器服务 Secret |

### 10.2 环境变量分组

| 分组 | 示例 |
| --- | --- |
| 应用配置 | `APP_ENV`、`WORKSPACE_ROOT`、`LOG_LEVEL` |
| 数据库 | `DATABASE_URL` |
| Redis | `REDIS_URL` |
| 模型 | `MAIN_MODEL`、`OPENAI_API_KEY`、`OPENAI_BASE_URL` |
| Gitee | `GITEE_WEBHOOK_SECRET`、`GITEE_TOKEN_USERNAME` |
| 并发 | `MAX_MODEL_CONCURRENCY`、`MAX_REPO_WRITE_CONCURRENCY` |
| SSE | `SSE_HEARTBEAT_SECONDS`、`SSE_TIMEOUT_SECONDS` |

---

## 11. 并发控制方案

### 11.1 并发控制总原则

| 资源 | 策略 |
| --- | --- |
| 同一会话 | 串行 |
| 同一仓库写任务 | 串行 |
| 只读任务 | 有限并发 |
| 模型调用 | 全局限流 |
| Worker 数量 | 按 CPU、内存、模型额度调整 |
| PostgreSQL 连接 | 使用连接池 |
| Redis Stream | 每个 run 独立 stream |

### 11.2 锁粒度

```mermaid
flowchart TD
    A["任务进入 Worker"] --> B["获取 thread 锁"]
    B --> C{"是否写任务?"}
    C -->|否| D["直接执行只读 Agent"]
    C -->|是| E["获取 repo-write 锁"]
    E --> F["执行 coding/sync/push/PR"]
    D --> G["释放 thread 锁"]
    F --> H["释放 repo-write 锁"]
    H --> G
```

锁 key：

| 锁 | Redis key |
| --- | --- |
| 会话锁 | `lock:thread:{thread_id}` |
| 仓库写锁 | `lock:repo-write:{owner}/{repo}` |
| 模型并发 | `limit:model:{model_name}` |

### 11.3 锁超时

所有分布式锁都必须有过期时间。

例如：

```text
SET lock:repo-write:owner-example/efg-test worker-uuid NX EX 1800
```

含义：

- `NX`：不存在时才设置，保证互斥。
- `EX 1800`：30 分钟自动过期，避免 Worker 崩溃后永久死锁。
- value 使用 `worker-uuid`，释放锁时要确认持有者，避免误删别人的锁。

### 11.4 排队策略

如果锁不可用，有两种策略：

| 策略 | 说明 | 适用 |
| --- | --- | --- |
| 立即拒绝 | 返回“当前仓库正在运行写任务，请稍后再试” | 课程演示、低复杂度 |
| 进入队列等待 | run 状态保持 queued，Worker 稍后重试 | 多用户平台 |

推荐生产使用队列等待，但要设置最大等待时间。

---

## 12. SSE 在多容器下的实现

### 12.1 第二阶段 SSE

第二阶段中，SSE 和 Agent 仍在同一 Web 容器：

```mermaid
sequenceDiagram
    participant V as Vue
    participant API as ASGI 容器
    participant RT as runtime.py

    V->>API: POST SSE
    API->>RT: run_agent_task
    RT-->>API: event_sink -> asyncio.Queue
    API-->>V: SSE
```

优点：

- 改造小。
- 接近当前项目结构。

缺点：

- Web 容器承担长任务。
- 容器重启会影响任务。
- 不利于独立扩容 Worker。

### 12.2 第三阶段 SSE

第三阶段中，SSE 从 Redis Stream 读取：

```mermaid
sequenceDiagram
    participant V as Vue
    participant API as 任意 ASGI 容器
    participant R as Redis Stream
    participant W as Agent Worker

    V->>API: POST SSE
    API->>R: XADD task queue
    W->>R: XREAD task queue
    W->>R: XADD stream:run:{run_id} text_delta
    API->>R: XREAD stream:run:{run_id}
    API-->>V: SSE text_delta
    W->>R: XADD stream:run:{run_id} done
    API-->>V: SSE done
```

优点：

- API 容器和 Worker 解耦。
- 任意 API 容器都能提供 SSE。
- Worker 可单独扩容。
- 任务事件不依赖单个进程内存。

缺点：

- 需要 Redis Stream 管理消费位置。
- 需要处理 SSE 客户端重连后从哪个 event id 继续读。
- 实现复杂度高于本地队列。

### 12.3 SSE 心跳

长连接需要心跳，避免代理或浏览器以为空闲断开。

SSE 心跳事件：

```text
event: ping
data: {"ts": 1780000000000}
```

建议：

| 参数 | 建议值 |
| --- | --- |
| 心跳间隔 | 15-30 秒 |
| Nginx `proxy_read_timeout` | 1800-3600 秒 |
| 前端无事件超时 | 60-120 秒 |
| Agent 最大运行时间 | 按任务类型设置，例如 10-30 分钟 |

---

## 13. 代码改造清单

### 13.1 第一阶段代码改造

| 模块 | 改造 |
| --- | --- |
| `settings.py` | 支持 Linux `WORKSPACE_ROOT=/data/ai_workspace` |
| `local_shell.py` | 确认路径解析兼容 Linux |
| `start_all.py` | 云端可拆分为单独后端启动命令 |
| `dashboard_routes.py` | SSE header 保持 no-buffering |
| 日志 | 输出 stdout + 文件可选 |

### 13.2 第二阶段代码改造

| 模块 | 改造 |
| --- | --- |
| `store` | 新增 PostgreSQL Store 实现 |
| `graph.py` | checkpointer / LangGraph Store 改 PostgreSQL |
| `runtime.py` | 接入 Redis 分布式锁 |
| `events.py` | run_events 写 PostgreSQL |
| `server.py` | 不依赖进程内状态保存关键数据 |
| 配置 | 新增 `DATABASE_URL`、`REDIS_URL` |

### 13.3 第三阶段代码改造

| 模块 | 改造 |
| --- | --- |
| `agent/worker.py` | 新增 Worker 入口 |
| `runtime.py` | 支持被 Worker 调用，不直接依赖 FastAPI |
| `dashboard_routes.py` | 提交任务到 Redis 队列，SSE 从 Redis Stream 读 |
| `streaming_runtime.py` | `event_sink` 写 Redis Stream |
| `lock_manager.py` | Redis 分布式锁 |
| `queue.py` | Redis 队列封装 |
| `deployment` | Dockerfile、compose、Nginx 配置 |

---

## 14. 监控和日志

### 14.1 日志

建议所有容器都输出 JSON 日志到 stdout：

| 字段 | 说明 |
| --- | --- |
| `ts` | 时间 |
| `level` | INFO / WARNING / ERROR |
| `service` | api / worker |
| `thread_id` | 会话 ID |
| `run_id` | 本轮运行 ID |
| `repo` | owner/repo |
| `task_kind` | planning/coding/review/qa |
| `event` | 当前事件 |
| `duration_ms` | 耗时 |
| `error` | 脱敏错误 |

### 14.2 指标

建议监控：

| 指标 | 说明 |
| --- | --- |
| 当前 running run 数量 | 判断系统负载 |
| queued run 数量 | 判断是否积压 |
| coding 平均耗时 | 判断 Worker 是否足够 |
| 模型调用次数 | 控制成本 |
| 模型错误率 | 监控 API 稳定性 |
| Gitee API 错误率 | 监控认证和限流 |
| Redis lock 等待时间 | 判断仓库冲突 |
| PostgreSQL 慢查询 | 判断数据库瓶颈 |
| SSE 连接数 | 判断 Web 压力 |

### 14.3 告警

建议配置告警：

- queued 任务超过阈值。
- running 任务超过最大运行时间。
- Redis 不可用。
- PostgreSQL 连接池耗尽。
- 模型 API 连续失败。
- Gitee push/PR 连续失败。
- Worker 心跳丢失。

---

## 15. 安全方案

### 15.1 Token 安全

| 风险 | 方案 |
| --- | --- |
| 日志泄露 token | 所有日志经过 `mask_token` |
| 镜像泄露 token | 不把 `.env` COPY 到镜像 |
| 前端泄露 token | Gitee token 只在后端使用 |
| PR URL 带 token | 禁止输出带 token 的 remote URL |

### 15.2 工作区权限

云端仍然要保留 DeepAgents 权限控制：

- 主 Agent 可写 `/projects`、`/reviews`、`/tmp`。
- reviewer 子 Agent 只读 `/projects`，只写 `/reviews`、`/tmp`。
- `/skills`、`/policies`、`/runtimes` 默认只读。
- `/memories` 通过 StoreBackend 读写，不对应真实文件系统路径。

### 15.3 容器权限

建议：

- 容器不要使用 root 用户运行应用。
- 工作区目录只挂载必要路径。
- secrets 只注入 api/worker，不注入 nginx。
- 限制容器可访问的内网资源。
- 对公网只暴露 Nginx。

---

## 16. 迁移路线图

### 16.1 第一周：单容器云端可运行

目标：

- 项目能在阿里云 Linux 上启动。
- Nginx 能代理前端和 FastAPI。
- SSE 不被缓冲。
- Gitee clone/push/PR 成功。
- deepseek-v4-pro 模型调用成功。

验收：

| 测试 | 预期 |
| --- | --- |
| 打开首页 | Vue 页面正常 |
| 输入技术方案任务 | SSE 实时输出 |
| 确认实施 | 能改代码、测试、PR |
| 查看历史 | checkpoint 恢复正常 |
| 删除会话 | Store + checkpoint 清理 |

### 16.2 第二周：PostgreSQL + Redis 锁

目标：

- SQLite Store 迁移 PostgreSQL。
- checkpoint 迁移 PostgreSQL。
- Redis 分布式锁保护 thread 和 repo。
- 多个 ASGI 容器可同时运行。

验收：

| 测试 | 预期 |
| --- | --- |
| 两个容器同时启动 | 都能查询同一历史 |
| 同 thread 连续提交 | 第二个任务排队或拒绝 |
| 同 repo 两个 coding | 串行执行 |
| 多个 qa/review | 可有限并发 |

### 16.3 第三周：Worker + Redis Stream

目标：

- Web 层不再直接运行 Agent。
- Worker 从队列消费任务。
- SSE 从 Redis Stream 读取事件。
- Worker 可水平扩容。

验收：

| 测试 | 预期 |
| --- | --- |
| API 容器重启 | 已运行 Worker 任务不受影响 |
| SSE 连接到任意 API 容器 | 都能收到当前 run 事件 |
| Worker 扩容 | 队列消费能力提升 |
| Worker 异常退出 | run 标记 failed 或重新入队 |

---

## 17. 最终推荐结论

如果只是课程演示，可以先做：

> 单容器 + Nginx + SQLite + Linux 工作区。

如果要部署到你的阿里云服务器，并且有多个 Docker ASGI 节点，至少要做到：

> 多 ASGI 容器 + PostgreSQL + Redis 分布式锁 + Nginx SSE 配置。

如果要稳定支持多人同时使用，最终推荐：

> 多 ASGI Web 容器 + 独立 Agent Worker + PostgreSQL + Redis Queue/Stream/Lock + 共享工作区 + Nginx 负载均衡。

一句话总结：

> ASGI 容器做 Web 接口，Worker 做 Agent 长任务，PostgreSQL 保存长期状态，Redis 负责队列、锁和实时事件，Nginx 负责流量入口和 SSE 代理；同一会话串行，同一仓库写任务串行，只读任务有限并发。
