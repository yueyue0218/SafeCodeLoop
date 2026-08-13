# SafeCodeLoop 设计文档（SPEC）

## 1. 问题陈述

SafeCodeLoop 是一个面向编程任务的迷你 Coding Agent Harness。它不是一个普通应用，也不是一组提示词，而是一个用于展示“编码智能体如何被工程化封装”的小型系统。

它要解决的问题是：很多人把 coding agent 理解成“LLM 加一个提示词”，但真正可靠的 coding agent 还需要主循环、工具系统、上下文、护栏、测试反馈、凭据管理和分发机制。SafeCodeLoop 的目标就是把这些机制用代码实现出来，并且能用 mock LLM 做确定性测试。

一句话目标：

> 实现一个带治理护栏和测试反馈闭环的迷你 coding agent harness，能够在受控工作区内读写文件、运行命令、拦截危险动作，并用 mock LLM 演示自我修正。

## 2. 目标用户

- AI4SE 课程中希望理解 Agent Harness 工程机制的开发者。
- 想理解 coding agent 内部机制的开发者。
- 需要在无真实 LLM API key、无网络条件下复现和检查 harness 机制的评审者。

## 3. 项目范围

### 3.1 范围内

- 自己实现 agent 主循环。
- 提供可替换的 LLM 抽象层：
  - mock LLM 用于测试和演示。
  - 可选真实 LLM adapter。
- 实现 coding 工具：
  - 列出文件。
  - 读取文件。
  - 在工作区内写文件。
  - 运行受控 shell 命令。
- 实现治理护栏：
  - 阻止危险 shell 命令。
  - 阻止写入工作区外路径。
  - 对安装依赖、发布、外部副作用等动作返回需要人工审批。
- 实现反馈闭环：
  - 运行测试或校验器。
  - 分类失败原因。
  - 把结构化反馈回灌给下一轮 agent。
- 实现最小记忆和上下文管理：
  - 保存项目约定、历史失败、人工决策。
  - 控制上下文大小，不全量塞入。
- 实现配置系统：
  - 工作区路径。
  - 最大步数。
  - 可用工具。
  - 危险命令规则。
  - 测试命令。
  - 模型供应商。
- 实现凭据管理：
  - 配置 API key。
  - 查看状态、更新、清除。
  - 不回显明文 key。
- 提供 CLI。
- 提供 mock LLM 单元测试。
- 提供机制演示。
- 采用 CLI-only + release 链接交付。
- WebUI 作为可选增强，不作为 P0 必做项。

### 3.2 范围外

- 完整 IDE 插件。
- 大规模多仓库自动重构。
- 自动联网浏览。
- 不受限制地运行任意不可信代码。
- 替代 Codex / Claude Code 等成熟 coding agent。
- 基于 LangChain AgentExecutor、AutoGen、CrewAI、LlamaIndex Agent 等高层 agent runner 搭建。

## 4. 用户故事

### US-1：运行受控编程任务

作为开发者，我希望通过 CLI 提交一个小型编程任务，让 SafeCodeLoop 能按步骤读写文件、运行测试，并在完成、失败、被拦截或达到最大步数时停止。

验收标准：

- 可以通过 CLI 提交任务。
- 每一步记录 LLM 输出、解析出的动作、工具结果和最终状态。
- 遇到完成、失败、危险动作、需要审批或最大步数时能停止。

### US-2：不依赖真实 LLM 也能测试

作为评审者，我希望使用 mock LLM 跑确定性测试，这样不需要网络和 API key 也能验证 harness 机制。

验收标准：

- mock LLM 可以按脚本返回动作。
- 测试可以断言 agent loop 的精确行为。
- 核心机制测试不调用真实 LLM。

### US-3：危险命令由代码拦截

作为用户，我希望危险操作在执行前被代码拦截，而不是只靠提示词提醒 LLM。

验收标准：

- `rm -rf /`、删除数据库、访问敏感文件、写入工作区外路径等动作会被拦截。
- 被拦截动作会记录 guardrail 事件。
- 工具执行器不会收到已经被拦截的动作。

### US-4：根据测试反馈自我修正

作为开发者，我希望 agent 收到测试失败信息后，下一轮动作能根据反馈改变，从而展示真实反馈闭环。

验收标准：

- 测试失败会被转换成结构化反馈。
- 下一轮 mock LLM 能收到该反馈。
- 演示中能稳定复现“先失败、再修正、最后通过”。

### US-5：通过配置约束运行边界

作为项目 owner，我希望通过配置文件控制工作区、工具、危险命令规则和测试命令。

验收标准：

- 合法配置可加载。
- 非法配置有清晰错误。
- 配置会影响工具和护栏行为。

### US-6：安全配置 API Key

作为用户，我希望安全配置 LLM API key，避免 key 被写进源码、日志或提交记录。

验收标准：

- 支持设置、查看状态、更新、清除 key。
- 状态命令不显示明文 key。
- 若使用 `.env` fallback，必须说明其明文风险。
- 测试和源码中不包含真实 key。

## 5. 功能规约

### 5.1 Agent 主循环

输入：

- 用户任务。
- 工作区路径。
- 配置。
- 可选记忆。

行为：

1. 根据任务、配置、记忆和最近 observation 组装上下文。
2. 调用 LLM adapter。
3. 解析 LLM 输出为结构化 action。
4. 校验 action。
5. 执行 guardrail 检查。
6. 如果允许，则调用对应工具。
7. 将工具结果转成 observation。
8. 将 observation 回灌到下一轮。
9. 满足停止条件时结束。

输出：

- 运行状态：`success`、`failed`、`blocked`、`needs_approval`、`max_steps`、`validation_budget_exhausted`、`repeated_validation_failure`。
- 每一步日志。
- 工具输出。
- 护栏事件。
- 反馈事件。

边界条件：

- LLM 输出格式错误时，生成 parse-error observation。
- 最大步数防止无限循环。
- 工具失败不会让程序崩溃，而是作为反馈进入下一步。

### 5.2 LLM 抽象层

输入：

- 上下文消息。
- 模型配置。

行为：

- `MockLLM` 返回测试脚本中的预设响应。
- `OpenAICompatibleLLM` 通过底层 `/chat/completions` 单次调用连接兼容供应商；主循环、动作解析、工具、治理和反馈仍由 SafeCodeLoop 实现。

输出：

- 原始模型响应。
- 不含密钥的供应商元数据。

边界条件：

- 未配置真实 key 时返回明确错误。
- 鉴权、限流、超时、网络错误和无效响应转换为不含密钥的稳定错误。
- 单元测试默认使用 mock LLM。

### 5.3 Action 解析器

支持的 action：

- `list_files`
- `read_file`
- `write_file`
- `run_command`
- `run_validation`
- `remember`
- `finish`
- `request_approval`

边界条件：

- 未知 action type 拒绝。
- 缺少必要字段拒绝。
- 路径先规范化，再进入护栏检查。

### 5.4 工具系统

行为：

- 根据 action type 调度注册工具。
- 执行前做参数校验。
- 将结果转换为结构化 observation。

边界条件：

- 未注册工具安全失败。
- 工作区外写入被拒绝。
- 命令执行受 allowlist 和 guardrail 控制。

### 5.5 治理护栏

行为：

- 将 action 分类为：
  - `allow`
  - `block`
  - `needs_approval`
- 明确危险命令直接 block。
- 修改依赖、发布、外部副作用等动作进入人工审批状态。

关键要求：

- 护栏检查必须在工具执行前发生。
- 被 block 的 action 不能进入 executor。
- 护栏是确定性代码，不是提示词。

人工审批状态机：

- 风险动作在执行前创建 `pending` 审批记录，使用 OS keyring 中独立保存的签名 key 对 canonical action 生成 HMAC-SHA256 签名。
- `approve` / `reject` 可在后续 CLI 进程中改变审批状态。
- `resume` 在执行前重新验证记录完整性与 action 签名，并一次性消费批准。
- 已拒绝、未批准、已消费、动作不匹配或记录被篡改时安全失败。
- 只持久化恢复所需的最小审批状态，不保存完整 LLM 对话或凭据。

### 5.6 反馈闭环

行为：

- 运行配置的测试命令或校验器。
- 将结果分类为：
  - `pass`
  - `test_failure`
  - `syntax_error`
  - `type_error`
  - `lint_failure`
  - `timeout`
  - `environment_error`
  - `unknown_failure`
- 生成反馈消息，进入下一轮上下文。

边界条件：

- 测试失败不能被当作完成。
- timeout 有结构化结果。
- 成功写入代码或工程配置后，必须有更新后的客观验证通过，`finish` 才能返回成功。
- 验证失败后直接请求 `finish` 会生成 `completion_rejected` observation 并继续循环。
- 总验证次数受 `maxValidations` 限制；相同类别与摘要连续失败达到 `maxRepeatedFailures` 时打开熔断器。
- 审批恢复路径使用相同的完成门槛、预算与重复失败规则，不能绕过验证状态机。
- 完整验证输出保留在运行日志；回灌模型的 details 默认限制为 1200 字符，并携带原始字符数、SHA-256 和日志位置。
- 压缩时优先保留失败位置与诊断行，避免超大 stdout/stderr 全量进入模型上下文。

### 5.7 记忆与上下文

行为：

- 保存项目事实、人工决策、失败模式。
- 根据任务选择相关记忆。
- 按优先级和最近性控制上下文大小。

边界条件：

- 记忆中不得保存 API key。
- 记忆文件尽量保持可读。

### 5.8 配置系统

配置字段：

- `workspaceRoot`
- `maxSteps`
- `maxValidations`
- `maxRepeatedFailures`
- `allowedTools`
- `blockedCommandPatterns`
- `approvalRequiredPatterns`
- `testCommand`
- `modelProvider`
- `model`
- `baseUrl`
- `requestTimeout`
- `credentialProvider`
- `memoryPath`

行为：

- 启动时加载配置。
- 提供默认值。
- 对非法配置给出明确错误。

### 5.9 凭据管理

行为：

- 默认使用 OS keyring；Windows 上使用 Windows Credential Manager。
- CLI 通过隐藏输入录入 key，不接受命令行明文 key 参数。
- 明文文件 backend 仅允许通过依赖注入用于隔离测试，不作为生产 CLI fallback。
- 支持 `key set`、`key status`、`key clear`。

边界条件：

- 不打印明文 key。
- 不把 key 写入日志。
- 不把 key 存入 memory。

### 5.10 CLI 与可选 WebUI

P0 只要求 CLI。

CLI 行为：

- 提交任务。
- 指定 mock script。
- 指定 workspace。
- 输出运行状态和步骤日志。
- 显示 guardrail 和 feedback 结果。

WebUI：

- 可选增强。
- 如果时间紧，不实现 WebUI。

## 6. 非功能需求

### 6.1 性能

- mock LLM 测试应能快速在 CI 中完成。
- 默认最大步数防止长时间运行。
- 默认不读取超大文件。

### 6.2 安全

威胁模型：

- LLM 提出危险命令。
- LLM 尝试访问工作区外文件。
- 用户误提交 API key。
- 日志泄露密钥。
- 任务 prompt 中包含诱导绕过规则的内容。

对策：

- 工具执行前做确定性 guardrail 检查。
- 路径规范化与工作区边界检查。
- 日志中做 secret redaction。
- key 不进入源码。
- 测试使用 mock LLM。
- README 说明 `.env` 明文风险。

### 6.3 可用性

- CLI 输出清楚说明当前状态。
- 错误信息告诉用户下一步怎么处理。
- README 能支持新机器从零运行。

### 6.4 可观测性

- 每次运行保存 step log。
- guardrail 决策记录原因。
- feedback 记录分类结果。
- 普通 `run_command` 保留为工具 observation；只有显式 `run_validation` 产生客观验证 feedback。
- 真实 LLM 响应不得记录密钥。

## 7. 系统架构

```text
用户 / CLI / 可选 WebUI
        |
        v
Run Controller
        |
        v
Agent Loop
  |     |       |        |
  |     |       |        +--> Memory Store
  |     |       +----------> Feedback Sensor
  |     +------------------> Guardrail Engine
  +------------------------> LLM Adapter
                                |
                                +--> Mock LLM
                                +--> Real LLM Provider

Agent Loop -> Action Parser -> Tool Dispatcher -> Tools -> Observation -> Agent Loop
```

主要模块：

- `core/loop`：主循环与停止条件。
- `llm`：LLM interface、mock LLM、真实 adapter。
- `actions`：action schema 与 parser。
- `tools`：工具注册与实现。
- `guardrails`：危险动作规则与审批状态。
- `feedback`：测试传感器与失败分类。
- `memory`：记忆存储与上下文选择。
- `config`：配置加载与校验。
- `credentials`：密钥存储与脱敏。
- `cli`：命令行入口。

## 8. 数据模型

### Run

- `id`
- `task`
- `status`
- `startedAt`
- `finishedAt`
- `steps`

### Step

- `index`
- `contextSummary`
- `llmResponse`
- `parsedAction`
- `guardrailDecision`
- `toolResult`
- `feedback`

### Action

- `type`
- `arguments`
- `requestId`

### GuardrailDecision

- `decision`
- `severity`
- `reason`
- `ruleId`

### ApprovalRecord

- `id`
- `action`
- `actionHash`
- `reason`
- `status`：`pending` / `approved` / `rejected` / `consumed`

### FeedbackEvent

- `validator`
- `status`
- `category`
- `summary`
- `rawOutputRef`

### MemoryItem

- `id`
- `kind`
- `content`
- `createdAt`
- `priority`

## 9. 领域与机制设计

### 9.1 Coding 领域需要的工具

- 文件发现。
- 文件读取。
- 文件写入。
- shell 命令执行。
- 测试 / lint / typecheck 校验器。

### 9.2 客观反馈信号

- 单元测试退出码。
- lint/typecheck 退出码。
- action schema 校验结果。
- guardrail 决策。
- 文件操作结果。

这些信号都由代码产生，不依赖 LLM 自我评价。

### 9.3 危险动作

- 递归删除根目录、home、workspace。
- 删除或重置数据库。
- 写入工作区外路径。
- 读取常见敏感文件。
- 未经批准安装全局依赖、发布、部署。
- 打印环境变量或 credential 文件。

### 9.4 记忆需求

- 项目约定。
- 历史失败命令。
- guardrail 决策。
- 人工批准或拒绝记录。
- 常见失败模式。

记忆不得存储密钥。

### 9.5 主要贡献

本项目主要贡献是：

> 治理护栏 + 测试反馈闭环。

理由：

- 作业强调真实机制必须能在移除 LLM 后被单测验证。
- 护栏和反馈最容易被错误地写成提示词，因此最适合作为代码机制展示。
- mock LLM 可以确定性复现危险动作拦截和反馈修正。

深度目标：

- guardrail 支持 `allow`、`block`、`needs_approval`。
- guardrail 在执行前发生。
- feedback classifier 区分测试失败、语法错误、超时、环境错误。
- 演示中能看到失败反馈改变下一步动作。

## 10. 凭据与分发设计

### 10.1 凭据存储

优先方案：

- OS keyring，包括 Windows Credential Manager。

测试方案：

- 测试可以显式注入临时文件 backend；生产 CLI 不自动降级到明文存储。

凭据命令：

- `key set`
- `key status`
- `key clear`

要求：

- 不回显明文。
- 状态不显示可识别的 key 片段。
- 不写日志。
- 不提交 Git。

### 10.2 分发

默认采用：

> CLI-only + release 链接。

理由：

- 课程补充说明允许 Agent Harness 项目只提供 CLI 和 release。
- 这样能把时间集中在 harness 内核、mock 测试和机制演示上。

可选：

- Docker 镜像或 Dockerfile。
- 如果时间充足再做 WebUI。

README 必须说明：

- 如何安装。
- 如何运行 CLI。
- 如何运行 mock LLM demo。
- 如何配置 key。
- 如何运行测试。
- release 链接在哪里。
- 已知限制。

## 11. 技术选型

锁定选型：

- Python 3.11+
- `argparse` 做 CLI。
- `pytest` 做测试。
- `setuptools` 做 `pyproject.toml` 构建后端。
- 包名：`safecodeloop`。
- CLI 全局命令名：`safecodeloop`。
- 版本号唯一来源：`src/safecodeloop/__init__.py` 中的 `__version__`。
- 同时支持 `python -m safecodeloop.cli` 和 `python -m safecodeloop`，后者通过 `src/safecodeloop/__main__.py` 转发到 CLI。
- JSON 文件做 mock LLM script、配置和记忆。
- Docker / release 做分发。

理由：

- Python 实现文件工具、命令执行和测试反馈最快。
- pytest 适合做确定性 mock LLM 单元测试。
- CLI-only 方案能降低交付风险。

## 12. 验收标准

项目完成时应满足：

- `SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md` 完成。
- 使用另一个不同 agent 做过冷启动验证，并记录结果。
- 自己实现 agent 主循环。
- LLM 抽象层支持 mock LLM。
- 工具系统支持文件和命令工具。
- guardrail 能在执行前拦截危险动作。
- feedback loop 能运行测试并把失败反馈回灌。
- 最小 memory/context 实现完成。
- config 系统控制运行行为。
- 凭据管理不硬编码、不回显明文。
- mock LLM 单元测试覆盖核心机制。
- 机制演示包含：
  - 危险动作被拦截。
  - 失败反馈改变下一步动作。
  - 主要贡献机制演示。
- `.gitlab-ci.yml` 包含 `unit-test` job。
- 最后一次 CI 通过。
- README 写清安装、运行、测试、分发、key 配置、安全边界和 release 链接。
- 有 release 链接。
- `submission.jsonc` 填写仓库链接、`is_deployed=false`、release 链接。
- `AGENT_LOG.md` 和 `REFLECTION.md` 完成。

## 13. 风险与未决问题

### 风险

- 范围膨胀，变成完整 coding agent。
- 误用高层 agent 框架，违反作业边界。
- TDD 证据不足。
- key 泄露。
- WebUI 消耗过多时间。
- 冷启动验证暴露 SPEC/PLAN 不清楚。

### 对策

- 保持 CLI-only。
- 以 mock LLM 单测为中心。
- 优先实现护栏和反馈闭环。
- 每个 task 记录 `AGENT_LOG.md`。
- 提交前做凭据泄漏检查。

### 未决问题

- 是否实现 OS keyring，还是用 `.env` fallback 并充分说明风险。
- release 使用 GitHub 还是 NJU Git。
- 冷启动验证使用哪个不同 agent。
