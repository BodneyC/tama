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
from tama.ui.sprites import load_frames

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

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        egg = load_frames(Variant.DEFAULT, LifeStage.EGG, AnimationKey.IDLE)[0]
        with Vertical(id="new-pet"):
            yield Static("A new egg has appeared!", classes="dialog-title")
            yield Static(egg, id="egg", markup=False)
            yield Input(
                placeholder="Name your pet",
                max_length=MAX_NAME_LENGTH,
                validators=[PetNameValidator()],
                validate_on=["submitted"],
                id="name",
            )
            yield Static(id="name-error", markup=False)

    @on(Input.Submitted, "#name")
    def _submit(self, event: Input.Submitted) -> None:
        result = event.validation_result
        if result is not None and not result.is_valid:
            self.query_one("#name-error", Static).update(NAME_RULE)
            return
        self.dismiss(validate_name(event.value))
