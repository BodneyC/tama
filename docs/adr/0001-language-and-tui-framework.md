# ADR 0001: Python + Textual for the TUI

- **Status:** Accepted
- **Date:** 2026-11-02

## Context

We need a cross-platform terminal app with smooth frame-based animation, multiple screens and
modals, good styling on light/dark terminals, persistence, and — critically — a strong story
for automated testing of the UI. The codebase should be approachable and strictly typed.

Candidates considered:

| Option | Pros | Cons |
| --- | --- | --- |
| **Python + Textual** | Rich widget/screen model, CSS styling, built-in timers/animation, async headless `Pilot` testing, official SVG snapshot plugin, themes, excellent docs. Fully typed. | Python startup time (~200–400 ms); distribution needs Python (mitigated by `uv tool`/`pipx`). |
| Rust + ratatui | Single static binary, fast, strong types. | Immediate-mode: screens, focus, modals, layout all hand-rolled; UI testing via buffer asserts only; much more code for the same polish. |
| Go + Bubble Tea | Single binary, Elm architecture is a good fit, `teatest`. | Less type expressiveness; fewer built-in widgets; styling more manual. |

## Decision

Python 3.12+ with Textual. Supporting libraries: Pydantic v2 (save schema & validation),
platformdirs (paths), Typer (CLI). Tooling: uv, ruff, mypy --strict, pytest (+asyncio, cov,
hypothesis, textual-snapshot), import-linter, pre-commit.

## Consequences

- UI behaviour and appearance are testable in CI headlessly.
- Strict typing plus a pure, framework-free domain layer keeps logic portable: if a single
  binary becomes a requirement, the domain could be ported or the app packaged with PyInstaller.
- Users need Python ≥ 3.12 or `uv`, documented in the README.
