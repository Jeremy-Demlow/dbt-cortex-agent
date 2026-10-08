from __future__ import annotations

import re
from pathlib import PurePosixPath

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_VERSION = re.compile(r"^VERSION\$[1-9][0-9]*$", re.IGNORECASE)
_PATH_PART = re.compile(r"^[A-Za-z0-9_$.-]+$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")


def identifier(value: str, label: str = "identifier") -> str:
    text = str(value)
    if not _IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} must be an unquoted Snowflake identifier: {value!r}")
    return text.upper()


def fqn(value: str, label: str, *, parts: int = 3) -> str:
    values = str(value).split(".")
    if len(values) != parts:
        raise ValueError(f"{label} must have {parts} dot-separated identifiers: {value!r}")
    return ".".join(identifier(item, label) for item in values)


def version(value: str, label: str = "version") -> str:
    text = str(value)
    if not _VERSION.fullmatch(text):
        raise ValueError(f"{label} must look like VERSION$N: {value!r}")
    return text.upper()


def stage_path(value: str, label: str = "stage path") -> tuple[str, str]:
    text = str(value)
    if not text.startswith("@") or "/" not in text:
        raise ValueError(f"{label} must look like @DATABASE.SCHEMA.STAGE/folder: {value!r}")
    stage, suffix = text[1:].split("/", 1)
    stage_name = fqn(stage, label)
    path = PurePosixPath(suffix)
    if (
        not suffix
        or suffix.startswith("/")
        or any(part in {"", ".", ".."} or not _PATH_PART.fullmatch(part) for part in path.parts)
    ):
        raise ValueError(f"{label} contains an unsafe folder suffix: {value!r}")
    return stage_name, path.as_posix()


def git_commit_path(value: str, label: str = "Git skill path") -> tuple[str, str, str]:
    """Split ``@DB.SCHEMA.REPO/commits/<sha>/<folder>`` into repository, commit, and folder.

    Only full commit SHAs are accepted: branch and tag paths resolve differently
    after each FETCH, so they cannot pin a committed Agent version.
    """
    repository, suffix = stage_path(value, label)
    parts = suffix.split("/", 2)
    if len(parts) != 3 or parts[0] != "commits" or not _COMMIT.fullmatch(parts[1]):
        raise ValueError(
            f"{label} must look like @DATABASE.SCHEMA.REPOSITORY/commits/<40-character "
            f"commit SHA>/<folder>: {value!r}"
        )
    return repository, parts[1].lower(), parts[2]
