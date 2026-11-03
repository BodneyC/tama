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

- [x] `Stats`, `clamp`, `Balance` with defaults from SPEC §2.1
- [x] `Pet`, `LifeStage`, `Variant`; `new_egg(name, now, rng)`
- [x] `events.py` event types
- [x] `simulation.advance` — decay (awake/asleep), poop generation, sickness rolls, health
      damage, care mistakes, sleep/wake, aging, stage transitions, death
- [x] `actions.apply` for every action in SPEC §3, including refusal reasons
- [x] `minigame.py` Left/Right state machine
- [x] `animation.select_animation`
- [x] Hypothesis properties: bounds, tick-splitting equivalence, dead-is-terminal, age monotonic
- [x] 100% branch coverage on `tama.domain`
- [x] `attention.attention_reasons` (SPEC §4)

**Accept:** A test simulates a full lifespan egg→dead with a fixed seed and asserts the
expected sequence of stage events.

## M2 — Persistence

- [x] `SaveFileV1` Pydantic model + domain mapping (incl. RNG state via `getstate()`)
- [x] `JsonSaveRepository`: atomic write, `.bak` rotation, load-with-fallback
- [x] Corrupt/missing/unwritable handling with typed errors
- [x] Migration framework + test that a v1 fixture file in `tests/fixtures/saves/` loads
- [x] `infra/paths.py`, `infra/config.py` (TOML + env + CLI precedence)

**Accept:** Round-trip property test: `load(save(pet)) == pet` for arbitrary pets.

## M3 — Services

- [x] `GameSession`: `create`/`load` (the UI picks which), `tick()`, `act(action)`,
      `finish_game(won=)`, offline catch-up with cap, away summary, clock-went-backwards handling
- [x] Autosave policy (interval, after action, on stage change, on shutdown)
- [x] `tama status` CLI subcommand (no TUI)

**Accept:** Integration test: create pet → advance FakeClock 5 h → reload → away-summary
events match expectations; file on disk is valid.

## M4 — TUI foundation

- [x] `TamaApp` with screen stack, bindings, 1 s tick timer, `app.tcss`
- [x] `MainScreen` with header (name/stage/age/stat icons), stage area, footer
- [x] `NewPetScreen` (name input with validation), `HelpScreen`, `StatusScreen` (stat bars)
- [x] All actions wired (incl. basic `FeedMenu` and `MiniGameScreen`); refusal toasts; quit saves
- [x] Terminal-too-small notice; SIGTERM/SIGHUP save
- [x] Pilot tests for each binding; first snapshot tests
- [x] `tama` launches the TUI (`--new`, `--reduced-motion`, `--quiet`, hidden `--speed`/`--seed`)

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

- [ ] `AwaySummaryScreen` (currently a toast), `MemorialScreen`, `ErrorScreen` (currently the app
      exits with a message); animate `FeedMenu` and `MiniGameScreen` (basic versions from M4)
- [ ] Attention calls with blinking indicator + optional bell
- [ ] Balancing pass: play at `--speed 60` for a full life; adjust `Balance` only
      (known: an untreated sick child dies in ~2.5 h — sickness may need to be gentler)
- [x] Logging to file; no stray terminal output (landed in M4)

**Accept:** A complete life can be played start to finish; every screen has a snapshot test.

## M7 — Release readiness

- [ ] README with screenshot/GIF (e.g. via `vhs` or `asciinema`), install instructions
      (`uv tool install`, `pipx install`)
- [ ] CHANGELOG.md (Keep a Changelog), version 1.0.0
- [ ] CI matrix: Linux/macOS/Windows × Python 3.12/3.13 on every push/PR (re-enable the commented-out
      macOS matrix entry in `.github/workflows/ci.yml`)
- [ ] Build wheel (`uv build`) and smoke-test the installed `tama` entry point in CI
- [ ] Final review against SPEC; open issues for anything deferred
