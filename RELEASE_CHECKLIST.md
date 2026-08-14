# Release Checklist

## Required Before Creating Release

- [x] `python -m pytest` passes locally (`116 passed`).
- [x] `.gitlab-ci.yml` contains a `unit-test` job that runs `python -m pytest`.
- [x] GitHub Actions verifies tests, distributions, and isolated wheel installation.
- [x] `Dockerfile` and `.dockerignore` are present.
- [x] Docker image builds and CLI smoke tests pass in the container.
- [x] `README.md` is complete.
- [x] `REFLECTION.md` is reviewed and personalized by the project author.
- [x] `submission.jsonc` is outside the source archive and filled with real student/repository/release values.

## Package Command

```powershell
.\scripts\package_release.ps1
```

Expected output:

```text
release\SafeCodeLoop-0.1.0.zip
release\safecodeloop-0.1.0-py3-none-any.whl
release\safecodeloop-0.1.0.tar.gz
release\SHA256SUMS
```

## Archive Must Include

- `src/`
- `tests/`
- `demos/`
- `SPEC.md`
- `PLAN.md`
- `SPEC_PROCESS.md`
- `AGENT_LOG.md`
- `.gitlab-ci.yml`
- `Dockerfile`
- `.dockerignore`
- `pyproject.toml`
- `safecodeloop.config.example.json`

## Archive Must Not Include

- `.git/`
- `.env` or `.env.*`
- `.safecodeloop/`
- `__pycache__/`
- `.pytest_cache/`
- `.pyc`
- local run logs
- real API keys or credentials

## Final Release Verification

- [x] Record Docker image build and container smoke results.
- [x] Generate the final source archive from tracked files and record the source commit in `BUILD_INFO.txt`.
- [x] Build the wheel and source distribution.
- [x] Generate SHA-256 checksums for the zip, wheel, and source distribution.
- [x] Install the wheel in a new virtual environment and run `--help` and `--version`.
- [x] Point `v0.1.0` at the final `main` commit and attach all four artifacts to the GitHub Release.
- [x] Verify the public Release URL without relying on a repository checkout.
