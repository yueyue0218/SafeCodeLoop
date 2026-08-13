# SafeCodeLoop 项目反思

这次 A 类 Agent Harness 作业让我真正意识到，coding agent 不是“LLM 加提示词”，而是一套围绕 LLM 的工程系统。SafeCodeLoop 最终做成了一个 CLI-only 的迷你 harness：包含主循环、action parser、MockLLM、工具注册表、文件/命令工具、guardrail、feedback classifier、memory、config、credential 命令、CI、Dockerfile 和 release 打包脚本。项目规模不大，但覆盖了 agent harness 的关键外壳，也让我更清楚地理解了 Superpowers 方法论的价值和局限。

对我最有用的部分是先写 `SPEC.md` 和 `PLAN.md`。一开始我很容易把作业理解成普通应用或 WebUI 项目，但 SPEC 把方向固定为“带治理护栏和测试反馈闭环的 coding agent harness”。老师补充说明允许 CLI-only + release 后，PLAN 也及时调整，不再把 WebUI 当成 P0。这一步避免了范围失控，把时间集中到了作业 A 真正评分的机制上。

第二个有用的部分是 task 拆分。T3.1 只做 action parser，T3.2 只做 MockLLM，T3.3 只做主循环骨架，T4 再接工具和护栏，T5 再做反馈、记忆、配置和凭据。这样每一步都有清楚的失败测试和验证命令。如果一开始把主循环、工具、护栏、反馈混在一起实现，代码很可能会变成一团，也很难解释每个机制到底在哪里。

TDD 对这个项目来说更像放大器，而不是阻碍。它确实让早期速度变慢，因为每个模块都要先看到红灯，例如 `ModuleNotFoundError`、接口参数缺失、CLI 参数不支持等。但红灯让边界变清楚：parser 不执行工具，guardrail 必须在工具执行前发生，command tool 的失败要变成结构化结果而不是直接崩溃。T6.3 和 T6.4 尤其体现了 TDD 的价值：日志中必须真的出现 `feedback_kind: test_failure`、`feedback_kind: pass` 和 `status: blocked`，而不是只在 README 里口头描述。

Subagent 工作流的经验是：它适合小颗粒度、边界清楚的任务，不适合长期无人监督。冷启动验证里，另一个 agent 能理解 T2.1/T2.2 的目标，但也暴露了构建后端、版本号来源、CLI 命令名、`python -m safecodeloop` 是否支持等歧义。这说明 subagent 能帮忙发现 SPEC/PLAN 的漏洞，但项目方向、交付路线、评分风险仍然需要人来判断。

SPEC/PLAN 的质量直接影响实现质量。一个典型例子是交付方式：通用要求里提到 WebUI 和部署 URL，但老师补充说明 A 类可以只交 CLI 和 release 链接。如果这个修正没有写进 SPEC/PLAN，后续就可能把大量时间花在 WebUI 上。另一个例子是 T6.4，最初“展示治理护栏 + 反馈闭环”这个描述还不够具体；后来验收标准被加强为同一条 demo 先失败、再修正通过、最后危险命令被拦截，这样才真正体现主要贡献机制。

最有效的 prompt / context 策略不是简单说“帮我写代码”，而是给出 task 编号、相关文件、预期失败测试、验证命令和禁止猜测的边界。例如冷启动验证时，只给 `SPEC.md` 和 `PLAN.md`，要求不清楚就停下提问；实现阶段则要求先写失败测试，再补最小实现，再跑回归测试。这种上下文能让 AI 输出更可控，也能留下可审计证据。

凭据和分发要求让我意识到，工程化不是附加项。凭据方面，项目实现了 `key status/set/clear`，状态输出会 mask key，测试用临时路径避免污染真实配置。但当前仍是本地 JSON fallback，不是 OS keyring，所以 README 必须诚实说明风险。分发方面，`.gitlab-ci.yml`、Dockerfile、release 脚本都迫使我区分“文件已提供”“命令已运行”“外部网络失败”“最终通过”。Docker CLI 已验证可用，但 build 因 Docker Hub 网络不可达未完成，这种限制也应该如实记录，而不是假装通过。

如果重做，我会更早建立提交节奏和最终清单。前期主要关注实现，后期集中补 README、release、Docker 状态和日志，压力会比较大。更好的做法是每个 phase 完成后立即更新 PLAN、AGENT_LOG 和 README 草稿。另一个会提前处理的是凭据存储，如果时间更多，我会优先接 Windows Credential Manager 或 Python keyring，而不是只做 JSON fallback。

我对 Superpowers 方法论的批判是：它很有用，但容易形式化。SPEC、PLAN、AGENT_LOG 如果只是为了凑文件，会变成负担；只有当它们真正改变实现顺序、暴露歧义、约束测试和记录取舍时才有价值。这个项目中，方法论最有价值的地方不是“写了很多文档”，而是让 AI 协作变得可验证、可复现、可追责。

总体来说，SafeCodeLoop 让我理解到，AI coding 的核心不是让模型多写代码，而是建立一个能解析模型输出、约束危险动作、接收客观反馈、记录过程并最终可分发的工程系统。这个项目虽然小，但它把 coding agent 的关键机制做成了可以运行、可以测试、可以审查的形式。
