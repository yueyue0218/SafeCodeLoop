# AGENT_LOG

## 2026-08-09 20:30 · T2.1 / T2.2 · 项目骨架与 CLI 基础入口

触发的流程：

- 按 `PLAN.md` 进入实现阶段。
- 遵循 TDD：先写失败测试，再补最小实现。

关键上下文：

- 冷启动验证后已明确：
  - 构建后端：`setuptools`
  - 包名：`safecodeloop`
  - CLI 命令名：`safecodeloop`
  - 版本号来源：`src/safecodeloop/__init__.py` 的 `__version__`
  - 支持 `python -m safecodeloop.cli` 和 `python -m safecodeloop`

完成内容：

- 新增 `pyproject.toml`。
- 新增 `.gitignore`。
- 新增 `src/safecodeloop/__init__.py`。
- 新增 `src/safecodeloop/__main__.py`。
- 新增 `src/safecodeloop/cli.py`。
- 新增 `tests/test_smoke.py`。
- 新增 `tests/test_cli.py`。

TDD 记录：

- 第一次运行 `python -m pytest` 时，环境缺少 `pytest`，先安装 `pytest`。
- 安装后再次运行，得到预期红灯：`ModuleNotFoundError: No module named 'safecodeloop'`。
- 补充最小包结构和 CLI 后，测试仍有两项失败：`python -m safecodeloop.cli` 没有输出。
- 原因：`cli.py` 缺少 `if __name__ == "__main__"` 模块执行入口。
- 修复后运行 `python -m pytest`，结果：`4 passed in 0.35s`。

人工干预：

- 发现 `src/` 布局下，子进程执行 `python -m safecodeloop` 需要先安装项目。
- 执行 `python -m pip install -e .`，后续 CI/README 也应体现“先安装再测试/运行”的要求。

教训：

- 冷启动验证提出的 packaging/entry point 问题是有效的；如果没有提前修订，T2.1/T2.2 会出现实现口径不一致。
- CLI 模块入口需要同时支持函数调用和 `python -m` 执行，这是后续 release 可用性的基础。

## 2026-08-09 23:25 · T3.1 · Action Schema 与 Parser

触发的流程：

- 继续按 `PLAN.md` 执行 Phase 3。
- 遵循 TDD：先写 `tests/test_actions.py`，再实现 `src/safecodeloop/actions.py`。

完成内容：

- 新增 `tests/test_actions.py`。
- 新增 `src/safecodeloop/actions.py`。
- 定义 `Action` dataclass。
- 定义 `ActionParseError`。
- 实现 `parse_action(raw_response)`。
- 支持 action：
  - `list_files`
  - `read_file`
  - `write_file`
  - `run_command`
  - `remember`
  - `finish`
  - `request_approval`

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_actions.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.actions'`。
- 绿灯：补充 `actions.py` 后，`tests/test_actions.py` 结果为 `7 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `11 passed in 0.33s`。

人工干预：

- 选择使用 JSON 作为 LLM action 输出格式，符合 SPEC 中“解析 LLM 输出为 typed action”的要求。
- 当前 parser 保持最小实现：只做 action 类型、必要字段和 JSON 格式校验；路径规范化留到后续工具/护栏任务中处理。

教训：

- T3.1 的边界应保持清楚：parser 不执行动作，也不判断安全，只负责把 LLM 输出变成确定性结构或错误。

## 2026-08-11 00:10 · T3.2 · LLM Interface 与 MockLLM

触发的流程：

- 继续执行 `PLAN.md` 的 T3.2。
- 遵循 TDD：先写 `tests/test_llm.py`，再实现 `src/safecodeloop/llm.py`。

完成内容：

- 新增 `tests/test_llm.py`。
- 新增 `src/safecodeloop/llm.py`。
- 定义 `LLMResponse`。
- 定义 `LLMError`。
- 定义 `LLMClient` protocol。
- 实现 `MockLLM`：
  - 按脚本顺序返回响应。
  - 脚本耗尽时抛出清晰错误。
  - 记录调用历史。
  - 对 secret-like 内容做脱敏。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_llm.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.llm'`。
- 绿灯：补充 `llm.py` 后，`tests/test_llm.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `16 passed in 0.32s`。

人工干预：

- 当前只实现 mock LLM 和接口抽象，不接真实 LLM。
- 真实 LLM adapter 留到凭据管理和真实 provider 配置稳定后再做。
- 添加了基础 secret redaction，避免调用历史记录中出现 `OPENAI_API_KEY=...` 或 `sk-...` 形式内容。

教训：

- mock LLM 不是测试替身这么简单，它是后续主循环、护栏和反馈闭环所有确定性测试的基础。

## 2026-08-11 00:25 · T3.3 · 主 Agent Loop 骨架

触发的流程：

- 继续执行 `PLAN.md` 的 T3.3。
- 遵循 TDD：先写 `tests/test_loop.py`，再实现 `src/safecodeloop/loop.py`。

完成内容：

- 新增 `tests/test_loop.py`。
- 新增 `src/safecodeloop/loop.py`。
- 定义 `LoopStep`。
- 定义 `RunResult`。
- 实现 `AgentLoop.run(task)` 的最小闭环：
  - 调用 `LLMClient.generate`。
  - 使用 `parse_action` 解析 LLM 输出。
  - 处理 `finish`。
  - 将 parse error 转成 observation 并回灌下一轮。
  - 达到最大步数时返回 `max_steps`。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_loop.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.loop'`。
- 绿灯：补充 `loop.py` 后，`tests/test_loop.py` 结果为 `3 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `19 passed in 0.33s`。

人工干预：

- 当前主循环不执行工具，也不做 guardrail 判断。
- 对非 `finish` action 只记录 `action_parsed` observation，并提示 tools 尚未连接。
- 这样可以把 T3.3 限定在核心循环骨架，避免提前混入 T4 的工具与护栏职责。

教训：

- 主循环的第一版应保持小：先证明 LLM、parser、step log、parse-error feedback 和 max-step 停机能工作，再逐步接入工具和治理。

## 2026-08-11 00:40 · T4.1 · 工具注册表

触发的流程：

- 进入 `PLAN.md` 的 Phase 4。
- 遵循 TDD：先写 `tests/test_tools.py`，再实现 `src/safecodeloop/tools.py`。

完成内容：

- 新增 `tests/test_tools.py`。
- 新增 `src/safecodeloop/tools.py`。
- 定义 `ToolResult`。
- 定义 `ToolHandler`。
- 实现 `ToolRegistry.register(name, handler)`。
- 实现 `ToolRegistry.dispatch(action)`。
- 实现 `ToolResult.to_observation(tool_name)`。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_tools.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.tools'`。
- 绿灯：补充 `tools.py` 后，`tests/test_tools.py` 结果为 `4 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `23 passed in 0.42s`。

人工干预：

- T4.1 只实现注册和分发，不做真实文件/命令工具。
- 工具异常被转换为结构化 `ToolResult`，避免单个工具异常直接打断 harness。
- 工作区路径和命令安全边界留给 T4.2/T4.4。

教训：

- 工具系统需要先建立统一结果模型。后续文件工具、命令工具、主循环 observation 都可以复用 `ToolResult`，避免每个工具各自定义返回格式。

## 2026-08-11 00:55 · T4.2 · 文件工具

触发的流程：

- 继续执行 `PLAN.md` 的 T4.2。
- 遵循 TDD：先写 `tests/test_file_tools.py`，再扩展 `src/safecodeloop/tools.py`。

完成内容：

- 新增 `tests/test_file_tools.py`。
- 扩展 `src/safecodeloop/tools.py`。
- 新增 `Workspace` 路径边界辅助类。
- 新增 `create_file_tool_registry(workspace_root)`。
- 注册文件工具：
  - `list_files`
  - `read_file`
  - `write_file`

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_file_tools.py`，失败原因是 `ImportError: cannot import name 'create_file_tool_registry'`。
- 绿灯：补充文件工具后，`tests/test_file_tools.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `28 passed in 0.44s`。

人工干预：

- 路径解析统一通过 `Path.resolve()` 和 workspace 父路径检查完成。
- `list_files` 返回 POSIX 风格相对路径，避免 Windows 路径分隔符影响测试和日志。
- `write_file` 会自动创建父目录，但仅限 workspace 内。
- 读/写工作区外路径当前在文件工具层拒绝；后续 T4.4 仍会实现独立 guardrail，在执行前拦截。

教训：

- 文件工具本身需要边界检查，即使后续还有 guardrail。这样可以形成双层防护：工具层保证不会越界，guardrail 层保证危险动作不会进入执行器。

## 2026-08-11 01:10 · T4.3 · 命令工具

触发的流程：

- 继续执行 `PLAN.md` 的 T4.3。
- 遵循 TDD：先写 `tests/test_command_tool.py`，再扩展 `src/safecodeloop/tools.py`。

完成内容：

- 新增 `tests/test_command_tool.py`。
- 扩展 `src/safecodeloop/tools.py`。
- 新增 `create_command_tool_registry(workspace_root, timeout_seconds=10.0)`。
- 注册命令工具：
  - `run_command`

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_command_tool.py`，失败原因是 `ImportError: cannot import name 'create_command_tool_registry'`。
- 绿灯：补充命令工具后，`tests/test_command_tool.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `33 passed in 3.03s`。

人工干预：

- 命令执行使用 `subprocess.run`，在指定 workspace 中运行，并捕获 `stdout`、`stderr` 和退出码。
- 非 0 退出码不会抛异常，而是返回结构化 `ToolResult(ok=False)`，方便后续反馈分类器处理。
- 超时会返回 `command timed out` 和 `timeout_seconds`。
- 当前 T4.3 只实现命令执行器；危险命令拦截还没有做，留给 T4.4 Guardrail Engine。

教训：

- 命令工具必须把失败也当成可观察结果，而不是 Python 异常。这样后续 agent loop 才能把测试失败、命令失败、超时统一回灌给 LLM。

## 2026-08-11 01:30 · T4.4 · Guardrail Engine

触发的流程：

- 继续执行 `PLAN.md` 的 T4.4。
- 遵循 TDD：先写 `tests/test_guardrails.py`，再实现 `src/safecodeloop/guardrails.py`。

完成内容：

- 新增 `tests/test_guardrails.py`。
- 新增 `src/safecodeloop/guardrails.py`。
- 定义 `GuardrailDecision`，支持：
  - `allowed`
  - `blocked`
  - `needs_approval`
- 定义 `GuardrailEngine.check(action)`。
- 实现基础规则：
  - 拦截 `rm -rf /`。
  - 拦截数据库删除命令。
  - 拦截读写 workspace 外路径。
  - 安装依赖命令返回 `needs_approval`。
  - workspace 内安全读文件允许通过。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_guardrails.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.guardrails'`。
- 绿灯：补充 `guardrails.py` 后，`tests/test_guardrails.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `38 passed in 3.22s`。

人工干预：

- 当前规则采用保守的静态检查，不实际执行命令。
- 文件路径检查复用与工具层一致的 `Path.resolve()` 思路，保证 workspace 外路径在执行前就被拦截。
- 依赖安装不是直接禁止，而是进入 `needs_approval`，因为开发过程中安装依赖可能合理，但需要人工确认。

教训：

- Guardrail 应该独立于工具执行器存在。这样 T4.5 接入主循环时，可以先判断动作，再决定是否调用工具，形成真正的执行前治理。

## 2026-08-11 01:50 · T4.5 · 串联 Loop、Guardrails 与 Tools

触发的流程：

- 继续执行 `PLAN.md` 的 T4.5。
- 遵循 TDD：先写 `tests/test_loop_tools_guardrails.py`，再扩展 `src/safecodeloop/loop.py`。

完成内容：

- 新增 `tests/test_loop_tools_guardrails.py`。
- 扩展 `AgentLoop.__init__`，新增可选参数：
  - `tool_registry`
  - `guardrail_engine`
- 主循环中非 `finish` action 的处理顺序改为：
  - 先解析 action。
  - 如果配置了 guardrail，先执行 guardrail check。
  - `blocked` 和 `needs_approval` 会立即停止，不调用工具。
  - `allowed` 后再调用 tool registry。
  - tool result 转成 observation 并回灌下一轮 LLM。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_loop_tools_guardrails.py`，3 个测试失败，原因是 `AgentLoop.__init__()` 不支持 `tool_registry` 和 `guardrail_engine` 参数。
- 绿灯：补充主循环串联逻辑后，`tests/test_loop_tools_guardrails.py` 结果为 `3 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `41 passed in 3.25s`。

人工干预：

- 为了保持旧测试兼容，`tool_registry` 和 `guardrail_engine` 都是可选参数；不传时仍保留“tools are not connected yet”的旧行为。
- 对 `finish` action 不执行工具和护栏检查，直接结束。
- 对 `blocked` 和 `needs_approval` 都返回明确 run status，方便后续 CLI 用退出码和提示文本表达。

教训：

- T4.5 是从“零件可用”到“harness 可用”的关键连接点。工具本身不应该承担流程治理，主循环必须显式负责执行顺序。

## 2026-08-11 02:10 · T5.1 · Validator 和 Feedback Classifier

触发的流程：

- 进入 `PLAN.md` 的 Phase 5。
- 遵循 TDD：先写 `tests/test_feedback.py`，再实现 `src/safecodeloop/feedback.py`。

完成内容：

- 新增 `tests/test_feedback.py`。
- 新增 `src/safecodeloop/feedback.py`。
- 定义 `Feedback` 数据结构。
- 定义 `Validator.validate(result)`。
- 实现 `classify_tool_result(result)`，支持分类：
  - `pass`
  - `test_failure`
  - `syntax_error`
  - `timeout`
  - `command_failure`

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_feedback.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.feedback'`。
- 绿灯：补充反馈分类器后，`tests/test_feedback.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `46 passed in 3.16s`。

人工干预：

- T5.1 只做分类，不直接修改主循环。
- 输入复用 T4.3 的 `ToolResult`，避免引入新的命令执行结果格式。
- `Feedback.to_observation()` 预留给 T5.2 使用，后续可以直接把结构化反馈回灌给 LLM。

教训：

- 反馈分类器把“命令输出文本”变成“agent 可理解的错误类型”。这一步是反馈闭环的前置条件，否则 LLM 只能看到一大段原始日志，难以稳定修正。

## 2026-08-11 02:30 · T5.2 · 反馈回灌进主循环

触发的流程：

- 继续执行 `PLAN.md` 的 T5.2。
- 遵循 TDD：先写 `tests/test_feedback_loop.py`，再扩展 `src/safecodeloop/loop.py`。

完成内容：

- 新增 `tests/test_feedback_loop.py`。
- 扩展 `AgentLoop.__init__`，新增可选参数 `validator`。
- 当 `run_command` action 执行完成且配置了 `validator` 时：
  - 将 `ToolResult` 交给 `Validator.validate()`。
  - 把 `Feedback.to_observation()` 的结构化结果作为 step observation。
  - 将 feedback observation 回灌给下一轮 LLM。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_feedback_loop.py`，失败原因是 `AgentLoop.__init__()` 不支持 `validator` 参数。
- 绿灯：补充反馈回灌逻辑后，`tests/test_feedback_loop.py` 结果为 `1 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `47 passed in 3.20s`。

人工干预：

- `validator` 是可选参数，不传时保持 T4.5 的旧行为。
- 只对 `run_command` 结果做反馈分类，避免把 `write_file`、`read_file` 等文件工具误判成命令反馈。
- 测试中模拟第一次 pytest 失败、第二次通过，证明 mock LLM 能在下一轮收到 `test_failure` feedback 后写出修正。

教训：

- 反馈回灌不能只把原始 stdout/stderr 塞回上下文；结构化的 `feedback_kind` 能让后续 demo 更稳定，也更容易向助教解释“自我修正机制”到底在哪里。

## 2026-08-11 02:50 · T5.3 · Memory Store

触发的流程：

- 继续执行 `PLAN.md` 的 T5.3。
- 遵循 TDD：先写 `tests/test_memory.py`，再实现 `src/safecodeloop/memory.py`。

完成内容：

- 新增 `tests/test_memory.py`。
- 新增 `src/safecodeloop/memory.py`。
- 定义 `MemoryItem`。
- 定义 `MemoryStore`，支持：
  - `remember(content, kind, priority)`
  - `all()`
  - `retrieve(query, limit)`
- 记忆以 JSON 文件持久化。
- 记忆内容写入前复用 `redact_secrets()` 做密钥脱敏。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_memory.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.memory'`。
- 绿灯：补充 Memory Store 后，`tests/test_memory.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `52 passed in 3.27s`。

人工干预：

- 检索策略采用最小可解释规则：先按 query 命中词数量，再按最近写入，再按 priority 排序。
- 对疑似密钥不直接拒绝，而是脱敏后保存；这样可以保留“用户提到过凭据配置问题”这类事实，同时不泄露明文。
- 空 JSON 文件按空记忆处理，避免首次创建/异常中断后无法启动。

教训：

- Memory 的价值不是保存一切，而是保存可复用的项目事实。T5.3 先把持久化和脱敏边界定住，T5.4 再考虑如何把相关记忆放进 LLM 上下文。

## 2026-08-11 03:10 · T5.4 · Memory 加入上下文组装

触发的流程：

- 继续执行 `PLAN.md` 的 T5.4。
- 遵循 TDD：先写 `tests/test_context_memory.py`，再扩展 `src/safecodeloop/loop.py`。

完成内容：

- 新增 `tests/test_context_memory.py`。
- 扩展 `AgentLoop.__init__`，新增可选参数：
  - `memory_store`
  - `memory_context_budget`
- 在 run 开始时根据 task 检索相关 memory。
- 如果存在相关 memory，则在第一轮 LLM 调用前加入 `memory_context` system message。
- 如果没有相关 memory，则不额外添加 system message。
- 使用字符预算限制 memory context，避免上下文过长。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_context_memory.py`，3 个测试失败，原因是 `AgentLoop.__init__()` 不支持 `memory_store` 参数。
- 绿灯：补充 memory context 组装后，`tests/test_context_memory.py` 结果为 `3 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `55 passed in 3.24s`。

人工干预：

- `memory_store` 是可选参数，不传时保持原有主循环行为。
- memory context 使用简单文本格式 `memory_context:`，方便 mock LLM 和后续日志验证。
- 初始实现只放 memory content，不放 id/timestamp，避免上下文噪音。

教训：

- 记忆接入不能无脑塞进所有历史。即使是最小实现，也需要相关性检索和预算控制，否则上下文会污染 LLM 判断。

## 2026-08-11 03:30 · T5.5 · Config Loader

触发的流程：

- 继续执行 `PLAN.md` 的 T5.5。
- 遵循 TDD：先写 `tests/test_config.py`，再实现 `src/safecodeloop/config.py` 并扩展 guardrail。

完成内容：

- 新增 `tests/test_config.py`。
- 新增 `src/safecodeloop/config.py`。
- 新增 `safecodeloop.config.example.json`。
- 定义 `SafeCodeLoopConfig`。
- 定义 `ConfigError`。
- 实现 `load_config(path)`，支持：
  - 默认配置。
  - JSON 配置覆盖默认值。
  - unknown field 拒绝。
  - 非法 `maxSteps` 拒绝。
  - 非整数 `maxSteps` 拒绝。
  - list/string 字段校验。
- 扩展 `GuardrailEngine`，支持配置传入 `blocked_command_patterns`。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_config.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.config'`。
- 绿灯：补充配置加载器和可配置 guardrail 后，`tests/test_config.py` 结果为 `6 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `61 passed in 3.24s`。

人工干预：

- 配置文件字段使用 SPEC 中的 camelCase，例如 `maxSteps`、`memoryPath`、`blockedCommandPatterns`。
- Python 内部 dataclass 使用 snake_case，加载时做字段映射。
- 不存在或空配置文件返回默认配置，方便 CLI 初次运行。

教训：

- 配置系统不能只是读取 JSON；它必须校验边界，并且真的影响运行行为。T5.5 通过配置 blocked pattern 改变 guardrail 决策，证明配置不是摆设。

## 2026-08-11 03:50 · T5.6 · 凭据命令

触发的流程：

- 继续执行 `PLAN.md` 的 T5.6。
- 遵循 TDD：先写 `tests/test_credentials.py`，再实现 `src/safecodeloop/credentials.py` 并扩展 CLI。

完成内容：

- 新增 `tests/test_credentials.py`。
- 新增 `src/safecodeloop/credentials.py`。
- 扩展 `src/safecodeloop/cli.py` 的 `key` 子命令，支持：
  - `key status [provider]`
  - `key set <provider> --value <key>`
  - `key clear [provider]`
- 凭据存储默认路径为用户目录下 `.safecodeloop/credentials.json`。
- 测试中通过 `SAFECODELOOP_CREDENTIALS_PATH` 指向临时文件，避免污染真实用户配置。
- 状态输出只显示 masked key，不显示明文。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_credentials.py`，失败原因是 `ModuleNotFoundError: No module named 'safecodeloop.credentials'`。
- 绿灯：补充凭据模块和 CLI key 子命令后，`tests/test_credentials.py` 结果为 `5 passed`。
- CLI 验证：`python -m safecodeloop.cli key status` 输出未配置提示，退出码为 0。
- 回归：运行 `python -m pytest`，全量结果为 `66 passed in 3.36s`。

人工干预：

- 当前实现是本地 JSON fallback，不是 OS keyring。
- CLI 的 `key set` 不打印明文 key，只输出 provider 已 stored。
- 测试中使用假 key `sk-test-secret`，并断言状态输出不会包含完整明文。

教训：

- 凭据功能即使是 fallback 实现，也要先把“状态不泄露明文”和“测试不污染真实配置”做稳。后续 README 必须明确说明 JSON fallback 的明文风险。

## 2026-08-12 00:10 · T6.1 · run CLI

触发的流程：

- 进入 `PLAN.md` 的 Phase 6。
- 遵循 TDD：先写 `tests/test_cli_run.py`，再扩展 `src/safecodeloop/cli.py` 和 `src/safecodeloop/tools.py`。

完成内容：

- 新增 `tests/test_cli_run.py`。
- 扩展 `run` 子命令，支持：
  - `--mock-script`
  - `--workspace`
  - `--config`
  - `--log`
  - task 参数
- CLI run 会组装：
  - `MockLLM`
  - `AgentLoop`
  - `GuardrailEngine`
  - `Validator`
  - `MemoryStore`
  - 组合工具注册表
- 新增 `create_agent_tool_registry()`，同时注册文件工具和命令工具。
- 支持 JSON run log 输出。
- 被 guardrail 拦截时返回非 0。

TDD 记录：

- 红灯：首次运行 `python -m pytest tests/test_cli_run.py`，3 个测试失败，原因是 `run` 子命令不支持 `--mock-script`、`--workspace`、`--log` 和 task 参数。
- 绿灯：补充 run CLI 后，`tests/test_cli_run.py` 结果为 `3 passed`。
- CLI 冒烟：`python -m safecodeloop.cli run --mock-script <script> --workspace <tmp> smoke` 输出 `status: success`，退出码为 0。
- 回归：运行 `python -m pytest`，全量结果为 `69 passed in 3.68s`。

人工干预：

- mock script 支持两种形式：JSON list，或包含 `responses` 字段的 JSON object。
- list 内元素既可以是 action object，也可以是原始 JSON 字符串。
- run log 中记录 status、final message、每一步 LLM 响应、action 和 observation。

教训：

- 到 T6.1 为止，项目第一次具备了真正可运行的 CLI harness。前面的 loop、tools、guardrail、feedback、memory、config 都通过这个入口汇合，后续 demo 可以基于它稳定构建。
