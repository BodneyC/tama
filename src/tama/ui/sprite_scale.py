"""Half-size pixel art, for the small pets beside a pet-vs-pet board (SPEC §5.1)."""

from collections import Counter
from collections.abc import Sequence

TRANSPARENT = "."


def halve(rows: Sequence[str]) -> tuple[str, ...]:
    """Shrink pixel rows to half the width and height, keeping the face.

    Each 2×2 block becomes one pixel. Inside the body (a block with no transparent pixel) the
    colour that is rarest in the whole frame wins, so one-pixel eyes, mouths and cheeks
    survive; at the edges the most common colour wins (transparent unless two are inked).
    The result has an even height (padded at the top), as sprites need.
    """
    width = len(rows[0]) if rows else 0
    padded = [row + TRANSPARENT * (width % 2) for row in rows]
    if len(padded) % 2:
        padded.append(TRANSPARENT * len(padded[0]))
    frequency = Counter(p for row in padded for p in row if p != TRANSPARENT)
    small: list[str] = []
    for y in range(0, len(padded), 2):
        line: list[str] = []
        for x in range(0, len(padded[0]), 2):
            block = [padded[y][x], padded[y][x + 1], padded[y + 1][x], padded[y + 1][x + 1]]
            line.append(_pixel(block, frequency))
        small.append("".join(line))
    if len(small) % 2:
        small.insert(0, TRANSPARENT * len(small[0]))
    return tuple(small)


def _pixel(block: list[str], frequency: Counter[str]) -> str:
    ink = [p for p in block if p != TRANSPARENT]
    if len(ink) < 2:
        return TRANSPARENT
    if len(ink) == len(block):
        return min(ink, key=lambda p: (frequency[p], block.index(p)))
    return Counter(ink).most_common(1)[0][0]
