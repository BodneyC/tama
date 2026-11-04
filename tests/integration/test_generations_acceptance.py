"""M6.11 acceptance: a good elder's egg hatches into Mochi II, whose line outlives the parent."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.infra.clock import FakeClock
from tama.persistence.roster import PetRoster
from tama.services.describe import family_line, lineage_text
from tama.services.library import PetLibrary
from tama.services.session import SessionSettings
from tama.ui.screens.main import MainScreen
from tama.ui.screens.memorial import MemorialScreen
from tests.factories import FIXED_NOW, make_pet
from tests.ui.helpers import library_with, make_library_app

LIFESPAN = timedelta(days=15)


async def test_a_good_elders_egg_carries_the_line_on(tmp_path: Path) -> None:
    clock = FakeClock(FIXED_NOW)
    elder = replace(
        make_pet(
            stage=LifeStage.ELDER,
            variant=Variant.GOOD,
            species="owl",
            stats=Stats(discipline=70),
            lifespan=LIFESPAN,
            age=LIFESPAN - timedelta(minutes=1),
        ),
        name="Mochi",
    )
    library, [parent] = library_with(tmp_path, elder, clock=clock)
    app = make_library_app(library, clock=clock)
    async with app.run_test() as pilot:
        clock.advance(timedelta(minutes=2))
        app.tick()
        await pilot.pause()
        assert isinstance(app.screen, MemorialScreen)
        assert app.session is not None
        assert app.session.pet.cause_of_death is DeathCause.OLD_AGE

        await pilot.press("e")  # the name prompt is filled in with "Mochi II"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        heir = app.session.pet
        assert (heir.name, heir.species, heir.generation) == ("Mochi II", "owl", 2)
        assert heir.stats.discipline == 25

    library.archive(parent)  # the parent's files go; the line lives on in the heir's save
    fresh = PetLibrary(PetRoster(tmp_path), clock=clock, settings=SessionSettings())
    [row] = fresh.summaries()
    assert row.pet is not None
    assert lineage_text(row.pet) == "Generation 2 · founded by Mochi"
    assert family_line(row.pet) == "Mochi → Mochi II"


async def test_a_pet_that_died_of_poor_health_offers_no_egg(tmp_path: Path) -> None:
    clock = FakeClock(FIXED_NOW)
    frail = replace(make_pet(stats=Stats(hunger=0, health=1)), name="Bao")
    library, _ = library_with(tmp_path, frail, clock=clock)
    app = make_library_app(library, clock=clock)
    async with app.run_test() as pilot:
        clock.advance(timedelta(hours=1))
        app.tick()
        await pilot.pause()
        assert isinstance(app.screen, MemorialScreen)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, MemorialScreen)
        assert not library.summaries()[0].egg_waiting
