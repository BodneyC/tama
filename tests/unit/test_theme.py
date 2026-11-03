from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from tama.domain.pet import DEFAULT_SPECIES
from tama.ui import sprites
from tama.ui.colours import Mode
from tama.ui.sprites import UI_KEYS, UiColour, clear_caches
from tama.ui.theme import (
    CSS_PREFIX,
    FALLBACK_COLOUR,
    UiFile,
    css_variables,
    default_ui,
    ui_palette,
)

THEME = {"panel": "#101010", "success": "#00aa00", "foreground": "#eeeeee"}


@pytest.fixture(autouse=True)
def fresh_caches() -> Iterator[None]:
    clear_caches()
    yield
    clear_caches()


def test_defaults_cover_every_ui_colour() -> None:
    assert set(default_ui()) == UI_KEYS


def test_defaults_follow_the_theme() -> None:
    assert default_ui()["header-background"].colour(Mode.DARK) == "$panel"
    assert default_ui()["stat-good"].colour(Mode.LIGHT) == "$success"


def test_species_overrides_replace_defaults() -> None:
    palette = ui_palette(DEFAULT_SPECIES)

    assert palette["accent"] == UiColour(dark="#f6b26b", light="#b45f06")
    assert palette["stat-good"] == default_ui()["stat-good"]


def test_species_without_a_palette_uses_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    assert ui_palette("nobody") == default_ui()


def test_css_variables_pick_the_mode_and_resolve_theme_references() -> None:
    palette = {
        "header-background": UiColour(dark="$panel", light="#fafafa"),
        "accent": UiColour(dark="#111111", light="#222222"),
    }

    dark = css_variables(palette, mode=Mode.DARK, theme_colours=THEME)
    light = css_variables(palette, mode=Mode.LIGHT, theme_colours=THEME)

    assert dark == {f"{CSS_PREFIX}header-background": "#101010", f"{CSS_PREFIX}accent": "#111111"}
    assert light == {f"{CSS_PREFIX}header-background": "#fafafa", f"{CSS_PREFIX}accent": "#222222"}


def test_unknown_theme_reference_falls_back_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    palette = {"accent": UiColour(dark="$nope", light="$nope")}

    variables = css_variables(palette, mode=Mode.DARK, theme_colours=THEME)

    assert variables == {f"{CSS_PREFIX}accent": FALLBACK_COLOUR}
    assert "$nope" in caplog.text


def test_ui_file_must_define_exactly_the_ui_colours() -> None:
    with pytest.raises(ValidationError, match="missing"):
        UiFile.model_validate({"ui": {"accent": "#000000"}})
