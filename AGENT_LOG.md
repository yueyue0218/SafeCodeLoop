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
