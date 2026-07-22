"""Reusable, secret-safe fixtures for the Phase 1 trust contract suites."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest


@dataclass
class FakeClock:
    """UTC clock whose value advances only when a test asks it to."""

    current: datetime = field(
        default_factory=lambda: datetime(2030, 1, 1, tzinfo=timezone.utc)
    )

    def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: float = 0) -> datetime:
        self.current += timedelta(seconds=seconds)
        return self.current


@dataclass(frozen=True)
class GeneratedOperatorMaterial:
    """Generated values that must never be interpolated into failure messages."""

    bootstrap_secret: str
    scopes: tuple[str, ...]
    actor_id: str = "operator-fixture"


@dataclass
class SinkCapture:
    """Named test sinks used to prove sensitive material was not emitted."""

    responses: list[Any] = field(default_factory=list)
    logs: list[Any] = field(default_factory=list)
    audits: list[Any] = field(default_factory=list)
    artifacts: list[Any] = field(default_factory=list)

    def named_values(self) -> dict[str, tuple[Any, ...]]:
        return {
            "responses": tuple(self.responses),
            "logs": tuple(self.logs),
            "audits": tuple(self.audits),
            "artifacts": tuple(self.artifacts),
        }


@dataclass
class CrashPoint:
    """Deterministic fault hook for transaction and lifecycle boundary tests."""

    armed_at: str | None = None
    hits: list[str] = field(default_factory=list)

    def arm(self, boundary: str) -> None:
        self.armed_at = boundary

    def __call__(self, boundary: str) -> None:
        self.hits.append(boundary)
        if self.armed_at == boundary:
            raise RuntimeError(f"injected crash at safe boundary {boundary}")


@dataclass
class FakeRuntimeTree:
    """Minimal effect tree for proving stop guards block new work honestly."""

    effects: list[str] = field(default_factory=list)
    descendants: dict[str, bool] = field(default_factory=dict)

    def start_effect(self, safe_id: str) -> None:
        self.effects.append(safe_id)

    def add_descendant(self, safe_id: str, *, confirmed_stopped: bool = False) -> None:
        self.descendants[safe_id] = confirmed_stopped

    def confirm_stopped(self, safe_id: str) -> None:
        self.descendants[safe_id] = True


@pytest.fixture
def isolated_control_path(tmp_path: Path) -> Path:
    """Return a fresh control.db path outside the repository's durable data dir."""

    path = tmp_path / "data" / "control.db"
    path.parent.mkdir(parents=True)
    return path


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def operator_session_factory() -> Callable[..., GeneratedOperatorMaterial]:
    """Generate non-production bootstrap material without reading environment state."""

    def factory(
        *,
        scopes: tuple[str, ...] = (
            "operator.read",
            "operator.execute",
            "runs.control",
            "approvals.write",
            "secrets.admin",
            "voice.use",
            "emergency.stop",
        ),
        actor_id: str = "operator-fixture",
    ) -> GeneratedOperatorMaterial:
        return GeneratedOperatorMaterial(
            bootstrap_secret=secrets.token_urlsafe(48),
            scopes=scopes,
            actor_id=actor_id,
        )

    return factory


@pytest.fixture
def restricted_scope_session(operator_session_factory):
    return operator_session_factory(scopes=("operator.read",))


@pytest.fixture
def csrf_pair() -> tuple[str, str]:
    """Return a synchronizer token and a distinct invalid token."""

    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


@pytest.fixture
def capture_sinks() -> SinkCapture:
    return SinkCapture()


@pytest.fixture
def crash_point() -> CrashPoint:
    return CrashPoint()


@pytest.fixture
def fake_runtime_tree() -> FakeRuntimeTree:
    return FakeRuntimeTree()
