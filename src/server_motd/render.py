"""Boxed renderer: banner, then one or two columns of result blocks.

Maps Status to colour; the schema has no layout. Two columns at TWO_COLUMN_MIN
columns wide or more, one below. A row is abbreviated only if it won't fit.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import NamedTuple

from server_motd.model import Result, Status

TWO_COLUMN_MIN = 70

_COLOUR = {
    Status.INFO: "",
    Status.OK: "32",
    Status.WARN: "33",
    Status.CRIT: "31",
    Status.UNAVAILABLE: "31",
}


class BoxStyle(NamedTuple):
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str
    lt: str  # left tee
    rt: str  # right tee
    tt: str  # tee pointing down
    bt: str  # tee pointing up


BOX_STYLES: dict[str, BoxStyle] = {
    "single": BoxStyle("┌", "┐", "└", "┘", "─", "│", "├", "┤", "┬", "┴"),
    "rounded": BoxStyle("╭", "╮", "╰", "╯", "─", "│", "├", "┤", "┬", "┴"),
    "double": BoxStyle("╔", "╗", "╚", "╝", "═", "║", "╠", "╣", "╦", "╩"),
    "heavy": BoxStyle("┏", "┓", "┗", "┛", "━", "┃", "┣", "┫", "┳", "┻"),
    "ascii": BoxStyle("+", "+", "+", "+", "-", "|", "+", "+", "+", "+"),
}


class _Line(NamedTuple):
    text: str  # may contain escape codes
    width: int  # printable width


_BLANK = _Line("", 0)


def _paint(text: str, status: Status, color: bool) -> str:
    code = _COLOUR[status]
    return f"\x1b[{code}m{text}\x1b[0m" if color and code else text


def _bold(text: str, color: bool) -> str:
    return f"\x1b[1m{text}\x1b[0m" if color else text


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(width - 1, 0)] + "…"


def _block(result: Result, width: int, color: bool) -> list[_Line]:
    title = _fit(result.title, width)
    lines = [_Line(_bold(title, color), len(title))]
    label_w = max((len(r.label) for r in result.rows), default=0)
    for row in result.rows:
        prefix = f"{row.label:<{label_w}}  "
        if len(prefix) >= width:
            prefix = _fit(prefix.rstrip(), width - 1) + " "
        value = _fit(row.value, width - len(prefix))
        text = prefix + _paint(value, row.status, color)
        lines.append(_Line(text, len(prefix + value)))
    return lines


def _stack(blocks: list[list[_Line]]) -> list[_Line]:
    out: list[_Line] = []
    for block in blocks:
        if out:
            out.append(_BLANK)
        out.extend(block)
    return out


def _split(blocks: list[list[_Line]]) -> list[list[_Line]]:
    """Fill the left column in order until it holds about half the lines."""
    total = sum(len(b) + 1 for b in blocks)
    cut = len(blocks)
    used = 0
    for i, block in enumerate(blocks):
        if used * 2 >= total:
            cut = i
            break
        used += len(block) + 1
    return [_stack(blocks[:cut]), _stack(blocks[cut:])]


def _figlet(title: str, inner: int) -> list[str]:
    """Figlet art for the title, or [] if pyfiglet is absent or art is too wide."""
    try:
        pyfiglet = importlib.import_module("pyfiglet")
        art = str(pyfiglet.figlet_format(title, width=inner))
    except Exception:
        return []
    lines = [s.rstrip() for s in art.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    if not lines or max(len(s) for s in lines) > inner:
        return []
    return lines


def _banner(title: str, inner: int, color: bool) -> list[_Line]:
    art = _figlet(title, inner)
    if not art:
        art = [_fit(title, inner)]
    return [_Line(_bold(s, color), len(s)) for s in art]


def _row(style: BoxStyle, cells: Sequence[_Line], widths: Sequence[int]) -> str:
    out = style.v
    for cell, w in zip(cells, widths, strict=True):
        out += f" {cell.text}{' ' * (w - cell.width)} {style.v}"
    return out


def render(
    results: Sequence[Result],
    width: int,
    color: bool,
    title: str = "",
    box: str = "single",
) -> str:
    style = BOX_STYLES.get(box, BOX_STYLES["single"])
    width = max(width, 20)
    inner = width - 4
    if width >= TWO_COLUMN_MIN:
        left = (width - 7) // 2
        widths = [left, width - 7 - left]
    else:
        widths = [inner]

    def border(lc: str, mid: str, rc: str, tee: str) -> str:
        if len(widths) == 1:
            return lc + mid * (width - 2) + rc
        return lc + mid * (widths[0] + 2) + tee + mid * (widths[1] + 2) + rc

    lines = [style.tl + style.h * (width - 2) + style.tr]
    lines += [_row(style, [b], [inner]) for b in _banner(title, inner, color)]
    lines.append(border(style.lt, style.h, style.rt, style.tt))

    blocks = [_block(r, min(widths), color) for r in results]
    cols = _split(blocks) if len(widths) == 2 else [_stack(blocks)]
    for i in range(max(len(c) for c in cols)):
        cells = [c[i] if i < len(c) else _BLANK for c in cols]
        lines.append(_row(style, cells, widths))
    lines.append(border(style.bl, style.h, style.br, style.bt))
    return "\n".join(lines) + "\n"
