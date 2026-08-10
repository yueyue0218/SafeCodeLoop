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
- 记录老师补充说明后改为 CLI-only + release 的原因。

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

依赖：T4.1。

可并行：否。

### T4.3 实现命令工具

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

依赖：T4.1。

可并行：是。

### T4.4 实现 Guardrail Engine

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

依赖：T3.1。

可并行：是。

### T4.5 串联 Loop、Guardrails 与 Tools

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

依赖：T3.3、T4.2、T4.3、T4.4。

可并行：否。

## 7. Phase 5：反馈、记忆、配置、凭据

### T5.1 实现 Validator 和 Feedback Classifier

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

依赖：T4.3。

可并行：是。

### T5.2 将反馈回灌进主循环

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

依赖：T4.5、T5.1。

可并行：否。

### T5.3 实现 Memory Store

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

依赖：T2.1。

可并行：是。

### T5.4 将 Memory 加入上下文组装

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

依赖：T5.3、T3.3。

可并行：否。

### T5.5 实现 Config Loader

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

依赖：T4.4。

可并行：是。

### T5.6 实现凭据命令

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

依赖：T3.2、T2.2。

可并行：是。

## 8. Phase 6：CLI 与机制演示

### T6.1 实现 `run` CLI

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

依赖：T4.5、T5.2、T5.5。

可并行：否。

### T6.2 Demo 1：危险动作拦截

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

依赖：T6.1。

可并行：是。

### T6.3 Demo 2：反馈闭环自我修正

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

依赖：T6.1。

可并行：是。

### T6.4 Demo 3：主要贡献机制

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

依赖：T6.2、T6.3。

可并行：否。

## 9. Phase 7：CI、分发、Release

### T7.1 添加 `.gitlab-ci.yml`

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

依赖：T2.1。

可并行：是。

### T7.2 添加 Dockerfile

目标：提供可分发容器构建方式。

涉及文件：

- `Dockerfile`
- `.dockerignore`

验证命令：

```bash
docker build -t safecodeloop .
docker run --rm safecodeloop --help
```

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

依赖：T7.3。

可并行：否。

## 10. Phase 8：最终文档

### T8.1 编写 README

目标：让助教能从零运行项目。

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

依赖：T6.1、T7.2。

可并行：是。

### T8.2 维护 `AGENT_LOG.md`

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

依赖：贯穿全程。

### T8.3 编写 `REFLECTION.md`

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

目标：完成老师补充要求的提交元数据。

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

依赖：T7.4。

## 11. 最终提交清单

- [ ] `SPEC.md`
- [ ] `PLAN.md`
- [ ] `SPEC_PROCESS.md`
- [ ] 源代码
- [ ] mock LLM 单元测试
- [ ] 机制演示
- [ ] `README.md`
- [ ] `AGENT_LOG.md`
- [ ] `REFLECTION.md`
- [ ] `.gitlab-ci.yml`，包含 `unit-test`
- [ ] Dockerfile 或等价分发产物
- [ ] 最后一次 CI pass 记录
- [ ] GitHub/NJU Git 仓库链接
- [ ] release 链接
- [ ] `submission.jsonc` 与源码压缩包并列提交
- [ ] 仓库和压缩包内无真实凭据
