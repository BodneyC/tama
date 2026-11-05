# Testing Strategy

## Layers

| Layer | Location | Tools | Notes |
| --- | --- | --- | --- |
| Domain unit | `tests/unit/domain/` | pytest, hypothesis | Fast, pure. Test-first. 100% branch coverage. |
| Persistence | `tests/unit/persistence/` | pytest, `tmp_path` | Round-trip, atomicity, `.bak` fallback, corrupt files, every migration. |
| Services | `tests/unit/services/` | pytest, `FakeClock`, in-memory repo | Session ticking, autosave policy, offline catch-up. |
| UI behaviour | `tests/ui/` | `App.run_test()` + `Pilot`, pytest-asyncio | Press keys, assert on screen/widget state and session state. |
| UI snapshots | `tests/ui/snapshots/` | pytest-textual-snapshot | SVG snapshots (stored as `__snapshots__/**/*.raw`) of key screens at 80×24 with a `FakeClock`, fixed seed and no tick timer. |
| Integration | `tests/integration/` | pytest, Typer `CliRunner` | CLI flags, `tama status`, full load→play→save→reload cycle. |
| Assets | `tests/unit/test_sprites.py`, `test_theme.py` | pytest (parametrised) | Every base palette and sprite file parses; merged palettes cover every pixel; size limits; shared canvases; every required (stage, animation) exists for every species; generated art is up to date; every sprite draws something in every look (dark/light × colour/mono). Renderer tested cell by cell; UI colour resolution per mode. |

## Conventions

- Test names describe behaviour: `test_meal_is_refused_when_pet_is_asleep`.
- Shared builders in `tests/factories.py`: `make_pet(**overrides)`, `make_ctx(seed=0, now=...)`.
  Do not hand-construct full `Pet` objects in tests.
- Never use real time or real randomness. `FakeClock` + `random.Random(seed)` everywhere.
  A test-wide autouse fixture fails any test that calls `datetime.now()` in the domain (optional
  but encouraged: patch and assert not called).
- Never touch the user's real save dir: an autouse fixture sets `TAMA_SAVE_PATH` and the
  platformdirs env to `tmp_path`.
- Hypothesis: use `@settings(deadline=None)` for simulation tests; register a `ci` profile with
  more examples, selected via `HYPOTHESIS_PROFILE=ci`.
- UI tests: build the app with `tests/ui/helpers.make_app` (in-memory save, `FakeClock`,
  `tick_interval=None`, no signal handlers) and call `app.tick()` by hand. Capture toasts with
  `Notes(app)`. Use `await pilot.pause()` after key presses that push or pop screens.
- Mini-games (ADR 0006): test the rules on hand-written boards (every winning direction, full
  columns, occupied cells, draws) and drive the opponent with a seeded RNG and a `Balance`
  whose mistake chance is 0 (it must take wins and blocks) or 1 (it must still only make legal
  moves). Property tests: random legal games always end with exactly one result within the
  board's size. Snapshot each board game mid-game and finished, in monochrome too.
- Holiday (ADR 0008): property-test that advancing a paused pet by any duration changes only
  `updated_at`, and that pause → wait → resume equals not having waited at all.
- Several pets (ADR 0007): roster tests use `tmp_path` and real files; assert that read-only
  views (`--status`, the pet select screen, the header count) leave every pet file byte-for-byte
  unchanged, and that two sessions can't hold the same pet's lock.
- Weight (SPEC §2.7): keep the tick-splitting property with weight burn in play; test the
  band edges for every stage and that a weight episode is one care mistake however long it
  lasts. Judge the band and burn rate on `tools/balance.py`, not on unit tests.
- Journal (ADR 0009): property-test that recording the events of `advance(a + b)` equals
  recording `advance(a)` then `advance(b)`; that moments are capped and life/first entries
  never dropped; and that read-only views leave the journal in the file unchanged.
- Generations (ADR 0010): test `heir_name` on numerals and long names; simulate a crash between
  writing the heir and the parent (write the heir, skip the parent) and assert the egg can't be
  hatched twice; old-age-only eggs.
- Visits (ADR 0011): Pilot tests with two pets in a `tmp_path` roster; assert the guest's lock
  is released and its file saved on every way out (end, auto-end, `t`, `q`, signal handler,
  an exception raised in the visit screen); pet-vs-pet games replay identically from saved RNG
  states.
- Reviewing snapshots: Pilot tests can't see layout bugs (an empty dialog still "contains"
  its text), so look at every new or changed snapshot. Render one to PNG, swapping in a
  locally installed monospace font that has the block glyphs (Textual's SVGs ask for Fira Code):

  ```sh
  sed -E 's/font-family: [^;"]*/font-family: "DejaVu Sans Mono"/g' snap.raw > /tmp/snap.svg
  uvx --from cairosvg cairosvg /tmp/snap.svg -o /tmp/snap.png
  ```

  Emoji may still render as boxes (a font limitation, not a bug); thin seams between cells
  are a rasteriser artefact.
- Snapshot files are byte-exact: pre-commit's whitespace hooks skip `__snapshots__/`.
- Sprite art: review whole animation sets as contact sheets rendered straight from the pixel
  grids (every frame of every animation), not only snapshots, which show one frame.
- Mark slow tests `@pytest.mark.slow`; CI runs everything, local default runs everything too
  (they should stay fast — budget for whole suite: < 45 s).
- Tests run in parallel by default (`pytest-xdist`, `-n auto` in `pyproject.toml`); coverage
  and the snapshot failure report still work. Use `-n0` to debug a single test with `pdb`, and
  always for `--snapshot-update`: the snapshot plugin refuses concurrent snapshot writes.

## Coverage

`pytest-cov` with branch coverage, configured in `pyproject.toml`. `fail_under = 90`.
Domain package additionally checked at 100% in CI
(`uv run coverage report --include='src/tama/domain/*' --fail-under=100`).
`ui` code is exercised by Pilot tests; `pragma: no cover` only for truly untestable lines
(e.g. `if __name__ == "__main__"`) with justification.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request, on Linux, macOS
and Windows × Python 3.12 and 3.13:

- **check**: the definition of done (format, lint, mypy, import contracts, tests) and the 100%
  domain coverage gate; the snapshot report is uploaded when it fails.
- **package**: `uv build`, then the wheel is run as installed, away from `src/`: `tama
  --version`, `--list-species`, `tools/smoke.py` (hatches a pet through the TUI, headless, so the
  wheel must carry its sprites and stylesheet), then `--status` and `journal` find that pet.
  Locally: `uv build`, then the same commands with `uvx --from dist/tama-*.whl tama ...` and
  `uv run --no-project --with dist/tama-*.whl python -I tools/smoke.py DATA_DIR`.
