---
description: Run the full definition-of-done quality gate
---

Run the project's full quality gate and fix any failures you introduced:

```sh
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
uv run coverage report --include='src/tama/domain/*' --fail-under=100
```

Report a concise summary: which steps passed or failed, and what you fixed. Don't weaken
lint/type/coverage config to make something pass; fix the code. If a rule seems genuinely
wrong, explain why and ask first.
