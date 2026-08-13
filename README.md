# SafeCodeLoop

[![CI](https://github.com/yueyue0218/SafeCodeLoop/actions/workflows/ci.yml/badge.svg)](https://github.com/yueyue0218/SafeCodeLoop/actions/workflows/ci.yml)

SafeCodeLoop is a minimal coding agent harness for the AI4SE final project. It demonstrates how a coding agent can be wrapped with deterministic engineering mechanisms instead of relying only on prompts.

The main contribution is:

> Guardrails before execution + test feedback loop after execution.

It is CLI-only. The project uses mock LLM scripts for deterministic tests and demos, so graders can verify the behavior without an API key or network access.

## Features

- Custom agent loop.
- JSON action parser.
- Mock LLM interface.
- Workspace-scoped file tools.
- Controlled command execution.
- Explicit validation actions separated from ordinary commands.
- Deterministic guardrail engine.
- Persistent one-time human approval workflow.
- Test feedback classifier.
- Memory/context store.
- JSON config loader.
- API key status/set/clear commands.
- CLI demos for dangerous-action blocking, feedback correction, and the combined contribution mechanism.

## Requirements

- Python 3.11 or newer.
- `pytest` for tests.
- Docker Desktop is optional for container verification.

## Install

From the repository root:

```powershell
python -m pip install -e .
python -m pip install pytest
```

Check the CLI:

```powershell
safecodeloop --help
python -m safecodeloop --help
python -m safecodeloop.cli --help
```

## Run Tests

```powershell
python -m pytest
```

Current local result:

```text
100 passed
```

## CLI Usage

Run a mock-scripted task:

```powershell
safecodeloop run --mock-script demos\feedback_correction.json --workspace .\tmp-workspace --log .\run-log.json correct a failing implementation
```

The run log records each step:

- raw mock LLM response
- parsed action
- tool result or feedback
- guardrail result
- final status

## Demos

### Demo 1: Dangerous Action Blocked

```powershell
safecodeloop run --mock-script demos\dangerous_action.json --workspace .\tmp-danger --log .\danger-log.json demonstrate dangerous command blocking
```

Expected result:

- status: `blocked`
- guardrail reason includes recursive root deletion
- command is not executed by the tool layer

### Demo 2: Feedback Correction

This demo needs 6 steps, so create a small config file:

```powershell
Set-Content -Path .\demo-config.json -Value '{"maxSteps":6}'
safecodeloop run --mock-script demos\feedback_correction.json --config .\demo-config.json --workspace .\tmp-feedback --log .\feedback-log.json correct a failing implementation
```

Expected result:

- first pytest run produces `feedback_kind: test_failure`
- corrected code is written
- second pytest run produces `feedback_kind: pass`
- final status is `success`

### Demo 3: Main Contribution

```powershell
Set-Content -Path .\demo-config.json -Value '{"maxSteps":6}'
safecodeloop run --mock-script demos\governance_feedback_depth.json --config .\demo-config.json --workspace .\tmp-main --log .\main-log.json demonstrate feedback and guardrails
```

Expected result:

- pytest first reports `test_failure`
- the mock LLM writes corrected code
- pytest then reports `pass`
- a later dangerous command is blocked before execution
- final status is `blocked`

## Configuration

Example config:

```json
{
  "workspaceRoot": ".",
  "maxSteps": 5,
  "allowedTools": ["list_files", "read_file", "write_file", "run_command", "run_validation"],
  "blockedCommandPatterns": [],
  "approvalRequiredPatterns": [],
  "testCommand": "python -m pytest",
  "modelProvider": "mock",
  "model": "glm-5.2",
  "baseUrl": "https://njusehub.info/v1",
  "requestTimeout": 60,
  "credentialProvider": "njusehub",
  "memoryPath": ".safecodeloop/memory.json"
}
```

See `safecodeloop.config.example.json`.

### OpenAI-compatible provider

SafeCodeLoop can call an OpenAI-compatible `/chat/completions` endpoint while keeping the agent loop, action parsing, tools, guardrails, feedback, and stopping rules in this repository.

Store the API key securely:

```powershell
safecodeloop key set njusehub
```

Create a config file with `modelProvider` set to `openai-compatible`, select the model and base URL, then run without `--mock-script`:

```powershell
safecodeloop run --config .\real-provider.json --workspace .\tmp-real list the workspace and finish
```

The NJUSE Hub values shown in its access guide are:

```json
{
  "modelProvider": "openai-compatible",
  "model": "glm-5.2",
  "baseUrl": "https://njusehub.info/v1",
  "requestTimeout": 60,
  "credentialProvider": "njusehub"
}
```

Do not put the API key in this file. Provider and model availability can change; check the platform's model marketplace before a real run.

## Credentials

Credential commands:

```powershell
safecodeloop key status
safecodeloop key set openai
safecodeloop key clear openai
```

`key set` prompts for the secret without echoing it. SafeCodeLoop stores credentials through the operating-system keyring; on Windows this uses Windows Credential Manager. Status output reports only whether a credential exists and never displays the value or a recognizable fragment. Command-line key values are intentionally unsupported because process arguments and shell history can expose them.

The plaintext file backend is available only through explicit dependency injection for isolated tests. It is not selected by the production CLI. Do not commit `.env`, logs, local memory, or real API keys.

## Human approval workflow

Actions such as dependency installation pause before tool execution and produce an approval ID:

```text
status: needs_approval
dependency install requires approval
approval_id: <id>
```

Inspect and decide the action in a later CLI invocation:

```powershell
safecodeloop approval status <id> --workspace .\my-workspace
safecodeloop approval approve <id> --workspace .\my-workspace
# or: safecodeloop approval reject <id> --workspace .\my-workspace
```

After approval, resume the original task with the same provider configuration:

```powershell
safecodeloop run --resume <id> --config .\config.json --workspace .\my-workspace continue the task
```

Each approval is bound to an HMAC-SHA256 signature of the canonical action and can be consumed only once. The signing key is stored separately in the OS keyring. Rejected, modified, already consumed, or tampered records fail closed. Approval files may contain action arguments, so `.safecodeloop/` remains local and excluded from Git.

## Docker

Docker files are provided:

- `Dockerfile`
- `.dockerignore`

Build and run when Docker Desktop is installed:

```powershell
docker build -t safecodeloop .
docker run --rm safecodeloop --help
```

Current local verification:

- Docker CLI is available: Docker version 29.7.2.
- `docker build -t safecodeloop .` reached the base-image pull step.
- Build could not complete because the machine could not connect to Docker Hub `auth.docker.io` / `registry-1.docker.io` over port 443.

Retry the build when Docker Hub network access is available.

## Release Package

Generate a source release archive:

```powershell
.\scripts\package_release.ps1
```

Output:

```text
release\SafeCodeLoop-0.1.0.zip
```

The packaging script uses `git ls-files`, so only tracked project files are included. It also checks that the archive does not contain `.git`, `.env`, `.safecodeloop`, cache files, `.pyc`, or logs.

## Project Structure

```text
src/safecodeloop/        package source
tests/                  pytest suite
demos/                  deterministic mock LLM scripts
scripts/                release packaging script
SPEC.md                 design specification
PLAN.md                 implementation plan
SPEC_PROCESS.md         spec/process record
AGENT_LOG.md            agent collaboration log
RELEASE_CHECKLIST.md    release checklist
.gitlab-ci.yml          CI unit-test job
.github/workflows/ci.yml GitHub test, build, and wheel smoke test
Dockerfile              container distribution file
```

## Safety Boundary

SafeCodeLoop is a teaching harness, not a production sandbox. It uses deterministic guardrail checks and workspace path checks, but it still runs local commands through the host shell when `run_command` is allowed. Use temporary workspaces for demos and do not run untrusted scripts.

## Known Limitations

- Core tests and deterministic demos use `MockLLM`; real-provider runs require network access, a configured key, and an available compatible model.
- A usable OS keyring backend must be available on the target system.
- Docker build is pending until Docker Desktop is installed.
- WebUI is intentionally not implemented; this follows the CLI-only plus release-link route allowed for Agent Harness submissions.
- Release URL is created in T7.4 and should be filled after publishing a real GitHub/NJU Git release.
