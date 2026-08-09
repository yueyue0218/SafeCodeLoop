# SafeCodeLoop 规约过程文档（SPEC_PROCESS）

## 1. 文档目的

本文档记录 SafeCodeLoop 项目中 `SPEC.md` 和 `PLAN.md` 的形成过程，用于证明项目不是一次性让 AI 生成，而是经过了需求理解、人工判断、方案修正和过程记录。

项目基本信息：

- 项目名称：SafeCodeLoop
- 项目类型：A · Coding Agent Harness
- 当前交付方式：CLI-only + release 链接
- 主要贡献：治理护栏 + 测试反馈闭环

## 2. 过程时间线

### 2.1 第一轮：理解作业到底要做什么

初始问题：

作业要求很长，而且混合了通用要求和 A 类 harness 的额外要求。用户一开始不清楚这是要做普通应用，还是要做一个 agent。

AI 的解释：

AI 将作业重新解释为：

> A 类作业不是做普通 Web 应用，而是做一个简化版 coding agent harness，也就是自己实现 LLM 外围的工程系统。

需要实现的关键机制包括：

- agent 主循环。
- LLM 抽象层和 mock LLM。
- 工具分发。
- 治理护栏。
- 测试反馈闭环。
- 记忆和上下文管理。
- 配置。
- 凭据管理。
- 测试、CI、分发和过程文档。

人工决策：

用户接受这个解释，并决定做一个范围较小但机制完整的项目，而不是做一个泛泛的应用。

结果：

项目被命名为 SafeCodeLoop。

项目定位为：

> 一个带危险命令护栏和测试反馈闭环的迷你 coding agent harness。

### 2.2 第二轮：确定主攻机制

问题：

作业要求 harness 至少覆盖六个维度：决策、工具、记忆、治理、反馈、配置；同时又要求选择一个机制密集的维度深入实现。

AI 建议：

选择“治理护栏 + 测试反馈闭环”作为主要贡献。

理由：

- 这两个机制最容易用代码做确定性测试。
- 也最符合 A 类作业强调的“机制必须是代码，不能只是提示词”。
- mock LLM 可以稳定复现危险动作拦截和失败后修正。

人工决策：

采纳该建议。

确定的设计：

- 所有六个维度都做最小实现。
- 治理护栏和反馈闭环做得更深入。
- 不追求多 agent、大型 UI 或复杂 IDE 集成。

### 2.3 第三轮：老师补充说明改变交付方式

初始理解：

通用要求里写了线上部署 URL 和 WebUI，因此最初任务清单把 WebUI 当成必做。

老师补充说明：

老师在群里说明，A 类 Agent Harness 可以有两种交付方式：

- 方案一：只提供 CLI，不做 WebUI，提供托管平台 release 链接。
- 方案二：CLI + WebUI，提供 WebUI 链接。

用户提出问题：

用户询问这是否影响之前拆分的任务，以及 `submission.jsonc` 应该如何处理。

AI 分析：

AI 判断这是一个关键修正：

- WebUI 不再是必做。
- CLI-only + release 链接是合法方案。
- `submission.jsonc` 必须和源码压缩包并列提交，不能放进压缩包内部。
- CLI-only 情况下，`is_deployed=false`，`deploy_release_url` 填 release 链接。

人工决策：

选择更稳妥的 CLI-only + release 路线。

原因：

- 时间应优先投入 harness 内核。
- 作业评分重点是机制、测试、TDD、文档和分发，不是 UI。
- WebUI 会增加范围和部署风险。

结果：

- `SPEC.md` 修改为 WebUI 可选。
- `PLAN.md` 锁定 Python CLI + release 路线。
- `AI4SE_FINAL_TASKS.md` 增加 release 和 submission 任务。
- `submission.jsonc` 模板被复制到外层作业目录。

## 3. 采纳的 AI 建议

### 3.1 项目选型：SafeCodeLoop

采纳内容：

做一个小型 coding agent harness，而不是普通应用。

原因：

它最直接满足 A 类作业要求，并且能清楚展示 agent 主循环、工具、护栏和反馈。

### 3.2 以 mock LLM 测试为中心

采纳内容：

所有核心机制都优先用 mock LLM 测试验证。

原因：

作业明确要求：移除真实 LLM 后，机制仍应能通过确定性单测验证。

### 3.3 主攻治理护栏和反馈闭环

采纳内容：

把治理护栏和反馈闭环作为主要贡献。

原因：

这两个机制最能体现“harness 是工程，不是提示词”。

### 3.4 采用 CLI-only + release

采纳内容：

不把 WebUI 作为 P0，优先交付 CLI 和 release 链接。

原因：

老师补充说明允许这样交付，且该路线风险更低。

### 3.5 使用 Python

采纳内容：

使用 Python 3.11+、`argparse`、`pytest`。

原因：

Python 更适合快速实现文件工具、命令执行、JSON mock script 和 pytest 单元测试。

## 4. 修改或推翻的 AI 建议

### 4.1 推翻“WebUI 必做”

原始 AI 输出：

第一次任务拆分里把 WebUI URL 写入了核心交付物。

人工修正：

根据老师补充说明，将 WebUI 改为可选项。

最终结果：

采用 CLI-only + release。

### 4.2 控制范围，避免过度设计

潜在问题：

AI 容易把 harness 扩展成多 agent、复杂 UI、复杂部署平台。

人工决策：

只做一个 agent loop，并围绕 mock LLM、guardrail、feedback 做深。

### 4.3 拒绝“提示词式护栏”

错误方向：

在系统提示词里写“不要运行危险命令”。

人工决策：

护栏必须是代码函数或状态机，并能直接单测。

原因：

作业明确说明提示词规则不算机制实现。

## 5. 已生成文件

当前已经生成：

- `C:\Users\HP\AI4SE_Final_Project\AI4SE_FINAL_TASKS.md`
- `C:\Users\HP\AI4SE_Final_Project\submission.jsonc`
- `C:\Users\HP\AI4SE_Final_Project\SafeCodeLoop\SPEC.md`
- `C:\Users\HP\AI4SE_Final_Project\SafeCodeLoop\PLAN.md`
- `C:\Users\HP\AI4SE_Final_Project\SafeCodeLoop\SPEC_PROCESS.md`

## 6. 冷启动验证记录

该步骤已执行第一轮。

使用的第二 agent：

- Gemini

提供给 Gemini 的上下文：

- `SPEC.md`
- `PLAN.md`

没有提供先前对话背景。

使用的 prompt 要点：

```text
你只能看到 SafeCodeLoop 的 SPEC.md 和 PLAN.md，不能使用任何先前对话上下文。
请从 PLAN.md 中选择 1-2 个早期实现任务尝试推进。
如果任何需求、文件路径、行为或测试期望不明确，请停止并提问，不要猜测。
请记录你被什么卡住、你倾向于做出哪些假设。
```

Gemini 选择尝试的任务：

- T2.1 创建 Python 包结构。
- T2.2 添加 CLI 基础入口。

Gemini 正确理解的内容：

- T2.1 应建立最小 Python 工程骨架。
- T2.2 应使用 `argparse` 建立 CLI。
- 应先写 `test_package_imports`、CLI help 测试、CLI version 测试。
- 不应在该阶段实现 agent 核心逻辑。

Gemini 暴露的 SPEC/PLAN 歧义：

1. `pyproject.toml` 未指定构建后端。
2. CLI version 测试要求版本输出，但未说明版本号唯一来源。
3. 未说明是否要在 `[project.scripts]` 注册全局命令，也未说明命令名。
4. PLAN 只写了 `python -m safecodeloop.cli --help`，但没有说明是否支持更标准的 `python -m safecodeloop`。

判断：

这些问题属于 SPEC/PLAN 颗粒度不足，不是 Gemini 误读。它们会影响后续 subagent 实现的一致性，因此需要修订文档。

修订决策：

- 构建后端锁定为 `setuptools`。
- 包名锁定为 `safecodeloop`。
- CLI 全局命令名锁定为 `safecodeloop`。
- 版本号唯一来源锁定为 `src/safecodeloop/__init__.py` 中的 `__version__`。
- 初始版本号为 `0.1.0`。
- 新增 `src/safecodeloop/__main__.py`，支持 `python -m safecodeloop`。
- `pyproject.toml` 需要配置 `[project.scripts]`：

```toml
[project.scripts]
safecodeloop = "safecodeloop.cli:main"
```

修订后的影响：

- T2.1 和 T2.2 的文件清单更完整。
- CLI 测试期望更明确。
- 后续 subagent 不需要猜测 packaging 和 entry point 策略。

## 7. 当前风险

- 真实 LLM adapter 可能来不及完整实现，因此必须保证 mock LLM 路径完整。
- OS keyring 可能实现成本较高，可能需要 `.env` fallback，但必须说明风险。
- release 平台尚未最终确定。
- worktree / PR 历史还需要在后续实现过程中认真维护。
- 冷启动验证可能暴露当前 SPEC/PLAN 仍有歧义。

## 8. 阶段性反思

目前 AI 做得好的地方：

- 帮助把复杂作业要求拆成可执行机制。
- 识别 mock LLM 测试是评分核心。
- 根据老师补充说明及时调整交付路线。

目前 AI 做得不够好的地方：

- 一开始过度相信通用要求，把 WebUI 当成必做。
- 如果用户不提供群消息，AI 无法知道最新解释。
- 初始任务拆分略偏大，需要人工压缩范围。

目前最重要的人类判断：

不是让 AI 直接写项目，而是由人确定边界、纠正需求理解、决定取舍。这个项目应该优先做出可测试、可解释、可提交的 harness 机制，而不是追求看起来功能很多。
