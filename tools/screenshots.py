"""The README's screenshots, taken from the real app at the minimum 60x20 terminal.

    uv run python -m tools.screenshots            # writes docs/images/*.svg

Two pets are raised through simulated days of attentive care (so the journal is a real one),
then the app is driven with Textual's pilot on a frozen clock and each screen is saved as an
SVG, which GitHub shows inline. Deterministic: the same code gives the same pictures.
"""

import argparse
import asyncio
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import Random

from textual.pilot import Pilot

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import Action
from tama.domain.minigames import GameKind, GameResult, Side
from tama.domain.minigames.four_in_a_row import FourInARow
from tama.domain.minigames.opponent import pet_move
from tama.domain.stage import LifeStage
from tama.infra.clock import FakeClock
from tama.persistence.roster import PetFile, PetRoster
from tama.services.library import PetLibrary
from tama.services.session import GameSession, SessionSettings
from tama.ui.app import TamaApp
from tama.ui.screens.games.pet_vs_pet import PetVsPetScreen
from tama.ui.widgets.pet_view import ViewOptions

OUT = Path(__file__).parents[1] / "docs" / "images"
SIZE = (60, 20)
BORN = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
NOW = BORN + timedelta(days=3, hours=22, minutes=40)  # 07:40 on day 5: dawn, just up
CHECK_EVERY = timedelta(minutes=10)

type Shot = Callable[[Pilot[None]], Awaitable[None]]


def raise_pet(roster: PetRoster, name: str, species: str, born: datetime, seed: int) -> PetFile:
    """Hatch ``name`` at ``born`` and look after it attentively until ``NOW``."""
    clock, settings = FakeClock(born), SessionSettings()
    file = roster.create(name)
    session = GameSession.create(
        name, repo=file.repo(), clock=clock, settings=settings, seed=seed, species=species
    )
    rounds = 0
    while clock.now() < NOW:
        clock.advance(CHECK_EVERY)
        session.tick()
        pet = session.pet
        if pet.misbehaving and not pet.is_asleep:
            session.act(Action.DISCIPLINE)
        if pet.is_sick and not pet.is_asleep:
            session.act(Action.MEDICINE)
        if pet.poop_count:
            session.act(Action.CLEAN)
        if session.pet.stats.hunger < 60:
            session.act(Action.MEAL)
        if session.pet.stats.happiness < 80 and session.act(Action.PLAY).refusal is None:
            rounds += 1
            result = GameResult.WIN if rounds % 3 else GameResult.LOSS
            session.finish_game(result, GameKind.FOUR_IN_A_ROW)
        if session.pet.is_asleep == session.pet.lights_on:
            session.act(Action.LIGHTS)
    session.close()
    return file


async def capture(library: PetLibrary, open_pet: PetFile, name: str, steps: Shot) -> Path:
    """Open ``open_pet``, run ``steps`` and save the screen as ``<name>.svg``."""
    app = TamaApp(
        library=library,
        open_pet=open_pet,
        clock=FakeClock(NOW),
        settings=SessionSettings(),
        tick_interval=None,
        handle_signals=False,
        view=ViewOptions(animate=False),
    )
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await steps(pilot)
        await pilot.pause()
        return Path(app.save_screenshot(filename=f"{name}.svg", path=str(OUT)))


async def main_screen(pilot: Pilot[None]) -> None:
    """Nothing to do: the pet at home."""


def game_under_way(moves: int = 9) -> FourInARow:
    """Four in a Row a few moves in, an adult (moving first) against a teen."""
    game, rng = FourInARow(), Random(5)
    for turn in range(moves):
        side, stage = (
            (Side.PLAYER, LifeStage.ADULT) if turn % 2 == 0 else (Side.PET, LifeStage.TEEN)
        )
        game = game.play(pet_move(game, stage, DEFAULT_BALANCE, rng, side=side))
    return game


async def visit(pilot: Pilot[None]) -> None:
    """Invite the other pet and watch a game of Four in a Row, paused mid-game.

    The app plays a watched game instantly when animation is off, so the board is set up
    from real pet moves instead, as in the visit snapshots.
    """
    await pilot.press("v", "1")
    await pilot.pause()
    app = pilot.app
    if not isinstance(app, TamaApp) or app.visit is None:
        raise SystemExit("the visit was refused; pick a time when both pets are up")
    screen = PetVsPetScreen(
        GameKind.FOUR_IN_A_ROW, app.visit, app.view, game=game_under_way(), autoplay=False
    )
    app.push_screen(screen)


async def journal(pilot: Pilot[None]) -> None:
    """Open the journal."""
    await pilot.press("j")


async def take_all() -> list[Path]:
    """Raise the pets and take every screenshot."""
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as data:
        roster = PetRoster(Path(data))
        mochi = raise_pet(roster, "Mochi", "tama", BORN, seed=3)
        raise_pet(roster, "Pip", "owl", BORN + timedelta(days=1, hours=4), seed=8)
        library = PetLibrary(roster, clock=FakeClock(NOW), settings=SessionSettings())
        return [
            await capture(library, mochi, "main", main_screen),
            await capture(library, mochi, "visit", visit),
            await capture(library, mochi, "journal", journal),
        ]


def main() -> None:
    """Write the screenshots and say where."""
    argparse.ArgumentParser(description=__doc__).parse_args()
    for path in asyncio.run(take_all()):
        print(path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path)  # noqa: T201 - a CLI tool


if __name__ == "__main__":
    main()
