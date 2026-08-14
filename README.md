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
213 passed, 2 skipped
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

### Action output protocol

The model must return exactly one JSON action object. Field names are action-specific, all action arguments are strings, unknown or duplicate fields are rejected, and required command/path/content fields are validated before any guardrail or tool can run.

```json
{"type":"read_file","path":"README.md"}
```

For recovery from common model formatting mistakes, the parser can extract one unambiguous object from a Markdown JSON fence or brief surrounding prose. Responses containing multiple JSON objects remain ambiguous and are rejected. A response is limited to 65,536 characters; parse-error feedback contains only a bounded reason and repair hint, never the invalid response itself.

Validation feedback is classified as `pass`, `test_failure`, `syntax_error`, `type_error`, `lint_failure`, `timeout`, `environment_error`, or `unknown_failure`. Full evidence remains in the run log, while the model receives a bounded diagnostic excerpt with the original character count and SHA-256 reference.

The validation loop has deterministic stopping controls. Code or project-configuration writes require a later passing validation before `finish` can succeed. Validation runs have a configurable budget, and repeated failures with the same category and summary open a circuit instead of looping indefinitely. These checks also apply after an approved action is resumed.

## Demos

### Recommended: One-Command Main Contribution Demo

Run the complete deterministic mechanism demo without a network connection or
API key:

```powershell
safecodeloop demo main-contribution
```

The command uses the real AgentLoop, Validator, GuardrailEngine, tools, and
ApprovalStore to demonstrate:

1. MockLLM writes an incorrect implementation.
2. Validation reports `test_failure`.
3. MockLLM corrects the implementation and validation reports `pass`.
4. A demo policy marks a harmless command as requiring human approval.
5. The default decision drives `pending -> approved -> consumed` and resumes the exact hashed action.
6. A structured `main-contribution-audit.json` records every action, observation, action hash, transition, and final status.

The concise terminal summary looks like:

```text
feedback: test_failure -> pass
approval: pending -> approved -> consumed
action_hash: <64 hexadecimal characters>
final_status: success
audit_log: <generated path>
```

By default, an isolated output directory with no date in its name is created
under the operating-system temporary directory. Select a predictable location
or demonstrate rejection with:

```powershell
safecodeloop demo main-contribution --output-dir .\demo-output
safecodeloop demo main-contribution --decision reject --output-dir .\demo-rejected
```

The governed command is deliberately harmless and local, so the approval state
machine is visible without installing a package, publishing, accessing a key,
or changing external state.

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

### Demo 3: Low-Level Combined Script

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
  "maxValidations": 4,
  "maxRepeatedFailures": 2,
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

One shared redaction layer sanitizes LLM input/output, AgentLoop boundaries, CLI results and errors, and the complete run-log structure before serialization. It recognizes bearer tokens, common API-key/token/password fields, `sk-...` values, and the exact credential loaded for a real-provider run. Runtime values shorter than 8 characters are deliberately not registered as exact secrets because replacing common short strings would corrupt normal diagnostics; do not use short values as real credentials.

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

Each approval keeps a stable HMAC-SHA256 action hash and a separate HMAC signature over the complete record envelope: approval ID, action, action hash, reason, status, run ID, step ID, rule ID, and timestamps. Every legal state transition re-signs the record with the key stored in the OS keyring. Rejected, modified, copied under another ID, already consumed, malformed, or tampered records fail closed. Records created by versions without the complete-record signature are intentionally rejected and must be recreated. Approval files may contain action arguments, so `.safecodeloop/` remains local and excluded from Git.

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

- Docker Desktop Engine 29.7.2 built `safecodeloop:0.1.0` successfully.
- Container `--help` and `--version` smoke tests pass.
- The container reproduces the deterministic failure-correction-pass demo without an API key.
- The image excludes Git metadata, release output, local approval state, and the private execution plan.

The release image includes `pytest` so the feedback demo runs without extra installation. Safe mock runs initialize no credential backend; OS keyring access remains lazy and is required only when an approval record is created or resumed.

## Release Package

Generate the source archive, wheel, source distribution, and SHA-256 manifest from a clean commit:

```powershell
.\scripts\package_release.ps1
```

Outputs:

```text
release\SafeCodeLoop-0.2.0.zip
release\safecodeloop-0.2.0-py3-none-any.whl
release\safecodeloop-0.2.0.tar.gz
release\SHA256SUMS
```

The packaging script refuses tracked-file changes, uses `git ls-files`, records the source commit in `BUILD_INFO.txt`, and checks that the archive does not contain `.git`, `.env`, `.safecodeloop`, cache files, `.pyc`, or logs. Verify downloads against `SHA256SUMS` before installation. Installing the wheel normally requires network access for its `keyring` dependency unless that dependency is already cached.

Public release: <https://github.com/yueyue0218/SafeCodeLoop/releases/tag/v0.2.0>

## Author and License

SafeCodeLoop is authored by 曹潇月 and released under the [MIT License](LICENSE).
The project implements its agent loop, action protocol, guardrails, feedback
control, tools, memory, and configuration in this repository; development use
of AI assistance is documented in `AGENT_LOG.md` and `REFLECTION.md`.

Direct runtime, build, and test dependency licenses are recorded in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md): `keyring` provides runtime
credential storage, `setuptools` is the build backend, `build` creates release
artifacts, and `pytest` runs the test suite. Transitive dependency terms must be
reviewed for the exact environment used when redistributing the project.

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
LICENSE                 MIT license for SafeCodeLoop
THIRD_PARTY_NOTICES.md  direct dependency license audit
.gitlab-ci.yml          CI unit-test job
.github/workflows/ci.yml GitHub test, build, and wheel smoke test
Dockerfile              container distribution file
```

## Safety Boundary

Every command and file action receives a deterministic `allowed`, `blocked`, or `needs_approval` decision before dispatch. Decisions include a stable `rule_id`, severity, and reason; matching blocked rules take priority over approval rules, and approval rules take priority over the default allow decision.

Built-in rules fail closed for destructive deletion variants across POSIX, PowerShell, and cmd; shell obfuscation; parent traversal; workspace/symlink escapes; and sensitive files such as `.env`, SSH keys, credential files, and `.safecodeloop` approval data. Dependency installation, publishing/deployment, external writes, nested shells, and compound commands require approval. `blockedCommandPatterns` and `approvalRequiredPatterns` add case-insensitive regular-expression rules; invalid expressions are rejected when configuration is loaded.

SafeCodeLoop is a teaching harness, not a production sandbox. Allowed commands still run through the host shell, so deterministic rules cannot enumerate every indirect side effect or obfuscation. Use temporary workspaces for demos and do not run untrusted scripts.

## Known Limitations

- Core tests and deterministic demos use `MockLLM`; real-provider runs require network access, a configured key, and an available compatible model.
- A usable OS keyring backend must be available on the target system.
- Pattern redaction cannot identify every previously unknown proprietary secret format; operators must still avoid placing credentials in tasks, source files, or shell commands.
- Complete-record signatures detect modification and ordinary copy/replay attempts, but a privileged attacker who can roll back the entire approval file to a previously valid signed snapshot remains outside this local-file state machine's rollback guarantees.
- WebUI is intentionally not implemented; this follows the CLI-only plus release-link route allowed for Agent Harness submissions.
- Python wheel installation requires access to the declared `keyring` dependency unless it is already available locally.
