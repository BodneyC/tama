# Roadmap

Work through milestones **in order**. Each milestone ends with the full check passing
(`/check`) and a commit (or several). Tick boxes as you go. Don't start UI work before the
domain milestone is green — the domain is the foundation.

## M0 — Project skeleton

- [x] `uv sync` works; `uv.lock` committed
- [x] `src/tama/` package with `__init__.py` (`__version__` from package metadata), `__main__.py`, `py.typed`
- [x] `cli.py` Typer app with `--version`; `tama` script entry point
- [x] `errors.py` with `TamaError` base
- [x] `infra/clock.py`: `Clock` protocol, `SystemClock`, `FakeClock`, `ScaledClock` + tests
- [x] `tests/conftest.py` with save-dir isolation fixture; `tests/factories.py` stub
- [x] Ruff, mypy, pytest, import-linter all run green on the skeleton
- [x] pre-commit hooks installed and passing
- [x] CI workflow green (Linux/macOS/Windows × 3.12/3.13 verified; macOS since disabled in CI)

**Accept:** `uv run tama --version` prints the version; `/check` passes.

## M1 — Domain core

- [ ] `Stats`, `clamp`, `Balance` with defaults from SPEC §2.1
- [ ] `Pet`, `LifeStage`, `Variant`; `new_egg(name, now, rng)`
- [ ] `events.py` event types
- [ ] `simulation.advance` — decay (awake/asleep), poop generation, sickness rolls, health
      damage, care mistakes, sleep/wake, aging, stage transitions, death
- [ ] `actions.apply` for every action in SPEC §3, including refusal reasons
- [ ] `minigame.py` Left/Right state machine
- [ ] `animation.select_animation`
- [ ] Hypothesis properties: bounds, tick-splitting equivalence, dead-is-terminal, age monotonic
- [ ] 100% branch coverage on `tama.domain`

**Accept:** A test simulates a full lifespan egg→dead with a fixed seed and asserts the
expected sequence of stage events.

## M2 — Persistence

- [ ] `SaveFileV1` Pydantic model + domain mapping (incl. RNG state via `getstate()`)
- [ ] `JsonSaveRepository`: atomic write, `.bak` rotation, load-with-fallback
- [ ] Corrupt/missing/unwritable handling with typed errors
- [ ] Migration framework + test that a v1 fixture file in `tests/fixtures/saves/` loads
- [ ] `infra/paths.py`, `infra/config.py` (TOML + env + CLI precedence)

**Accept:** Round-trip property test: `load(save(pet)) == pet` for arbitrary pets.

## M3 — Services

- [ ] `GameSession`: `load_or_create`, `tick(now)`, `act(action)`, offline catch-up with cap,
      event aggregation for away summary, clock-went-backwards handling
- [ ] Autosave policy (interval, after action, on stage change, on shutdown)
- [ ] `tama status` CLI subcommand (no TUI)

**Accept:** Integration test: create pet → advance FakeClock 5 h → reload → away-summary
events match expectations; file on disk is valid.

## M4 — TUI foundation

- [ ] `TamaApp` with screen stack, bindings, 1 s tick timer, `app.tcss`
- [ ] `MainScreen` with header (name/stage/age/stat icons), stage area, footer
- [ ] `NewPetScreen` (name input with validation), `HelpScreen`, `StatusScreen` (stat bars)
- [ ] All actions wired; refusal toasts; quit saves
- [ ] Terminal-too-small notice; SIGTERM/SIGHUP save
- [ ] Pilot tests for each binding; first snapshot tests

**Accept:** Playable end-to-end with a static (single-frame) sprite.

## M5 — Animation & art

- [ ] Sprite file format + loader + asset validation test
- [ ] `PetView` widget: looped + one-shot playback, wandering, blink
- [ ] Full sprite set for default variant (all stages × animations in SPEC §5.2) and a second
      adult variant
- [ ] Hatch and evolve sequences; Zzz/sick/poop overlays; lights-off dimming
- [ ] `--reduced-motion`; `NO_COLOR` respected; looks good on light & dark themes

**Accept:** Snapshot tests for each life stage's idle key frame; manual check at `--speed 600`.

## M6 — Remaining screens & polish

- [ ] `FeedMenu`, `MiniGameScreen`, `AwaySummaryScreen`, `MemorialScreen`, `ErrorScreen`
- [ ] Attention calls with blinking indicator + optional bell
- [ ] Balancing pass: play at `--speed 60` for a full life; adjust `Balance` only
- [ ] Logging to file; no stray terminal output

**Accept:** A complete life can be played start to finish; every screen has a snapshot test.

## M7 — Release readiness

- [ ] README with screenshot/GIF (e.g. via `vhs` or `asciinema`), install instructions
      (`uv tool install`, `pipx install`)
- [ ] CHANGELOG.md (Keep a Changelog), version 1.0.0
- [ ] CI matrix: Linux/macOS/Windows × Python 3.12/3.13 on every push/PR (re-enable the commented-out
      macOS matrix entry in `.github/workflows/ci.yml`)
- [ ] Build wheel (`uv build`) and smoke-test the installed `tama` entry point in CI
- [ ] Final review against SPEC; open issues for anything deferred
