# MY-AICODING 课程版重写开发方案

本文档用于规划一个全新的课程版 AI Coding 项目。目标是在不修改参考项目 `<参考项目目录>\open-swe` 的前提下，重新创建一个新项目，带初级程序员逐步敲出一个 Windows 本地运行版 AI Coding Agent。

课程版项目不考虑远程沙箱，只考虑 Windows 本地运行。前端部分不讲，直接复制当前项目的 `ui/`。Agent 核心代码由讲师带同学手写。

## 一、课程目标

课程最终要实现一个简化但完整的 AI Coding 服务：

```text
用户在网页输入任务
  -> 后端接收任务
  -> Agent clone Gitee 仓库
  -> Agent 读写代码
  -> Agent 运行测试
  -> Agent 修复问题
  -> Agent commit/push
  -> Agent 创建 Gitee Pull Request
  -> 前端显示运行日志和最终结果
```

这个课程版项目不是完整复刻 Open SWE。Open SWE 原项目包含 GitHub App、Slack、Linear、reviewer、analyzer、LangSmith、远程沙箱、多用户 dashboard 等大量生产能力。对于初级程序员，直接讲全部内容会让主线变得复杂。

课程第一版以 AI Coding 主链路为基础，同时加入 Reviewer Agent 和 skills。也就是说，第一版要覆盖“写代码”和“审查代码”两条主线，但仍然不讲 Slack、Linear、远程沙箱、多租户权限和完整 dashboard。

```text
模型 + 工具 + 本地工作区 + Git/Gitee + 测试验收 + Reviewer Agent + skills + 前端展示
```

## 二、总体开发原则

1. 当前项目 `<参考项目目录>\open-swe` 完全不动。
2. 讲课时重新创建一个新项目。
3. 前端 `ui/` 不讲，直接复制。
4. Agent 核心代码必须手写。
5. skills、提示词、配置模板、启动脚本可以复制，但需要在对应阶段解释它们如何被 Agent 使用。
6. 第一版不接远程沙箱。
7. 所有文件操作限制在 `<AI_WORKSPACE_ROOT>`。
8. 第一版优先支持 Gitee。
9. GitHub 可作为后续扩展。
10. 第一版建议只支持网页触发任务，不讲 Gitee Webhook。
11. 第一版加入 Reviewer Agent，但只讲 PR diff review 主流程，不讲完整 review-style analyzer 和 cron。

## 三、新项目建议位置

建议新项目目录：

```text
<项目目录>
```

不要放在当前项目目录下面，避免误操作当前项目。

## 四、新项目推荐结构

最终项目结构建议如下：

```text
my-aicoding-course/
  agent/
    __init__.py
    app.py
    server.py
    prompt.py
    env_utils.py

    core/
      __init__.py
      state.py
      graph.py
      model.py
      persistence.py
      runtime.py

    backends/
      __init__.py
      local_shell.py
      permissions.py
      workspace.py

    tools/
      __init__.py
      file_tools.py
      shell_tools.py
      git_tools.py
      gitee_tools.py
      reviewer_tools.py
      rubric_tools.py

    api/
      __init__.py
      routes.py
      schemas.py

    store/
      __init__.py
      sqlite_store.py

    skills/
      ...

  ui/
    ...

  scripts/
    start_backend.cmd
    start_ui.cmd
    start_all.py

  workspace/
    README.md

  data/
    checkpoints.sqlite
    store.sqlite

  .env.example
  langgraph.json
  pyproject.toml
  README.md
```

目录职责：

```text
agent/core/       Agent 核心编排，课堂重点手写
agent/backends/   Windows 本地工作区、本地命令执行、权限控制，课堂重点手写
agent/tools/      Agent 可调用工具，课堂重点手写
agent/api/        后端 API，课堂中后期手写
agent/store/      课程版本地 SQLite Store，课堂重点手写
agent/skills/     可复制资产，第一版用于 reviewer/analyzer 教学
ui/               前端成品资产，直接复制，不讲
scripts/          启动脚本，可以手写简化版，也可以参考当前项目
workspace/        课程项目自身的占位目录，真实代码工作区使用 <AI_WORKSPACE_ROOT>
data/             课程项目本地持久化目录，保存 SQLite checkpoint 和 SQLite store
```

## 五、核心和非核心划分

### 必须带同学手写的核心代码

```text
agent/env_utils.py
agent/core/model.py
agent/core/state.py
agent/core/graph.py
agent/core/persistence.py
agent/core/runtime.py
agent/store/sqlite_store.py
agent/backends/workspace.py
agent/backends/permissions.py
agent/backends/local_shell.py
agent/tools/file_tools.py
agent/tools/shell_tools.py
agent/tools/git_tools.py
agent/tools/gitee_tools.py
agent/tools/reviewer_tools.py
agent/tools/rubric_tools.py
agent/prompt.py
agent/server.py
agent/api/routes.py
agent/api/schemas.py
agent/reviewer.py
agent/reviewer_diff.py
agent/reviewer_findings.py
agent/reviewer_publish.py
```

这些代码构成 AI Coding 主链路：

```text
模型
  -> Agent 编排
  -> 工具调用
  -> 本地工作区
  -> Git/Gitee
  -> 测试/验收
  -> 前端展示
```

### 可以复制或参考的非核心资产

```text
ui/
agent/skills/
default_prompt.md
langgraph.json
scripts/start_ui_dev.cmd
scripts/start_langgraph_dev.cmd
start_open_swe.py
```

复制时要注意：配置文件和启动脚本不建议原样照用，应复制后裁剪成课程版。

### 第一版仍不建议复制或讲解的内容

```text
agent/dashboard/
agent/analyzer.py
agent/review_style_*.py
agent/scheduler.py
agent/encryption.py
agent/utils/github_app.py
agent/utils/github_comments.py
agent/utils/slack.py
agent/utils/linear.py
agent/tools/linear_*.py
agent/tools/slack_*.py
evals/
.github/
Dockerfile
```

原因：

```text
这些属于生产平台能力或周边集成，不是 AI Coding 主链路。
初级程序员容易被 OAuth、Slack、cron、store、metadata、完整 dashboard 等概念分散注意力。
Reviewer Agent 保留，但只讲简化 PR review 主流程。
```

## 六、阶段 0：准备课程项目

### 目标

创建空项目骨架，让同学知道项目结构。

### 课堂操作

```powershell
mkdir <项目目录>
cd <项目目录>

mkdir agent
mkdir agent\core
mkdir agent\backends
mkdir agent\tools
mkdir agent\api
mkdir scripts
mkdir workspace
```

创建空文件：

```text
agent/__init__.py
agent/core/__init__.py
agent/backends/__init__.py
agent/tools/__init__.py
agent/api/__init__.py
README.md
.env.example
pyproject.toml
```

### 讲课重点

讲清楚：

```text
我们不是一上来写完整平台。
我们先写 Agent 能力内核，然后再接 UI 和 Gitee。
```

### 阶段验收

```text
项目目录创建完成。
同学能说清楚 agent/core、agent/backends、agent/tools 的职责。
```

## 七、阶段 1：环境变量和模型配置

### 目标

让项目可以读取 `.env`，并创建 DeepSeek 模型。

### 课堂手写文件

```text
agent/env_utils.py
agent/core/model.py
.env.example
```

### 可参考当前项目文件

```text
<参考项目目录>\open-swe\agent\env_utils.py
<参考项目目录>\open-swe\agent\utils\model.py
```

注意：`agent/utils/model.py` 不建议直接复制，它包含生产项目的多模型、多 profile、fallback 等复杂逻辑。课程版应手写简化版本。

### 课程版 `.env.example`

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
MAIN_MODEL=deepseek-v4-pro

GITEE_TOKEN=
GITEE_API_BASE_URL=https://gitee.com/api/v5

AI_WORKSPACE_ROOT=<AI_WORKSPACE_ROOT>
```

### 核心代码目标

课程版只需要实现：

```python
def make_main_model():
    return ChatOpenAI(
        model="deepseek-v4-pro",
        temperature=1.1,
        openai_api_key=DEEPSEEK_API_KEY,
        openai_api_base=DEEPSEEK_BASE_URL,
        max_tokens=25600,
        model_kwargs={
            "extra_body": {
                "thinking": {"type": "disabled"}
            }
        },
    )
```

### 讲课重点

```text
模型配置必须和业务代码分离。
API Key 只能放在 .env，不应该写死在代码里。
```

### 阶段验收

```text
运行一个 Python 文件，能打印：
1. DeepSeek API Key 已加载
2. DeepSeek Base URL 已加载
3. 当前模型名称是 deepseek-v4-pro
```

不要求此阶段真实调用模型。

## 八、阶段 2：设计 Windows 本地工作区

### 目标

明确所有文件操作只能发生在 `<AI_WORKSPACE_ROOT>`。

### 课堂手写文件

```text
agent/backends/workspace.py
agent/backends/permissions.py
```

### 核心概念

AI Coding 最大风险之一是权限失控。模型如果能随便读写文件，可能会访问：

```text
<用户主目录>\.ssh
<参考项目目录>\open-swe\.env
C:\Windows\System32
```

所以在写 Agent 之前，必须先写工作区权限。

### 推荐实现

#### workspace_root

```text
<AI_WORKSPACE_ROOT>
```

#### resolve_workspace_path(path)

作用：

```text
把 Agent 传入的相对路径或虚拟路径，转换成 Windows 绝对路径。
```

#### assert_safe_path(path)

作用：

```text
禁止访问 <AI_WORKSPACE_ROOT> 之外的文件。
```

### 允许示例

```text
<AI_WORKSPACE_ROOT>\demo\main.py
<AI_WORKSPACE_ROOT>\projects\repo1\README.md
```

### 禁止示例

```text
<用户主目录>\.ssh\id_rsa
<参考项目目录>\open-swe\.env
..\..\Windows\System32
```

### 讲课重点

```text
本地运行不等于没有沙箱。
我们的本地工作区权限控制，就是课程版的安全边界。
```

### 阶段验收

```text
给一个合法路径，返回真实路径。
给一个越界路径，抛出 PermissionError。
```

此阶段不要写 Agent。

## 九、阶段 3：实现 LocalShellBackend

### 目标

让系统可以在 Windows 本地工作区内读写文件和执行命令。

### 课堂手写文件

```text
agent/backends/local_shell.py
```

### 可参考当前项目文件

```text
<参考项目目录>\open-swe\agent\integrations\local_shell.py
```

建议只参考，不直接复制。课程版应更简单。

### 推荐类设计

```python
class LocalShellBackend:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def read_file(self, path: str) -> str:
        ...

    def write_file(self, path: str, content: str) -> None:
        ...

    def list_files(self, path: str = ".") -> list[str]:
        ...

    def run(self, command: str, cwd: str = ".") -> CommandResult:
        ...
```

### 第一版命令白名单

建议第一版只允许：

```text
python
pytest
pip
git
dir
type
```

不要一开始允许任意 PowerShell 命令。

### 讲课重点

```text
LocalShellBackend 是 Agent 和本地 Windows 系统之间的隔离层。
Agent 不能直接执行命令，只能通过 backend 执行受控命令。
```

### 阶段验收

通过普通 Python 调用 backend：

```text
1. 创建文件
2. 读取文件
3. 执行 python --version
4. 在 <AI_WORKSPACE_ROOT> 里运行 pytest
```

此阶段仍然不要写 Agent。

## 十、阶段 4：手写最小工具层

### 目标

把 backend 封装成 Agent 可调用的 tools。

### 课堂手写文件

```text
agent/tools/file_tools.py
agent/tools/shell_tools.py
agent/tools/__init__.py
```

### 第一版工具

只写 5 个：

```text
read_file
write_file
list_files
run_command
get_workspace_info
```

### 工具层职责

每个工具都做三件事：

```text
1. 参数校验
2. 权限检查
3. 调用 backend
```

### 讲课重点

```text
模型本身不能直接读文件、写文件、执行命令。
它只能请求调用工具。
工具层就是 AI 和真实世界之间的安全接口。
```

### 阶段验收

不用 Agent，直接在 Python 中调用工具：

```python
write_file("demo/hello.py", "print('hello')")
print(read_file("demo/hello.py"))
print(run_command("python demo/hello.py"))
```

## 十一、阶段 5：写最小 DeepAgent

### 目标

让模型可以通过 tools 完成一个本地代码任务。

### 课堂手写文件

```text
agent/prompt.py
agent/core/state.py
agent/core/graph.py
agent/server.py
```

### 核心结构

如果使用 DeepAgents，核心结构类似：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model=make_main_model(),
    system_prompt=SYSTEM_PROMPT,
    tools=[
        read_file,
        write_file,
        list_files,
        run_command,
    ],
)
```

### 第一版系统提示词

不要直接复制当前项目完整 prompt。先手写短版：

```text
你是 MY-AICODING，一个 Windows 本地 AI Coding 智能体。
你只能操作 <AI_WORKSPACE_ROOT> 目录下的文件。
你需要先理解任务，再修改代码，再运行测试，最后总结结果。
所有面向用户的回复使用中文。
路径、命令、代码标识保持原样。
```

### 此阶段暂不接入

```text
Gitee
前端
webhook
reviewer
rubric
```

### 验收任务

让 Agent 完成：

```text
请在 demo_python 目录创建一个最小 FastAPI 项目：
1. /health 返回 {"status":"ok"}
2. 添加 pytest 测试
3. 添加 README
4. 运行测试
```

### 阶段成功标志

```text
Agent 能在 <AI_WORKSPACE_ROOT>\demo_python 中生成代码并运行测试。
```

## 十二、阶段 6：接 LangGraph 开发服务

### 目标

让 Agent 能作为 LangGraph graph 被启动。

### 课堂手写文件

```text
langgraph.json
agent/server.py
```

### 可参考当前项目文件

```text
<参考项目目录>\open-swe\langgraph.json
<参考项目目录>\open-swe\agent\server.py
```

注意：不要复制当前 `server.py`，它包含太多生产逻辑。

### 课程版 langgraph.json

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent/server.py:get_agent"
  },
  "env": ".env"
}
```

### 讲课重点

```text
LangGraph dev server 负责运行 Agent。
前端不是直接调用 Python 函数，而是通过 LangGraph API 创建 thread 和 run。
```

### 阶段验收

```powershell
langgraph dev --port 2024
```

能启动，并且能打开：

```text
http://127.0.0.1:2024/docs
```

## 十三、阶段 7：数据保存设计

### 目标

让学生明确看到数据是如何保存的。课程项目不沿用 LangGraph dev server 默认的 `.langgraph_api/*.pckl` 存储，而是显式设计两套本地 SQLite 持久化：

```text
checkpointer：使用 langgraph-checkpoint-sqlite，保存 Agent thread state 和聊天历史。
store：使用自定义 LocalSqliteStore，保存平台业务数据。
```

### 课堂手写文件

```text
agent/core/persistence.py
agent/store/__init__.py
agent/store/sqlite_store.py
```

### 需要加入的依赖

课程版 `pyproject.toml` 需要加入：

```text
langgraph-checkpoint-sqlite
```

建议课程中明确说明：

```text
langgraph-checkpoint-sqlite 负责 LangGraph 的 checkpoint。
我们自己写的 LocalSqliteStore 负责业务数据，不等同于 LangGraph checkpoint。
业务 Store 使用 Python 标准库 sqlite3，不需要额外第三方库。
```

### 推荐本地数据目录

```text
<项目目录>\data\checkpoints.sqlite
<项目目录>\data\store.sqlite
```

也可以通过 `.env` 配置：

```env
CHECKPOINT_DB_PATH=<项目目录>\data\checkpoints.sqlite
STORE_DB_PATH=<项目目录>\data\store.sqlite
```

### Checkpointer 设计

`agent/core/persistence.py` 负责创建 SQLite checkpointer。

示意代码：

```python
from pathlib import Path
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver


def make_checkpointer(db_path: str):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(conn)
```

然后在创建 Agent graph 时传入：

```python
agent = create_deep_agent(
    model=make_main_model(),
    system_prompt=SYSTEM_PROMPT,
    tools=[...],
    checkpointer=make_checkpointer(CHECKPOINT_DB_PATH),
)
```

课堂上要讲清楚：

```text
checkpointer 保存的是 LangGraph thread state。
聊天历史 messages 存在 checkpoint 中。
同一个 thread_id 再次读取时，可以恢复历史上下文。
```

### SQLite Store 设计

`agent/store/sqlite_store.py` 负责保存业务数据。第一版不引入外部数据库服务，使用 Python 标准库 `sqlite3` 创建一个本地 SQLite 文件。

建议第一版建 4 张表：

```sql
CREATE TABLE IF NOT EXISTS threads (
  thread_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  repo_url TEXT,
  repo_owner TEXT,
  repo_name TEXT,
  branch_name TEXT,
  pr_url TEXT,
  latest_run_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  error TEXT,
  FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
);

CREATE TABLE IF NOT EXISTS review_findings (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  file TEXT NOT NULL,
  line INTEGER,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

第一版实现这些方法：

```text
upsert_thread(...)
get_thread(thread_id)
list_threads(limit=50)
update_thread_status(thread_id, status)
record_run(...)
add_finding(...)
list_findings(thread_id)
set_setting(key, value)
get_setting(key)
```

示意用法：

```python
store.upsert_thread(
    thread_id=thread_id,
    title=title,
    repo_url=repo_url,
    latest_run_status="pending",
)
```

课堂上要讲清楚：

```text
SQLite Store 保存平台业务数据。
例如任务列表、仓库信息、PR URL、review findings、用户设置。
它不负责保存 LangGraph 的完整消息状态。
```

### Checkpointer 与 SQLite Store 的分工

```text
checkpointer 保存：
- thread state
- messages
- tool call 状态
- Agent 执行过程
- 用于恢复对话上下文

SQLite Store 保存：
- thread 列表摘要
- repo_url
- PR URL
- latest_run_status
- 用户配置
- review findings
- pending queue
```

### 课堂演示方式

建议现场演示三步：

```text
1. 删除 data/checkpoints.sqlite 和 data/store.sqlite，启动项目，确认没有历史数据。
2. 创建一个新任务，关闭服务再重启，确认聊天历史还能从 SQLite checkpoint 恢复。
3. 用 DB Browser for SQLite 或 Python sqlite3 查询 data/store.sqlite，展示任务摘要、PR URL、review findings 等业务数据。
```

### 阶段验收

```text
1. 同一个 thread_id 重启后仍能看到聊天历史。
2. data/checkpoints.sqlite 文件真实生成。
3. data/store.sqlite 文件真实生成。
4. 学生能说清楚：聊天正文在 checkpoint，业务摘要在 SQLite Store。
```

## 十四、阶段 8：复制前端 UI

### 目标

不讲前端，直接复制当前项目 UI。

### 复制时机

后端最小 Agent 已经能通过 LangGraph 跑起来以后。

### 复制来源

```text
<参考项目目录>\open-swe\ui
```

### 复制目标

```text
<项目目录>\ui
```

### 建议复制

```text
ui/src
ui/public
ui/assets
ui/package.json
ui/yarn.lock
ui/vite.config.ts
ui/tsconfig.json
ui/components.json
ui/eslint.config.js
ui/.prettierrc
ui/.prettierignore
ui/README.md
```

### 不要复制

```text
ui/node_modules
ui/.tanstack/tmp
ui/tsconfig.tsbuildinfo
```

### 复制后配置

设置前端 API 地址：

```text
VITE_DASHBOARD_API_BASE_URL=http://127.0.0.1:2024
```

### 可隐藏的页面

第一版可以隐藏或暂时不讲：

```text
Automations
Review
Usage
Admin
Slack Connect
```

也可以先不删，只讲 Agents 页面。

### 阶段验收

```powershell
cd ui
corepack yarn install
corepack yarn dev
```

浏览器打开：

```text
http://127.0.0.1:3000/agents
```

能看到页面。

## 十五、阶段 9：补一个简化 API 适配层

### 目标

让复制来的前端能调用课程版后端。

### 课堂手写文件

```text
agent/api/routes.py
agent/api/schemas.py
agent/app.py
```

### 路线 A：兼容当前前端接口

适合尽量少改前端。

最小实现接口：

```text
GET /dashboard/api/me
GET /dashboard/api/agents/threads
POST /dashboard/api/agents/runs
GET /dashboard/api/agents/threads/{thread_id}
```

可参考当前项目：

```text
<参考项目目录>\open-swe\agent\dashboard\thread_api.py
<参考项目目录>\open-swe\agent\dashboard\routes.py
<参考项目目录>\open-swe\agent\webapp.py
```

但不建议直接复制，因为它们过于复杂。

### 路线 B：改前端为极简接口

适合教学，逻辑更清晰。

只保留一个接口：

```text
POST /api/chat
```

请求：

```json
{
  "repo_url": "https://gitee.com/xxx/demo.git",
  "message": "创建一个 FastAPI 项目"
}
```

响应：

```json
{
  "thread_id": "...",
  "messages": []
}
```

### 推荐选择

课程第一版建议使用路线 B。等同学理解后，再讲路线 A 如何兼容完整前端。

### 阶段验收

```text
页面输入任务后，后端能收到任务并打印日志。
```

## 十六、阶段 10：加入 Gitee clone 能力

### 目标

让 Agent 能操作真实 Gitee 仓库，但所有动作仍然只发生在 Windows 本地工作区。

### 课堂手写文件

```text
agent/tools/git_tools.py
agent/tools/gitee_tools.py
```

### 第一版只做 Git

先实现：

```text
clone_repo(repo_url)
git_status(repo_dir)
git_diff(repo_dir)
git_add_commit(repo_dir, message)
git_push(repo_dir, branch)
```

不要一开始就做 PR。

### Gitee Token 使用方式

讲清楚：

```text
Gitee 私人令牌不是给模型看的。
模型只知道“我要 push”，真正认证由后端工具完成。
工具层必须避免打印 token。
```

课堂版可先使用：

```text
https://oauth2:<token>@gitee.com/owner/repo.git
```

但要明确：

```text
日志中不能输出包含 token 的 URL。
```

### 阶段验收任务

给一个空 Gitee 仓库：

```text
1. clone 到 <AI_WORKSPACE_ROOT>\projects\repo-name
2. 让 Agent 创建 FastAPI 项目
3. git commit
4. push 到新分支
```

## 十七、阶段 11：加入 Gitee Pull Request 能力

### 目标

代码 push 后，通过 Gitee Open API 创建 PR。

### 课堂手写文件

```text
agent/tools/gitee_tools.py
```

### 可参考当前项目

```text
<参考项目目录>\open-swe\agent\tools\open_gitee_pull_request.py
<参考项目目录>\open-swe\agent\utils\gitee.py
<参考项目目录>\open-swe\agent\utils\scm_tokens.py
```

建议课堂手写简化版，不直接复制。

### 最小函数

```text
create_gitee_pull_request(owner, repo, head, base, title, body)
```

### 参数说明

```text
owner   空间地址，例如 owner
repo    仓库路径，例如 default_repo
head    源分支
base    目标分支，通常是 master 或 main
title   PR 标题
body    PR 描述
```

### 阶段验收任务

Agent 完成代码后：

```text
1. 创建分支 my-aicoding/task-xxxx
2. commit
3. push
4. 创建 Gitee Pull Request
5. 返回 PR URL
```

## 十八、阶段 12：复制并启用 skills 和提示词资产

### 复制时机

最小 Agent、本地工具、Gitee PR 全部跑通以后，开始复制并启用 skills。

不要太早复制。初学者还没理解 Agent 主流程时，skills 和复杂 prompt 会增加负担。当前决定是第一版加入 Reviewer Agent，因此 skills 不再只是备用资产，而是 Reviewer/Analyzer 能力的教学入口。

### 可复制 skills

来源：

```text
<参考项目目录>\open-swe\agent\skills
```

目标：

```text
<项目目录>\agent\skills
```

当前 skills 包括：

```text
agent/skills/bootstrap-repo-analysis/SKILL.md
agent/skills/continual-learning/SKILL.md
```

这两个更偏 reviewer/analyzer。由于第一版决定加入 Reviewer Agent 和 skills，它们应在 Reviewer Agent 阶段前复制，并在讲解中说明：

```text
bootstrap-repo-analysis：用于冷启动分析仓库历史 PR review 风格。
continual-learning：用于根据后续 finding 结果持续优化 review 风格。
```

### 第一版启用方式

第一版不建议一开始完整实现 analyzer 和 cron，但建议把 skills 纳入课程：

```text
1. 先复制 skills 文件。
2. 讲 SKILL.md 的作用：它是给智能体读取的任务说明书。
3. 在 Reviewer Agent 阶段，先让 reviewer 读取固定 review prompt。
4. 再展示 skills 如何扩展为“仓库 review 风格学习”能力。
5. cron 和完整 continual-learning 自动化可以保留为后续扩展。
```

这样第一版既能讲 skills，又不会过早引入完整 analyzer/cron/store 体系。

### 可复制提示词参考

```text
<参考项目目录>\open-swe\default_prompt.md
<参考项目目录>\open-swe\agent\prompt.py
```

建议教学顺序：

```text
1. 先手写短 prompt
2. 跑通主链路
3. 展示当前项目完整 prompt
4. 讲为什么生产 prompt 更复杂
5. 再把完整 prompt 作为增强版资产复制进新项目
```

## 十九、阶段 13：加入 Reviewer Agent

### 目标

在第一版中加入一个独立的代码审查智能体，让同学理解“写代码的 Agent”和“审查代码的 Agent”是两条不同链路。

主 Agent 负责：

```text
理解任务
修改代码
运行测试
commit/push
创建 Pull Request
```

Reviewer Agent 负责：

```text
读取 PR diff
分析变更风险
记录 finding
发布 review 结果
跟踪 finding 是否已修复
```

### 课堂手写文件

```text
agent/reviewer.py
agent/reviewer_diff.py
agent/reviewer_findings.py
agent/reviewer_publish.py
agent/tools/reviewer_tools.py
```

### 可参考当前项目

```text
<参考项目目录>\open-swe\agent\reviewer.py
<参考项目目录>\open-swe\agent\reviewer_diff.py
<参考项目目录>\open-swe\agent\reviewer_findings.py
<参考项目目录>\open-swe\agent\reviewer_publish.py
<参考项目目录>\open-swe\agent\reviewer_reconcile.py
<参考项目目录>\open-swe\agent\tools\add_finding.py
<参考项目目录>\open-swe\agent\tools\update_finding.py
<参考项目目录>\open-swe\agent\tools\list_findings.py
<参考项目目录>\open-swe\agent\tools\publish_review.py
```

注意：当前项目 reviewer 代码包含 GitHub、Slack、metadata、watch mode、re-review、thread reconciliation 等生产能力。课程版第一版不要直接复制完整实现，应手写简化版。

### 课程版 Reviewer 第一版范围

第一版只实现 PR diff review 主流程：

```text
1. 输入 repo、PR number、base/head branch。
2. 拉取 PR diff。
3. 让 reviewer 只读分析 diff。
4. 通过 add_finding 记录问题。
5. 通过 list_findings 汇总问题。
6. 生成一段中文 review 结果。
7. 可选：调用 Gitee API 发布 PR 评论。
```

第一版暂不实现：

```text
watch mode
自动 re-review
finding thread 自动关闭
reviewer cron
review style continual-learning 自动任务
Slack 通知
GitHub GraphQL review thread reconciliation
```

### Reviewer 工具设计

建议第一版只写 4 个 reviewer tools：

```text
add_finding
list_findings
clear_findings
publish_review_comment
```

finding 数据结构可以先保持简单：

```json
{
  "id": "finding-001",
  "file": "main.py",
  "line": 12,
  "severity": "medium",
  "title": "登录失败时没有返回错误提示",
  "description": "当前代码在认证失败后仍然返回成功页面，用户无法判断登录是否失败。"
}
```

### finding 存储方式

课程第一版不要一上来讲 LangGraph metadata。统一写入本地 SQLite Store：

```text
data/store.sqlite 的 review_findings 表
```

等同学理解后，再升级到：

```text
LangGraph thread metadata
```

### Reviewer Prompt

课程版 reviewer prompt 要短，重点强调：

```text
你是代码审查智能体。
你只能审查，不允许修改代码。
你只关注本次 diff 引入的问题。
不要提出纯风格建议。
每个 finding 必须说明具体文件、行号、风险和修复建议。
所有面向用户的输出使用中文。
```

### 与 skills 的关系

Reviewer Agent 是第一版讲 skills 的最佳入口：

```text
1. 先讲 reviewer prompt 如何约束审查行为。
2. 再展示 SKILL.md 如何作为更长、更结构化的任务说明。
3. 最后说明 bootstrap-repo-analysis 和 continual-learning 如何用于“学习仓库 review 风格”。
```

第一版可以先做到：

```text
Reviewer 读取一个固定 review skill 文件，并把它拼接进 system prompt。
```

不必第一版就实现完整 analyzer。

### 阶段验收任务

准备一个已有 PR，或让主 Agent 先创建一个 PR，然后运行 Reviewer Agent：

```text
1. Reviewer 能获取 PR diff。
2. Reviewer 能输出中文 review 结果。
3. Reviewer 能记录 findings。
4. Reviewer 不会修改代码。
5. Reviewer 可以把 review 结果发布到 Gitee PR 评论。
```

### 讲课重点

```text
主 Agent 是执行者。
Reviewer Agent 是审查者。
执行者关注“完成任务”。
审查者关注“这次变更有没有引入风险”。
两个智能体的 prompt、tools、权限都应该不同。
```

## 二十、阶段 14：加入 Rubric 验收闭环

### 目标

让 Agent 不是“写完就算完成”，而是按验收标准自动检查。

### 课堂手写文件

```text
agent/tools/rubric_tools.py
agent/core/graph.py
```

### 前提

如果使用 DeepAgents 官方 `RubricMiddleware`，需要：

```text
deepagents >= 0.6.5
```

### 推荐配置

```python
RubricMiddleware(
    model=make_grader_model(),
    tools=[
        run_tests,
        check_git_status,
        check_readme_exists,
    ],
    max_iterations=3,
)
```

### 第一版固定 rubric

```text
- 代码已经生成
- pytest 测试通过
- README 包含安装、启动、测试说明
- git diff 不为空
- 已成功 push 到 Gitee 分支
- 已创建 Pull Request
```

### 讲课重点

```text
主 Agent 负责实现任务。
Grader 负责按 rubric 验收。
验收失败时，反馈会重新注入给主 Agent，驱动下一轮修复。
```

### 阶段验收任务

用户输入：

```text
创建 FastAPI 项目并提交 PR。
```

Grader 检查：

```text
1. pytest 是否通过
2. README 是否完整
3. PR 是否创建
```

不满足则自动让 Agent 继续修复。

## 二十一、阶段 15：加入前端实时日志

### 目标

让学生看到 Agent 正在做什么，而不是页面卡住。

### 课堂手写文件

```text
agent/api/routes.py
agent/core/runtime.py
```

### 推荐事件流

```text
任务已接收
正在 clone 仓库
正在分析文件
正在写入 main.py
正在运行 pytest
测试失败，正在修复
正在提交代码
正在创建 PR
任务完成
```

### 可参考当前前端文件

```text
<参考项目目录>\open-swe\ui\src\components\agents\ported\MessageView.tsx
<参考项目目录>\open-swe\ui\src\components\agents\AgentThreadView.tsx
<参考项目目录>\open-swe\ui\src\lib\agents\queries.ts
```

讲课时只讲后端事件格式，不讲 React 细节。

### 阶段验收

```text
前端可以看到 Agent 实时步骤。
```

## 二十二、阶段 16：整理成课程版产品

### 目标

让同学能完整启动课程项目。

### 整理内容

```text
README.md
.env.example
scripts/start_backend.cmd
scripts/start_ui.cmd
scripts/start_all.py
演示 Gitee 仓库
课程任务样例
```

### 最终验收

新同学 clone 课程项目后，按文档可以完成：

```text
1. 创建 .env
2. 安装 Python 依赖
3. 安装前端依赖
4. 启动后端
5. 启动前端
6. 输入 Gitee 仓库地址和任务
7. Agent 生成代码
8. Agent 运行测试
9. Agent push 分支
10. Agent 创建 Pull Request
```

## 二十三、建议课程章节安排

### 第 1 讲：我们要做什么

讲：

```text
AI Coding Agent 的本质：
模型 + 工具 + 工作区 + 版本控制 + 验收闭环
```

操作：

```text
创建项目结构。
```

### 第 2 讲：环境变量和模型

写：

```text
env_utils.py
model.py
```

验收：

```text
成功加载 DeepSeek 配置。
```

### 第 3 讲：本地工作区安全

写：

```text
workspace.py
permissions.py
```

验收：

```text
只能访问 <AI_WORKSPACE_ROOT>。
```

### 第 4 讲：LocalShellBackend

写：

```text
local_shell.py
```

验收：

```text
能读写文件，能执行 python/pytest/git。
```

### 第 5 讲：Agent Tools

写：

```text
file_tools.py
shell_tools.py
```

验收：

```text
工具可以被普通 Python 调用。
```

### 第 6 讲：最小 DeepAgent

写：

```text
prompt.py
server.py
graph.py
```

验收：

```text
Agent 能创建一个本地 Python 小项目。
```

### 第 7 讲：LangGraph 服务化

写：

```text
langgraph.json
scripts/start_backend.cmd
```

验收：

```text
langgraph dev --port 2024 启动成功。
```

### 第 8 讲：数据保存设计

写：

```text
persistence.py
sqlite_store.py
```

讲解：

```text
langgraph-checkpoint-sqlite 保存聊天历史和 thread state。
本地 SQLite Store 保存任务摘要、PR URL、review findings 等业务数据。
```

验收：

```text
重启后仍能恢复聊天历史，且能查询 data/store.sqlite 查看业务数据。
```

### 第 9 讲：复制前端

复制：

```text
ui/
```

验收：

```text
能打开页面。
```

### 第 10 讲：后端 API 连接前端

写：

```text
api/routes.py
api/schemas.py
```

验收：

```text
页面输入任务，后端收到任务。
```

### 第 11 讲：Gitee 仓库操作

写：

```text
git_tools.py
gitee_tools.py
```

验收：

```text
clone、commit、push 成功。
```

### 第 12 讲：创建 Pull Request

扩展：

```text
gitee_tools.py
```

验收：

```text
Agent 创建 Gitee PR。
```

### 第 13 讲：复制并启用 skills

复制：

```text
agent/skills/
default_prompt.md
```

讲解：

```text
SKILL.md 是给智能体读取的任务说明书。
Reviewer Agent 可以通过 skill 获得更结构化的审查流程。
```

验收：

```text
Reviewer 能读取固定 skill/prompt 内容。
```

### 第 14 讲：Reviewer Agent

写：

```text
reviewer.py
reviewer_diff.py
reviewer_findings.py
reviewer_publish.py
reviewer_tools.py
```

验收：

```text
Reviewer 能读取 PR diff，输出中文 review，记录 finding，并可发布 Gitee PR 评论。
```

### 第 15 讲：Rubric 自动验收

写：

```text
rubric_tools.py
```

验收：

```text
不满足标准时，Agent 自动继续修复。
```

### 第 16 讲：日志和运行状态

写：

```text
runtime.py
routes.py
```

验收：

```text
前端看到实时任务步骤。
```

### 第 17 讲：整理成课程版产品

做：

```text
README
启动脚本
.env.example
演示仓库
```

验收：

```text
新同学 clone 课程项目后，可以按文档启动。
```

## 二十四、建议第一版不讲的内容

第一版课程不要讲：

```text
Slack
Linear
GitHub App
远程沙箱
多租户用户权限
完整 analyzer graph
review style continual-learning cron
LangSmith tracing
定时任务
团队管理
复杂 dashboard
```

这些可以作为第二期课程：

```text
企业级 AI Coding 平台扩展
```

第一期必须把主链路讲透：

```text
用户输入任务
  -> Agent 理解任务
  -> clone 仓库
  -> 读写代码
  -> 运行测试
  -> 修复错误
  -> commit/push
  -> 创建 PR
  -> Reviewer Agent 审查 PR
  -> 返回结果
```

## 二十五、待确认边界

以下模块的第一版范围已经重新确定：

### 1. RubricMiddleware

建议：

```text
作为核心增强讲，但不是第一阶段必须。它放在 Reviewer Agent 之后，
用于讲“任务完成后的自动验收闭环”。
```

### 2. Gitee Webhook

如果只讲网页发起任务：

```text
可以不讲 webhook。
```

如果要讲在 Gitee Issue/PR 评论里触发 Agent：

```text
Webhook 应作为后续核心模块。
```

### 3. Reviewer Agent

决定：

```text
第一期加入。
但只讲简化 PR diff review 主流程，不讲完整 watch mode、re-review、thread reconciliation。
```

### 4. Skills

决定：

```text
第一期加入。
复制 agent/skills/，并用 Reviewer Agent 说明 SKILL.md 如何作为智能体任务说明书。
完整 analyzer/continual-learning/cron 放到后续扩展。
```

## 二十六、推荐第一版课程范围

推荐第一版只做：

```text
Web 页面触发 AI Coding
Windows 本地工作区执行
langgraph-checkpoint-sqlite 保存聊天历史
本地 SQLite Store 保存业务数据
Gitee 仓库 clone
代码生成和修改
pytest/ruff 验收
commit/push
创建 Pull Request
复制并启用 skills
Reviewer Agent 审查 PR diff
实时日志展示
```

不做：

```text
Gitee Webhook
Slack
Linear
完整 Analyzer
review style cron
远程沙箱
多用户权限体系
```

这样初级程序员更容易理解完整闭环，也更适合课堂上逐步手写。
