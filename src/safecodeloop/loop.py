from dataclasses import dataclass, field
from typing import Any

from safecodeloop.actions import Action, ActionParseError, parse_action
from safecodeloop.approval import ApprovalError, ApprovalStore
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import LLMClient
from safecodeloop.memory import MemoryStore
from safecodeloop.tools import ToolRegistry


ACTION_PROTOCOL = """You are the decision component of SafeCodeLoop.
Return exactly one JSON action object and no markdown or explanatory text.
Allowed actions:
- {"type":"list_files","path":"optional/relative/path"}
- {"type":"read_file","path":"relative/path"}
- {"type":"write_file","path":"relative/path","content":"file content"}
- {"type":"run_command","command":"command to execute"}
- {"type":"run_validation","command":"test, lint, or typecheck command"}
- {"type":"remember","content":"fact","kind":"optional kind"}
- {"type":"request_approval","reason":"reason"}
- {"type":"finish","message":"result summary"}
Use only relative paths inside the workspace. Use finish only when the task is complete."""


@dataclass(frozen=True)
class LoopStep:
    index: int
    llm_response: str
    action: Action | None = None
    observation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResult:
    status: str
    final_message: str
    steps: list[LoopStep]
    approval_id: str | None = None


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        max_steps: int = 5,
        tool_registry: ToolRegistry | None = None,
        guardrail_engine: GuardrailEngine | None = None,
        validator: Validator | None = None,
        memory_store: MemoryStore | None = None,
        memory_context_budget: int = 1000,
        approval_store: ApprovalStore | None = None,
        max_validations: int = 4,
        max_repeated_failures: int = 2,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if max_validations < 1:
            raise ValueError("max_validations must be at least 1")
        if max_repeated_failures < 1:
            raise ValueError("max_repeated_failures must be at least 1")
        self.llm = llm
        self.max_steps = max_steps
        self.tool_registry = tool_registry
        self.guardrail_engine = guardrail_engine
        self.validator = validator
        self.memory_store = memory_store
        self.memory_context_budget = memory_context_budget
        self.approval_store = approval_store
        self.max_validations = max_validations
        self.max_repeated_failures = max_repeated_failures

    def run(self, task: str) -> RunResult:
        steps: list[LoopStep] = []
        messages = self._initial_messages(task)
        validation_count = 0
        completion_blocker: str | None = None
        previous_failure: tuple[str, str] | None = None
        repeated_failure_count = 0

        for index in range(self.max_steps):
            response = self.llm.generate(messages)
            try:
                action = parse_action(response.content)
            except ActionParseError as exc:
                observation = {
                    "kind": "parse_error",
                    "message": str(exc),
                    "raw_response": response.content,
                }
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        observation=observation,
                    )
                )
                messages.append(
                    {
                        "role": "system",
                        "content": f"parse_error: {observation['message']}",
                    }
                )
                continue

            if action.type == "finish":
                if completion_blocker is not None:
                    observation = {
                        "kind": "completion_rejected",
                        "reason": completion_blocker,
                    }
                    steps.append(
                        LoopStep(
                            index=index,
                            llm_response=response.content,
                            action=action,
                            observation=observation,
                        )
                    )
                    messages.append(
                        {
                            "role": "system",
                            "content": f"completion_rejected: {completion_blocker}",
                        }
                    )
                    continue
                observation = {"kind": "action_parsed", "action_type": action.type}
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        action=action,
                        observation=observation,
                    )
                )
                return RunResult(
                    status="success",
                    final_message=str(action.arguments.get("message", "")),
                    steps=steps,
                )

            if self.guardrail_engine is not None:
                decision = self.guardrail_engine.check(action)
                if decision.status != "allowed":
                    approval_id = None
                    if decision.status == "needs_approval" and self.approval_store is not None:
                        approval_id = self.approval_store.create(action, decision.reason).id
                    observation = {
                        "kind": "guardrail_result",
                        "status": decision.status,
                        "reason": decision.reason,
                    }
                    if approval_id is not None:
                        observation["approval_id"] = approval_id
                    steps.append(
                        LoopStep(
                            index=index,
                            llm_response=response.content,
                            action=action,
                            observation=observation,
                        )
                    )
                    return RunResult(
                        status=decision.status,
                        final_message=decision.reason,
                        steps=steps,
                        approval_id=approval_id,
                    )

            if self.tool_registry is None:
                observation = {"kind": "action_parsed", "action_type": action.type}
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        action=action,
                        observation=observation,
                    )
                )
                messages.append(
                    {
                        "role": "system",
                        "content": f"observation: parsed action {action.type}; tools are not connected yet",
                    }
                )
                continue

            if action.type == "run_validation" and validation_count >= self.max_validations:
                observation = {
                    "kind": "validation_control",
                    "status": "budget_exhausted",
                    "validation_count": validation_count,
                    "max_validations": self.max_validations,
                }
                steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=observation))
                return RunResult(
                    status="validation_budget_exhausted",
                    final_message="Validation budget exhausted before another validation run.",
                    steps=steps,
                )

            tool_result = self.tool_registry.dispatch(action)
            if self.validator is not None and action.type == "run_validation":
                validation_count += 1
                feedback = self.validator.validate(tool_result)
                observation = feedback.to_observation()
                context_observation = self.validator.context_observation(feedback)
                if feedback.passed:
                    completion_blocker = None
                    previous_failure = None
                    repeated_failure_count = 0
                else:
                    completion_blocker = "validation has not passed"
                    failure_key = (feedback.kind, feedback.summary)
                    repeated_failure_count = (
                        repeated_failure_count + 1 if failure_key == previous_failure else 1
                    )
                    previous_failure = failure_key
                    observation["failure_count"] = repeated_failure_count
                    context_observation["failure_count"] = repeated_failure_count
            else:
                observation = tool_result.to_observation(action.type)
                context_observation = observation
                if (
                    self.validator is not None
                    and action.type == "write_file"
                    and tool_result.ok
                    and self._is_code_change(str(action.arguments.get("path", "")))
                ):
                    completion_blocker = "workspace changes require validation"
            steps.append(
                LoopStep(
                    index=index,
                    llm_response=response.content,
                    action=action,
                    observation=observation,
                )
            )
            messages.append(
                {
                    "role": "system",
                    "content": f"tool_result: {context_observation}",
                }
            )
            if (
                action.type == "run_validation"
                and self.validator is not None
                and not feedback.passed
                and repeated_failure_count >= self.max_repeated_failures
            ):
                return RunResult(
                    status="repeated_validation_failure",
                    final_message="Repeated validation failure circuit opened.",
                    steps=steps,
                )

        return RunResult(
            status="max_steps",
            final_message="Reached max steps without finish action.",
            steps=steps,
        )

    def resume(self, approval_id: str, task: str) -> RunResult:
        if self.approval_store is None:
            raise ApprovalError("approval store is not configured")
        if self.tool_registry is None:
            raise ApprovalError("tools are not connected")

        record = self.approval_store.get(approval_id)
        self.approval_store.consume(approval_id, record.action)
        tool_result = self.tool_registry.dispatch(record.action)
        validation_count = 0
        completion_blocker: str | None = None
        previous_failure: tuple[str, str] | None = None
        repeated_failure_count = 0
        if self.validator is not None and record.action.type == "run_validation":
            validation_count = 1
            feedback = self.validator.validate(tool_result)
            observation = feedback.to_observation()
            context_observation = self.validator.context_observation(feedback)
            if not feedback.passed:
                completion_blocker = "validation has not passed"
                previous_failure = (feedback.kind, feedback.summary)
                repeated_failure_count = 1
                observation["failure_count"] = repeated_failure_count
                context_observation["failure_count"] = repeated_failure_count
        else:
            observation = tool_result.to_observation(record.action.type)
            context_observation = observation

        messages = self._initial_messages(task)
        messages.append(
            {
                "role": "system",
                "content": f"approved_tool_result: {context_observation}",
            }
        )
        steps = [
            LoopStep(
                index=0,
                llm_response="[approved action resumed]",
                action=record.action,
                observation={
                    **observation,
                    "approval_id": approval_id,
                    "approval_status": "consumed",
                },
            )
        ]

        for index in range(1, self.max_steps + 1):
            response = self.llm.generate(messages)
            try:
                action = parse_action(response.content)
            except ActionParseError as exc:
                observation = {"kind": "parse_error", "message": str(exc)}
                steps.append(LoopStep(index=index, llm_response=response.content, observation=observation))
                messages.append({"role": "system", "content": f"parse_error: {exc}"})
                continue

            if action.type == "finish":
                if completion_blocker is not None:
                    rejected = {"kind": "completion_rejected", "reason": completion_blocker}
                    steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=rejected))
                    messages.append({"role": "system", "content": f"completion_rejected: {completion_blocker}"})
                    continue
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        action=action,
                        observation={"kind": "action_parsed", "action_type": "finish"},
                    )
                )
                return RunResult(
                    status="success",
                    final_message=str(action.arguments.get("message", "")),
                    steps=steps,
                )

            decision = self.guardrail_engine.check(action) if self.guardrail_engine else None
            if decision is not None and decision.status != "allowed":
                next_id = None
                if decision.status == "needs_approval":
                    next_id = self.approval_store.create(action, decision.reason).id
                guardrail_observation = {
                    "kind": "guardrail_result",
                    "status": decision.status,
                    "reason": decision.reason,
                }
                if next_id:
                    guardrail_observation["approval_id"] = next_id
                steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=guardrail_observation))
                return RunResult(decision.status, decision.reason, steps, approval_id=next_id)

            if action.type == "run_validation" and validation_count >= self.max_validations:
                control = {
                    "kind": "validation_control",
                    "status": "budget_exhausted",
                    "validation_count": validation_count,
                    "max_validations": self.max_validations,
                }
                steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=control))
                return RunResult("validation_budget_exhausted", "Validation budget exhausted before another validation run.", steps)

            next_result = self.tool_registry.dispatch(action)
            if self.validator is not None and action.type == "run_validation":
                validation_count += 1
                next_feedback = self.validator.validate(next_result)
                next_observation = next_feedback.to_observation()
                next_context_observation = self.validator.context_observation(next_feedback)
                if next_feedback.passed:
                    completion_blocker = None
                    previous_failure = None
                    repeated_failure_count = 0
                else:
                    completion_blocker = "validation has not passed"
                    failure_key = (next_feedback.kind, next_feedback.summary)
                    repeated_failure_count = repeated_failure_count + 1 if failure_key == previous_failure else 1
                    previous_failure = failure_key
                    next_observation["failure_count"] = repeated_failure_count
                    next_context_observation["failure_count"] = repeated_failure_count
            else:
                next_observation = next_result.to_observation(action.type)
                next_context_observation = next_observation
            steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=next_observation))
            messages.append({"role": "system", "content": f"tool_result: {next_context_observation}"})
            if (
                action.type == "run_validation"
                and self.validator is not None
                and not next_feedback.passed
                and repeated_failure_count >= self.max_repeated_failures
            ):
                return RunResult("repeated_validation_failure", "Repeated validation failure circuit opened.", steps)

        return RunResult("max_steps", "Reached max steps without finish action.", steps)

    def _initial_messages(self, task: str) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": ACTION_PROTOCOL},
            {"role": "user", "content": task},
        ]
        if self.memory_store is None:
            return messages

        memory_context = self._build_memory_context(task)
        if not memory_context:
            return messages
        return [messages[0], {"role": "system", "content": memory_context}, *messages[1:]]

    def _build_memory_context(self, task: str) -> str:
        if self.memory_context_budget < len("memory_context:\n"):
            return ""

        lines = []
        used = len("memory_context:\n")
        for item in self.memory_store.retrieve(task):
            line = f"- {item.content}"
            projected = used + len(line) + 1
            if projected > self.memory_context_budget:
                continue
            lines.append(line)
            used = projected

        if not lines:
            return ""
        return "memory_context:\n" + "\n".join(lines)

    @staticmethod
    def _is_code_change(path: str) -> bool:
        lowered = path.lower()
        code_suffixes = (
            ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt",
            ".c", ".h", ".cc", ".cpp", ".cs", ".go", ".rs", ".rb", ".php",
            ".sh", ".ps1", ".sql", ".lean", ".toml", ".yaml", ".yml",
        )
        config_names = {
            "dockerfile", "makefile", "pyproject.toml", "package.json",
            "package-lock.json", "requirements.txt",
        }
        name = lowered.replace("\\", "/").rsplit("/", 1)[-1]
        return lowered.endswith(code_suffixes) or name in config_names
