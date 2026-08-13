# SafeCodeLoop 实现计划（PLAN）

> 交付路线：CLI-only + release 链接。WebUI 是可选项，不进入 P0。

## 1. 锁定技术路线

- 语言：Python 3.11+
- CLI：`argparse`
- 测试：`pytest`
- 构建后端：`setuptools`
- Python 包名：`safecodeloop`
- CLI 命令名：`safecodeloop`
- 版本号唯一来源：`src/safecodeloop/__init__.py` 的 `__version__`
- 模块执行方式：同时支持 `python -m safecodeloop.cli` 和 `python -m safecodeloop`
- 分发：Dockerfile + GitHub/NJU Git release
- LLM：mock LLM 必做，真实 LLM adapter 可选
- 一键测试命令：`python -m pytest`
- CI：`.gitlab-ci.yml`，必须包含 `unit-test` job

## 2. 分支 / Worktree / PR 策略

- `feature/spec-plan-process`：只放规约、计划和过程文档。
- `feature/core-loop`：LLM 抽象、action parser、主循环。
- `feature/tools-guardrails`：工具系统和治理护栏。
- `feature/feedback-memory-config`：反馈、记忆、配置、凭据。
- `feature/cli-demos`：CLI 和机制演示。
- `feature/ci-release-docs`：CI、Docker、README、release、submission。

每个 PR 需要写明：

- 哪个 subagent 完成。
- 人工改了什么。
- 跑了哪些测试。
- 是否符合 SPEC / PLAN。

## 3. Phase 1：实现前文档

### T1.1 完成 `SPEC.md`

目标：冻结项目范围。

涉及文件：

- `SPEC.md`

验证步骤：

- 检查是否覆盖作业要求的 SPEC 十项内容。
- 检查 A 类额外要求“领域与机制设计”是否完整。
- 检查 WebUI 是否只作为可选项。

依赖：无。

状态：已完成初版。

### T1.2 完成 `PLAN.md`

目标：把 SPEC 拆成可执行 task。

涉及文件：

- `PLAN.md`

验证步骤：

- 每个实现 task 都有失败测试。
- 每个 task 都有涉及文件和验证命令。
- release 和 submission 任务被纳入计划。

依赖：T1.1。

状态：进行中。

### T1.3 完成 `SPEC_PROCESS.md`

目标：记录与 AI 协作生成规约的过程。

涉及文件：

- `SPEC_PROCESS.md`

验证步骤：

- 至少记录 3 轮关键迭代。
- 记录采纳和推翻的 AI 建议。
- 记录依据课程补充说明改为 CLI-only + release 的原因。

依赖：T1.1、T1.2。

状态：已完成初版。

### T1.4 冷启动验证

目标：用另一个不同类型 agent 检查 `SPEC.md + PLAN.md` 是否清楚。

涉及文件：

- `SPEC_PROCESS.md`
- 可能修改 `SPEC.md`
- 可能修改 `PLAN.md`

执行方式：

- 只给第二个 agent `SPEC.md` 和 `PLAN.md`。
- 要求它尝试 1-2 个早期 task。
- 如果不清楚，必须停下提问，不许猜。

验证步骤：

- 记录它问了什么。
- 记录它误解了什么。
- 记录因此修改了哪些 SPEC / PLAN 内容。

依赖：T1.3。

状态：待做。

## 4. Phase 2：项目骨架与测试框架

### T2.1 创建 Python 包结构

状态：已完成。

目标：建立最小工程骨架，不实现核心逻辑。

涉及文件：

- `pyproject.toml`
- `src/safecodeloop/__init__.py`
- `src/safecodeloop/__main__.py`
- `src/safecodeloop/cli.py`
- `tests/test_smoke.py`
- `.gitignore`

先写失败测试：

- `test_package_imports`：期望 `import safecodeloop` 成功。

实现要点：

- 配置 pytest。
- `pyproject.toml` 使用 `setuptools.build_meta`。
- `project.name` 使用 `safecodeloop`。
- `src/safecodeloop/__init__.py` 暴露 `__version__`，初始版本为 `0.1.0`。
- `src/safecodeloop/__main__.py` 调用 `cli.main()`，支持 `python -m safecodeloop`。
- 暂不实现 agent 逻辑。

验证命令：

```bash
python -m pytest
```

实际验证：

- 红灯：首次运行 `python -m pytest` 时，`ModuleNotFoundError: No module named 'safecodeloop'`。
- 绿灯：补充包结构并执行 `python -m pip install -e .` 后，`python -m pytest` 结果为 `4 passed`。

依赖：T1.4。

可并行：否。

### T2.2 添加 CLI 基础入口

状态：已完成。

目标：CLI 可以显示 help 和 version。

涉及文件：

- `src/safecodeloop/cli.py`
- `tests/test_cli.py`

先写失败测试：

- `test_cli_help_exits_zero`
- `test_cli_version_exits_zero`
- `test_python_m_safecodeloop_exits_zero`

实现要点：

- 使用 `argparse`。
- 预留 `run`、`key`、`demo` 子命令。
- 在 `pyproject.toml` 的 `[project.scripts]` 中注册 `safecodeloop = "safecodeloop.cli:main"`。
- `--version` 输出 `safecodeloop 0.1.0`，版本号从 `safecodeloop.__version__` 读取。

验证命令：

```bash
python -m pytest tests/test_cli.py
python -m safecodeloop.cli --help
python -m safecodeloop --help
```

实际验证：

- 红灯：`python -m safecodeloop.cli --help` 初次能退出但没有输出，因为 `cli.py` 缺少模块执行入口。
- 绿灯：补充 `if __name__ == "__main__": raise SystemExit(main())` 后，`tests/test_cli.py` 全部通过。

依赖：T2.1。

可并行：是。

## 5. Phase 3：核心循环

### T3.1 实现 Action Schema 与 Parser

状态：已完成。

目标：把 LLM 输出解析成结构化 action。

涉及文件：

- `src/safecodeloop/actions.py`
- `tests/test_actions.py`

先写失败测试：

- 合法 JSON action 可解析。
- 未知 action type 被拒绝。
- 缺少必要字段被拒绝。

实现要点：

- 支持 `list_files`、`read_file`、`write_file`、`run_command`、`remember`、`finish`、`request_approval`。
- 后续将验证命令拆分为显式 `run_validation`，避免把普通命令成功误记为测试通过；该动作复用受控命令工具并继续经过相同 guardrail。

验证命令：

```bash
python -m pytest tests/test_actions.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_actions.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.actions'`。
- 绿灯：新增 `src/safecodeloop/actions.py` 后，`tests/test_actions.py` 结果为 `7 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `11 passed`。

依赖：T2.1。

可并行：是。

### T3.2 实现 LLM Interface 与 MockLLM

状态：已完成。

目标：让测试不依赖真实 LLM。

涉及文件：

- `src/safecodeloop/llm.py`
- `tests/test_llm.py`

先写失败测试：

- `MockLLM` 按顺序返回脚本响应。
- 脚本用完时返回清晰错误。
- 调用历史记录上下文，但不记录密钥。

验证命令：

```bash
python -m pytest tests/test_llm.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_llm.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.llm'`。
- 绿灯：新增 `src/safecodeloop/llm.py` 后，`tests/test_llm.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `16 passed`。

依赖：T2.1。

可并行：是。

后续增强：新增底层 OpenAI-compatible chat completion adapter，不使用高层 agent runner；HTTP 请求、响应和错误通过 fake transport 离线测试，真实 key 从 OS keyring 读取。

### T3.3 实现主循环骨架

状态：已完成。

目标：完成 `LLM -> parse action -> finish/max_steps/parse_error` 的最小闭环。

涉及文件：

- `src/safecodeloop/loop.py`
- `tests/test_loop.py`

先写失败测试：

- mock LLM 返回 `finish` 后状态为 `success`。
- 非法 LLM 输出变成 parse-error observation。
- 超过最大步数返回 `max_steps`。

验证命令：

```bash
python -m pytest tests/test_loop.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_loop.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.loop'`。
- 绿灯：新增 `src/safecodeloop/loop.py` 后，`tests/test_loop.py` 结果为 `3 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `19 passed`。

依赖：T3.1、T3.2。

可并行：否。

## 6. Phase 4：工具系统与治理护栏

### T4.1 实现工具注册表

状态：已完成。

目标：根据 action 调度工具。

涉及文件：

- `src/safecodeloop/tools.py`
- `tests/test_tools.py`

先写失败测试：

- 未注册工具返回结构化错误。
- 注册工具能收到规范化参数。
- 工具结果能转成 observation。

验证命令：

```bash
python -m pytest tests/test_tools.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_tools.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.tools'`。
- 绿灯：新增 `src/safecodeloop/tools.py` 后，`tests/test_tools.py` 结果为 `4 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `23 passed`。

依赖：T3.1。

可并行：是。

### T4.2 实现文件工具

状态：已完成。

目标：支持工作区内列文件、读文件、写文件。

涉及文件：

- `src/safecodeloop/tools.py`
- `tests/test_file_tools.py`

先写失败测试：

- list 返回相对路径。
- read 返回文件内容。
- write 可以创建父目录。
- 写入工作区外被拒绝。

验证命令：

```bash
python -m pytest tests/test_file_tools.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_file_tools.py` 时，`ImportError: cannot import name 'create_file_tool_registry'`。
- 绿灯：扩展 `src/safecodeloop/tools.py` 后，`tests/test_file_tools.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `28 passed`。

依赖：T4.1。

可并行：否。

### T4.3 实现命令工具

状态：已完成。

目标：运行受控命令并捕获输出。

涉及文件：

- `src/safecodeloop/tools.py`
- `tests/test_command_tool.py`

先写失败测试：

- 允许的命令能运行。
- stdout/stderr/exit code 被记录。
- timeout 返回结构化结果。
- 命令在 workspace 中运行。

验证命令：

```bash
python -m pytest tests/test_command_tool.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_command_tool.py` 时，`ImportError: cannot import name 'create_command_tool_registry'`。
- 绿灯：扩展 `src/safecodeloop/tools.py` 后，`tests/test_command_tool.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `33 passed`。

依赖：T4.1。

可并行：是。

### T4.4 实现 Guardrail Engine

状态：已完成。

目标：执行前判断 action 是允许、拦截还是需要审批。

涉及文件：

- `src/safecodeloop/guardrails.py`
- `tests/test_guardrails.py`

先写失败测试：

- `rm -rf /` 被拦截。
- 删除数据库命令被拦截。
- 写入工作区外路径被拦截。
- 安装依赖命令返回 `needs_approval`。
- 工作区内安全读取被允许。

验证命令：

```bash
python -m pytest tests/test_guardrails.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_guardrails.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.guardrails'`。
- 绿灯：新增 `src/safecodeloop/guardrails.py` 后，`tests/test_guardrails.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `38 passed`。

依赖：T3.1。

可并行：是。

### T4.5 串联 Loop、Guardrails 与 Tools

状态：已完成。

目标：主循环中先护栏检查，再工具执行。

涉及文件：

- `src/safecodeloop/loop.py`
- `tests/test_loop_tools_guardrails.py`

先写失败测试：

- 被 block 的 action 不调用 executor。
- 被允许的写文件 action 会修改 workspace 文件。
- `needs_approval` 会让 run 停止并返回对应状态。

验证命令：

```bash
python -m pytest tests/test_loop_tools_guardrails.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_loop_tools_guardrails.py` 时，3 个测试失败，原因是 `AgentLoop.__init__()` 不支持 `tool_registry` 和 `guardrail_engine` 参数。
- 绿灯：扩展 `src/safecodeloop/loop.py` 后，`tests/test_loop_tools_guardrails.py` 结果为 `3 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `41 passed`。

依赖：T3.3、T4.2、T4.3、T4.4。

可并行：否。

后续增强：将 `needs_approval` 从终止状态扩展为可跨进程恢复的一次性审批状态机；审批通过 HMAC-SHA256 绑定原始 action，并用 mock LLM 与 CLI 测试批准、拒绝、篡改和重复消费。

## 7. Phase 5：反馈、记忆、配置、凭据

### T5.1 实现 Validator 和 Feedback Classifier

状态：已完成。

目标：把测试结果转换成结构化反馈。

涉及文件：

- `src/safecodeloop/feedback.py`
- `tests/test_feedback.py`

先写失败测试：

- exit code 0 分类为 `pass`。
- pytest 失败文本分类为 `test_failure`。
- SyntaxError 分类为 `syntax_error`。
- timeout 分类为 `timeout`。

验证命令：

```bash
python -m pytest tests/test_feedback.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_feedback.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.feedback'`。
- 绿灯：新增 `src/safecodeloop/feedback.py` 后，`tests/test_feedback.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `46 passed`。

依赖：T4.3。

可并行：是。

### T5.2 将反馈回灌进主循环

状态：已完成。

目标：展示 agent 根据测试反馈修正下一步动作。

涉及文件：

- `src/safecodeloop/loop.py`
- `tests/test_feedback_loop.py`

先写失败测试：

- mock LLM 第一次写错代码。
- validator 返回失败。
- 下一轮 mock LLM 收到反馈并写出修正。
- 最终状态为 success。

验证命令：

```bash
python -m pytest tests/test_feedback_loop.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_feedback_loop.py` 时，测试失败，原因是 `AgentLoop.__init__()` 不支持 `validator` 参数。
- 绿灯：扩展 `src/safecodeloop/loop.py` 后，`tests/test_feedback_loop.py` 结果为 `1 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `47 passed`。

依赖：T4.5、T5.1。

可并行：否。

### T5.3 实现 Memory Store

状态：已完成。

目标：保存和检索项目事实，不保存密钥。

涉及文件：

- `src/safecodeloop/memory.py`
- `tests/test_memory.py`

先写失败测试：

- memory item 能持久化到 JSON。
- 检索返回最近 / 高优先级记录。
- 疑似密钥内容会被拒绝或脱敏。

验证命令：

```bash
python -m pytest tests/test_memory.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_memory.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.memory'`。
- 绿灯：新增 `src/safecodeloop/memory.py` 后，`tests/test_memory.py` 结果为 `5 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `52 passed`。

依赖：T2.1。

可并行：是。

### T5.4 将 Memory 加入上下文组装

状态：已完成。

目标：相关记忆进入 LLM 上下文。

涉及文件：

- `src/safecodeloop/loop.py`
- `tests/test_context_memory.py`

先写失败测试：

- 相关 memory 出现在 mock LLM call context。
- 上下文预算小时，不相关 memory 被省略。

验证命令：

```bash
python -m pytest tests/test_context_memory.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_context_memory.py` 时，3 个测试失败，原因是 `AgentLoop.__init__()` 不支持 `memory_store` 参数。
- 绿灯：扩展 `src/safecodeloop/loop.py` 后，`tests/test_context_memory.py` 结果为 `3 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `55 passed`。

依赖：T5.3、T3.3。

可并行：否。

### T5.5 实现 Config Loader

状态：已完成。

目标：从配置文件加载运行规则。

涉及文件：

- `src/safecodeloop/config.py`
- `tests/test_config.py`
- `safecodeloop.config.example.json`

先写失败测试：

- 默认配置可加载。
- 非法 maxSteps 被拒绝。
- 配置中的 blocked pattern 会影响 guardrail。

验证命令：

```bash
python -m pytest tests/test_config.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_config.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.config'`。
- 绿灯：新增 `src/safecodeloop/config.py`、示例配置，并扩展 `GuardrailEngine` 后，`tests/test_config.py` 结果为 `6 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `61 passed`。

依赖：T4.4。

可并行：是。

### T5.6 实现凭据命令

状态：已完成。

目标：支持 key 设置、状态、清除，并避免明文泄露。

涉及文件：

- `src/safecodeloop/credentials.py`
- `src/safecodeloop/cli.py`
- `tests/test_credentials.py`

先写失败测试：

- status 不显示明文 key。
- clear 后无法读取 key。
- 缺 key 时给出配置提示。

实现要点：

- 如果 OS keyring 来不及实现，可使用环境变量 / `.env` fallback，但必须文档化风险。
- 测试中不能出现真实 key。

验证命令：

```bash
python -m pytest tests/test_credentials.py
python -m safecodeloop.cli key status
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_credentials.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.credentials'`。
- 绿灯：新增 `src/safecodeloop/credentials.py` 并扩展 `src/safecodeloop/cli.py` 后，`tests/test_credentials.py` 结果为 `5 passed`。
- CLI 验证：`python -m safecodeloop.cli key status` 输出未配置提示，退出码为 0，未显示明文 key。

后续安全强化：在 `feat/secure-credential-storage` 中将生产默认存储升级为 OS keyring，并将 CLI 改为隐藏输入；临时文件 backend 仅通过依赖注入用于测试。
- 回归：运行 `python -m pytest`，全量结果为 `66 passed`。

依赖：T3.2、T2.2。

可并行：是。

## 8. Phase 6：CLI 与机制演示

### T6.1 实现 `run` CLI

状态：已完成。

目标：通过命令行运行 harness。

涉及文件：

- `src/safecodeloop/cli.py`
- `tests/test_cli_run.py`

先写失败测试：

- `run --mock-script demo.json --workspace tmp "task"` 成功时返回 0。
- `--log` 能写出运行日志。
- 被拦截 action 返回非 0 并显示原因。

验证命令：

```bash
python -m pytest tests/test_cli_run.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_cli_run.py` 时，3 个测试失败，原因是 `run` 子命令不支持 `--mock-script`、`--workspace`、`--log` 和 task 参数。
- 绿灯：扩展 `src/safecodeloop/cli.py` 和 `src/safecodeloop/tools.py` 后，`tests/test_cli_run.py` 结果为 `3 passed`。
- CLI 冒烟：`python -m safecodeloop.cli run --mock-script <script> --workspace <tmp> smoke` 输出 `status: success`，退出码为 0。
- 回归：运行 `python -m pytest`，全量结果为 `69 passed`。

依赖：T4.5、T5.2、T5.5。

可并行：否。

### T6.2 Demo 1：危险动作拦截

状态：已完成。

目标：满足 A.6 机制演示第一项。

涉及文件：

- `demos/dangerous_action.json`
- `tests/test_demo_guardrail.py`

先写失败测试：

- mock LLM 试图执行危险命令，guardrail 拦截。

验证命令：

```bash
python -m pytest tests/test_demo_guardrail.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_demo_guardrail.py` 时，测试失败，原因是 `demos/dangerous_action.json` 尚不存在，CLI run 无法生成 log。
- 绿灯：新增 `demos/dangerous_action.json` 后，`tests/test_demo_guardrail.py` 结果为 `1 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `70 passed`。

依赖：T6.1。

可并行：是。

### T6.3 Demo 2：反馈闭环自我修正

状态：已完成。

目标：满足 A.6 机制演示第二项。

涉及文件：

- `demos/feedback_correction.json`
- `tests/test_demo_feedback.py`

先写失败测试：

- demo 中第一次校验失败，反馈回灌后第二次通过。

验证命令：

```bash
python -m pytest tests/test_demo_feedback.py
```

实际验证：

- 红灯：`tests/test_demo_feedback.py` 在 demo 文件不存在时失败。
- 绿灯：新增 `demos/feedback_correction.json` 后，`tests/test_demo_feedback.py` 结果为 `1 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `72 passed`。

实现说明：

- demo 先写入错误实现和测试，运行 `python -m pytest` 得到 `test_failure`。
- mock LLM 随后写入修正版实现，再运行 `python -m pytest` 得到 `pass`。
- 最终 `finish`，CLI 返回 `success`。

依赖：T6.1。

可并行：是。

### T6.4 Demo 3：主要贡献机制

状态：已完成。

目标：展示治理护栏 + 反馈闭环的组合深度。

涉及文件：

- `demos/governance_feedback_depth.json`
- `tests/test_demo_main_contribution.py`

先写失败测试：

- run 中同时出现 allow、block 或 needs_approval、feedback 分类和最终状态。

验证命令：

```bash
python -m pytest tests/test_demo_main_contribution.py
```

实际验证：

- 红灯：`tests/test_demo_main_contribution.py` 在 demo 文件不存在时失败。
- 绿灯：新增并修正 `demos/governance_feedback_depth.json` 后，`tests/test_demo_main_contribution.py` 结果为 `1 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `72 passed`。

实现说明：

- T6.4 依赖 T6.3 的完整反馈闭环，不只停留在“失败反馈”。
- demo 先完成：错误实现 -> pytest `test_failure` -> 修正实现 -> pytest `pass`。
- 然后尝试执行 `rm -rf /`，Guardrail 在执行前拦截，最终状态为 `blocked`。
- 因为 `blocked` / `needs_approval` 的安全语义是立即停机，所以综合 demo 把危险动作放在反馈闭环成功之后。

依赖：T6.2、T6.3。

可并行：否。

## 9. Phase 7：CI、分发、Release

### T7.1 添加 `.gitlab-ci.yml`

状态：已完成本地配置；远程 CI pass 待平台运行确认。

目标：满足课程 CI 要求。

涉及文件：

- `.gitlab-ci.yml`

验证标准：

- 必须包含名为 `unit-test` 的 job。
- `unit-test` 执行 `python -m pytest`。

验证命令：

```bash
python -m pytest
```

实际验证：

- 新增 `.gitlab-ci.yml`，包含名为 `unit-test` 的 job。
- CI job 使用 `python:3.11` 镜像。
- CI 安装当前包和 pytest 后执行 `python -m pytest`。
- 本地回归：`python -m pytest` 结果为 `72 passed`。

GitHub 托管适配：

- 新增 `.github/workflows/ci.yml`，保留现有 `.gitlab-ci.yml`。
- pull request 和 `main` push 触发 `unit-test` job。
- job 运行全量测试、构建 wheel，并在隔离虚拟环境安装 wheel 后执行 CLI smoke test。
- 本地构建与安装验证完成后，由 GitHub Actions 的实际运行结果确认远程状态。

依赖：T2.1。

可并行：是。

### T7.2 添加 Dockerfile

状态：已完成文件；Docker CLI 已验证，容器 build 因 Docker Hub 网络不可达待重试。

目标：提供可分发容器构建方式。

涉及文件：

- `Dockerfile`
- `.dockerignore`

验证命令：

```bash
docker build -t safecodeloop .
docker run --rm safecodeloop --help
```

实际验证：

- 新增 `Dockerfile`，基于 `python:3.11-slim` 安装当前包。
- 新增 `.dockerignore`，排除 `.git`、缓存、虚拟环境、`.env`、本地 `.safecodeloop` 和 release 产物。
- 本地回归：`python -m pytest` 结果为 `72 passed`。
- Docker CLI 可用：Docker version 29.7.2。
- `docker build -t safecodeloop .` 已执行到拉取基础镜像阶段。
- build 未完成原因：当前网络无法连接 Docker Hub `auth.docker.io` / `registry-1.docker.io:443`，未声称容器 build 已通过。

依赖：T2.2。

可并行：是。

### T7.3 准备 Release 包

目标：生成可上传 release 的源码 / 构建产物。

涉及文件：

- `scripts/package_release.ps1`
- `RELEASE_CHECKLIST.md`

实现要点：

- 包含源码、文档、测试、Dockerfile、README。
- 排除 `.env`、`.git`、缓存、本地日志。

验证命令：

```powershell
.\scripts\package_release.ps1
```

依赖：T7.2、T8.1。

可并行：否。

### T7.4 创建仓库 Release

状态：已完成。

目标：生成 `submission.jsonc` 需要填写的 release 链接。

涉及内容：

- GitHub 或 NJU Git release 页面。
- `submission.jsonc`

实现要点：

- CLI-only 路线下 `is_deployed=false`。
- `deploy_release_url` 填 release 链接。

验证步骤：

- 打开 release 链接确认可访问。
- 确认 `submission.jsonc` 指向真实仓库和 release。

实际验证：

- GitHub Release 已创建：`https://github.com/yueyue0218/SafeCodeLoop/releases/tag/v0.1.0`。
- release asset 上传 `SafeCodeLoop-0.1.0.zip`。
- `submission.jsonc` 已填写真实 release 链接。

依赖：T7.3。

可并行：否。

## 10. Phase 8：最终文档

### T8.1 编写 README

状态：已完成。

目标：让复现者能从零运行项目。

涉及文件：

- `README.md`

必须包含：

- 项目简介。
- 安装。
- CLI 使用。
- mock LLM demo。
- 测试命令。
- Docker build/run。
- key 配置和风险说明。
- 安全边界。
- 目录结构。
- release 链接。
- 已知限制。

验证步骤：

- 按 README 在干净目录跑一遍。

实际验证：

- 新增 `README.md`。
- 覆盖项目简介、安装、CLI 使用、三个 mock demo、测试命令、Docker build/run、key 配置风险、安全边界、目录结构、release 包和已知限制。
- 本地验证 `python -m pytest`：`72 passed`。
- 本地验证 `python -m safecodeloop --help` 和 `safecodeloop --help` 均可用。
- README 如实记录 Docker CLI 已验证可用，但 Docker Hub 网络不可达导致 build 未完成。

依赖：T6.1、T7.2。

可并行：是。

### T8.2 维护 `AGENT_LOG.md`

状态：已完成最终整理。

目标：记录 AI 协作全过程。

涉及文件：

- `AGENT_LOG.md`

每条记录包含：

- 时间戳。
- task 编号。
- 使用的 Superpowers skill。
- 关键 prompt / context。
- subagent 输出或 commit hash。
- 人工修改内容和原因。
- 教训。

验证标准：

- 每个已完成 PLAN task 都有对应日志。

实际验证：

- 已覆盖 T2.1/T2.2 至 T8.3 的主要实现、验证和交付过程。
- 已补充 release 包准备、Docker 验证边界和最终日志整理记录。
- 已清理不适合最终提交的口语化措辞。

依赖：贯穿全程。

### T8.3 编写 `REFLECTION.md`

状态：已完成。

目标：完成 1500-2500 字反思报告。

涉及文件：

- `REFLECTION.md`

必须回答：

- 哪些 Superpowers skill 最有用，哪些形式大于实质。
- TDD 是阻碍还是放大器。
- subagent 工作流能自主多久。
- task 颗粒度经验。
- SPEC / PLAN 质量如何影响实现。
- 一个规约不清导致 subagent 偏离的案例。
- 最有效的 prompt / context 策略。
- 凭据与分发要求迫使你想清楚什么。
- 如果重做会改变什么。
- 对 Superpowers 方法论的批判。

依赖：大部分实现完成后。

可并行：否。

### T8.4 填写 `submission.jsonc`

状态：已完成。

目标：完成课程补充要求的提交元数据。

文件位置：

- `C:\Users\HP\AI4SE_Final_Project\submission.jsonc`

填写方式：

```jsonc
{
  "id": "你的学号",
  "name": "你的姓名",
  "repo_url": "仓库链接",
  "is_deployed": false,
  "deploy_release_url": "release 链接"
}
```

注意：

- 不要改文件名。
- 不要放进源码压缩包内部。
- 和源码压缩包并列提交到 selearning。

实际验证：

- `submission.jsonc` 位于 `C:\Users\HP\AI4SE_Final_Project\submission.jsonc`，不在源码压缩包内部。
- 已填写学号、姓名、仓库链接、`is_deployed=false` 和真实 release 链接。

依赖：T7.4。

## 11. 最终提交清单

- [x] `SPEC.md`
- [x] `PLAN.md`
- [x] `SPEC_PROCESS.md`
- [x] 源代码
- [x] mock LLM 单元测试
- [x] 机制演示
- [x] `README.md`
- [x] `AGENT_LOG.md`
- [x] `REFLECTION.md`
- [x] `.gitlab-ci.yml`，包含 `unit-test`
- [x] Dockerfile 或等价分发产物
- [x] 本地单元测试 pass 记录
- [x] GitHub/NJU Git 仓库链接
- [x] release 链接
- [x] `submission.jsonc` 与源码压缩包并列提交
- [x] 仓库和压缩包内无真实凭据
