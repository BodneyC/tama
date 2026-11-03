"""Naming a new egg."""

from typing import ClassVar, override

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.validation import ValidationResult, Validator
from textual.widgets import Input, Static

from tama.domain.animation import AnimationKey
from tama.domain.pet import MAX_NAME_LENGTH, validate_name
from tama.domain.stage import LifeStage, Variant
from tama.errors import InvalidArgumentError
from tama.ui.sprites import DEFAULT_SPECIES, load_sprite
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


class NewPetScreen(Screen[str]):
    """Shows a fresh egg and asks for its name.

    Dismisses with the (normalised) name, or with ``None`` if the player escapes.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "dismiss", "Quit")]

    def __init__(self, view: ViewOptions | None = None) -> None:
        """Show a wobbling egg, drawn with ``view`` options."""
        super().__init__()
        self._view = view or ViewOptions()

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        with Vertical(id="new-pet"):
            yield Static("A new egg has appeared!", classes="dialog-title")
            yield PetView(self._view, id="egg")
            yield Input(
                placeholder="Name your pet",
                max_length=MAX_NAME_LENGTH,
                validators=[PetNameValidator()],
                validate_on=["submitted"],
                id="name",
            )
            yield Static(id="name-error", markup=False)

    def on_mount(self) -> None:
        """Start the egg wobbling."""
        wobble = load_sprite(DEFAULT_SPECIES, Variant.DEFAULT, LifeStage.EGG, AnimationKey.WOBBLE)
        self.query_one(PetView).set_loop(wobble)

    @on(Input.Submitted, "#name")
    def _submit(self, event: Input.Submitted) -> None:
        result = event.validation_result
        if result is not None and not result.is_valid:
            self.query_one("#name-error", Static).update(NAME_RULE)
            return
        self.dismiss(validate_name(event.value))
