from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path
from typing import Any

from safecodeloop.approval import ApprovalStore
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import MockLLM
from safecodeloop.loop import AgentLoop, RunResult
from safecodeloop.redaction import SecretRedactor, redact_value
from safecodeloop.tools import create_agent_tool_registry


_DEMO_TASK = "Demonstrate validation feedback and governed human approval."
_DEMO_APPROVAL_PATTERN = r"^echo\s+approved-demo-action$"
_DEMO_ACTIONS = (
    {
        "type": "write_file",
        "path": "demo_target.py",
        "content": "def answer():\n    return 0\n",
    },
    {
        "type": "write_file",
        "path": "demo_check.py",
        "content": (
            "from demo_target import answer\n\n"
            "if answer() != 42:\n"
            "    raise AssertionError('1 failed')\n"
            "print('1 passed')\n"
        ),
    },
    {"type": "run_validation", "command": "python demo_check.py"},
    {
        "type": "write_file",
        "path": "demo_target.py",
        "content": "def answer():\n    return 42\n",
    },
    {"type": "run_validation", "command": "python demo_check.py"},
    {"type": "run_command", "command": "echo approved-demo-action"},
    {
        "type": "finish",
        "message": "Feedback correction and approved action completed.",
    },
)


class DemoError(RuntimeError):
    pass


def run_main_contribution_demo(
    decision: str = "approve",
    output_dir: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    if decision not in {"approve", "reject"}:
        raise DemoError(f"unsupported demo decision: {decision}")

    root = (
        Path(tempfile.mkdtemp(prefix="safecodeloop-demo-"))
        if output_dir is None
        else Path(output_dir)
    )
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    redactor = SecretRedactor()
    approval_store = ApprovalStore(
        root / "approval-state.json",
        signing_key=secrets.token_bytes(32),
    )
    loop = AgentLoop(
        llm=MockLLM(
            [json.dumps(action) for action in _DEMO_ACTIONS],
            redactor=redactor,
        ),
        max_steps=6,
        tool_registry=create_agent_tool_registry(workspace),
        guardrail_engine=GuardrailEngine(
            workspace,
            approval_required_patterns=(_DEMO_APPROVAL_PATTERN,),
        ),
        validator=Validator(),
        approval_store=approval_store,
        redactor=redactor,
    )

    initial_result = loop.run(_DEMO_TASK)
    if initial_result.status != "needs_approval" or not initial_result.approval_id:
        raise DemoError(
            "main-contribution demo did not reach the expected approval boundary"
        )

    approval_id = initial_result.approval_id
    pending_record = approval_store.get(approval_id)
    final_record = pending_record
    transitions = [pending_record.status]
    resumed_result: RunResult | None = None
    feedback_sequence = [
        str(step.observation["feedback_kind"])
        for step in initial_result.steps
        if step.observation.get("kind") == "feedback"
    ]
    if feedback_sequence != ["test_failure", "pass"]:
        raise DemoError(
            "main-contribution demo did not produce test_failure followed by pass"
        )

    if decision == "approve":
        transitions.append(approval_store.approve(approval_id).status)
        resumed_result = loop.resume(approval_id, _DEMO_TASK)
        final_record = approval_store.get(approval_id)
        transitions.append(final_record.status)
        if transitions[-1] != "consumed" or resumed_result.status != "success":
            raise DemoError(
                "approved demo action was not consumed and completed successfully"
            )
        final_status = resumed_result.status
    else:
        final_record = approval_store.reject(approval_id)
        transitions.append(final_record.status)
        final_status = "rejected"

    audit = redact_value(
        {
            "schema_version": 1,
            "demo": "main-contribution",
            "decision": decision,
            "feedback_sequence": feedback_sequence,
            "approval": {
                "id": pending_record.id,
                "action_hash": pending_record.action_hash,
                "action_hash_algorithm": "HMAC-SHA256",
                "run_id": pending_record.run_id,
                "step_id": pending_record.step_id,
                "rule_id": pending_record.rule_id,
                "reason": pending_record.reason,
                "created_at": pending_record.created_at,
                "updated_at": final_record.updated_at,
                "transitions": transitions,
            },
            "initial_run": _run_result_payload(initial_result),
            "resumed_run": (
                None
                if resumed_result is None
                else _run_result_payload(resumed_result)
            ),
            "final_status": final_status,
        },
        redactor=redactor,
    )
    audit_path = root / "main-contribution-audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return audit, audit_path


def _run_result_payload(result: RunResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "final_message": result.final_message,
        "approval_id": result.approval_id,
        "steps": [
            {
                "index": step.index,
                "llm_response": step.llm_response,
                "action": (
                    None
                    if step.action is None
                    else {
                        "type": step.action.type,
                        "arguments": step.action.arguments,
                    }
                ),
                "observation": step.observation,
            }
            for step in result.steps
        ],
    }
