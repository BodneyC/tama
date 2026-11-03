"""Builders and probes for Textual UI tests."""

from pathlib import Path
from random import Random
from typing import Any

from textual.app import App
from textual.widgets import Static

from tama.domain.pet import Pet
from tama.infra.clock import FakeClock
from tama.persistence.models import SaveGame
from tama.persistence.repository import SaveRepository
from tama.persistence.roster import PetFile, PetRoster
from tama.services.library import PetLibrary
from tama.services.session import SessionSettings
from tama.ui.app import TamaApp
from tama.ui.widgets.pet_view import ViewOptions
from tests.factories import FIXED_NOW, make_pet
from tests.fakes import InMemorySaveRepository


def repo_with(seed: int = 0, **pet_overrides: Any) -> InMemorySaveRepository:
    """An in-memory save holding a pet (a content CHILD by default)."""
    return InMemorySaveRepository(SaveGame(make_pet(**pet_overrides), Random(seed).getstate()))


def make_app(
    repo: SaveRepository | None = None,
    *,
    clock: FakeClock | None = None,
    **kwargs: Any,
) -> TamaApp:
    """A deterministic app: in-memory save, frozen clock, no tick timer, no signal handlers."""
    options: dict[str, Any] = {
        "settings": SessionSettings(),
        "tick_interval": None,
        "handle_signals": False,
        "view": ViewOptions(animate=False),
        **kwargs,
    }
    return TamaApp(
        repo=repo if repo is not None else InMemorySaveRepository(),
        clock=clock or FakeClock(FIXED_NOW),
        **options,
    )


def mono(**kwargs: Any) -> ViewOptions:
    """View options for a monochrome, non-animated test app."""
    return ViewOptions(monochrome=True, animate=False, **kwargs)


def text(app: App[Any], selector: str) -> str:
    """The plain text currently shown by the ``Static`` matching ``selector``."""
    return str(app.screen.query_one(selector, Static).render())


class Notes:
    """Records ``app.notify`` calls."""

    def __init__(self, app: App[Any]) -> None:
        self.messages: list[tuple[str, str]] = []

        def record(message: str, **kwargs: Any) -> None:
            self.messages.append((message, kwargs.get("severity", "information")))

        app.notify = record  # type: ignore[method-assign]  # capture toasts for assertions

    def __contains__(self, fragment: str) -> bool:
        return any(fragment in message for message, _ in self.messages)

    def severities(self) -> list[str]:
        return [severity for _, severity in self.messages]


def library_with(
    data_dir: Path, *pets: Pet, clock: FakeClock | None = None
) -> tuple[PetLibrary, list[PetFile]]:
    """A real roster in ``data_dir`` holding ``pets`` (saved in order), and their files."""
    roster = PetRoster(data_dir)
    files = []
    for seed, pet in enumerate(pets):
        file = roster.create(pet.name)
        file.repo().save(SaveGame(pet, Random(seed).getstate()))
        files.append(file)
    library = PetLibrary(roster, clock=clock or FakeClock(FIXED_NOW), settings=SessionSettings())
    return library, files


def make_library_app(library: PetLibrary, **kwargs: Any) -> TamaApp:
    """A deterministic app over several pets."""
    options: dict[str, Any] = {
        "settings": SessionSettings(),
        "tick_interval": None,
        "handle_signals": False,
        "view": ViewOptions(animate=False),
        **kwargs,
    }
    clock = options.pop("clock", None) or FakeClock(FIXED_NOW)
    return TamaApp(library=library, clock=clock, **options)
