from __future__ import annotations

import re
from pathlib import Path


ARTIFACT_SCHEMA_VERSION = 2
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def artifact_slug(value: object, label: str) -> str:
    text = str(value)
    if text in {".", ".."} or not _SLUG.fullmatch(text):
        raise ValueError(f"{label} must be a safe artifact slug: {value!r}")
    return text


def contained_path(root: str | Path, *components: object) -> Path:
    base = Path(root).resolve()
    target = base.joinpath(*(artifact_slug(value, "artifact path component") for value in components))
    resolved = target.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Artifact path escapes configured root {base}: {resolved}") from exc
    return resolved