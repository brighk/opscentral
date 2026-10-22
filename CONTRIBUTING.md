# Contributing to OpsCentral

Thanks for your interest in contributing! This guide covers how to set up the
project locally and what we expect from a pull request.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python (it installs the right Python version for you)
- Node.js 22 and npm
- Docker, for PostgreSQL/TimescaleDB and Redis

## Setup

```bash
git clone https://github.com/brighk/opscentral.git
cd opscentral
make install        # uv sync for backend + agent, npm ci for frontend, git hooks
make db-up          # start PostgreSQL and Redis
```

See [docs/getting-started.md](docs/getting-started.md) for running the full stack.

## Project layout

| Directory   | What it is                          | Tooling                      |
|-------------|-------------------------------------|------------------------------|
| `backend/`  | FastAPI API + Celery workers        | uv, ruff, pyright, pytest    |
| `agent/`    | Monitoring agent (Linux/Win/macOS)  | uv, ruff, pyright            |
| `frontend/` | React + Mantine dashboard           | npm, eslint, tsc             |

The backend and agent are separate uv projects with their own `uv.lock`. The agent
supports Python 3.10+, because it runs on customer machines that may have older
Python versions; the backend requires 3.12+.

## Checks

Pre-commit hooks run automatically on `git commit` (installed by `make install`).
They run ruff (lint + format), pyright, eslint, tsc, and a secret scanner on the
parts of the repo you changed. To run everything:

```bash
make lint           # all pre-commit hooks on all files
make test           # backend test suite
```

CI runs the same hooks plus the tests and builds on every pull request; all checks
must pass before a PR can merge.

## Dependencies

- Python: `uv add <pkg>` (or `uv add --dev <pkg>`) inside `backend/` or `agent/`.
  Commit the updated `uv.lock`.
- Frontend: `npm install <pkg>` inside `frontend/`. Commit `package-lock.json`.

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Keep PRs focused; one logical change per PR is easiest to review.
3. Add or update tests for behavior changes.
4. Fill in the PR template.

PRs are squash-merged, so the PR title becomes the commit message; make it
descriptive.

### Security-sensitive areas

The agent runs with elevated privileges on monitored machines and can execute
remote actions. Changes to `agent/`, `install.sh`, `install.ps1`,
`backend/app/remote_actions/`, `backend/app/runbooks/` or authentication code get
extra scrutiny; please explain the security impact in your PR description.

If you find a security vulnerability, please **do not open a public issue**.
Report it privately through GitHub's
[security advisories](https://github.com/brighk/opscentral/security/advisories/new).
