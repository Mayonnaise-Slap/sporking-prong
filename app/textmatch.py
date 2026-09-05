from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz

DEFAULT_MATCH_THRESHOLD = 75.0

_ELLIPSIS_RE = re.compile(r"\s*(?:\.{3}|…)\s*")
_FRAGMENT_RE = re.compile(r"«([^»]{6,})»|\*\*([^*]{6,})\*\*|`([^`]{6,})`|\"([^\"]{6,})\"")


def _fold(text: str) -> str:
    return "".join(char.lower() if len(char.lower()) == 1 else char for char in text)


class _Flat:
    def __init__(self, work: str) -> None:
        pieces: list[str] = []
        lines: list[int] = []
        for number, line in enumerate(work.splitlines(), start=1):
            collapsed = " ".join(line.split())
            if not collapsed:
                continue
            if pieces:
                pieces.append(" ")
                lines.append(number)
            pieces.append(collapsed)
            lines.extend([number] * len(collapsed))
        self.text = "".join(pieces)
        self.lower = _fold(self.text)
        self.line_of_char = lines

    def span(self, start: int, end: int) -> tuple[int, int]:
        first = min(max(start, 0), len(self.line_of_char) - 1)
        last = min(max(end - 1, first), len(self.line_of_char) - 1)
        return self.line_of_char[first], self.line_of_char[last]


def locate(
    quote: Optional[str],
    work: str,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> tuple[Optional[int], Optional[int]]:
    if not quote or not work:
        return None, None
    return _locate(" ".join(quote.split()), _Flat(work), threshold)


def _locate(needle: str, flat: _Flat, threshold: float) -> tuple[Optional[int], Optional[int]]:
    if not needle or not flat.line_of_char:
        return None, None

    start = flat.lower.find(_fold(needle))
    if start >= 0:
        return flat.span(start, start + len(needle))

    parts = [part for part in _ELLIPSIS_RE.split(needle) if part.strip()]
    if len(parts) > 1:
        spans = [_locate(part, flat, threshold) for part in parts]
        found = [(first, last) for first, last in spans if first is not None]
        if found:
            return min(first for first, _ in found), max(last for _, last in found)

    alignment = fuzz.partial_ratio_alignment(
        _fold(needle), flat.lower, score_cutoff=threshold
    )
    if alignment is not None:
        return flat.span(alignment.dest_start, alignment.dest_end)

    fragments = {piece for groups in _FRAGMENT_RE.findall(needle) for piece in groups if piece}
    for fragment in sorted(fragments, key=len, reverse=True):
        found = _locate(" ".join(fragment.split()), flat, threshold)
        if found[0] is not None:
            return found

    return None, None
