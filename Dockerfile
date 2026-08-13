FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

COPY demos ./demos
COPY SPEC.md PLAN.md SPEC_PROCESS.md AGENT_LOG.md ./

ENTRYPOINT ["safecodeloop"]
CMD ["--help"]
