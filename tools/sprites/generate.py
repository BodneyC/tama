"""Regenerate every generated sprite collection.

    uv run python -m tools.sprites.generate

To add a species, write ``tools/sprites/<species>.py`` with ``NAME`` and ``build()`` (copy
``owl.py``) and add it to ``COLLECTIONS``. Only generated collections are rewritten; any
hand-drawn species directory is left alone.
"""

from collections.abc import Callable
from pathlib import Path

from tools.sprites import bear, overlays, owl, tama
from tools.sprites.kit import Collection

ROOT = Path(__file__).resolve().parents[2] / "src" / "tama" / "assets" / "sprites"

COLLECTIONS: tuple[Callable[[], Collection], ...] = (
    tama.build,
    owl.build,
    bear.build,
    overlays.build,
)
"""Every generated collection: one per species, plus the shared overlays."""


def sprite_set() -> dict[Path, str]:
    """Every generated file, keyed by path relative to the sprites root."""
    files: dict[Path, str] = {}
    for build in COLLECTIONS:
        collection = build()
        files.update(
            {Path(collection.name) / path: text for path, text in collection.files.items()}
        )
    return files


def generated_collections() -> set[str]:
    """Names of the directories this script owns."""
    return {build().name for build in COLLECTIONS}


def generate(root: Path = ROOT) -> list[Path]:
    """Write every generated file under ``root``, removing stale files in generated collections."""
    files = sprite_set()
    for name in generated_collections():
        for stale in (root / name).rglob("*.toml"):
            if stale.relative_to(root) not in files:
                stale.unlink()
    written = []
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    paths = generate()
    print(f"Wrote {len(paths)} sprite files under {ROOT}")  # noqa: T201 - CLI output
