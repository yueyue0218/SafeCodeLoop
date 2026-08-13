# Release Checklist

## Required Before Creating Release

- [ ] `python -m pytest` passes locally.
- [ ] `.gitlab-ci.yml` contains a `unit-test` job that runs `python -m pytest`.
- [ ] `Dockerfile` and `.dockerignore` are present.
- [ ] Docker build is verified when Docker Desktop is available.
- [ ] `README.md` is complete.
- [ ] `REFLECTION.md` is reviewed and personalized by the project author.
- [ ] `submission.jsonc` is outside the source archive and filled with real student/repository/release values.

## Package Command

```powershell
.\scripts\package_release.ps1
```

Expected output:

```text
release\SafeCodeLoop-0.1.0.zip
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

## Known Pending Items

- Docker build is pending until Docker Desktop is installed and running.
- README and reflection are handled in Phase 8.
- GitHub/NJU Git release URL is handled in T7.4.
