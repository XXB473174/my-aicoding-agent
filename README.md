# MY-AICODING

本地运行的 AI Coding 智能体：用 FastAPI + DeepAgents/LangGraph 驱动 DeepSeek，在受控工作区里完成 **Gitee 仓库分析、技术方案、代码修改、测试、提交、推送、创建 Pull Request 和代码审查**，并通过 Vue 3 + POST SSE 页面实时展示过程。

> 当前版本只支持 **Gitee**，不支持 GitHub、GitLab、Bitbucket 等其他托管平台。

> 仓库地址：<https://github.com/XXB473174/my-aicoding-agent>　使用条款见[第 8 节](#8-开源与使用说明)。

---

## 1. 项目解决什么问题

直接把“让 AI 改代码”放进真实仓库，通常会遇到四个问题：

1. **AI 一上来就改代码**：需求还没确认，文件已经被修改，回滚成本高。
2. **执行过程不可见**：模型读了哪些文件、跑了什么测试、有没有提交和创建 PR，用户看不到。
3. **上下文反复丢失**：每次对话都重新分析仓库，重复扫描、重复试错。
4. **审查和修复混在一起**：Review 还没确认，代码已经被“顺手”改掉。

MY-AICODING 把这件事拆成一条可观察、可恢复的本地流程：

```text
用户提出需求
  -> 识别任务类型（分析 / 方案 / 问答 / 审查 / 同步 / 开发）
  -> 开发类任务先生成技术方案，等待用户确认
  -> 用户确认后进入 coding
  -> 在本地工作区读取仓库、修改代码、运行测试
  -> git add / commit / push
  -> 创建或复用 Gitee Pull Request
  -> 任务完成后更新仓库级长期记忆
```

核心思路：

- **先方案、后实施**：coding 必须拿到用户确认过的方案，否则 runtime 会把任务转成 planning。
- **本地受控工作区**：Agent 只在自己的工作区里操作仓库，不直接碰项目源码目录。
- **过程可观察**：任务计划、模型正文、状态、分支、PR 地址通过 SSE 实时展示。
- **状态可恢复**：聊天历史写入 LangGraph checkpoint，业务状态写入 SQLite Store。
- **审查只读**：`code_reviewer` 子 Agent 只读 diff 和 PR 上下文，不修改代码、不提交、不创建 PR。

---

## 2. 主要功能

### 2.1 Gitee 仓库开发闭环

- 支持 `https://gitee.com/<owner>/<repo>`、`https://gitee.com/<owner>/<repo>.git` 和 `owner/repo` 三种输入形式。
- 通过 DeepAgents 原生 `execute` 执行普通 Git 命令：`clone`、`fetch`、`status`、`add`、`commit`、`push`。
- 通过 `open_gitee_pull_request` 创建或复用 Gitee Pull Request（相同 `head/base` 的 PR 会复用）。
- 通过 `publish_gitee_pr_comment` 发布 PR 评论；按系统提示词流程，发布前会先询问用户确认。
- Gitee Token 由 `LocalShellBackend` 通过 Git askpass 注入，不写入命令、日志或 commit message。

### 2.2 任务类型识别与只读保护

运行时会把用户输入归类为 7 种任务类型：

| 类型 | 典型输入 | 行为 |
|---|---|---|
| `inspect` | “当前工作区有哪些项目？” | 不调用模型，直接查看 `/projects` |
| `sync` | “把远程代码 pull 一下” | 不调用模型，执行 clone / fetch / pull（固定 `master` 和 `--ff-only`） |
| `qa` | “这个函数是做什么的？” | 按只读模式问答 |
| `analysis` | “分析这个项目的结构” | 按只读模式分析 |
| `planning` | “给我一个改造方案” | 按只读模式输出技术方案并等待确认 |
| `review` | “审查这个 PR” | 委派 `code_reviewer` 子 Agent 做业务代码只读审查，可保存审查报告 |
| `coding` | “实现这个功能”“确认实施” | 在拿到确认方案后，允许修改代码、测试、提交、push、创建 PR |

分类采用“模型结构化分类 + 关键词兜底 + 安全降级”：

- 用户明确说“不要修改”“只分析”“只审查”时，会强制降级为只读任务。
- 用户明确说“确认实施”“开始实施”“提交”“push”，并且当前会话存在可确认方案时，才允许进入 coding。
- 模型分类失败时自动回退到关键词规则，不会因为模型异常而放开写权限。

### 2.3 先方案、后实施（Human-in-the-loop）

- 全新会话中的开发需求会先进入 `planning`，输出中文 Markdown 技术方案，最后询问“是否确认实施该方案？”。
- 方案正文以 LangGraph checkpoint 为权威来源，不写入 `thread_plans`，也不保存 Markdown 文件。
- 用户输入“确认实施 / 同意 / 按方案实施 / 开始实施”后，runtime 从 checkpoint 找回最近的方案，再以 `coding` 模式执行。
- 用户输入“修改方案 / 补充方案 / 重新生成方案”后，会基于上一版方案重新输出完整新版方案。
- 没有可确认方案时，单独输入“确认”不会执行旧任务，而是按当前输入重新分类处理。

### 2.4 代码审查子 Agent

- 用户要求 PR Review 时，主 Agent 委派 `code_reviewer`。
- Reviewer 可读取：Gitee PR 详情、提交列表、变更文件、已有评论、本地 diff、审查规则。
- 结构化 finding 写入 `store.sqlite` 的 `review_findings` 表，包含文件、行号、severity、标题和描述。
- 最终输出中文审查报告：结论、阻塞问题、高风险问题、一般建议、测试建议。
- 用户要求保存时，可写入 `/reviews/<repo>/pr-<number>-review.md`。
- Reviewer 不修改业务代码、不提交、不 push、不创建 PR；发布 PR 评论由主 Agent 按提示词流程先征得用户确认后执行。
- 支持“审查 -> 修复方案 -> 确认实施”的闭环：主 Agent 读取审查报告和结构化 findings，先生成修复方案，确认后再修复代码。

### 2.5 仓库级长期记忆

- 每个 Gitee 仓库有独立的记忆文件：`/memories/{owner}/{repo}.md`。
- 记忆由 LangGraph Store 持久化，默认文件为 `data/langgraph_store.sqlite`。
- 首次处理仓库时自动写入模板；分析、问答、审查、coding 等通用 Agent 任务结束后，会从最终回答中提取技术栈、测试命令、关键文件、分支和 PR 等稳定信息并更新。
- 每轮 Agent 开始前，运行时会把仓库标识、记忆路径和记忆正文注入上下文，减少重复分析。
- 记忆与真实文件冲突时，以真实仓库文件和命令输出为准。

### 2.6 受控本地工作区

Agent 看到的路径是虚拟路径，实际映射到 `AI_WORKSPACE_ROOT`：

| 虚拟路径 | 用途 | Agent 写权限 |
|---|---|---|
| `/projects` | Gitee 仓库克隆目录 | 允许 |
| `/reviews` | 审查报告 | 允许 |
| `/tmp` | 临时文件 | 允许 |
| `/memories` | 仓库级长期记忆 | 允许 |
| `/skills` | DeepAgents skills | 只读 |
| `/policies` | 工作区规范 | 只读 |
| `/runtimes` | 共享运行环境 | 只读 |
| `/logs` | 工作区日志 | 只读 |
| `.secrets` | Git askpass 等敏感文件 | 禁止访问 |

同时包含：

- 命令安全守卫：拦截危险命令、路径穿越和工作区外绝对路径。
- Token 脱敏：日志、异常、工具输出中的 Gitee Token 会替换为 `***`。
- 超时控制：单次 `execute` 默认最长 3600 秒。
- 单轮运行保护：按任务类型限制工具调用次数和运行时长。

### 2.7 实时 Web 页面

- Vue 3 + Vite，单页应用，无需额外路由。
- POST SSE 单请求完成“提交用户消息 + 运行 Agent + 流式返回”。
- 页面展示：用户消息、任务计划卡片、Markdown 回答、运行状态、当前分支、PR 链接。
- 左侧会话列表支持新建、切换和删除；删除会同时清理 Store 和 checkpoint。
- 历史正文只从 LangGraph checkpoint 恢复，不从 Store 的 `run_events` 拼接。

### 2.8 外部资料工具

- `web_search`：调用智谱 Web Search API，补充框架文档、错误背景等外部资料（需要 `ZHIPU_API_KEY`）。
- `fetch_url`：读取用户指定的 HTTP/HTTPS 页面，带内网/本机地址拦截和重定向校验。

---

## 3. 安装方法

### 3.1 环境要求

| 依赖 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（主要支持）；Linux 可参考 `scripts/start_backend.sh` 与 `.env` 中的 Linux 路径示例 |
| Python | 3.14+（`pyproject.toml` 声明 `>=3.14`，推荐 3.14） |
| Node.js | 20.19+ 或 22.12+（Vite 7 要求，推荐 Node.js 22/24） |
| Git | 已安装并可在命令行使用 |
| 账号 | DeepSeek API Key；具备仓库读写权限的 Gitee 私人令牌 |

> **版本注意**：当前代码按 `deepagents==0.6.11` 编写，请固定该版本。安装 `deepagents 0.7+` 可能出现 backend factory 和 permissions 兼容错误。

### 3.2 创建 Python 环境并安装依赖

在项目根目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel

.venv\Scripts\python.exe -m pip install `
  "deepagents==0.6.11" `
  "fastapi>=0.138.0" `
  "uvicorn>=0.49.0" `
  "langchain-openai>=1.3.2" `
  "langgraph-checkpoint-sqlite>=3.1.0" `
  "python-dotenv>=1.2.2" `
  "requests>=2.32.0" `
  "httpx>=0.27" `
  "zhipuai>=2.1.5"
```

Linux/macOS 把 `.venv\Scripts\python.exe` 换成 `.venv/bin/python` 即可。

### 3.3 安装前端依赖

```powershell
cd ui
npm install
cd ..
```

如果本机已安装 Yarn，也可以使用 `yarn install`（项目带有 `ui/yarn.lock`）。

### 3.4 配置 `.env`

在项目根目录创建 `.env`（仓库已忽略该文件，不要提交真实密钥）。可以先复制模板再填值：

```powershell
Copy-Item .env.example .env
```

下面示例中的项目路径请按实际位置修改：

```env
# ===== DeepSeek（必填）=====
DEEPSEEK_API_KEY=sk-你的DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
MAIN_MODEL=deepseek-v4-pro

# ===== Gitee（必填）=====
# 需要仓库读取、提交、推送和创建 PR 的权限
GITEE_TOKEN=你的Gitee私人令牌
GITEE_API_BASE_URL=https://gitee.com/api/v5

# ===== 工作区与数据目录（建议显式配置）=====
AI_WORKSPACE_ROOT=C:\ai_workspace
LX_AICODING_DATA_DIR=<项目目录>\data
LX_AICODING_LOG_DIR=<项目目录>\logs

# ===== 可选：联网搜索 =====
ZHIPU_API_KEY=你的智谱Key
```

说明：

- `.env` 中的**非空值优先于同名系统环境变量**；空值不会覆盖系统变量。
- `GITEE_TOKEN` 找不到时会回退读取 `SCM_GITEE_TOKEN`。
- `AI_WORKSPACE_ROOT` 是 Agent 的工作区，不要指向项目源码目录（否则 Agent 可能改动本项目）；后端首次运行会自动创建 `projects`、`skills`、`policies`、`reviews`、`runtimes`、`tmp`、`logs`、`.secrets` 子目录。
- 如果希望把数据或日志放到其他位置，可继续配置 `CHECKPOINT_DB_PATH`、`STORE_DB_PATH`、`LANGGRAPH_STORE_DB_PATH`。

常用可选配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `INTENT_MODEL` | 同 `MAIN_MODEL` | 意图分类模型 |
| `INTENT_MODEL_TEMPERATURE` | `0` | 意图分类温度 |
| `INTENT_MODEL_MAX_TOKENS` | `200` | 意图分类最大输出 |
| `LX_AICODING_LOG_LEVEL` | `INFO` | 日志级别 |
| `LX_AICODING_LOG_RETENTION_DAYS` | `14` | 日志保留天数 |
| `AGENT_MAX_TOOL_CALLS` | `240` | 全局单轮工具调用上限 |
| `AGENT_MAX_SECONDS` | `1800` | 全局单轮运行秒数上限 |
| `AGENT_CODING_MAX_TOOL_CALLS` | `300` | coding 任务工具调用上限 |
| `AGENT_CODING_MAX_SECONDS` | `1800` | coding 任务运行秒数上限 |

### 3.5 同步 skills 到工作区

DeepAgents 运行时读取的是 `AI_WORKSPACE_ROOT/skills`，项目源码中的 skills 位于 `agent/skills`，安装后需要同步一次：

```powershell
# sync_skills.py 直接读取进程环境变量，不会自动加载 .env
# 这里必须与 .env 中的 AI_WORKSPACE_ROOT 保持一致
$env:AI_WORKSPACE_ROOT = "C:\ai_workspace"

.venv\Scripts\python.exe scripts\sync_skills.py
.venv\Scripts\python.exe scripts\verify_skills_sync.py
```

同步的 skill：

- `repo-bootstrap-analysis`：首次分析陌生 Gitee 仓库。
- `ai-coding-implementation`：复杂业务代码实施、测试和 Git 收尾。
- `code-review`：PR / diff 代码审查。

> 以后修改了 `agent/skills` 下的内容，需要重新执行一次 `sync_skills.py` 才会生效。

### 3.6 启动

同时启动前后端：

```powershell
.venv\Scripts\python.exe scripts\start_all.py
```

打开：

- 前端页面：<http://127.0.0.1:3000>
- 后端健康检查：<http://127.0.0.1:2024/health>

也可以分开启动：

```powershell
scripts\start_backend.cmd   # 后端 127.0.0.1:2024
scripts\start_ui.cmd        # 前端 127.0.0.1:3000
```

停止：

```powershell
.venv\Scripts\python.exe scripts\stop_all.py
```

或直接按 `Ctrl+C`，`start_all.py` 会同时停止前后端并清理 2024/3000 端口。如果启动前端口已被其他进程占用，可以先执行 `scripts\stop_all.py`。

### 3.7 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:2024/health
```

返回示例：

```json
{
  "ok": true,
  "project_root": "C:\\my_project\\MY_AICoding",
  "workspace_root": "C:\\ai_workspace",
  "checkpoint_db": "C:\\my_project\\MY_AICoding\\data\\checkpoints.sqlite",
  "store_db": "C:\\my_project\\MY_AICoding\\data\\store.sqlite",
  "log_dir": "C:\\my_project\\MY_AICoding\\logs",
  "backend_log": "C:\\my_project\\MY_AICoding\\logs\\backend.log",
  "agent_log": "C:\\my_project\\MY_AICoding\\logs\\agent-runs.log",
  "has_deepseek_key": true,
  "deepseek_base_url": "https://api.deepseek.com",
  "main_model": "deepseek-v4-pro",
  "has_gitee_token": true
}
```

`/health` 只返回密钥是否存在，不会返回真实 Key 或 Token。

---

## 4. 使用方法

### 4.1 页面操作

1. 打开 <http://127.0.0.1:3000>。
2. 在底部“Gitee 仓库”输入框填写仓库地址，支持完整 URL 或 `owner/repo`。
   - 页面默认值是占位地址 `https://gitee.com/owner/repo`，请改成你自己的测试仓库。
3. 在输入框写任务，`Enter` 发送，`Shift+Enter` 换行。
4. 右侧会实时显示：用户消息、任务计划卡片、Markdown 回答、运行状态。
5. 创建 PR 后，页面顶部会出现当前分支和 PR 链接。
6. 左侧可以新建任务、切换历史会话、删除会话（删除会同时清理聊天历史和业务记录）。

### 4.2 推荐流程：先方案，再实施

**第一步：提出开发需求**

```text
给 https://gitee.com/owner/demo 增加部门管理模块，包含列表、新增、修改、删除和 pytest 测试。
```

第一轮不会修改代码，而是输出技术方案，最后询问“是否确认实施该方案？”。

**第二步：确认实施**

```text
确认实施
```

后端会从当前会话的 checkpoint 找到上一份方案，以 coding 模式执行：读取仓库、修改代码、运行测试、提交、push、创建或复用 PR。

**如果方案需要调整**

```text
修改方案：部门删除改成软删除，并补充权限校验。
```

会基于上一版方案重新输出完整新版方案，仍然不会直接改代码。

### 4.3 只读任务示例

```text
分析 https://gitee.com/owner/demo 的项目结构、启动方式和测试方式。
```

```text
这个项目的订单状态流转在哪些文件里实现？
```

```text
只审查 https://gitee.com/owner/demo 的 PR #12，不要修改代码。
```

这些任务按只读模式运行，不会主动写文件、提交、push 或创建 PR。

### 4.4 代码审查与修复闭环

**审查 PR**

```text
审查 https://gitee.com/owner/demo 的 PR #12，输出中文审查报告。
```

**保存报告**

```text
把审查报告保存到 /reviews/demo/pr-12-review.md
```

**基于报告生成修复方案**

```text
根据 /reviews/demo/pr-12-review.md 和结构化 findings，生成修复技术方案。
```

**确认修复**

```text
确认实施
```

主 Agent 会按普通 coding 流程修复、测试、提交、push 并更新 PR。

**发布 PR 评论**

```text
把审查总结发布到 Gitee PR #12 的评论区。
```

系统提示词要求先询问用户确认，再调用 `publish_gitee_pr_comment`。

### 4.5 快捷分支

以下两类输入不调用模型，直接执行：

- 工作区查询：“当前工作区有哪些项目？”——直接列出 `/projects`。
- 仓库同步：“把远程代码 pull 一下”——clone 或 `fetch` + `pull origin master --ff-only`。

> 快捷分支的结果写入 `store.sqlite` 的 `run_events` 和日志；当前页面主要展示 Agent 正文和任务计划，不单独渲染 `run_events`。

### 4.6 HTTP / SSE 接口

前端实际调用：

```text
GET    /health
GET    /dashboard/api/me
GET    /dashboard/api/options
GET    /dashboard/api/threads
GET    /dashboard/api/threads/{thread_id}
POST   /dashboard/api/threads/stream-message
POST   /dashboard/api/threads/{thread_id}/stream-message
DELETE /dashboard/api/threads/{thread_id}
```

说明：

- `POST /dashboard/api/threads/stream-message`：创建新会话并运行 Agent，返回 `text/event-stream`。
- `POST /dashboard/api/threads/{thread_id}/stream-message`：在已有会话中追加一轮输入；请求体不传 `repo` 时复用会话保存的仓库地址。
- `DELETE` 成功返回 `204`；会话不存在返回 `404`。
- 没有独立的后台任务轮询接口，也不使用旧的 `/api/tasks`。
- 没有真实登录系统，`/dashboard/api/me` 返回固定的本地用户，适合本地单用户使用。

请求体：

```json
{
  "content": "给仓库增加部门管理模块",
  "repo": "https://gitee.com/owner/demo",
  "model_id": "deepseek-v4-pro",
  "effort": "default",
  "images": null
}
```

`repo` 支持完整 URL 或 `owner/repo`；`model_id`、`effort`、`images` 当前只做兼容，实际模型由 `.env` 的 `MAIN_MODEL` 决定。

SSE 事件：

| 事件 | 作用 |
|---|---|
| `thread_snapshot` | 会话元信息（状态、仓库、分支、PR） |
| `user_message` | 本轮用户输入 |
| `message_start` | 创建 assistant 消息容器 |
| `text_delta` | 模型正文增量或累计正文 |
| `todo_delta` | 任务计划列表更新 |
| `error` | 本轮运行失败 |
| `thread_done` | 本轮结束后的会话元信息（不含历史 messages） |
| `done` | 流结束 |

### 4.7 数据、日志与工作区

运行后会生成：

```text
data\checkpoints.sqlite        LangGraph checkpoint：对话历史、工具调用状态、thread state
data\store.sqlite              业务 Store：threads、runs、run_events、review_findings
data\langgraph_store.sqlite    DeepAgents StoreBackend：仓库级长期记忆
logs\backend.log               后端、接口、配置和异常日志
logs\agent-runs.log            仅 Agent 执行链路（agent.run.*）
```

日志按天轮转，历史文件名为 `backend.log.YYYY-MM-DD`、`agent-runs.log.YYYY-MM-DD`。

`AI_WORKSPACE_ROOT` 下的目录：

```text
projects/     Gitee 仓库
skills/       DeepAgents skills
policies/     工作区规范（workspace.md、git.md、security.md）
reviews/      审查报告
runtimes/     共享运行环境
tmp/          临时文件
logs/         工作区日志
.secrets/     Git askpass 等敏感文件
```

### 4.8 验证脚本

基础后端验证（不调用模型、不 push）：

```powershell
.venv\Scripts\python.exe scripts\verify_backend.py
```

skills 同步验证：

```powershell
.venv\Scripts\python.exe scripts\verify_skills_sync.py
```

真实 Gitee 任务验证（会调用模型并操作 Gitee，**只对测试仓库运行**）：

```powershell
# 第一次：按“先方案”流程生成方案
.venv\Scripts\python.exe scripts\verify_gitee_e2e.py `
  https://gitee.com/owner/test-repo.git `
  --thread-id e2e-demo

# 第二次：在同一 thread 确认实施，进入 coding 并创建 PR
.venv\Scripts\python.exe scripts\verify_gitee_e2e.py `
  https://gitee.com/owner/test-repo.git `
  --thread-id e2e-demo `
  --prompt "确认实施"
```

其他 `scripts/verify_*.py` 多数是离线或模拟验证，不需要真实模型；具体见各脚本顶部说明。运行验证脚本前，请确认 `AI_WORKSPACE_ROOT` 已创建且当前用户可写。

---

## 5. 输入输出示例

以下输出为示例节选，实际内容取决于仓库和模型。

### 示例 1：开发需求先生成方案（只读）

输入：

```text
仓库：https://gitee.com/owner/demo
给 demo 增加部门管理模块，包含列表、新增、修改、删除和 pytest 测试。
```

输出（节选）：

```markdown
## 需求理解

为 demo 增加部门管理模块，提供部门列表、新增、修改、删除接口，并补充 pytest 测试。

## 涉及模块和需要阅读的文件

- app/models.py：现有数据模型
- app/routes/：现有路由组织方式
- tests/：测试目录和 pytest 配置

## 具体实施步骤

1. 新增 Department 模型，字段包括 id、name、description、created_at。
2. 新增部门增删改查路由。
3. 补充 pytest 测试。
4. 运行最小测试并修复失败。

## 验证方案

- python -m pytest -v

## 风险点

- 删除接口需要确认是否存在关联数据。
- 需要确认权限校验方式。

是否确认实施该方案？
```

说明：本轮 `task_kind=planning`，不会修改文件、不会提交、不会创建 PR。

### 示例 2：确认实施并创建 PR

输入：

```text
确认实施
```

输出（节选）：

```markdown
已按确认的方案完成部门管理模块。

- 修改文件：app/models.py、app/routes/departments.py、tests/test_departments.py
- 验证命令：python -m pytest -v
- 测试结果：12 passed
- 分支：feature/departments
- Pull Request：https://gitee.com/owner/demo/pulls/12
```

说明：runtime 从 checkpoint 找回上一份方案，以 `coding` 模式执行；最终分支名和 PR 编号由实际执行结果决定。

### 示例 3：代码审查

输入：

```text
审查 https://gitee.com/owner/demo 的 PR #12，输出中文审查报告，不要修改代码。
```

输出（节选）：

```markdown
## 审查结论

- 结论：有条件通过
- 阻塞问题：0 个
- 高风险问题：1 个
- 一般建议：2 个

## 主要发现

| 严重级别 | 文件 | 行号 | 问题 | 建议 |
|---|---|---|---|---|
| high | app/routes/departments.py | 42 | 删除接口缺少权限校验 | 增加管理员权限校验 |
| medium | app/models.py | 18 | name 字段没有唯一约束 | 增加唯一索引并处理冲突 |

## 测试建议

- 补充无权限用户删除部门的测试。
- 补充重名部门的测试。

## 是否发布到 Gitee PR 评论？

是否需要我把以上审查总结发布到 Gitee Pull Request 评论区？
```

说明：Reviewer 只读审查；结构化 finding 写入 `store.sqlite`，不会修改代码或创建 PR。

### 示例 4：SSE 接口调用

请求：

```powershell
curl.exe -N -X POST "http://127.0.0.1:2024/dashboard/api/threads/stream-message" `
  -H "Content-Type: application/json" `
  -H "Accept: text/event-stream" `
  -d '{"content":"给仓库增加部门管理模块","repo":"https://gitee.com/owner/demo"}'
```

响应（典型事件序列）：

```text
event: thread_snapshot
data: {"id":"6f1c...","title":"给仓库增加部门管理模块","repo":"owner/demo","repoFullName":"owner/demo","branch":null,"model":"deepseek-v4-pro","status":"running","pr":null}

event: user_message
data: {"thread_id":"6f1c...","message_id":"6f1c...-user-...","author":"user","content":"给仓库增加部门管理模块"}

event: message_start
data: {"thread_id":"6f1c...","message_id":"6f1c...-assistant-startup-...","author":"agent"}

event: text_delta
data: {"thread_id":"6f1c...","message_id":"6f1c...-assistant-startup-...","content":"正在理解需求并准备仓库上下文...\n\n","mode":"append"}

event: todo_delta
data: {"thread_id":"6f1c...","message_id":"6f1c...-live-plan-...","run_id":"...","todos":[{"content":"分析仓库结构和现有实现","status":"in_progress"},{"content":"生成完整技术方案","status":"pending"}]}

event: message_start
data: {"thread_id":"6f1c...","message_id":"6f1c...-live-assistant-...-1","author":"agent","run_id":"...","assistant_index":"1"}

event: text_delta
data: {"thread_id":"6f1c...","message_id":"6f1c...-live-assistant-...-1","run_id":"...","assistant_index":"1","content":"## 需求理解...\n\n是否确认实施该方案？","mode":"replace"}

event: thread_done
data: {"id":"6f1c...","status":"finished","branch":null,"pr":null}

event: done
data: {"thread_id":"6f1c..."}
```

字段和顺序会随任务变化；页面以 `text_delta` 更新正文、以 `todo_delta` 更新任务计划、以 `done` 结束流。

### 示例 5：仓库记忆

任务完成后，`data/langgraph_store.sqlite` 中会保存类似内容：

```markdown
# 仓库记忆：owner/demo

## 基本信息
- 仓库地址：https://gitee.com/owner/demo.git
- 本地目录：/projects/demo
- 命令目录：demo

## 技术栈
- FastAPI
- SQLite
- pytest

## 测试命令
- python -m pytest -v

## 关键文件
- app/models.py
- app/routes/departments.py
- tests/test_departments.py

## 分支与 PR
- 最近分支：`feature/departments`
- 最近 Pull Request：https://gitee.com/owner/demo/pulls/12

## 最近结论
- 2026-10-22（coding）：完成部门管理模块，12 个测试全部通过。
```

Agent 可通过虚拟路径 `/memories/owner/demo.md` 读取这份记忆。

---

## 6. 项目结构

```text
agent/
  api/                FastAPI 路由：/health、/dashboard/api
  backends/           本地工作区 backend、命令安全、路径权限
  core/               运行时、意图识别、模型、持久化、中间件、SSE 事件流
  skills/             三个 DeepAgents skill 源文件
  store/              业务 SQLite Store
  tools/              Gitee、代码审查、web_search、fetch_url
  app.py              FastAPI 应用入口
  prompt.py           系统提示词
  server.py           DeepAgent 装配
scripts/
  start_all.py        同时启动前后端
  start_backend.cmd   启动后端
  start_ui.cmd        启动前端
  stop_all.py         停止 2024/3000 端口进程
  sync_skills.py      同步 skills 到工作区
  verify_*.py         各类验证脚本
ui/                   Vue 3 + Vite 前端
data/                 SQLite 数据（运行后生成，已忽略）
logs/                 日志（运行后生成，已忽略）
```

---

## 7. 已知边界与注意事项

- **只支持 Gitee**：输入 GitHub/GitLab 地址会直接提示不支持。
- **本地单用户**：没有登录、权限和多租户体系，`/dashboard/api/me` 返回固定本地用户，不要直接暴露到公网。
- **本地 shell 不是强隔离沙箱**：`LocalShellBackend` 提供路径、命令和权限保护，但不是容器级隔离；建议在专用机器或专用系统账号下运行。
- **只读模式主要靠流程约束**：`qa`、`analysis`、`planning`、`review` 通过任务路由、系统提示词和工具限制来约束写操作；主 Agent 的通用文件权限仍然允许写 `/projects`，因此不要把“只读模式”当作硬安全边界。
- **skills 需要手动同步**：修改 `agent/skills` 后必须重新执行 `scripts/sync_skills.py`。
- **同步快捷分支固定 master**：`git pull origin master --ff-only`；默认分支不是 `master` 的仓库请使用 Agent 任务而不是“pull 一下”。
- **PR 默认目标分支是 master**：仓库默认分支为 `main` 时，请在任务中明确说明。
- **首次开发需求不会直接改代码**：这是有意设计。必须看到方案后输入“确认实施”。
- **模型和网络依赖**：DeepSeek API、Gitee API、Git 网络任一不可用都会导致任务失败；详细原因看 `logs/backend.log` 和 `logs/agent-runs.log`。
- **前端是单页应用**：没有 `/agents` 等前端路由，统一访问 <http://127.0.0.1:3000>。

---

## 8. 开源与使用说明

本项目代码以只读方式公开，但**未声明开源许可证**（仓库根目录没有 `LICENSE` 文件），默认保留全部权利。使用与分享限制如下：

- **允许**：克隆、阅读、学习、自行在本地运行和修改。
- **请先确认**：转载、二次发布、用于商业用途或对外培训前，请先联系作者。
- **请勿提交**：`.env`、`Token`、日志、SQLite 数据和个人本机路径。仓库已通过 `.gitignore` 默认忽略这些内容，提交前可用 `git status` 再确认一次。
- 如果之后要选择正式的开源许可证，可在仓库根目录加入 `LICENSE` 文件（例如 MIT 或 Apache-2.0），并在此处注明。
