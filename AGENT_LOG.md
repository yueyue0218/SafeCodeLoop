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
