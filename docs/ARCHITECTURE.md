# Architecture

## Overview: functional core, imperative shell

```
             ┌─────────────────────────────────────────────┐
             │                  tama.ui                    │  Textual app, screens, widgets
             │      (imperative shell: timers, input)      │
             └───────────────┬─────────────────────────────┘
                             │ calls
             ┌───────────────▼─────────────────────────────┐
             │               tama.services                 │  GameSession: orchestrates
             │   (use cases: tick, act, load, autosave)    │  domain + clock + repository
             └──────┬───────────────────────────┬──────────┘
                    │                           │
        ┌───────────▼──────────┐    ┌───────────▼───────────┐
        │     tama.domain      │◄───│   tama.persistence    │  Pydantic DTOs, JSON repo,
        │ (pure, deterministic)│    │                       │  migrations, atomic writes
        └──────────────────────┘    └───────────────────────┘
                    ▲
        ┌───────────┴──────────┐
        │      tama.infra      │  Clock impls, paths, config loading, logging setup
        └──────────────────────┘
```

Import rules (enforced by `import-linter`, see `pyproject.toml`):

- `tama.domain` imports nothing from other `tama` packages except `tama.errors`, and no
  third-party packages.
- `tama.persistence` may import `tama.domain`, never `tama.ui` / `tama.services`.
- `tama.services` may import `domain`, `persistence`, `infra`; never `ui`.
- `tama.ui` may import anything except internals of `persistence` (go through services).

## Module layout

```
src/tama/
├── __init__.py            # __version__
├── __main__.py            # python -m tama
├── cli.py                 # Typer app; builds dependencies, launches TamaApp
├── errors.py              # TamaError hierarchy
├── domain/
│   ├── stats.py           # Stat enum, Stats value object, clamp helper
│   ├── stage.py           # LifeStage, Variant, DeathCause enums
│   ├── pet.py             # Pet (frozen dataclass) incl. Drift/Timers; new_egg()
│   ├── balance.py         # Balance: all tunable rates/thresholds
│   ├── context.py         # Context: injected RNG, Balance and local time zone
│   ├── events.py          # Event types, Action/RefusalReason enums, Outcome(pet, events)
│   ├── simulation.py      # advance(pet, elapsed, ctx) -> Outcome
│   ├── lifecycle.py       # stage transitions, adult variant selection, death
│   ├── actions.py         # apply(pet, action, ctx) / apply_game_outcome() -> Outcome
│   ├── attention.py       # attention_reasons(pet, balance) (SPEC §4)
│   ├── minigame.py        # Left/Right game state machine
│   └── animation.py       # select_animation(pet, last_event) -> AnimationKey (pure)
├── services/
│   ├── session.py         # GameSession: holds current Pet, applies ticks/actions, emits events
│   └── autosave.py        # debounced save policy
├── persistence/
│   ├── models.py          # Pydantic SaveFileV<N>, to_domain()/from_domain()
│   ├── repository.py      # SaveRepository protocol + JsonSaveRepository (atomic, .bak)
│   └── migrations.py      # versioned migration steps
├── infra/
│   ├── clock.py           # Clock protocol, SystemClock, FakeClock (tests), ScaledClock(--speed)
│   ├── paths.py           # platformdirs wrappers
│   ├── config.py          # Config dataclass, TOML loader, precedence merge
│   └── logging.py         # file logging setup
├── ui/
│   ├── app.py             # TamaApp(App): bindings, screen stack, tick timer
│   ├── app.tcss           # Textual CSS
│   ├── screens/           # main, status, feed_menu, minigame, away_summary, memorial, help, error, new_pet
│   ├── widgets/           # pet_view (animated sprite), stat_bar, header, poop_layer, toast helpers
│   └── sprites.py         # load + cache frames from assets via importlib.resources
└── assets/sprites/        # <variant>/<stage>/<animation>.txt (frames separated by a line "---")
```

Tests mirror this: `tests/unit/domain/...`, `tests/unit/persistence/...`, `tests/ui/...`,
`tests/integration/...`. See `TESTING.md`.

## Key design decisions

### Deterministic simulation

`advance(pet, elapsed, ctx)` is the single entry point for the passage of time. `ctx` carries
`Balance`, a `random.Random`, and the player's time zone (only used for day/night). See
[ADR 0002](adr/0002-fixed-step-exact-simulation.md):

- Time is simulated in fixed steps of `Balance.step` (1 minute), for live play and offline
  catch-up alike. Elapsed time shorter than a step is kept on the pet as `carry`.
- Stat drift is accumulated as exact `Fraction`s on the pet (`Pet.drift`, `poop_progress`), so
  nothing is lost to rounding.
- Random rolls happen only on whole hours of the pet's age, and always draw the same number
  of values, so how time is sliced never changes the RNG sequence.

Together these make `advance(a + b)` **exactly** equal to `advance(a)` then `advance(b)`, the
same events, the same pet, and the same RNG state. Property tests (hypothesis) assert this, plus
stats always in range, dead pets never change, and age is monotonic. A 72-hour catch-up is
~4,300 steps (well under a second).

### Events, not callbacks

Domain functions return an `Outcome(pet, events)`; a refused action is an `Outcome` with a
single `Refused` event. The UI reacts to events (play animation, toast,
bell); the away-summary is just the events from the catch-up `advance`, aggregated. The domain
knows nothing about how events are presented.

### Animation

- `domain/animation.py` decides *which* animation should be playing (pure, unit-tested).
- `ui/widgets/pet_view.py` (a `Static` subclass) owns *frame playback*: a `set_interval` timer
  advances the frame index; a one-shot queue plays reaction animations before reverting.
- `ui/sprites.py` parses sprite files once (`functools.cache`) into `tuple[Frame, ...]`, validating
  that all frames of an animation share dimensions (a test asserts this for every asset).
- Missing sprite for a variant falls back to the default variant, then a placeholder — never crash.

### Time in the UI

`TamaApp` runs a 1 s `set_interval` that calls `session.tick(clock.now())`. The session computes
elapsed since the last tick. With `ScaledClock`, `--speed` just scales elapsed time.

### Persistence boundary

The domain `Pet` is not a Pydantic model. `persistence/models.py` maps between the domain and
versioned DTOs. This keeps the domain dependency-free and lets the file format evolve
independently (migrations operate on raw dicts before validation).

### Error handling

- Expected failures (corrupt save, unwritable dir) → typed exceptions from `tama.errors`, caught
  in services/UI and surfaced as screens/toasts.
- Unexpected exceptions in the TUI → logged with traceback to the log file; Textual shows its
  error; the last good save is left untouched (saves are atomic).
