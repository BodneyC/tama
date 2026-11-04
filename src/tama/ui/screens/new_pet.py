"""Naming a new egg (and choosing which animal it is)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, override

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.validation import ValidationResult, Validator
from textual.widgets import Input, Static

from tama.domain.animation import AnimationKey
from tama.domain.pet import DEFAULT_SPECIES, MAX_NAME_LENGTH, validate_name
from tama.domain.stage import LifeStage, Variant
from tama.errors import InvalidArgumentError
from tama.ui.sprites import available_species, load_sprite
from tama.ui.widgets.pet_view import PetView, ViewOptions

NAME_RULE = f"Names are 1-{MAX_NAME_LENGTH} printable characters."


class PetNameValidator(Validator):
    """Accepts exactly the names the domain accepts."""

    @override
    def validate(self, value: str) -> ValidationResult:
        """Validate a candidate pet name."""
        try:
            validate_name(value)
        except InvalidArgumentError:
            return self.failure(NAME_RULE)
        return self.success()


@dataclass(frozen=True, slots=True)
class NewPet:
    """What the player chose for their new pet."""

    name: str
    species: str


class NewPetScreen(Screen[NewPet]):
    """Shows a fresh egg, asks for its name, and lets the player pick the animal (up/down).

    Dismisses with a :class:`NewPet`, or with ``None`` if the player escapes.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Quit"),
        # The name Input has no use for up/down, so they can choose the animal while typing.
        Binding("up", "species(-1)", "Previous animal", show=False),
        Binding("down", "species(1)", "Next animal", show=False),
    ]

    def __init__(  # noqa: PLR0913 - all optional, keyword-only after the first two
        self,
        view: ViewOptions | None = None,
        species: str = DEFAULT_SPECIES,
        *,
        taken: Callable[[str], bool] | None = None,
        name: str = "",
        title: str = "A new egg has appeared!",
        locked: bool = False,
    ) -> None:
        """Show a wobbling egg, starting on ``species``, drawn with ``view`` options.

        ``taken`` says whether a living pet already has a name (SPEC §6.1). An heir's egg
        (SPEC §2.8) comes with a ``name`` filled in, its own ``title``, and its species
        ``locked`` to its parent's.
        """
        super().__init__()
        self._taken = taken or (lambda _name: False)
        self._view = view or ViewOptions()
        self._species = species
        self._name = name
        self._title = title
        shipped = available_species()
        choices = shipped if species in shipped else (species, *shipped)
        self._choices = (species,) if locked else choices

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        with Vertical(id="new-pet"):
            yield Static(self._title, classes="dialog-title", markup=False)
            yield PetView(self._view, id="egg")
            yield Static(id="species", markup=False)
            yield Input(
                placeholder="Name your pet",
                max_length=MAX_NAME_LENGTH,
                validators=[PetNameValidator()],
                validate_on=["submitted"],
                value=self._name,
                id="name",
            )
            yield Static(id="name-error", markup=False)

    def on_mount(self) -> None:
        """Start the egg wobbling."""
        self._show_species()

    def action_species(self, step: int) -> None:
        """Switch to the next (``step`` 1) or previous (-1) animal, wrapping around."""
        index = self._choices.index(self._species)
        self._species = self._choices[(index + step) % len(self._choices)]
        self._show_species()

    def _show_species(self) -> None:
        wobble = load_sprite(self._species, Variant.DEFAULT, LifeStage.EGG, AnimationKey.WOBBLE)
        self.query_one(PetView).set_loop(wobble)
        hint = "  (↑↓ to change)" if len(self._choices) > 1 else ""
        self.query_one("#species", Static).update(f"Species: {self._species}{hint}")

    @on(Input.Submitted, "#name")
    def _submit(self, event: Input.Submitted) -> None:
        result = event.validation_result
        if result is not None and not result.is_valid:
            self.query_one("#name-error", Static).update(NAME_RULE)
            return
        name = validate_name(event.value)
        if self._taken(name):
            self.query_one("#name-error", Static).update(f"You already have a {name}.")
            return
        self.dismiss(NewPet(name, self._species))
