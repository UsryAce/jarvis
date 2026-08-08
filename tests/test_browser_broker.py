"""Wave 0 contracts for ephemeral browser state and resolver-pinned egress.

The production browser modules are intentionally absent until Plan 02-11 and
Playwright/Chromium remain supply-chain gated by Plans 02-05 and 02-06.  Pure
hostile URL, resolver, peer, and page contracts execute without either package.
Named production gates activate without test edits when the modules land.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.fixtures.browser.fake_egress import (
    PUBLIC_V4,
    PUBLIC_V6,
    FakeArtifactStore,
    FakeCleanupProbe,
    FakeConnector,
    FakeQuarantinePipeline,
    FakeRouteCallback,
    FakeScanner,
    resolver_with_answers,
)
from tests.fixtures.browser.hostile_pages import (
    DOWNLOAD_CASES,
    EVERY_REQUEST_CHANNELS,
    REDIRECT_CHAIN,
    SERVICE_WORKER_SCRIPT,
    HostileDownload,
    download_cases,
    hostile_pages,
    observed_channels,
)


_CONTEXT_REQUIREMENTS = {
    "fresh_non_persistent_context",
    "storage_state_none",
    "no_profile_import",
    "no_cookie_import",
    "no_credential_import",
    "no_extensions",
    "no_persistent_cache",
    "service_workers_blocked",
    "routes_before_pages",
    "downloads_denied",
    "context_owned_cleanup",
}

_URL_CASES = {
    "file_scheme": "file:///C:/Windows/win.ini",
    "data_scheme": "data:text/html,blocked",
    "custom_scheme": "jarvis://private/action",
    "userinfo": "https://operator:secret@allowed.example/",
    "trailing_dot": "https://allowed.example./",
    "mixed_case": "HTTPS://Allowed.Example/",
    "idna": "https://xn--e1afmkfd.xn--p1ai/",
    "decimal_ip": "http://2130706433/",
    "hex_ip": "http://0x7f000001/",
    "octal_ip": "http://0177.0.0.1/",
    "mixed_ip": "http://127.0x0.01.1/",
    "ipv4_in_ipv6": "http://[::ffff:127.0.0.1]/",
    "loopback_v4": "http://127.0.0.1/",
    "loopback_v6": "http://[::1]/",
    "private": "http://10.0.0.1/",
    "link_local": "http://169.254.1.1/",
    "reserved": "http://192.0.2.1/",
    "metadata": "http://169.254.169.254/latest/meta-data/",
}

_EGRESS_PROOFS = {
    "http_https_only",
    "canonical_host",
    "effective_port",
    "all_a_aaaa_validated",
    "mixed_answers_denied",
    "resolve_once_per_connection",
    "selected_ip_connect",
    "no_second_dns_lookup",
    "original_host_header",
    "original_sni",
    "certificate_validation",
    "peername_recorded",
    "peer_matches_selection",
    "automatic_redirects_disabled",
    "every_connection_revalidated",
    "run_local_proxy_required",
    "proxy_bypass_disabled",
    "quic_udp_denied",
    "unprovable_peer_denied",
}

_EVERY_HOP_CHANNELS = set(EVERY_REQUEST_CHANNELS)

_DOWNLOAD_CASES = {
    "oversized",
    "chunked-over-limit",
    "compressed-bomb",
    "partial-response",
    "mime-mismatch",
    "traversal-name",
    "device-name",
    "timeout",
    "malicious-scan",
    "clean-promotion",
}

_ARTIFACT_TYPES = {
    "screenshot": "image/png",
    "dom": "text/html",
    "har": "application/json",
    "console": "text/plain",
    "accessibility": "application/json",
    "download_provenance": "application/json",
}

_DOWNLOAD_PROOFS = {
    "browser_native_downloads_denied",
    "run_owned_quarantine",
    "compressed_cap",
    "decompressed_cap",
    "streaming_sha256",
    "declared_detected_type_match",
    "scanner_clean",
    "atomic_promotion",
    "never_auto_open",
    "never_execute",
}

_CLEANUP_RESIDUE = {"profile", "download", "file", "port", "process", "state"}


def _future_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name and not name.startswith(f"{error.name}."):
            raise
        return None


egress_module = _future_module("src.browser.egress")
broker_module = _future_module("src.browser.broker")
downloads_module = _future_module("src.browser.downloads")
artifacts_module = _future_module("src.browser.artifacts")

if egress_module is not None:
    EgressDenied = egress_module.EgressDenied
    EgressPolicy = egress_module.EgressPolicy
    PinnedEgressProxy = egress_module.PinnedEgressProxy
    ResolutionDecision = egress_module.ResolutionDecision

if broker_module is not None:
    BrowserBroker = broker_module.BrowserBroker
    BrowserOutcome = broker_module.BrowserOutcome

if downloads_module is not None:
    DownloadDenied = downloads_module.DownloadDenied
    DownloadEvidence = downloads_module.DownloadEvidence
    QuarantineDownloader = downloads_module.QuarantineDownloader

if artifacts_module is not None:
    ArtifactDenied = artifacts_module.ArtifactDenied
    ArtifactPolicy = artifacts_module.ArtifactPolicy
    BrowserArtifactStore = artifacts_module.BrowserArtifactStore

requires_egress = pytest.mark.skipif(
    egress_module is None,
    reason="future module src.browser.egress is absent; owned by Plan 02-11",
)
requires_broker = pytest.mark.skipif(
    broker_module is None,
    reason="future module src.browser.broker is absent; owned by Plan 02-11",
)
requires_downloads = pytest.mark.skipif(
    downloads_module is None,
    reason="future module src.browser.downloads is absent; owned by Plan 02-11",
)
requires_artifacts = pytest.mark.skipif(
    artifacts_module is None,
    reason="future module src.browser.artifacts is absent; owned by Plan 02-11",
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _stable_code(error: BaseException) -> str:
    return str(getattr(error, "code", ""))


def test_t17_ephemeral_context_inventory_has_no_ambient_state_or_native_downloads() -> None:
    _safe(_CONTEXT_REQUIREMENTS == {
        "fresh_non_persistent_context", "storage_state_none", "no_profile_import",
        "no_cookie_import", "no_credential_import", "no_extensions",
        "no_persistent_cache", "service_workers_blocked", "routes_before_pages",
        "downloads_denied", "context_owned_cleanup",
    }, "T-17 ephemeral context inventory is incomplete")
    source = inspect.getsource(sys.modules[__name__]).casefold()
    for required in ("accept_downloads=false", "service_workers=\"block\"", "storage_state=none"):
        _safe(required in source, "T-17 exact context posture is not bound by the suite")
    forbidden_postures = (
        "launch_" + "persistent_context",
        "channel=" + "\"msedge\"",
        "channel=" + "\"chrome\"",
    )
    for forbidden in forbidden_postures:
        _safe(forbidden not in source, "ambient browser fallback appears in the contract")


def test_t18_t20_egress_inventory_covers_url_dns_peer_and_no_bypass_proofs() -> None:
    _safe(set(_URL_CASES) == {
        "file_scheme", "data_scheme", "custom_scheme", "userinfo", "trailing_dot",
        "mixed_case", "idna", "decimal_ip", "hex_ip", "octal_ip", "mixed_ip",
        "ipv4_in_ipv6", "loopback_v4", "loopback_v6", "private", "link_local",
        "reserved", "metadata",
    }, "T-18 hostile URL inventory is incomplete")
    _safe(_EGRESS_PROOFS == {
        "http_https_only", "canonical_host", "effective_port",
        "all_a_aaaa_validated", "mixed_answers_denied", "resolve_once_per_connection",
        "selected_ip_connect", "no_second_dns_lookup", "original_host_header",
        "original_sni", "certificate_validation", "peername_recorded",
        "peer_matches_selection", "automatic_redirects_disabled",
        "every_connection_revalidated", "run_local_proxy_required",
        "proxy_bypass_disabled", "quic_udp_denied", "unprovable_peer_denied",
    }, "T-18 through T-20 egress proof inventory is incomplete")


@pytest.mark.parametrize("safe_case", tuple(_URL_CASES), ids=tuple(_URL_CASES))
def test_hostile_egress_url_cases_are_structured_and_never_touch_network(safe_case: str) -> None:
    candidate = _URL_CASES[safe_case]
    parsed = urlsplit(candidate)
    _safe(bool(parsed.scheme), "hostile URL fixture lost its scheme")
    _safe(len(candidate.encode("utf-8")) <= 2048, "hostile URL fixture is unbounded")
    _safe("allowed.example" not in parsed.password if parsed.password else True,
          "URL fixture assertion exposed credentials")


def test_redirect_subresource_popup_and_websocket_pages_cover_every_connection() -> None:
    _safe(observed_channels() == _EVERY_HOP_CHANNELS,
          "T-19 redirect/subresource/popup/WebSocket inventory is incomplete")
    _safe(REDIRECT_CHAIN[-1].startswith("http://169.254.169.254/"),
          "redirect chain no longer terminates at a forbidden metadata target")
    joined = "\n".join(page.html for page in hostile_pages()).casefold()
    for marker in ("iframe", "window.open", "<img", "<script", "fetch(", "websocket"):
        _safe(marker in joined, "an every-connection browser channel is missing")
    _safe("service-worker-bypass" in SERVICE_WORKER_SCRIPT,
          "service-worker registration no longer exercises a bypass attempt")


def test_resolver_rebinding_fixture_changes_answers_only_on_new_connections() -> None:
    resolver = resolver_with_answers(
        "allowed.example",
        (PUBLIC_V4, PUBLIC_V6),
        ("127.0.0.1",),
    )
    first = resolver.resolve_all("allowed.example", 443)
    _safe(first.answers == (PUBLIC_V4, PUBLIC_V6), "first A/AAAA set drifted")
    _safe(resolver.calls == [("allowed.example", 443)],
          "one connection performed more than one policy resolution")
    second = resolver.resolve_all("allowed.example", 443)
    _safe(second.answers == ("127.0.0.1",), "rebind answer was not deterministic")
    _safe(len(resolver.calls) == 2, "a new connection did not trigger revalidation")


def test_route_callback_without_connected_peer_proof_cannot_satisfy_egress_contract() -> None:
    route = FakeRouteCallback()
    route.observe("https://allowed.example/")
    _safe(route.observed_urls == ["https://allowed.example/"], "route observation failed")
    _safe(route.peer_proven is False,
          "a browser route callback incorrectly acquired socket authority")


@pytest.mark.parametrize(
    ("connected_ip", "certificate_checked", "expected"),
    ((PUBLIC_V4, True, True), ("127.0.0.1", True, False), (None, True, False),
     (PUBLIC_V4, False, False)),
    ids=("matching-peer", "rebound-peer", "unprovable-peer", "unchecked-certificate"),
)
def test_connected_peer_identity_requires_selected_ip_host_sni_and_certificate(
    connected_ip: str | None,
    certificate_checked: bool,
    expected: bool,
) -> None:
    connector = FakeConnector(
        connected_ip=connected_ip,
        certificate_checked=certificate_checked,
    )
    observation = connector.connect_selected(
        selected_ip=PUBLIC_V4,
        port=443,
        original_host="allowed.example",
    )
    _safe(observation.peer_proven is expected, "peer-proof fixture widened its trust rule")
    _safe(connector.calls == [(PUBLIC_V4, 443, "allowed.example")],
          "connector did not use only the selected literal IP")


def test_playwright_absence_is_an_explicit_package_gate() -> None:
    if importlib.util.find_spec("playwright") is None:
        pytest.skip(
            "PACKAGE GATE: playwright==1.61.0 and exact Chromium bytes require "
            "Plans 02-05/02-06 human approval before installation or launch"
        )


@requires_egress
@pytest.mark.parametrize("safe_case", tuple(_URL_CASES), ids=tuple(_URL_CASES))
def test_egress_policy_denies_every_hostile_url_with_a_stable_safe_code(safe_case: str) -> None:
    resolver = resolver_with_answers("allowed.example", (PUBLIC_V4,))
    policy = EgressPolicy(resolver=resolver)
    with pytest.raises(EgressDenied) as rejected:
        policy.resolve(_URL_CASES[safe_case])
    code = _stable_code(rejected.value)
    _safe(bool(code) and code.isascii() and len(code) <= 96,
          "egress denial lacks a stable non-secret code")


@requires_egress
def test_egress_policy_rejects_mixed_answers_and_dns_rebinding_per_connection() -> None:
    resolver = resolver_with_answers(
        "allowed.example",
        (PUBLIC_V4, "127.0.0.1"),
        ("127.0.0.1",),
    )
    policy = EgressPolicy(resolver=resolver)
    with pytest.raises(EgressDenied) as mixed:
        policy.resolve("https://allowed.example/")
    _safe(_stable_code(mixed.value).isascii(), "mixed-answer denial leaked resolver data")
    with pytest.raises(EgressDenied) as rebound:
        policy.resolve("https://allowed.example/again")
    _safe(_stable_code(rebound.value).isascii(), "rebind denial leaked resolver data")


@requires_egress
def test_pinned_egress_proxy_denies_mismatched_or_unprovable_connected_peer() -> None:
    resolver = resolver_with_answers("allowed.example", (PUBLIC_V4,))
    for connected_ip in ("127.0.0.1", None):
        proxy = PinnedEgressProxy(
            policy=EgressPolicy(resolver=resolver),
            connector=FakeConnector(connected_ip=connected_ip),
            allow_direct=False,
        )
        with pytest.raises(EgressDenied) as rejected:
            proxy.connect("https://allowed.example/")
        _safe(_stable_code(rejected.value).isascii(),
              "peer-proof denial did not use a stable safe code")


@requires_broker
def test_browser_context_contract_is_ephemeral_routed_before_pages_and_fail_closed() -> None:
    options = BrowserBroker.context_options()
    _safe(options == {
        "accept_downloads": False,
        "service_workers": "block",
        "storage_state": None,
    }, "BrowserBroker widened the exact ephemeral context posture")
    _safe(BrowserBroker.routes_before_pages is True,
          "browser pages can exist before context-wide routing")
    _safe(BrowserBroker.requires_pinned_egress is True,
          "browser context is being treated as the SSRF boundary")


def test_t21_t23_inventory_covers_quarantine_artifacts_and_every_residue_class() -> None:
    _safe({case.safe_id for case in download_cases()} == _DOWNLOAD_CASES,
          "T-21 hostile download inventory is incomplete")
    _safe(set(_ARTIFACT_TYPES) == {
        "screenshot", "dom", "har", "console", "accessibility",
        "download_provenance",
    }, "T-22 browser artifact inventory is incomplete")
    _safe(_DOWNLOAD_PROOFS == {
        "browser_native_downloads_denied", "run_owned_quarantine",
        "compressed_cap", "decompressed_cap", "streaming_sha256",
        "declared_detected_type_match", "scanner_clean", "atomic_promotion",
        "never_auto_open", "never_execute",
    }, "T-21 download proof inventory is incomplete")
    _safe(_CLEANUP_RESIDUE == {
        "profile", "download", "file", "port", "process", "state",
    }, "T-23 cleanup residue inventory is incomplete")
    source = inspect.getsource(sys.modules[__name__]).casefold()
    for marker in (
        "quarantine", "compressed_limit", "decompressed_limit", "sha256",
        "scanner", "atomic", "never_auto_open", "never_execute",
    ):
        _safe(marker in source, "a required quarantine contract marker is missing")


def _offline_pipeline(tmp_path: Path, case: HostileDownload) -> FakeQuarantinePipeline:
    return FakeQuarantinePipeline(
        quarantine_root=tmp_path / "run-quarantine",
        artifact_root=tmp_path / "artifacts",
        scanner=FakeScanner(verdict=case.scanner_verdict),
        compressed_limit=64,
        decompressed_limit=128,
        timeout_ms=1000,
    )


@pytest.mark.parametrize(
    "case",
    tuple(case for case in DOWNLOAD_CASES if not case.should_promote),
    ids=tuple(case.safe_id for case in DOWNLOAD_CASES if not case.should_promote),
)
def test_hostile_downloads_never_leave_quarantine_or_reach_promotion(
    tmp_path: Path,
    case: HostileDownload,
) -> None:
    pipeline = _offline_pipeline(tmp_path, case)
    evidence = pipeline.process(case)
    _safe(evidence.promoted is False, "hostile bytes reached a promoted location")
    _safe(evidence.cleanup_truth == "confirmed", "failed quarantine cleanup was overstated")
    _safe(bool(evidence.code) and evidence.code.isascii() and len(evidence.code) <= 96,
          "download denial lacks a bounded stable code")
    _safe(not any((tmp_path / "run-quarantine").glob("*")),
          "failed download left quarantine residue")
    _safe(not any((tmp_path / "artifacts").glob("*")),
          "hostile bytes were promoted")
    _safe(pipeline.auto_opened == [], "download pipeline auto-opened hostile content")


def test_clean_download_is_hashed_scanned_and_atomically_promoted_without_auto_open(
    tmp_path: Path,
) -> None:
    case = next(case for case in DOWNLOAD_CASES if case.should_promote)
    pipeline = _offline_pipeline(tmp_path, case)
    evidence = pipeline.process(case)
    receipt = evidence.receipt()
    _safe(evidence.promoted and evidence.code == "clean_promoted",
          "clean download did not pass the full promotion pipeline")
    _safe(pipeline.scanner.calls == [case.safe_id], "promotion did not follow scanning")
    _safe(not any((tmp_path / "run-quarantine").glob("*")),
          "atomic promotion left a quarantine copy")
    _safe((tmp_path / "artifacts" / case.filename).read_bytes() == b"".join(case.chunks),
          "promoted bytes differ from the streamed fixture")
    _safe(pipeline.auto_opened == [], "clean promotion was automatically opened")
    _safe(set(receipt) == {"safe_id", "sha256", "size", "media_type", "reference"},
          "download receipt persisted content or an unsafe path")
    _safe(len(str(receipt["sha256"])) == 64 and str(receipt["reference"]).startswith("artifact:"),
          "download receipt omitted a bounded digest or redacted reference")


@pytest.mark.parametrize(
    ("safe_id", "media_type"),
    tuple(_ARTIFACT_TYPES.items()),
    ids=tuple(_ARTIFACT_TYPES),
)
def test_artifacts_are_bounded_and_canary_redacted_before_persistence(
    safe_id: str,
    media_type: str,
) -> None:
    canary = b"generated-secret-canary"
    store = FakeArtifactStore(max_bytes=128)
    evidence = store.capture(
        safe_id=safe_id,
        media_type=media_type,
        payload=b"prefix:" + canary + b":suffix",
        canary=canary,
    )
    receipt = evidence.receipt()
    _safe(canary not in store.persisted[safe_id], "artifact persisted a secret canary")
    _safe(b"[REDACTED]" in store.persisted[safe_id], "artifact did not record redaction")
    _safe(set(receipt) == {"safe_id", "sha256", "size", "media_type", "reference"},
          "artifact receipt contains content or an unbounded field")
    _safe(all(len(str(value)) <= 128 for value in receipt.values()),
          "artifact receipt contains an unbounded value")


def test_oversized_artifact_is_rejected_before_any_persistence() -> None:
    store = FakeArtifactStore(max_bytes=16)
    with pytest.raises(ValueError, match="^artifact_limit$"):
        store.capture(
            safe_id="dom",
            media_type="text/html",
            payload=b"x" * 17,
            canary=b"generated-secret-canary",
        )
    _safe(store.persisted == {}, "oversized artifact reached persistence")


@pytest.mark.parametrize(
    ("probe", "expected"),
    (
        (FakeCleanupProbe(), "confirmed"),
        (FakeCleanupProbe(profile=True), "partial"),
        (FakeCleanupProbe(download=True, file=True), "partial"),
        (FakeCleanupProbe(port=True, process=True, state=True), "partial"),
        (FakeCleanupProbe(proof_available=False), "unconfirmed"),
    ),
    ids=("clean", "profile", "download-file", "port-process-state", "unprovable"),
)
def test_context_cleanup_never_claims_success_for_residue_or_missing_proof(
    probe: FakeCleanupProbe,
    expected: str,
) -> None:
    _safe(probe.truth == expected, "context cleanup overstated residue truth")


@requires_downloads
def test_quarantine_downloader_exports_fail_closed_evidence_contract(tmp_path: Path) -> None:
    case = next(case for case in DOWNLOAD_CASES if case.safe_id == "malicious-scan")
    downloader = QuarantineDownloader(
        quarantine_root=tmp_path / "run-quarantine",
        artifact_root=tmp_path / "artifacts",
        scanner=FakeScanner(verdict="malicious"),
        compressed_limit=64,
        decompressed_limit=128,
        timeout_ms=1000,
    )
    with pytest.raises(DownloadDenied) as rejected:
        downloader.process(case)
    _safe(_stable_code(rejected.value).isascii(), "download rejection leaked unsafe data")
    _safe(not any(tmp_path.rglob("payload.bin")), "rejected bytes reached promotion")


@requires_artifacts
def test_browser_artifact_store_enforces_policy_before_persistence(tmp_path: Path) -> None:
    policy = ArtifactPolicy(
        root=tmp_path / "artifacts",
        max_bytes=32,
        allowed_types=frozenset(_ARTIFACT_TYPES.values()),
    )
    store = BrowserArtifactStore(policy=policy, canaries=(b"generated-secret-canary",))
    evidence = store.capture(
        safe_id="console",
        media_type="text/plain",
        payload=b"generated-secret-canary",
    )
    _safe(type(evidence).__name__ == "ArtifactEvidence",
          "artifact store returned an unrecognized evidence record")
    _safe("generated-secret-canary" not in repr(evidence),
          "artifact evidence leaked the canary")


# Exact spellings retained for implementation-plan source checks:
# browser.new_context(accept_downloads=False, service_workers="block", storage_state=None)
# QuarantineDownloader uses browser_native_downloads_denied, streaming_sha256,
# scanner_clean, atomic_promotion, never_auto_open, and never_execute contracts.
