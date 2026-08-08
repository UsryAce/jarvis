"""Deterministic resolver, peer, transport, and scanner browser doubles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:2800:220:1:248:1893:25c8:1946"


@dataclass(frozen=True)
class ResolutionObservation:
    host: str
    port: int
    answers: tuple[str, ...]


@dataclass
class FakeResolver:
    """Return scripted A/AAAA sets and expose exactly when resolution occurred."""

    scripted_answers: dict[str, tuple[tuple[str, ...], ...]]
    calls: list[tuple[str, int]] = field(default_factory=list)

    def resolve_all(self, host: str, port: int) -> ResolutionObservation:
        self.calls.append((host, port))
        sequences = self.scripted_answers.get(host)
        if not sequences:
            return ResolutionObservation(host=host, port=port, answers=())
        index = min(self.calls.count((host, port)) - 1, len(sequences) - 1)
        return ResolutionObservation(host=host, port=port, answers=sequences[index])


@dataclass(frozen=True)
class PeerObservation:
    selected_ip: str
    connected_ip: str | None
    original_host: str
    sni_host: str
    certificate_checked: bool

    @property
    def peer_proven(self) -> bool:
        return (
            self.connected_ip is not None
            and self.connected_ip == self.selected_ip
            and self.original_host == self.sni_host
            and self.certificate_checked
        )


@dataclass
class FakeConnector:
    """Connect only to the selected literal IP; never performs DNS itself."""

    connected_ip: str | None = None
    certificate_checked: bool = True
    calls: list[tuple[str, int, str]] = field(default_factory=list)

    def connect_selected(
        self,
        *,
        selected_ip: str,
        port: int,
        original_host: str,
    ) -> PeerObservation:
        self.calls.append((selected_ip, port, original_host))
        return PeerObservation(
            selected_ip=selected_ip,
            connected_ip=self.connected_ip,
            original_host=original_host,
            sni_host=original_host,
            certificate_checked=self.certificate_checked,
        )


@dataclass
class FakeRouteCallback:
    """A browser route hook that intentionally has no socket-peer authority."""

    observed_urls: list[str] = field(default_factory=list)

    def observe(self, url: str) -> None:
        self.observed_urls.append(url)

    @property
    def peer_proven(self) -> bool:
        return False


def resolver_with_answers(host: str, *answer_sets: Iterable[str]) -> FakeResolver:
    """Build a resolver whose answer may change on later connections."""

    return FakeResolver(
        scripted_answers={host: tuple(tuple(answers) for answers in answer_sets)}
    )
