# CLAUDE.md

Guidance for Claude Code when working in this repository. Read this file fully before
starting any task, then read the docs it links to that are relevant to the task.

## Project

**tama** — a terminal (TUI) virtual pet in the spirit of the original Tamagotchi.
The pet hatches, grows through life stages, gets hungry/unhappy/dirty/sick over time
(including while the app is closed), and is cared for through keyboard actions. It is
animated with colour pixel-art sprites (block characters) and its state is persisted between sessions.

The goal is a **quality** codebase: strict typing, high test coverage, clean
architecture, reproducible tooling, and a polished user experience.

| Document | Purpose |
| --- | --- |
| [`docs/SPEC.md`](docs/SPEC.md) | Product spec: game mechanics, stats, life cycle, UI, controls |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layering, module layout, key design decisions |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Ordered milestones with acceptance criteria — **work through these in order** |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy, tooling and conventions |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records (why things are the way they are) |

## Tech stack

- **Python 3.12+**, managed with **[uv](https://docs.astral.sh/uv/)** (`uv.lock` committed)
- **[Textual](https://textual.textualize.io/)** — TUI framework (widgets, CSS, timers, test pilot)
- **[Pydantic v2](https://docs.pydantic.dev/)** — save-file schema, validation, (de)serialisation
- **[platformdirs](https://pypi.org/project/platformdirs/)** — OS-correct save/config locations
- **[Typer](https://typer.tiangolo.com/)** — CLI entrypoint (`tama`, `tama --new`, `tama --save-path`, ...)
- Dev: **pytest**, **pytest-asyncio**, **pytest-cov**, **hypothesis**, **pytest-textual-snapshot**,
  **mypy** (strict), **ruff** (lint + format), **pre-commit**

Do not add new runtime dependencies without recording the reason in a new ADR.

## Commands

If `uv` is missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```sh
uv sync                                  # install deps (incl. dev group) into .venv
uv run tama                              # run the game
TEXTUAL=devtools uv run tama           # run with Textual devtools (pair with `uv run textual console`)
uv run tama --save-path /tmp/t.json --speed 600   # quick manual play-through on a throwaway save

uv run ruff format .                     # format
uv run ruff check . --fix                # lint
uv run mypy                              # type-check (strict, config in pyproject.toml)
uv run pytest                            # all tests + coverage
uv run pytest tests/unit -q              # fast unit tests only
uv run pytest --snapshot-update          # regenerate UI snapshots (review the diff!)
uv run python tools/generate_sprites.py  # regenerate the pixel-art sprite set (see /add-sprite)
```

**Definition of done for any change** — all of these must pass:

```sh
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
```

The `/check` slash command runs exactly this.

## Architecture rules (non-negotiable)

See `docs/ARCHITECTURE.md` for detail. Summary:

1. **`tama.domain` is pure.** No imports from `textual`, `rich`, `pydantic`, `platformdirs`,
   no I/O, no `datetime.now()`, no `random` module globals. Time is passed in; randomness
   comes from an injected `random.Random`. This makes the simulation deterministic and
   trivially testable.
2. **Dependencies point inward:** `ui` → `app services` → `domain`; `persistence` → `domain`.
   The domain never imports outward. `import-linter` contracts in `pyproject.toml` enforce this.
3. **Time is injected** via a `Clock` protocol. Never call `datetime.now()`/`time.time()`
   outside `tama.infra.clock`.
4. **Simulation is tick-based and catch-up capable:** `advance(state, elapsed)` must produce
   the same result whether called once for 10 minutes or 600 times for 1 second (within
   documented tolerance). Offline time is simulated on load (capped, see SPEC).
5. **Saves are versioned and atomic.** Every save file has `schema_version`. Write to a temp
   file in the same dir, `fsync`, then `os.replace`. Keep one `.bak`. Never crash on a corrupt
   save — surface a recoverable error to the user.
6. **Sprites are data, not code.** Pixel-art frames live in `src/tama/assets/sprites/**/*.toml`
   and are loaded via `importlib.resources` (format: ADR 0003 and `/add-sprite`).

## Code conventions

- Fully typed; `mypy --strict` clean. No `Any` without a justifying comment. No `# type: ignore`
  without an error code and reason.
- Prefer `@dataclass(frozen=True, slots=True)` for domain value objects; state transitions return
  new objects (functional core) rather than mutating.
- Use `enum.StrEnum` for closed sets (life stage, mood, action).
- Domain numbers: stats are `int` in `0..100` clamped via one helper; durations are
  `datetime.timedelta`; timestamps are timezone-aware UTC `datetime`.
- Docstrings (Google style) on public functions/classes. Comments explain *why*, not *what*.
- Logging via `logging` (`logging.getLogger(__name__)`), never `print`. Logs go to a file in the
  platformdirs log dir, never to the terminal (it would corrupt the TUI).
- Errors: define exceptions in `tama/errors.py`, derived from `TamaError`.
- Keep modules small and cohesive (< ~300 lines). Tests mirror the `src/` layout.

## Workflow expectations

- Work milestone-by-milestone from `docs/ROADMAP.md`. Tick off checkboxes as items land.
- Write/extend tests **with** every change (test-first for domain logic). Coverage gate: 90%
  overall, 100% branch coverage for `tama.domain`.
- Small, focused commits using [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`).
- When a decision deviates from or extends these docs, update the docs in the same change and
  add an ADR for anything architectural.
- If a UI snapshot changes, inspect the SVG diff before accepting with `--snapshot-update`.
- Do not commit `.venv/`, save files, logs, or `snapshot_report.html`; do commit the snapshot
  files under `__snapshots__/` (SVG content, `.raw` extension).
