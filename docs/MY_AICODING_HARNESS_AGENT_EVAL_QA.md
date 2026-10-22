# Harness Agent 架构与 Agent 持续评估问答

本文档整理 20 道偏生产级 Agent、Harness 架构、持续评估、Agent Runtime、Trace 和 CI/CD 质量门禁方向的工程问答。回答结构统一采用“总 -> 分 -> 总”，便于按要点复述。

参考资料：

- Harness AI Evals：https://www.harness.io/products/ai-evals
- Harness Evals GitHub：https://github.com/harness/harness-evals
- LangGraph Persistence：https://docs.langchain.com/oss/python/langgraph/persistence
- LangChain Deep Agents Runtime：https://www.langchain.com/blog/runtime-behind-production-deep-agents
- OpenAI Agent Evals：https://developers.openai.ac.cn/api/docs/guides/agent-evals

## 1. 什么是 Agent Harness？它和单纯调用大模型有什么区别？

总：

Agent Harness 是大模型外面的一层工程化运行框架，负责把模型、工具、权限、状态、记忆、评估和部署串起来。

分：

单纯调用大模型只是一次输入输出，而 Harness 关注完整任务生命周期，包括任务路由、工具调用、状态持久化、失败恢复、权限边界、日志追踪和质量评估。企业里真正上线的不是一个 prompt，而是一套可治理、可观测、可回滚的 Agent 系统。

总：

所以我理解的 Agent Harness，本质是让大模型从“能力组件”变成“可生产运行的业务执行系统”。

## 2. 生产级 Agent 架构通常包含哪些核心模块？

总：

生产级 Agent 不能只有模型调用，至少要有入口层、调度层、执行层、工具层、状态层、记忆层、安全层和评估层。

分：

入口层负责 API、SSE、鉴权；调度层负责任务分类和 Agent 编排；执行层负责运行主 Agent 和 SubAgent；工具层对接代码仓库、数据库、HTTP、搜索等能力；状态层通过 checkpoint 保存会话；记忆层保存长期知识；安全层控制权限和沙箱；评估层负责离线和线上质量监控。

总：

这些模块组合起来，才能支撑长任务、多轮对话、多工具调用和企业级上线。

## 3. 为什么 Agent 需要持久化状态，而不是只依赖内存？

总：

因为生产 Agent 经常是长任务，可能跨分钟、跨小时，甚至跨服务重启，单靠内存无法保证可靠性。

分：

LangGraph 这类框架会通过 `thread_id` 和 checkpoint 保存图状态，每个 super-step 后都持久化。这样任务中断后可以恢复，用户确认后可以继续，服务重启后也不丢上下文。对于 AI Coding 场景，代码修改、测试、PR 创建都不是瞬时任务，更需要可恢复状态。

总：

所以 checkpoint 是 Agent 从 demo 走向生产的基础能力。

## 4. checkpoint 会不会把所有历史都重新塞进大模型上下文？

总：

不会简单等同于“全部塞回模型上下文”。checkpoint 保存的是图状态，但真正喂给模型的上下文还需要经过上下文管理。

分：

如果消息很多，系统通常会做摘要、截断、重要信息提取、长期记忆沉淀，避免超过模型上下文窗口。checkpoint 更像“可恢复的状态快照”，而不是每次都完整拼进 prompt。真正进入模型的内容要经过 runtime 或 middleware 的选择。

总：

因此生产 Agent 要同时设计 checkpoint 和 context engineering，不能只依赖自动恢复。

## 5. Agent 的长期记忆和 checkpoint 有什么区别？

总：

checkpoint 解决会话连续性，长期记忆解决跨任务、跨会话的知识沉淀。

分：

checkpoint 保存某个 `thread_id` 下的对话状态、工具调用状态和执行进度；长期记忆保存稳定知识，比如仓库结构、技术栈、测试命令、历史决策和注意事项。checkpoint 偏运行态，长期记忆偏知识态。

总：

两者配合，Agent 才既能恢复当前任务，又能避免每次重新理解项目。

## 6. Agent 为什么需要多层意图识别？

总：

因为用户一句话到最终工具执行，中间存在多个决策层，不能只做一次分类。

分：

第一层判断用户任务类型，比如写代码、审查、查询、规划；第二层由主 Agent 判断是否转交给 SubAgent；第三层把任务拆成计划；第四层在每个步骤里判断该读文件、改代码、跑测试还是提交 PR。这样可以降低误执行风险。

总：

多层意图识别的价值是把复杂任务拆成可控决策链，而不是让模型一次性自由发挥。

## 7. 为什么 Agent 项目要使用 SubAgent？

总：

SubAgent 是为了把复杂任务按职责拆开，让不同 Agent 使用不同提示词、工具和工作流程。

分：

比如 AI Coding 中，写代码 Agent 关注实现、测试、提交；Reviewer Agent 关注 diff、风险、finding 和审查规则。两者目标不同，如果混在一个 Agent 中，容易提示词过长、职责混乱、工具使用不稳定。

总：

SubAgent 架构能提升专业性、可维护性和扩展性，是复杂 Agent 系统常见设计。

## 8. Agent 工具调用失败怎么办？

总：

工具失败不能让系统直接崩溃，而要转换成 Agent 可理解、前端可展示、日志可追踪的结构化错误。

分：

工程上一般会做三层处理：工具层捕获底层异常，中间件把异常转成标准错误消息，runtime 更新任务状态并推送 SSE error。对于可恢复错误，比如路径错误、参数错误、测试失败，可以让 Agent 根据错误自我修正；对于不可恢复错误，则终止任务并提示用户。

总：

工具失败处理的核心是“可恢复、可观测、可追责”。

## 9. 如何防止 Agent 出现循环调用？

总：

防循环不能只靠 prompt，需要运行时限制和状态约束。

分：

常见做法包括 `recursion_limit`、模型调用次数限制、工具调用次数限制、最大运行时长、重复工具参数检测、任务状态机约束。如果 Agent 多次对同一错误执行相同工具，可以中断并要求人工确认。

总：

生产级 Agent 必须有硬限制，否则一次异常就可能造成成本失控或任务卡死。

## 10. Agent 的权限控制能靠 Prompt 保证吗？

总：

不能。Prompt 只能约束模型行为，不能作为安全边界。

分：

真正安全边界应该在后端：文件后端限制虚拟路径，工具层校验参数，命令执行层做白名单，敏感目录拒绝访问，高风险场景放进沙箱。即使模型被 prompt injection 诱导，也不能绕过后端权限。

总：

企业 Agent 的安全原则是：模型可以被诱导，但系统边界不能被诱导。

## 11. AI Coding Agent 为什么需要沙箱？

总：

因为写代码 Agent 会执行命令、安装依赖、运行测试，这些动作天然有安全风险。

分：

沙箱可以隔离文件系统、网络、进程和依赖环境，避免 Agent 误删宿主机文件、访问敏感路径、污染系统环境。企业场景还可以做每个任务独立容器、资源限额、超时回收、审计日志和网络白名单。

总：

沙箱是把 Agent 的执行能力关进可控边界里，是生产安全的关键。

## 12. 怎么保证 SSE 流式输出稳定？

总：

SSE 稳定性的关键是事件协议清晰、队列解耦、异常可结束、代理不缓冲。

分：

后端可以用消息队列承接 Agent 事件，Agent 写事件，SSE 消费事件，避免阻塞主线程。事件要区分 `message_start`、`text_delta`、`todo_delta`、`error`、`done`。部署 Nginx 时要关闭响应缓冲，并设置合理超时。异常时必须发送 error 或 done，不能让前端一直等。

总：

SSE 稳定不是只靠框架，而是靠“队列 + 协议 + 超时 + 结束事件”共同保证。

## 13. 为什么有些 Agent 项目选择 SSE 而不是 WebSocket？

总：

如果业务主要是服务端持续输出文本，SSE 更简单、更稳定。

分：

SSE 基于 HTTP，天然适合大模型 token 流、任务进度、状态推送；浏览器支持好，Nginx 也容易代理。WebSocket 更适合强双向、高频交互，比如在线协作、远程终端、实时游戏。AI Coding 场景一般是用户提交任务，后端持续输出，SSE 已经足够。

总：

选 SSE 是因为它匹配单向流式输出场景，不是因为 WebSocket 不好。

## 14. Agent 的持续评估应该评估什么？

总：

Agent 评估不能只看最终答案，还要看过程轨迹、工具调用和安全合规。

分：

常见维度包括正确性、任务完成度、事实一致性、工具选择是否正确、工具参数是否正确、是否遵守权限、安全策略是否违规、耗时和 token 成本。Harness Evals 这类方案也强调 offline eval、online eval、trajectory evaluation 和 pipeline gate。

总：

Agent 是一个系统，评估对象也必须是系统级行为，而不是单条回复。

## 15. 离线评估和线上评估有什么区别？

总：

离线评估用于上线前拦截回归，线上评估用于发现真实流量中的质量漂移。

分：

离线评估通常基于 golden dataset，在 CI/CD 中跑固定用例，对比 prompt、模型和工具改动是否退化。线上评估会抽样真实用户请求，结合 trace 和评分器发现新问题，再把失败样本沉淀回数据集。

总：

离线保证发布质量，线上保证长期质量，两者应该使用一致的指标体系。

## 16. 什么是 Agent 的 Golden Dataset？

总：

Golden Dataset 是一组经过人工确认的高价值测试样本，用来衡量 Agent 是否稳定。

分：

每条样本通常包含用户输入、期望结果、上下文、期望工具调用、风险标签等。对 AI Coding 项目，可以包含“新增接口”“修复测试”“审查 PR”“查询仓库记忆”等典型任务。它不是越多越好，而是要覆盖核心业务路径和高风险路径。

总：

Golden Dataset 是持续评估的基准，没有它就很难判断 Agent 改动是变好还是变差。

## 17. LLM-as-Judge 可靠吗？怎么使用更安全？

总：

LLM-as-Judge 有价值，但不能当作唯一裁判。

分：

它适合评估语义质量、完整性、相关性、是否遵守要求等难以精确判断的问题。但对于 JSON 结构、字段、工具调用顺序、测试结果、权限违规，应该优先用确定性规则。更稳妥的方式是 LLM 评分 + 规则评分 + 人工抽检组合使用。

总：

LLM-as-Judge 是评估工具，不是绝对真相，企业里必须配合确定性校验。

## 18. Agent Trace 在评估中有什么价值？

总：

Trace 是定位 Agent 问题的第一手证据。

分：

Trace 记录模型调用、工具调用、输入输出、handoff、guardrail、错误和耗时。通过 trace 可以判断 Agent 是否选错工具、是否重复调用、是否忽略规则、是否在错误上下文上继续推理。OpenAI 和 Harness 的评估思路都强调 trace-first。

总：

没有 trace，只能看到结果好坏；有 trace，才能知道为什么好、为什么坏。

## 19. Agent 如何接入 CI/CD 做质量门禁？

总：

Agent 的评估应该像单元测试一样进入流水线，分数不达标就阻断发布。

分：

做法是把 golden dataset、metrics、threshold 组织成 eval suite。每次改 prompt、模型、工具或 runtime 后，在 CI 中运行评估，对比 baseline。如果任务完成率、工具正确率、安全分、延迟或成本指标下降超过阈值，就让流水线失败。

总：

这样 Agent 的质量从“人工感觉还行”变成“可量化、可回归、可阻断”。

## 20. 如果让你设计一个企业级 AI Coding Agent 的持续评估体系，你会怎么做？

总：

我会按“离线回归、线上抽检、失败回灌、版本治理”四层来设计。

分：

离线层维护 coding、review、planning、qa 等 golden dataset；线上层采样真实 trace 做评分；失败样本进入人工复核，确认后回灌数据集；版本层记录 prompt、model、tools、skills、middleware 和 backend 版本，支持 A/B 对比和回滚。指标上同时看任务完成率、工具轨迹、测试通过率、安全违规率、延迟和成本。

总：

最终目标不是追求某一次回答漂亮，而是让 Agent 在持续迭代中质量可控、风险可控、成本可控。
