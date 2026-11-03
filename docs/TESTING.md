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
