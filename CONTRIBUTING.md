# Contributing

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest
```

## Workflow

- Branch from `main`: `feat/…`, `fix/…`, `chore/…`.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(router): …`, `fix(flow): …`). The changelog is built from them.
- Keep PRs small and about one thing. Flow JSON diffs are hard to review, so describe the caller-facing change in words.
- CI must be green. Prod deploys need an approval on the `production` environment.

## Conventions

- The call tree model (`calltree.py`) is the contract. Vendor-specific exports get a small adapter that outputs this YAML. Don't special-case vendors in the converter.
- Anything that changes generated flows needs a test asserting the exact blocks, and the sample flow must stay lint-clean.
- Wave planning rules come from real cutovers. Explain the reason in the docstring when you add one.
- Comments explain *why*. The code already says what.
