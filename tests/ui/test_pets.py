"""Several pets in the app: launching, the pet select screen, switching (SPEC §6.1)."""

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from textual.widgets import Input

from tama.domain.pet import Pet
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tama.infra.clock import FakeClock
from tama.persistence.lock import PetLock
from tama.services.roster import MAX_PETS
from tama.ui.screens.confirm import ConfirmScreen
from tama.ui.screens.error import PetErrorScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.memorial import MemorialScreen
from tama.ui.screens.new_pet import NewPetScreen
from tama.ui.screens.pet_select import PetSelectScreen
from tests.factories import FIXED_NOW, make_pet
from tests.ui.helpers import Notes, library_with, make_library_app, text

DEAD: dict[str, Any] = {"stage": LifeStage.DEAD, "cause_of_death": DeathCause.OLD_AGE}


def pet(name: str, **overrides: Any) -> Pet:
    return replace(make_pet(**overrides), name=name)


async def test_with_no_pets_the_name_prompt_hatches_the_first(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path)
    app = make_library_app(library)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, NewPetScreen)
        await pilot.press(*"Mochi", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        [file] = library.roster.files()
        assert file.key.startswith("mochi-")
        assert library.roster.last() == file
        assert library.open_file == file


async def test_a_single_pet_opens_straight_away(tmp_path: Path) -> None:
    library, [file] = library_with(tmp_path, pet("Mochi"))
    app = make_library_app(library)
    async with app.run_test():
        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.name == "Mochi"
        assert PetLock(file.path).path.exists()
    assert not PetLock(file.path).path.exists()  # released on exit


async def test_several_pets_offer_the_list_with_the_last_played_first(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi"), pet("Pip"))
    library.roster.set_last(files[2])
    app = make_library_app(library)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PetSelectScreen)
        assert [row.name for row in screen.rows] == ["Pip", "Bao", "Mochi"]

        await pilot.press("enter")
        await pilot.pause()

        assert app.session is not None
        assert app.session.pet.name == "Pip"


async def test_number_keys_pick_a_pet(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi", species="owl"))
    library.roster.set_last(files[0])
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()

        assert app.session is not None
        assert app.session.pet.name == "Mochi"
        assert app.species == "owl"  # the UI colours follow the open pet


async def test_t_saves_and_switches_to_another_pet(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi"))
    app = make_library_app(library, open_pet=files[0])
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MainScreen)
        await pilot.press("f", "m")  # feed Bao, then switch
        await pilot.press("t")
        await pilot.pause()

        assert isinstance(app.screen, PetSelectScreen)
        assert not PetLock(files[0].path).path.exists()
        assert files[0].repo().load().game.pet.stats.hunger == 100

        await pilot.press("2")
        await pilot.pause()
        assert app.session is not None
        assert app.session.pet.name == "Mochi"
        assert library.roster.last() == files[1]


async def test_a_new_pet_cannot_take_a_living_pets_name(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, pet("Mochi"), pet("Pip", **DEAD))
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("n", *"mochi", "enter")
        await pilot.pause()
        assert isinstance(app.screen, NewPetScreen)
        assert text(app, "#name-error") == "You already have a mochi."

        app.screen.query_one(Input).value = "Pip"  # a dead pet's name is free again
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert len(library.roster.files()) == 3


async def test_no_tenth_pet(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, *(pet(f"Pet{i}") for i in range(MAX_PETS)))
    app = make_library_app(library)
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("n")
        await pilot.pause()

        assert isinstance(app.screen, PetSelectScreen)
        assert "nine pets already" in notes


async def test_archiving_a_dead_pet_after_confirming(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Old", **DEAD))
    library.roster.set_last(files[0])
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("down", "a")
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("y")
        await pilot.pause()

        assert isinstance(app.screen, PetSelectScreen)
        assert [row.name for row in app.screen.rows] == ["Bao"]
        assert [f.key[:3] for f in library.roster.files()] == ["bao"]
        assert len(list((library.roster.directory / "archive").iterdir())) == 1


async def test_living_pets_cannot_be_archived(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, pet("Bao"), pet("Mochi"))
    app = make_library_app(library)
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("a")

        assert isinstance(app.screen, PetSelectScreen)
        assert "Only pets that have passed away" in notes


async def test_escape_on_the_list_quits(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, pet("Bao"), pet("Mochi"))
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert app.return_code in (0, None)


async def test_an_unreadable_pet_only_affects_itself(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, pet("Bao"))
    broken = library.roster.directory / "broken-abcdef.json"
    broken.write_text("{ nope", encoding="utf-8")
    app = make_library_app(library)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PetSelectScreen)
        index = next(i for i, row in enumerate(screen.rows) if row.pet is None)
        await pilot.press(str(index + 1))
        await pilot.pause()
        assert isinstance(app.screen, PetErrorScreen)

        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, PetSelectScreen)
        assert broken.exists()
        assert library.open_file is None

        await pilot.press(str(index + 1), "n")
        await pilot.pause()
        assert isinstance(app.screen, NewPetScreen)
        assert not broken.exists()
        assert list(library.roster.directory.glob("broken-abcdef.json.corrupt-*"))


async def test_a_pet_open_elsewhere_stays_closed(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi"))
    library.roster.set_last(files[0])
    PetLock(files[1].path, pid=os.getppid()).acquire()  # a live process that isn't us
    app = make_library_app(library)
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()

        assert isinstance(app.screen, PetSelectScreen)
        assert "already open in another tama" in notes


async def test_the_header_counts_other_pets_needing_care(tmp_path: Path) -> None:
    library, files = library_with(
        tmp_path,
        pet("Bao"),
        pet("Hungry", stats=Stats(hunger=5)),
        pet("Away", stats=Stats(hunger=5), paused_since=FIXED_NOW),
        pet("Old", **DEAD),
    )
    app = make_library_app(library, open_pet=files[0])
    async with app.run_test():
        assert text(app, "#others") == "⚠ +1"


async def test_the_memorials_new_egg_adds_a_pet(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Old", **DEAD), pet("Bao"))
    app = make_library_app(library, open_pet=files[0])
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MemorialScreen)
        await pilot.press("n", *"Sprout", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert len(library.roster.files()) == 3


async def test_new_adds_another_pet(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, pet("Bao"))
    app = make_library_app(library, start_new=True)
    async with app.run_test() as pilot:
        await pilot.press(*"Sprout", "enter")
        await pilot.pause()

        assert app.session is not None
        assert app.session.pet.name == "Sprout"
        assert len(library.roster.files()) == 2


async def test_pets_are_seen_as_of_now(tmp_path: Path) -> None:
    clock = FakeClock(FIXED_NOW)
    library, _ = library_with(tmp_path, pet("Bao"), pet("Mochi"), clock=clock)
    before = {f.path: f.path.read_bytes() for f in library.roster.files()}
    clock.advance(timedelta(hours=3))
    app = make_library_app(library, clock=clock)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PetSelectScreen)
        await pilot.press("escape")
    assert {f.path: f.path.read_bytes() for f in library.roster.files()} == before
