from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .identifiers import fqn, identifier, version

CONTROLLED_OPERATION_ERRORS = (OSError, RuntimeError, ValueError)


def is_controlled_operation_error(exc: Exception) -> bool:
    return isinstance(exc, CONTROLLED_OPERATION_ERRORS) or exc.__class__.__module__.startswith(
        "snowflake.connector"
    )


@dataclass(frozen=True, order=True)
class SnowflakeObjectName:
    database: str
    schema: str
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "database", identifier(self.database, "database"))
        object.__setattr__(self, "schema", identifier(self.schema, "schema"))
        object.__setattr__(self, "name", identifier(self.name, "object name"))

    @classmethod
    def parse(cls, value: str, label: str = "object") -> SnowflakeObjectName:
        database, schema, name = fqn(value, label).split(".")
        return cls(database, schema, name)

    def __str__(self) -> str:
        return f"{self.database}.{self.schema}.{self.name}"


class VersionKind(str, Enum):
    COMMITTED = "committed"
    ALIAS = "alias"
    SHORTCUT = "shortcut"


@dataclass(frozen=True)
class AgentVersionSelector:
    value: str
    kind: VersionKind

    @classmethod
    def parse(cls, value: str, label: str = "Agent version") -> AgentVersionSelector:
        text = str(value).strip()
        upper = text.upper()
        if upper.startswith("VERSION$"):
            return cls(version(upper, label), VersionKind.COMMITTED)
        if upper in {"DEFAULT", "FIRST", "LAST", "LIVE"}:
            return cls(upper, VersionKind.SHORTCUT)
        return cls(identifier(text, label), VersionKind.ALIAS)


class LifecyclePhase(str, Enum):
    PREFLIGHT = "preflight"
    SKILLS_UPLOADED = "skills_uploaded"
    VERSION_COMMITTED = "version_committed"
    ALIAS_RECONCILED = "alias_reconciled"
    DEFAULT_RECONCILED = "default_reconciled"
    METADATA_RECONCILED = "metadata_reconciled"
    LIVE_RECONCILED = "live_reconciled"
    VERIFIED = "verified"


@dataclass(frozen=True)
class PhaseResult:
    phase: LifecyclePhase
    completed: bool
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "phase": self.phase.value,
            "completed": self.completed,
        }
        if self.detail is not None:
            result["detail"] = self.detail
        return result


@dataclass(frozen=True)
class OperationOutcome:
    phases: tuple[PhaseResult, ...] = field(default_factory=tuple)

    def complete(self, phase: LifecyclePhase, detail: str | None = None) -> OperationOutcome:
        return OperationOutcome((*self.phases, PhaseResult(phase, True, detail)))

    def fail(self, phase: LifecyclePhase, detail: str) -> OperationOutcome:
        return OperationOutcome((*self.phases, PhaseResult(phase, False, detail)))

    def to_dict(self) -> list[dict[str, Any]]:
        return [result.to_dict() for result in self.phases]


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


class DurablePhaseError(RuntimeError):
    """A controlled failure that preserves already-durable lifecycle phases.

    Snowflake Agent uploads and DDL are durable phase by phase, so a later
    failure never rolls back earlier work. Callers use ``outcome`` to report
    exactly what completed instead of implying a transactional rollback.
    """

    def __init__(self, message: str, outcome: OperationOutcome) -> None:
        super().__init__(message)
        self.outcome = outcome
