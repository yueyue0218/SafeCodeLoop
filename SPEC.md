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

| NFR ID | 可测量要求 | 验收方法 |
|---|---|---|
| `NFR-PERF-01` | 116 项离线测试不访问真实 LLM 或网络；在本项目 Windows/Python 3.11 基线中目标 30 秒内完成（当前 7.57 秒） | 断网或不配置 key 后运行 `python -m pytest`，必须全部通过 |
| `NFR-PERF-02` | 单次进入模型上下文的 validation details 默认不超过 1200 字符 | 长输出测试断言 `details` 长度、截断标志、原长度与 SHA-256 |
| `NFR-PERF-03` | 默认单次 run 最多 5 个 agent steps、4 次 validations；相同失败连续 2 次打开熔断 | 加载默认 config，并通过 loop/config 单测验证终态 |
| `NFR-PERF-04` | 本地命令默认 10 秒 timeout；真实 provider 请求默认 60 秒 timeout | command/LLM stub 测试断言 timeout 参数和结构化错误 |
| `NFR-PERF-05` | Memory 默认每次检索最多 5 条候选记录，并支持调用方进一步降低 limit | memory 单测断言 limit、优先级与相关性排序 |

### 6.2 安全

#### 6.2.1 安全目标与信任假设

需要保护的资产包括：宿主机与工作区完整性、API key 和审批签名 key、审批状态完整性、验证证据真实性，以及 agent loop 的可用性。

SafeCodeLoop 采用以下信任假设：

- 本地操作者和操作系统凭据库属于可信计算基；LLM 响应、任务文本、仓库文件内容和审批记录文件均按不可信输入处理。
- MockLLM 只消除网络和模型随机性，不自动获得工具权限；其 action 与真实模型 action 经过完全相同的 parser、guardrail 和 dispatcher。
- Workspace 边界限制文件工具的访问范围，但 SafeCodeLoop 不是操作系统级沙箱；允许执行的 shell 命令仍可能产生 guardrail 规则无法枚举的副作用。
- OS keyring 不可用或审批记录完整性无法验证时，相关操作安全失败，不自动降低到明文存储或无签名执行。

#### 6.2.2 威胁模型

| 威胁 ID | 资产与攻击路径 | 确定性控制 | 验证证据 | 剩余风险 |
|---|---|---|---|---|
| `THR-01` | Prompt injection 或 LLM 直接提出危险 shell action | 模型响应先经 schema parser，再由 guardrail 在 executor 前判定 | `tests/test_actions.py`、`tests/test_guardrails.py`、危险动作 demo | 规则匹配不能覆盖所有 shell 混淆和间接副作用 |
| `THR-02` | 通过绝对路径、`..` 等方式访问 workspace 外文件 | 路径规范化后执行 containment check，越界读写拒绝 | `tests/test_file_tools.py` | 符号链接、挂载点及平台路径语义仍需操作系统级隔离补强 |
| `THR-03` | 将风险命令伪装成 validation 绕过普通命令治理 | `run_command` 与 `run_validation` 共享同一 guardrail；validation 只改变反馈语义，不改变权限 | `tests/test_loop_tools_guardrails.py`、`tests/test_feedback_loop.py` | 自定义安全命令仍可能执行其内部包含的高风险逻辑 |
| `THR-04` | API key 经 CLI 参数、配置、日志或 memory 泄露 | hidden input、OS keyring、secret redaction；生产 CLI 无明文文件 fallback | `tests/test_credentials.py`、`tests/test_memory.py` | 已被外部进程或系统管理员攻破的主机不在保护范围内 |
| `THR-05` | 审批文件被改写、换参或复制后重放 | canonical action + HMAC-SHA256；签名 key 独立存于 keyring；批准在工具调用前一次性消费 | `tests/test_approval.py` | 本地审批文件仍可能暴露 action 参数，因此 `.safecodeloop/` 必须保持本地并排除出 Git |
| `THR-06` | 模型在代码写入或 validation 失败后直接声明成功 | harness 根据真实工具事件维护 completion gate；新的客观 pass 前拒绝 `finish` | `tests/test_loop.py`、`tests/test_feedback_loop.py` | 配置错误或覆盖不足的 validator 可能给出不充分的 pass |
| `THR-07` | 超长 stdout/stderr 挤占上下文或把敏感内容反射给模型 | 完整 evidence 留在日志；模型只接收有界、脱敏摘要和 hash/reference | `tests/test_feedback.py`、`tests/test_feedback_loop.py` | 日志本身仍需由操作者控制文件权限和保留周期 |
| `THR-08` | 无限步骤、无限验证或相同失败重复消耗资源 | `maxSteps`、命令 timeout、`maxValidations` 和重复失败熔断器 | `tests/test_loop.py`、`tests/test_command_tool.py`、`tests/test_feedback_loop.py` | 单次允许命令仍可能消耗较多 CPU、内存或磁盘 |
| `THR-09` | Provider 鉴权、超时或异常响应导致崩溃并泄露 key | adapter 将错误转换为不含 secret 的稳定异常；核心测试默认不访问网络 | `tests/test_llm.py`、`tests/test_credentials.py` | 第三方服务的可用性、隐私策略和兼容性由供应商控制 |
| `THR-10` | Release 或镜像混入 `.git`、凭据、审批状态或本地日志 | release 基于 `git ls-files`；归档和 image 内容执行排除检查 | `RELEASE_CHECKLIST.md`、`.dockerignore`、Docker 验证记录 | 已被错误提交进 Git 历史的内容不会被打包规则自动消除，发布前仍需凭据扫描 |

#### 6.2.3 安全失败原则

- 无法解析、未知工具、越界路径、损坏审批记录和不可用 keyring 均返回明确错误，不猜测、不自动放宽权限。
- `blocked`、`needs_approval`、`validation_budget_exhausted` 与 `repeated_validation_failure` 是稳定终态，CLI 和运行日志必须保留原因。
- 安全控制由代码和状态机实现；prompt 可以解释规则，但不承担最终授权或完成判定。

### 6.3 可用性

| NFR ID | 可测量要求 | 验收方法 |
|---|---|---|
| `NFR-USE-01` | 支持 `safecodeloop`、`python -m safecodeloop` 和 `python -m safecodeloop.cli` 三种入口，help/version 均退出 0 | `tests/test_cli.py` 与 wheel smoke |
| `NFR-USE-02` | CLI 退出码稳定：成功与 key/approval 正常操作为 0；blocked/needs_approval/max_steps 等非成功 run 为 1；配置、凭据、provider、审批数据错误为 2 | `tests/test_cli_run.py`、`tests/test_credentials.py`、`tests/test_approval.py` |
| `NFR-USE-03` | 每次 run 至少输出 `status: <stable-enum>`；需要审批时额外输出 `approval_id`；错误路径输出不含 secret 的原因 | CLI capture 测试和三个 demo |
| `NFR-USE-04` | 在没有真实 key 的全新环境中，评审者只依赖 release、Python 3.11+ 或 Docker 即可运行 MockLLM 测试和演示 | 按 §10.3 全新机器验收清单执行 |

### 6.4 可观测性

| NFR ID | 可测量要求 | 验收方法 |
|---|---|---|
| `NFR-OBS-01` | 使用 `--log` 时生成 UTF-8 JSON，至少包含 run status、final message、approval id 与按 index 排序的 steps | `tests/test_cli_run.py` 解析日志并断言字段 |
| `NFR-OBS-02` | 每个 step 记录 LLM response、parsed action 和 observation；guardrail/feedback observation 包含稳定类别与原因 | loop、guardrail、feedback 和 demo 测试 |
| `NFR-OBS-03` | 完整 validation evidence 留在 step/run log；模型上下文仅包含有界摘要、原字符数、SHA-256 和 evidence 位置 | 长输出 feedback 测试 |
| `NFR-OBS-04` | 普通 `run_command` 不产生 validation feedback；只有显式 `run_validation` 产生客观验证事件 | `tests/test_feedback_loop.py` |
| `NFR-OBS-05` | API key 和 approval signing key 不得进入 LLM context、memory、run log 或 status 输出 | credentials、memory、LLM redaction 测试及提交前 secret scan |

### 6.5 可靠性与停止保证

| NFR ID | 可测量要求 | 验收方法 |
|---|---|---|
| `NFR-REL-01` | 非零命令退出、timeout、tool exception 和 parse error 转成结构化 observation/result，不使主进程因未捕获异常崩溃 | command、tools、loop 单测 |
| `NFR-REL-02` | 任一 run 必须在 success、failed、blocked、needs_approval、max_steps、validation budget exhausted 或 repeated failure 之一终止 | loop/feedback/approval 表驱动测试 |
| `NFR-REL-03` | 普通运行与 approval resume 使用相同 guardrail、completion gate、validation budget 和 circuit breaker | approval 与 feedback loop 回归测试 |

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

### 7.1 数据流与信任边界

```text
可信本地操作者
      |
      | TB-01：CLI 参数 / config 校验
      v
Run Controller -------------------------------> OS Keyring
      |                                             ^
      |                                             | TB-05：secret 与签名 key
      v                                             |
Agent Loop ---> LLM Adapter ---> External Provider |
    ^              |                 (不可信)       |
    |              | TB-02：原始模型响应            |
    |              v                               |
    |         Action Parser                        |
    |              |                               |
    |              | TB-03：未经授权的候选 action  |
    |              v                               |
    |       Guardrail / Approval ------------------+
    |              |
    |              | 仅 allow 或已消费 approval
    |              v
    |        Tool Dispatcher
    |          /          \
    | TB-04   v            v
    |     Workspace     Host Shell
    |          \          /
    |           ToolResult
    |              |
    |       Validation Classifier
    |          /             \
    | TB-06   v               v
    +-- 有界摘要进入上下文   完整证据进入 Run Log
```

| 边界 | 两侧组件 | 边界规则 |
|---|---|---|
| `TB-01` | 操作者/配置 → Run Controller | 校验路径、枚举、正整数预算和 provider 配置；key 不允许通过命令行明文传入 |
| `TB-02` | LLM Provider → Action Parser | 响应始终不可信；必须通过 JSON/schema 校验，原始内容不得直接调用工具 |
| `TB-03` | Parsed Action → Guardrail/Approval | action 只是候选副作用；必须先取得 allow 或与原 action 绑定的一次性 approval |
| `TB-04` | Tool Dispatcher → Workspace/Host Shell | 文件工具受 workspace containment 限制；命令有 timeout 并返回结构化结果 |
| `TB-05` | Approval/Credential 模块 → OS Keyring/本地记录 | secret 与签名 key 只进 keyring；本地审批记录按不可信文件重新验证完整性 |
| `TB-06` | Tool evidence → LLM Context/Run Log | 模型接收有界脱敏摘要；完整证据留在日志并通过长度、hash 和位置关联 |

### 7.2 外部依赖及失效行为

| 外部依赖 | 用途 | 不可用时行为 | 是否影响离线核心验收 |
|---|---|---|---|
| OpenAI-compatible provider | 可选真实决策来源 | 返回稳定 provider error，不泄露 key | 否，MockLLM 可替代 |
| OS keyring | API key 与 approval 签名 key | 涉及凭据或审批的路径安全失败 | 普通 MockLLM 安全任务不受影响 |
| Host shell | 执行允许的命令和 validator | timeout/非零退出转成结构化 `ToolResult` | 测试使用受控本地命令 |
| Workspace filesystem | 代码、memory、log 和审批记录 | I/O 错误转为 observation；越界访问拒绝 | 使用 pytest 临时目录验证 |
| pytest | 默认客观验证器和演示依赖 | 分类为 environment error，不能错误 success | 是，因此 CI 与演示镜像显式安装 |

主要模块：

- `loop.py`：主循环、完成门槛与停止条件。
- `llm.py`：LLM interface、MockLLM 与 OpenAI-compatible adapter。
- `actions.py`：action schema 与 parser。
- `tools.py`：工具注册、文件/命令工具与 validation action。
- `guardrails.py`：危险动作的 allow/block/needs_approval 决策。
- `approval.py`：持久审批、HMAC 完整性与一次性消费状态机。
- `feedback.py`：验证结果分类、有界摘要与 evidence reference。
- `memory.py`：记忆存储、脱敏与上下文选择。
- `config.py`：配置加载与校验。
- `credentials.py`：OS keyring、隐藏输入与脱敏。
- `cli.py`：命令行入口、审批命令与 resume。

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

> **反馈闭环（Validation Feedback Control Plane）**：由 harness 的确定性状态机控制“什么算客观验证、失败如何进入下一轮、以及何时允许任务成功结束”。

治理护栏是完整 Coding Agent Harness 的必要基础设施，也是所有工具与验证动作的安全前置条件；它具有可恢复审批、防篡改和一次性消费等增强，但不与反馈闭环并列为第二个主要贡献。这样既保证决策、工具、记忆、治理、反馈、配置六个维度均有可运行实现，也符合“选择一个机制密集维度深入实现”的要求。

理由：

- 作业强调真实机制必须能在移除 LLM 后被单测验证。
- 反馈闭环最容易退化成“把 stdout 原样塞回 prompt”，但这种做法不能阻止模型在失败后直接声明完成。
- MockLLM 可以确定性复现失败注入、反馈回灌、动作改变、重新验证和最终停止，不依赖网络、额度或模型随机性。
- 反馈控制同时涉及 action 协议、工具结果、上下文预算、完成判定与停止条件，具有足够的机制深度。

深度目标：

- 普通 `run_command` 只产生工具 observation；只有显式 `run_validation` 产生客观 validation feedback。
- feedback classifier 区分 `pass`、测试失败、语法错误、类型错误、lint 失败、超时、环境错误和未知失败。
- 完整 stdout/stderr 保留在运行日志；模型只接收默认不超过 1200 字符的诊断摘要，并获得原始字符数、SHA-256 与日志位置。
- 成功写入代码或工程配置后必须取得更新后的 validation pass，才能接受 `finish`。
- 验证失败后直接请求 `finish` 会产生 `completion_rejected` observation，而不是假成功。
- `maxValidations` 限制总验证次数；`maxRepeatedFailures` 对相同类别与摘要的连续失败打开熔断器。
- 普通运行路径和 approval resume 路径共享同一套完成门槛、验证预算与熔断规则。
- 主要贡献演示确定性复现 failure → bounded feedback → correction → pass；综合 demo 额外证明验证动作同样不能绕过执行前 guardrail。

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

### 10.3 全新机器验收流程

目标平台为 Windows 10/11 或常见 Linux（Python 3.11+），以及能够运行 Linux container 的 Docker Desktop/Engine。全新机器验收必须从与最终提交 commit 对齐的公开 release artifact 或该最终 commit 的仓库 clone 开始，不能依赖开发机的 editable install、已有虚拟环境、真实 API key 或未提交文件。

#### 路径 A：Python source release

前置条件：Python 3.11+、可访问 Python package index 以安装声明依赖和 pytest。

```powershell
python --version
python -m pip install . pytest
python -m pytest
python -m safecodeloop --help
python -m safecodeloop --version
```

客观通过标准：

- Python 版本不低于 3.11；
- 安装命令退出 0；
- 全量结果为 `116 passed`；
- help 与 version 均退出 0，version 为 `0.1.0`；
- 整个过程不要求配置真实 LLM key。

随后创建最小 demo config 并运行主要贡献演示：

```powershell
Set-Content -Path .\demo-config.json -Value '{"maxSteps":6}'
safecodeloop run --mock-script .\demos\feedback_correction.json --config .\demo-config.json --workspace .\tmp-feedback --log .\feedback-log.json correct a failing implementation
```

客观通过标准：日志依次包含 `test_failure` 和 `pass`，最终 CLI 输出 `status: success` 且退出 0；`feedback-log.json` 可被 JSON parser 读取。

需要真实 provider 时，必须在目标机器使用隐藏输入配置凭据：

```powershell
safecodeloop key status njusehub
safecodeloop key set njusehub
safecodeloop key status njusehub
safecodeloop key clear njusehub
```

客观通过标准：set 使用不可回显输入；status 只显示 configured/not configured；任何输出都不包含 key 或可识别片段。

#### 路径 B：Docker 干净环境

前置条件：Docker Engine/Desktop 可用，首次 build 可以访问基础镜像 registry。

```powershell
docker build --tag safecodeloop:0.1.0 .
docker run --rm safecodeloop:0.1.0 --help
docker run --rm safecodeloop:0.1.0 --version
Set-Content -Path .\demo-config.json -Value '{"maxSteps":6}'
docker run --rm -v "${PWD}\demo-config.json:/app/demo-config.json:ro" safecodeloop:0.1.0 run --mock-script /app/demos/feedback_correction.json --config /app/demo-config.json --workspace /tmp/demo correct a failing implementation
```

客观通过标准：image build 退出 0；help/version 退出 0；容器内 demo 出现 failure → correction → pass 并最终 `status: success`；普通安全 MockLLM 任务不初始化 OS keyring。

#### 分发验收失败条件

出现以下任一情况即判为分发验收失败：

- 需要未记录的环境变量、真实 key、开发机绝对路径或未提交文件；
- release archive 或 image 包含 `.git`、`.env`、`.safecodeloop`、运行日志、缓存或仓库外的私有执行辅助文档；课程交付物 `PLAN.md` 不属于排除对象；
- release tag、asset 内容与最终提交 commit 不一致，或无法从 artifact 追溯构建来源；
- 安装后 console script、模块入口、MockLLM 测试或 demo 任一不可运行；
- keyring 不可用时静默写入明文文件；
- validation 依赖缺失却错误返回 success。

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

## 13. 需求—机制—验收—测试追踪矩阵

以下编号为 SPEC 的稳定追踪标识，用于把课程要求、实现机制、客观验收和测试证据连接起来。测试文件均使用 MockLLM、stub 或本地临时资源验证核心机制，不依赖真实 LLM 和网络。

| 需求 ID | 需求与机制 | 客观验收标准 | 主要测试 / 演示证据 |
|---|---|---|---|
| `FR-ACT-01` | 模型输出必须先经过 Action Parser，未知类型或缺少字段安全失败 | 非法 JSON、未知 action、缺少参数均不得进入工具层 | `tests/test_actions.py` |
| `FR-LLM-01` | LLM 通过可注入接口接入，MockLLM 按脚本确定性返回动作 | 无 API key、无网络时可精确断言响应顺序与上下文 | `tests/test_llm.py` |
| `FR-LOOP-01` | AgentLoop 负责 context → LLM → parse → dispatch → observation → stop | `finish`、parse error、max steps 和各类终态均有稳定结果 | `tests/test_loop.py` |
| `FR-TOOL-01` | 工具由 registry 分发并返回结构化 `ToolResult` | 未注册工具安全失败；命令 exit code/stdout/stderr/timeout 可观察 | `tests/test_tools.py`、`tests/test_command_tool.py` |
| `FR-FILE-01` | 文件操作限制在规范化后的 workspace 边界内 | `..` 和工作区外路径被拒绝，合法读写成功 | `tests/test_file_tools.py` |
| `FR-GOV-01` | 所有工具与验证动作执行前经过 `allow/block/needs_approval` 判断 | 被 block 的 action 不调用 executor；验证动作不能成为旁路 | `tests/test_guardrails.py`、`tests/test_loop_tools_guardrails.py` |
| `FR-APR-01` | 风险动作使用可跨进程恢复的一次性审批状态机 | 未批准、拒绝、篡改、换参、重复消费均 fail closed | `tests/test_approval.py` |
| `FR-FBK-01` | 普通命令与客观验证在 action 协议层分离 | `run_command` 不产生 validation feedback；`run_validation` 才产生分类结果 | `tests/test_feedback_loop.py`、`tests/test_actions.py` |
| `FR-FBK-02` | 验证失败分类为稳定类别并以有界摘要进入模型上下文 | 八类结果可区分；完整证据留在日志；上下文包含长度、hash 和日志引用 | `tests/test_feedback.py`、`tests/test_feedback_loop.py` |
| `FR-FBK-03` | 写入或失败后必须取得新的客观 pass 才能完成 | 失败后或写入后直接 `finish` 被拒绝；通过验证后可 success | `tests/test_loop.py`、`tests/test_feedback_loop.py` |
| `FR-FBK-04` | 验证预算和重复失败熔断阻止无限循环 | 超预算返回 `validation_budget_exhausted`；重复失败返回 `repeated_validation_failure` | `tests/test_feedback_loop.py`、`tests/test_config.py` |
| `FR-MEM-01` | 项目事实持久化并按相关性、优先级和预算进入上下文 | 相关记忆可检索；不相关项在预算不足时省略；疑似密钥脱敏 | `tests/test_memory.py`、`tests/test_context_memory.py` |
| `FR-CFG-01` | 配置经校验后真实控制工具、治理和验证边界 | 非法正整数和未知值被拒绝；blocked pattern 与预算改变运行结果 | `tests/test_config.py` |
| `NFR-SEC-01` | 生产凭据存入 OS keyring，隐藏录入且不回显 | status/set/clear 不泄露明文；生产 CLI 不静默降级到明文文件 | `tests/test_credentials.py` |
| `NFR-OBS-01` | 每一步保存 action、治理、工具、feedback 和终态证据 | CLI 可生成结构化 run log，feedback evidence 可由 hash 与位置核对 | `tests/test_cli_run.py`、`tests/test_feedback_loop.py` |
| `DEMO-A6-01` | 确定性展示危险动作执行前拦截 | 最终状态为 `blocked`，危险命令未执行 | `tests/test_demo_guardrail.py`、`demos/dangerous_action.json` |
| `DEMO-A6-02` | 确定性展示失败反馈改变下一步动作 | 首次 validation 失败，修正后 pass，最终 success | `tests/test_demo_feedback.py`、`demos/feedback_correction.json` |
| `DEMO-MAIN-01` | 展示主要贡献“反馈控制面”的完整行为 | failure → feedback → correction → pass，并证明后续危险动作仍受治理 | `tests/test_demo_main_contribution.py`、`demos/governance_feedback_depth.json` |
| `DIST-01` | CLI、release 与 Docker 提供可复现分发路径 | 最终 tag/asset 与提交 commit 对齐；source 路径 `116 passed`；镜像可运行 help/version 和 MockLLM 反馈演示 | §10.3、`.github/workflows/ci.yml`、`.gitlab-ci.yml`、`Dockerfile`、`RELEASE_CHECKLIST.md` |

## 14. 风险、已决策事项与剩余边界

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
- 六维保持可运行最低实现，优先深化反馈闭环；治理护栏作为安全前置条件保持确定性测试覆盖。
- 每个 task 记录 `AGENT_LOG.md`。
- 提交前做凭据泄漏检查。

### 已决策事项

- 生产凭据使用 OS keyring；明文文件 backend 仅允许测试显式注入，不做生产 fallback。
- 分发采用 CLI-only + GitHub Release，并提供已实际构建验证的 Dockerfile/image 路径。
- 冷启动验证使用 Gemini，与主开发智能体类型不同；暴露的问题和修订记录见 `SPEC_PROCESS.md`。

### 剩余边界

- Guardrail 是确定性治理层，不等价于操作系统级安全沙箱，无法证明覆盖所有 shell 混淆形式。
- OpenAI-compatible adapter 的真实运行依赖供应商网络、凭据、模型可用性和响应兼容性；核心验收不依赖该路径。
- OS keyring 的可用性依赖目标系统；不可用时涉及凭据或签名的路径安全失败。
- Memory Store 是适合教学 harness 的轻量结构化存储，不面向大型多仓库语义检索。
