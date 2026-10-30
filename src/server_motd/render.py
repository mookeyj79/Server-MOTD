"""Single-column boxed renderer. Maps Status to colour; the schema has no layout."""

from __future__ import annotations

import textwrap
from collections.abc import Sequence

from server_motd.model import Result, Status

_COLOUR = {
    Status.INFO: "",
    Status.OK: "32",
    Status.WARN: "33",
    Status.CRIT: "31",
    Status.UNAVAILABLE: "31",
}


def _paint(text: str, status: Status, color: bool) -> str:
    code = _COLOUR[status]
    return f"\x1b[{code}m{text}\x1b[0m" if color and code else text


def _line(body: str, plain_len: int, inner: int) -> str:
    return f"│ {body}{' ' * (inner - plain_len)} │"


def render(results: Sequence[Result], width: int, color: bool) -> str:
    width = max(width, 20)
    inner = width - 4
    lines = ["┌" + "─" * (width - 2) + "┐"]
    for n, result in enumerate(results):
        if n:
            lines.append("├" + "─" * (width - 2) + "┤")
        title = result.title[:inner]
        body = f"\x1b[1m{title}\x1b[0m" if color else title
        lines.append(_line(body, len(title), inner))
        label_w = max((len(r.label) for r in result.rows), default=0)
        for row in result.rows:
            prefix = f"{row.label:<{label_w}}  "[: inner - 1]
            room = inner - len(prefix)
            chunks = textwrap.wrap(row.value, room) or [""]
            for k, chunk in enumerate(chunks):
                lead = prefix if k == 0 else " " * len(prefix)
                body = lead + _paint(chunk, row.status, color)
                lines.append(_line(body, len(lead) + len(chunk), inner))
    lines.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(lines) + "\n"
