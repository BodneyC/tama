# ADR 0006: Mini-games are pure state machines with a seeded, stage-skilled opponent

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

`p` has offered one game, Left or Right, whose only randomness is the pet's look. We are
adding two board games played *against* the pet, Four in a Row (connect-four style) and
Tic-Tac-Toe, chosen from a game select dialog (SPEC §3.1). Board games bring things the
current design doesn't cover: a draw result, an opponent that has to choose moves, and enough
rules (line detection, full boards, illegal moves) that bugs could easily hide in UI code.

## Decision

- Every game lives in `tama.domain.minigames` as a frozen state object. Its moves return a
  new state, and its `result` (a `GameResult`: win, draw or loss, from the player's side) is
  set once it is over. Left or Right moves there from `domain/minigame.py`. Like the rest of
  the domain, games import nothing from the UI and use no global randomness.
- The pet's moves come from one pure function in `opponent.py`: take a winning move, else block
  the player's immediate win, else (Four in a Row) avoid giving the player a win on top of
  its piece, else pick the best-placed move, breaking ties with the injected `random.Random`.
  With a per-stage **mistake chance** (in `Balance`) it plays a random legal move instead.
  This is a heuristic, not a search: it is predictable to test, cheap, and beatable, which
  suits a pet. Difficulty is tuned in `Balance` only.
- A game's result replaces the `won: bool` flag. `apply_game_outcome(pet, result, ctx)` maps
  win/draw/loss to stat changes (draw: happiness +10, energy −10), and the `Played` event
  carries the `GameResult`.
- `GameSession` gives games the session RNG (`pet_move`, as `guess` does today), so a played
  game advances the saved RNG and stays reproducible. Games in progress are not persisted:
  quitting mid-game abandons it, as with Left or Right, so the save schema doesn't change.
- Piece colours are two new UI colours, `piece-player` and `piece-pet` (ADR 0004), so species
  can theme them. Monochrome keeps the sides apart by shape (`●`/`○`), never colour alone.

## Consequences

- Game rules and the opponent get exhaustive unit and property tests without a UI; the UI
  layer is thin (render a state, map keys to moves) and covered by Pilot tests and snapshots.
- Adding another game means a state machine, an opponent preference (or a new pure function)
  and a screen; the select dialog lists games from `GameKind`.
- The opponent can be made stronger later (e.g. a shallow search) without touching the UI or
  the save format, as long as it stays a pure function of state, stage and RNG.
- `assets/ui.toml` and the list of UI colours in `/add-sprite` gain two keys.
