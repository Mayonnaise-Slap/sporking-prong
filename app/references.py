from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://\S+")
_OFFLOAD_RE = re.compile(
    r"(?:в|во|на)\s+(?:отдельн\w+\s+)?"
    r"(?:excel\w*|экселе|google\s*sheets?|таблиц\w+|вкладк\w+|приложени\w+|вложени\w+|файл\w+)"
    r"|см\.?\s*(?:таблиц\w+|приложени\w+|файл\w+)",
    re.IGNORECASE,
)


def external_references(text: str, limit: int = 10) -> tuple[str, ...]:
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        collapsed = " ".join(line.split())
        if not collapsed:
            continue
        if _URL_RE.search(collapsed) or _OFFLOAD_RE.search(collapsed):
            found.append(f"стр. {number}: {collapsed[:200]}")
            if len(found) >= limit:
                break
    return tuple(found)


def references_block(work: str) -> str:
    references = external_references(work)
    if not references:
        return ""
    listed = "\n".join(f"[{n}] {ref}" for n, ref in enumerate(references, start=1))
    return "\n\nВЫНЕСЕННЫЕ МАТЕРИАЛЫ (их содержимое сюда не попало):\n" + listed
