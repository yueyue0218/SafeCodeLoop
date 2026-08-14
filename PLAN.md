# SafeCodeLoop 实现计划（PLAN）

> 交付路线：CLI-only + release 链接。WebUI 是可选项，不进入 P0。

## 0. 当前执行基线（2026-08-14）

- 发布准备提交 `5418cc2` 已通过 PR #8 合入 `main`；最终发布收口在 `release/v0.1.0-finalize` 分支完成。
- 当前本地全量回归：`176 passed, 2 skipped`（symlink 用例在当前 Windows 权限下跳过）。
- Docker：`safecodeloop:0.1.0` 已成功构建；容器内 `--help`、`--version` 和完整 MockLLM 反馈演示通过。
- 分发：GitHub Release `v0.1.0` 的 tag 与最终 `main` 提交对齐；Release 提供源码 ZIP、wheel、sdist 和 `SHA256SUMS`，并已按 SPEC §10.3 完成 wheel 干净环境安装与 CLI 冒烟。
- 凭据：生产 CLI 使用 OS keyring；明文文件 backend 仅供测试显式注入。
- 真实模型：OpenAI-compatible adapter 已实现；核心验收仍使用离线 MockLLM。
- 本文各 task 中的较小测试数字是该 task 完成当时的历史回归结果；当前开发基线统一以上述 `176 passed, 2 skipped` 为准，`v0.1.0` Release 验收基线仍为 `116 passed`。

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
- LLM：MockLLM 用于确定性核心验收；OpenAI-compatible adapter 已实现
- 一键测试命令：`python -m pytest`
- CI：`.gitlab-ci.yml`，必须包含 `unit-test` job

## 2. 分支 / Worktree / PR 策略

### 2.1 初始规划

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

上述列表是 brainstorming 阶段的初始分组。实际执行中，早期 T2—T8 基础能力采用连续的小提交推进；安全与反馈深度增强阶段改用独立 feature branch + PR。二者的差异属于真实过程记录，不将早期线性提交追写成不存在的 PR。

### 2.2 实际提交与 PR 映射

| 执行范围 | 实际分支 / worktree | 关键提交 | PR / 合并提交 | 验证与说明 |
|---|---|---|---|---|
| T2—T5 基础 harness：parser、MockLLM、loop、tools、guardrail、feedback、memory、config | 早期主线连续提交 | `85c0088`—`b1be3fc` | 无独立 PR | 每项先红后绿并全量回归；这是相对初始“每模块一个 PR”策略的流程偏离，详细人工干预记录在 `AGENT_LOG.md` |
| T6 demos、T7 初版分发、T8 文档 | 早期主线连续提交 | `f9643b5`—`0a1a9ce` | 无独立 PR | 三个 demo 均有 pytest 断言；Docker 早期环境限制与 release 状态分别记录，未伪造当时结果 |
| 安全凭据存储 | `feat/secure-credential-storage` | `8653bb8` | PR #1 / `2a43b07` | OS keyring、隐藏输入、无生产明文 fallback；凭据专项与全量回归通过 |
| GitHub CI 与 wheel smoke | `ci/github-actions` | `c4d27f9` | PR #2 / `cbe6014` | PR/push 自动测试、构建 wheel、隔离环境安装与 CLI smoke |
| 真实 LLM adapter | `feat/openai-compatible-provider` | `a7094f7`、`525bedf`、`5b9d906` | PR #3 / `3ec8151` | 真实 provider 只替换单次决策组件；全量 `87 passed`，CI runtime warning 修正 |
| 可恢复 HITL | `feat/resumable-approvals` | `ec842e9`、`9192833` | PR #4 / `551b87a` | HMAC、一次消费、跨进程 resume、Linux CI 测试隔离；全量 `97 passed` |
| 显式 validation | `feat/t12-validation-loop` | `22475a0` | PR #5 / `8ba4147` | 普通命令与客观验证分离；validation 仍走 guardrail；全量 `100 passed` |
| 分类与有界反馈 | `feat/t12-feedback-classification` | `007643c` | PR #6 / `3300cc5` | 八类反馈、1200 字符摘要、hash/reference；全量 `106 passed` |
| 完成门槛与停止控制 | `feat/t12-validation-controls` | `20fde80` | PR #7 / `b140ea4` | 写入/失败后拒绝假成功、预算、熔断、resume 同规则；全量 `114 passed` |
| v0.1.0 干净环境验证 | `release/v0.1.0-prep` | `5418cc2` | PR #8 / `e11b0b9` | Docker build/run、惰性审批存储、演示镜像 pytest；本地最终 `116 passed` |
| v0.1.0 最终发布收口 | `release/v0.1.0-finalize` | 由 `v0.1.0` tag 追溯 | 最终发布 PR | 打包脚本生成源码 ZIP、wheel、sdist、commit 记录与 SHA-256；公开 Release 替换为最终资产并执行干净安装 |

### 2.3 两阶段评审纪律

每个增强 PR 在合并前依次进行：

1. **SPEC 合规检查**：确认是否实现关联机制、是否违反自研 harness 边界、是否产生绕过路径、是否超出 task 范围；
2. **代码质量检查**：检查安全失败、错误分类、凭据泄露、重复逻辑、跨平台行为、测试隔离和全量回归。

Critical issue 必须在同一 PR 中修复并重新验证后才能合并。以下是可由提交与 `AGENT_LOG.md` 复核的评审处置：

| PR | SPEC 合规检查及处置 | 代码质量检查及处置 | 结论 |
|---|---|---|---|
| #1 安全凭据 | 发现生产默认明文 JSON 不满足凭据安全要求，改为 OS keyring 和隐藏输入 | 移除 `--value` 明文参数与生产文件 fallback，避免 shell history/进程参数泄露 | 修正后通过；PR #1 本身无 GitHub checks，随后以 PR #2 补齐托管平台 CI |
| #2 GitHub CI | 发现只有 `.gitlab-ci.yml`，GitHub PR 无自动检查，新增 GitHub workflow | 增加 wheel 构建和隔离安装 smoke，避免 editable install 掩盖打包遗漏 | 通过 |
| #3 Provider | 确认 adapter 只负责单次 LLM 调用，不替代 loop、parser、tools、guardrail、feedback | 稳定分类鉴权/限流/超时/响应错误并保持 secret redaction；修复 Actions runtime warning | 修正后通过 |
| #4 HITL | 发现 `needs_approval` 只能停止、不能恢复，补齐 pending → decide → resume 状态机 | 普通 SHA-256 无法防同时篡改 action/hash，升级 HMAC；修复 Linux CI 对宿主 keyring 的隐式依赖 | 修正后通过 |
| #5 Validation | 发现所有命令都被当作客观验证，新增显式 `run_validation` | 复用 command executor，确认 validation 同样经过 guardrail，不复制 shell 路径 | 通过 |
| #6 Feedback | 对照 SPEC 补齐 type/lint/environment/unknown 分类和有界上下文 | 完整 evidence 留日志，摘要携带原长度、SHA-256 与位置，避免不可审计截断 | 通过 |
| #7 Controls | 发现写入后或失败后可直接 `finish`，增加完成门槛、预算和熔断 | 复审发现 approval resume 可绕过门槛；先加红灯测试，再让恢复路径复用同一状态机 | 修正后通过 |

早期线性提交虽然没有独立 PR，但每个 task 的红灯、绿灯、人工修正和回归结果均保留在 `AGENT_LOG.md`。这一偏离不补造流程证据，而作为“初始 worktree/PR 规划执行不足、后期通过七个正式 PR 改进”的过程反思保留。

### 2.4 Subagent 微步骤执行索引

下面把原本以模块命名的大 task 拆成可由 subagent 顺序执行的微步骤。每个 `Sx` 只包含一个可观察动作，预期耗时 2—5 分钟；若一步需要扩大公开接口、修改范围外文件或无法在一个短周期内得到预期红/绿结果，subagent 必须暂停并报告，不能自行扩大任务。

所有实现 task 在完成专属微步骤后，统一执行以下收尾门禁，每项同样视为一个独立微步骤：

1. `G1`：运行该 task 的专项 pytest，保存完整结果；
2. `G2`：运行 `python -m pytest`，确认没有回归；
3. `G3`：执行 SPEC 合规检查，逐条核对关联需求和范围外约束；
4. `G4`：执行代码质量检查，检查错误路径、secret、重复逻辑、测试隔离和跨平台行为；
5. `G5`：根据评审意见做最小修正，并重新执行受影响测试；
6. `G6`：更新 `PLAN.md` 状态、`AGENT_LOG.md` 红/绿证据及 commit/PR 信息；
7. `G7`：只暂存 task 涉及文件并创建语义明确的提交。

#### Phase 1：规约与冷启动

| Task | 2—5 分钟专属微步骤 |
|---|---|
| `T1.1 SPEC` | `S1` 按通用要求十项建立章节清单；`S2` 补 A 类领域与机制章节；`S3` 将范围内/外逐项分类；`S4` 为用户故事写客观验收；`S5` 检查凭据威胁模型与分发路径；`S6` 执行要求覆盖审阅 |
| `T1.2 PLAN` | `S1` 从 SPEC 提取稳定需求；`S2` 按依赖排序 phase；`S3` 为每个 task 填文件路径；`S4` 为每个 task 写预期红灯；`S5` 写专项与全量验证命令；`S6` 标记依赖和可并行组 |
| `T1.3 PROCESS` | `S1` 选取一次关键追问；`S2` 写对应对话节选；`S3` 写人工采纳/推翻决定；`S4` 记录 SPEC/PLAN 前后变化；`S5` 重复至至少三轮；`S6` 单列 brainstorming 优点与不满 |
| `T1.4 冷启动` | `S1` 创建无历史的新 agent session；`S2` 只提供 SPEC/PLAN；`S3` 指定 T2.1/T2.2；`S4` 记录第一个暂停问题；`S5` 判断是文档缺陷还是误读；`S6` 修订一处歧义；`S7` 用同样输入重新检查 |

#### Phase 2—3：骨架、协议与主循环

| Task | 2—5 分钟专属微步骤 |
|---|---|
| `T2.1 包结构` | `S1` 添加 import smoke 红灯；`S2` 运行并确认 `ModuleNotFoundError`；`S3` 创建 `src/safecodeloop/__init__.py`；`S4` 写唯一 `__version__`；`S5` 配置 setuptools package discovery |
| `T2.2 CLI 入口` | `S1` 添加 help 红灯；`S2` 添加 version 红灯；`S3` 实现共享 `main()`；`S4` 注册 console script；`S5` 添加 `__main__.py` 转发；`S6` 分别验证三种入口 |
| `T3.1 Action Parser` | `S1` 添加合法 action 红灯；`S2` 添加非法 JSON 红灯；`S3` 添加未知类型红灯；`S4` 添加缺失字段红灯；`S5` 定义 `Action` 数据结构；`S6` 实现最小 schema 校验；`S7` 确认 parser 不执行工具 |
| `T3.2 LLM/MockLLM` | `S1` 写接口替换红灯；`S2` 写脚本顺序红灯；`S3` 写耗尽错误红灯；`S4` 实现 LLM protocol；`S5` 实现 MockLLM 队列；`S6` 记录输入 context；`S7` 验证脱敏 |
| `T3.3 AgentLoop` | `S1` 写 finish 红灯；`S2` 写 parse-error observation 红灯；`S3` 写 max-steps 红灯；`S4` 实现单步 LLM 调用；`S5` 接入 parser；`S6` 实现固定终态；`S7` 验证每步索引和 observation |

#### Phase 4：工具与治理

| Task | 2—5 分钟专属微步骤 |
|---|---|
| `T4.1 Tool Registry` | `S1` 写未注册工具红灯；`S2` 写成功 dispatch 红灯；`S3` 定义 `ToolResult`；`S4` 实现 register/dispatch；`S5` 将工具异常转换为结构化失败 |
| `T4.2 文件工具` | `S1` 写 list 红灯；`S2` 写 read 红灯；`S3` 写 write 红灯；`S4` 写 `../` 越界红灯；`S5` 实现 canonical path；`S6` 实现 containment check；`S7` 注册三个文件工具 |
| `T4.3 命令工具` | `S1` 写 stdout/exit-code 红灯；`S2` 写 stderr 红灯；`S3` 写 timeout 红灯；`S4` 实现 workspace cwd；`S5` 实现 subprocess capture；`S6` 把非零退出转成 `ToolResult`；`S7` 把 timeout 转成结构化结果 |
| `T4.4 Guardrail` | `S1` 写递归删除红灯；`S2` 写数据库删除红灯；`S3` 写 dependency approval 红灯；`S4` 写安全 action allow 红灯；`S5` 定义三态 decision；`S6` 实现内置规则；`S7` 实现可配置规则 |
| `T4.5 Loop 集成` | `S1` 写 blocked 不调用 executor 红灯；`S2` 写 allow 调用工具红灯；`S3` 写 approval 暂停红灯；`S4` 注入 registry；`S5` 注入 guardrail；`S6` 固定 parse→guardrail→dispatch 顺序；`S7` 记录 decision 和 tool observation |
| `T4.6 可恢复审批` | `S1` 写 pending 持久化红灯；`S2` 写 approve/reject 红灯；`S3` 写换参/篡改红灯；`S4` 写重复消费红灯；`S5` 实现 canonical action；`S6` 加入 HMAC；`S7` 实现一次消费；`S8` 接入 CLI resume；`S9` 验证跨进程链路 |

#### Phase 5 与 T12：反馈、记忆、配置、凭据

| Task | 2—5 分钟专属微步骤 |
|---|---|
| `T5.1 Feedback` | `S1` 写 pass 分类红灯；`S2` 写 test/syntax/timeout 红灯；`S3` 定义 Feedback；`S4` 实现分类顺序；`S5` 实现 observation；`S6` 添加 type/lint/environment/unknown 表驱动用例 |
| `T5.2 回灌` | `S1` 写“失败进入下一次 context”红灯；`S2` 写“第二次验证通过”红灯；`S3` 注入 Validator；`S4` 把 feedback 转 observation；`S5` 将 observation 交给下一次 MockLLM；`S6` 断言动作确实改变 |
| `T5.3 Memory` | `S1` 写持久化红灯；`S2` 写 priority/recency 红灯；`S3` 写 secret 红灯；`S4` 定义 MemoryItem；`S5` 实现 JSON load/save；`S6` 实现检索评分；`S7` 实现脱敏 |
| `T5.4 Context Memory` | `S1` 写相关 memory 进入 context 红灯；`S2` 写预算淘汰红灯；`S3` 注入 MemoryStore；`S4` 构造相关性 query；`S5` 限制返回条数；`S6` 断言不相关内容不进入 context |
| `T5.5 Config` | `S1` 写默认值红灯；`S2` 写非法整数红灯；`S3` 写未知字段红灯；`S4` 定义 dataclass；`S5` 实现字段映射；`S6` 实现完整校验；`S7` 证明配置改变 guardrail/预算 |
| `T5.6 Credential` | `S1` 写 status 不泄密红灯；`S2` 写 set/clear 红灯；`S3` 写无 keyring 安全失败红灯；`S4` 定义 backend 接口；`S5` 实现 OS keyring；`S6` CLI 使用 hidden input；`S7` 移除明文 CLI 参数；`S8` 测试显式注入临时 backend |
| `T12.1 显式验证` | `S1` 写 parser 不识别 `run_validation` 红灯；`S2` 写普通命令不产生 feedback 红灯；`S3` 注册 validation tool；`S4` 复用 command executor；`S5` 接入 feedback；`S6` 验证同样经过 guardrail |
| `T12.2 有界反馈` | `S1` 为四类缺失分类写表驱动红灯；`S2` 写超长输出红灯；`S3` 实现 1200 字符上限；`S4` 优先保留诊断行；`S5` 添加原长度；`S6` 添加 SHA-256；`S7` 添加 run-log reference |
| `T12.3 完成控制` | `S1` 写失败后 finish 红灯；`S2` 写代码写入后 finish 红灯；`S3` 写 validation budget 红灯；`S4` 写重复失败红灯；`S5` 实现 dirty/validated 状态；`S6` 实现 completion rejected；`S7` 实现预算与熔断；`S8` 为 resume 绕过补红灯；`S9` 让 resume 复用同一状态机 |

#### Phase 6—8：CLI、演示、分发与文档

| Task | 2—5 分钟专属微步骤 |
|---|---|
| `T6.1 run CLI` | `S1` 写成功退出码红灯；`S2` 写非成功终态退出码红灯；`S3` 写 run-log 红灯；`S4` 添加参数；`S5` 组装 config/loop/tools；`S6` 输出稳定 status；`S7` 序列化步骤日志 |
| `T6.2 Guardrail Demo` | `S1` 写 demo 文件缺失红灯；`S2` 编写危险 action script；`S3` 运行 CLI；`S4` 断言 blocked；`S5` 断言危险命令未执行 |
| `T6.3 Feedback Demo` | `S1` 写缺失 demo 红灯；`S2` 写错误实现 action；`S3` 写第一次 validation；`S4` 写修正 action；`S5` 写第二次 validation；`S6` 写 finish；`S7` 断言 failure→pass→success |
| `T6.4 Main Demo` | `S1` 复用完整反馈链；`S2` 在 pass 后追加危险 action；`S3` 运行组合 demo；`S4` 断言 test_failure；`S5` 断言 pass；`S6` 断言最终 blocked 且未执行危险命令 |
| `T7.1 CI` | `S1` 写 `unit-test` job；`S2` 安装 package/pytest；`S3` 运行全量测试；`S4` 添加 wheel build；`S5` 隔离安装 wheel；`S6` 运行 CLI smoke；`S7` 观察远程结果并修正 runtime warning |
| `T7.2 Docker` | `S1` 写最小 Dockerfile；`S2` 写 `.dockerignore`；`S3` build image；`S4` 运行 help；`S5` 运行 version；`S6` 运行 feedback demo；`S7` 检查 image 排除项；`S8` 根据容器缺依赖红灯修正镜像 |
| `T7.3/7.4 Release` | `S1` 以 `git ls-files` 收集输入；`S2` 排除 secret/cache/log；`S3` 生成 zip；`S4` 检查归档成员；`S5` 创建 release；`S6` 上传 asset；`S7` 打开 URL 验证；`S8` 更新 submission metadata |
| `T8.1 README` | `S1` 写安装；`S2` 写三个 demo；`S3` 写 key 流程；`S4` 写 Docker/release；`S5` 写安全边界；`S6` 按命令从零复现并修正文档 |
| `T8.2 AGENT_LOG` | `S1` 补时间/task；`S2` 补 skill/context；`S3` 补红绿证据；`S4` 补人工修正；`S5` 补 commit/PR；`S6` 对照 PLAN 检查遗漏 |
| `T8.3 REFLECTION` | `S1` 列十个必答问题；`S2` 为每题选真实案例；`S3` 写 TDD 判断；`S4` 写 subagent/task 粒度；`S5` 写方法论批判；`S6` 检查 1500—2500 字和事实一致性 |

此索引描述的是可重复的派发粒度；各 task 后文保留原始红灯、绿灯和历史回归结果，用于证明这些微步骤在实际执行中的落地情况。

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

状态：已完成并持续维护；最终执行基线见第 0 节。

### T1.3 完成 `SPEC_PROCESS.md`

目标：记录与 AI 协作生成规约的过程。

涉及文件：

- `SPEC_PROCESS.md`

验证步骤：

- 至少记录 3 轮关键迭代。
- 记录采纳和推翻的 AI 建议。
- 记录依据课程补充说明改为 CLI-only + release 的原因。

依赖：T1.1、T1.2。

状态：已完成；2026-08-14 已按 brainstorming 评分要求完成深度重写。

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

状态：已完成；2026-08-14 按 T10.2 完成真实模型输出协议强化。

实际验证：

- 使用与主开发智能体不同的 Gemini，仅提供 `SPEC.md` 与 `PLAN.md`，尝试 T2.1/T2.2。
- 冷启动验证暴露构建后端、版本号唯一来源、console script 名称和 `python -m safecodeloop` 入口四处歧义。
- 据此锁定 `setuptools`、`src/safecodeloop/__init__.py::__version__`、`safecodeloop` 命令和 `__main__.py`，并把入口行为写入测试。
- 完整对话节选、处理决策与修订影响记录在 `SPEC_PROCESS.md` 第 3.6 节和第 6 节。

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
- 单一 Markdown code fence 或前后杂文中的 action 可恢复解析。
- 多 JSON、重复字段、额外字段、错误类型和空必填字符串被拒绝。
- 超过 65,536 字符的响应在 JSON 解析前被拒绝。
- schema 非法的 action 不进入 guardrail 或工具层。

实现要点：

- 支持 `list_files`、`read_file`、`write_file`、`run_command`、`remember`、`finish`、`request_approval`。
- 后续将验证命令拆分为显式 `run_validation`，避免把普通命令成功误记为测试通过；该动作复用受控命令工具并继续经过相同 guardrail。
- 每种 action 具有 required/optional/non-empty 字段集合；所有参数类型严格为字符串，未知字段 fail closed。
- parse error 回灌只包含不超过固定长度的原因和修复提示，不复制原始响应。

验证命令：

```bash
python -m pytest tests/test_actions.py
```

实际验证：

- 红灯：首次运行 `python -m pytest tests/test_actions.py` 时，`ModuleNotFoundError: No module named 'safecodeloop.actions'`。
- 绿灯：新增 `src/safecodeloop/actions.py` 后，`tests/test_actions.py` 结果为 `7 passed`。
- 回归：运行 `python -m pytest`，全量结果为 `11 passed`。
- T10.2 红灯：新增严格协议测试后，收集阶段因缺少 `MAX_ACTION_RESPONSE_CHARS` 失败。
- T10.2 绿灯：Action/Loop/Guardrail 专项 `33 passed`；增加“非法 schema 不调用工具”和“重复对象不可隐藏”用例后，全量 `132 passed`。

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

T11.3 深化（2026-08-14）：

- 增加 POSIX、PowerShell 和 cmd 删除变体，以及大小写、空白、管道、逻辑运算符和命令分隔符的表驱动对抗测试。
- 文件动作在规范化和 symlink 解析后执行工作区边界检查，并保护 `.env`、SSH key、credential 和内部审批数据；命令中的敏感路径及 `..` 同样 fail closed。
- dependency install、发布/部署、外部写入、嵌套 shell 和不可可靠解释的复合命令进入审批；混淆执行与破坏性命令直接阻止。
- decision 记录稳定 `rule_id`、`severity` 和 `reason`，并按 `blocked > needs_approval > allowed` 选择结果。
- blocked/approval 配置正则均接入 CLI；非法正则在配置加载时失败。
- 红灯范围：`43 failed, 23 passed, 1 skipped`；实现后专项 `66 passed, 1 skipped`；补充 symlink 敏感文件别名覆盖后全量 `176 passed, 2 skipped`。

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
- 后续增强：反馈分类扩展为八类；完整 evidence 保存在运行日志，模型上下文只接收有界诊断摘要及 SHA-256 引用。
- 后续增强：增加验证预算、重复失败熔断和完成门槛；代码写入或验证失败后，必须取得新的客观验证通过才能成功结束，审批恢复路径遵守相同规则。
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

状态：已完成；本地回归通过，GitHub Actions 的测试、构建与 wheel smoke 流程已在 PR 中通过；`.gitlab-ci.yml` 保留课程要求的 `unit-test` job。

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
- 上述 `72 passed` 是 T7.1 初次完成时的历史结果；最终全量回归为 `116 passed`。

GitHub 托管适配：

- 新增 `.github/workflows/ci.yml`，保留现有 `.gitlab-ci.yml`。
- pull request 和 `main` push 触发 `unit-test` job。
- job 运行全量测试、构建 wheel，并在隔离虚拟环境安装 wheel 后执行 CLI smoke test。
- 本地构建与安装验证完成后，由 GitHub Actions 的实际运行结果确认远程状态。

依赖：T2.1。

可并行：是。

### T7.2 添加 Dockerfile

状态：已完成并在干净容器环境验证。

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
- 早期构建曾因 Docker Hub 代理配置不适合宿主机进程而失败；调整 Docker Desktop HTTP/HTTPS 代理后成功拉取基础镜像。
- `docker build --tag safecodeloop:0.1.0 .` 已成功完成。
- 容器内 `--help`、`--version` 和 failure → correction → pass 的 MockLLM 演示均通过。
- 干净环境验证发现并修复两个问题：普通安全任务过早初始化 OS keyring，以及镜像缺少运行反馈 demo 所需的 pytest。
- 镜像内容检查确认排除 `.git`、release 目录、本地审批状态和仓库外的 `SAFE_CODE_LOOP_HIGH_SCORE_EXECUTION_PLAN.md`；课程要求的 `PLAN.md` 保留在镜像中。
- 最终本地全量回归：`116 passed`。

依赖：T2.2。

可并行：是。

### T7.3 准备 Release 包

状态：已完成最终打包与校验。

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

实际验证：

- 最终打包脚本从干净提交生成 `SafeCodeLoop-0.1.0.zip`、wheel、sdist 和 `SHA256SUMS`。
- 打包输入来自 `git ls-files`，避免将未跟踪的本地文件混入产物。
- 归档边界检查排除 `.git`、`.env`、`.safecodeloop`、缓存、`.pyc` 和运行日志。
- 源码 ZIP 内的 `BUILD_INFO.txt` 记录版本和构建提交，可与 `v0.1.0` tag 交叉核对。

依赖：T7.2、T8.1。

可并行：否。

### T7.4 创建仓库 Release

状态：已完成；最终 tag、提交和四个公开资产一致。

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
- release assets 包含 `SafeCodeLoop-0.1.0.zip`、wheel、sdist 和 `SHA256SUMS`。
- `submission.jsonc` 已填写真实 release 链接。
- `v0.1.0` tag 指向包含最终文档和发布脚本的 `main` 提交；wheel 已在新建虚拟环境中安装并通过 `--help`、`--version`。

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
- README 已更新为最终验证状态：Docker image 构建成功，容器内 CLI 与完整 MockLLM 反馈演示通过。

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
- [x] release 链接已创建
- [x] 最终 tag、release asset 与最终提交 commit 对齐，并按 SPEC §10.3 在干净环境复验
- [x] `submission.jsonc` 与源码压缩包并列提交
- [x] 仓库和压缩包内无真实凭据
