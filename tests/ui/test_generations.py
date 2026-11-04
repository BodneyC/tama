"""Hatching the egg a pet left (SPEC §2.8): from the memorial, the pet list and one save file."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from textual.widgets import Input, Static

from tama.domain.pet import AncestorRecord, Pet
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.services.roster import MAX_PETS
from tama.ui.screens.confirm import ConfirmScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.memorial import MemorialScreen
from tama.ui.screens.new_pet import NewPetScreen
from tama.ui.screens.pet_select import PetSelectScreen
from tests.factories import FIXED_NOW, make_pet
from tests.ui.helpers import Notes, library_with, make_app, make_library_app, repo_with, text

OLD: dict[str, Any] = {
    "stage": LifeStage.DEAD,
    "cause_of_death": DeathCause.OLD_AGE,
    "variant": Variant.GOOD,
    "species": "owl",
    "stats": Stats(discipline=80),
}


def pet(name: str, **overrides: Any) -> Pet:
    return replace(make_pet(**overrides), name=name)


def name_typed(app: Any) -> str:
    value: str = app.screen.query_one("#name", Input).value
    return value


async def test_the_memorial_hatches_the_egg_into_the_next_of_the_line(tmp_path: Path) -> None:
    library, [mochi] = library_with(tmp_path, pet("Mochi", **OLD))
    app = make_library_app(library)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MemorialScreen)
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, NewPetScreen)
        assert name_typed(app) == "Mochi II"
        assert text(app, ".dialog-title") == "Mochi's egg is hatching!"
        await pilot.press("down")  # the animal is the parent's: it can't change
        assert text(app, "#species") == "Species: owl"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        heir = app.session.pet
        assert (heir.name, heir.species, heir.generation) == ("Mochi II", "owl", 2)
        assert heir.stats.discipline == 25
        assert mochi.repo().load().game.pet.heir_hatched
        assert len(library.roster.files()) == 2


async def test_backing_out_of_the_name_returns_to_the_memorial(tmp_path: Path) -> None:
    library, _ = library_with(tmp_path, pet("Mochi", **OLD))
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, MemorialScreen)


async def test_no_egg_after_dying_of_poor_health(tmp_path: Path) -> None:
    library, _ = library_with(
        tmp_path, pet("Mochi", **(OLD | {"cause_of_death": DeathCause.POOR_HEALTH}))
    )
    app = make_library_app(library)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MemorialScreen)
        shown = [b.binding.description for b in app.screen.active_bindings.values() if b.enabled]
        assert "Hatch its egg" not in shown
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, MemorialScreen)


async def test_one_save_file_hands_over_to_the_heir(tmp_path: Path) -> None:
    repo = repo_with(**OLD)
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert repo.game is not None
        assert repo.game.pet.name == "Mochi II"
        assert repo.game.pet.ancestors[-1].name == "Mochi"


async def test_the_pet_list_hatches_a_dead_pets_egg(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi", **OLD))
    library.roster.set_last(files[1])
    app = make_library_app(library)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PetSelectScreen)
        assert "left an egg (e to hatch)" in text(app, "#preview-detail")
        await pilot.press("e")
        await pilot.pause()
        assert name_typed(app) == "Mochi II"
        await pilot.press("enter")
        await pilot.pause()

        assert app.session is not None
        assert app.session.pet.name == "Mochi II"


async def test_e_does_nothing_on_a_pet_without_an_egg(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi", **OLD))
    library.roster.set_last(files[0])
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, PetSelectScreen)


async def test_no_room_for_an_heir_at_nine_pets(tmp_path: Path) -> None:
    pets = [pet("Mochi", **OLD), *(pet(f"Pet {n}") for n in range(MAX_PETS - 1))]
    library, files = library_with(tmp_path, *pets)
    library.roster.set_last(files[0])
    app = make_library_app(library)
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, PetSelectScreen)
        assert "nine pets" in notes


async def test_archiving_warns_that_the_egg_goes_too(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Bao"), pet("Mochi", **OLD))
    library.roster.set_last(files[1])
    app = make_library_app(library)
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmScreen)
        question = str(app.screen.query(Static)[1].render())
        assert question.endswith("Its egg will be archived with it.")


async def test_status_shows_the_family(tmp_path: Path) -> None:
    founder = AncestorRecord("Mochi", FIXED_NOW, 1, Variant.GOOD, make_pet().age)
    app = make_app(repo_with(generation=2, ancestors=(founder,)))
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.pause()

        assert "Family     Generation 2 · founded by Mochi" in text(app, "#status-body")
