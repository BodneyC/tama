"""Tricks on the main screen: learning one, and showing off now and then (SPEC §2.10)."""

from tama.domain.animation import AnimationKey
from tama.domain.stage import LifeStage, Trick, Variant
from tama.domain.stats import Stats
from tama.ui.sprites import load_sprite
from tama.ui.widgets.pet_view import PetView, ViewOptions
from tests.ui.helpers import Notes, make_app, repo_with


def spin() -> object:
    return load_sprite("tama", Variant.DEFAULT, LifeStage.CHILD, AnimationKey.TRICK_SPIN)


async def test_disciplining_a_child_from_40_to_65_teaches_it_to_spin() -> None:
    app = make_app(repo_with(misbehaving=True, stats=Stats(discipline=40)))
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("d")

        assert ("Learned to spin!", "information") in notes.messages
        view = app.screen.query_one(PetView)
        assert view.current is spin()  # shown at once
        assert view._tricks == (Trick.WAVE, Trick.SPIN)  # then now and then, when content


async def test_a_content_pet_may_show_off_its_tricks() -> None:
    app = make_app(repo_with(stats=Stats(happiness=90, discipline=55)))
    async with app.run_test():
        assert app.screen.query_one(PetView)._tricks == (Trick.WAVE, Trick.SPIN)


async def test_an_unhappy_pet_keeps_its_tricks_to_itself() -> None:
    app = make_app(repo_with(stats=Stats(happiness=50, discipline=100)))
    async with app.run_test():
        assert app.screen.query_one(PetView)._tricks == ()


async def test_with_reduced_motion_a_new_trick_is_only_toasted() -> None:
    app = make_app(
        repo_with(misbehaving=True, stats=Stats(discipline=40)),
        view=ViewOptions(animate=False, reduced_motion=True),
    )
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("d")

        assert "Learned to spin!" in notes
        assert app.screen.query_one(PetView).reaction is None
