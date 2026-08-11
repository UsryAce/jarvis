"""Fail-closed verifier for the Phase 2 download-only package receipt.

Wheel archives are opened only as ZIP files. Nothing in an artifact is imported,
installed, extracted, or executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
import zipfile
from email.parser import BytesParser
from email.policy import compat32
from pathlib import Path
from typing import Any, Mapping, Sequence

from packaging.requirements import InvalidRequirement, Requirement
from packaging.tags import Tag
from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version


SCHEMA_VERSION = "jarvis.phase2.package-provenance.v1"
EXPECTED_ROOTS = {"cryptography": "49.0.0", "playwright": "1.61.0"}
PYPI_HOST = "pypi.org"
PYPI_FILE_HOST = "files.pythonhosted.org"
SDIST_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip")


class ProvenanceError(ValueError):
    """A stable, non-secret failure suitable for an approval gate."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise ProvenanceError(code)


def _unique_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("manifest_duplicate_key")
        result[key] = value
    return result


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load canonical JSON while rejecting duplicate keys and wrong schemas."""

    try:
        raw = Path(path).read_text(encoding="utf-8")
        manifest = json.loads(raw, object_pairs_hook=_unique_object)
    except ProvenanceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("manifest_unreadable")
    if type(manifest) is not dict:
        _fail("manifest_invalid")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        _fail("manifest_schema_mismatch")
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        _fail("artifact_unreadable")
    return digest.hexdigest()


def parse_wheel_artifact(path: str | Path) -> dict[str, Any]:
    """Parse identity and tags from a wheel filename without opening its code."""

    wheel_path = Path(path)
    if wheel_path.suffix.lower() != ".whl":
        _fail("source_distribution_forbidden")
    try:
        name, version, build, tags = parse_wheel_filename(wheel_path.name)
    except (InvalidWheelFilename, InvalidVersion, ValueError):
        _fail("wheel_filename_invalid")
    return {
        "path": wheel_path,
        "filename": wheel_path.name,
        "name": str(canonicalize_name(name)),
        "version": str(version),
        "build": tuple(build) if build else (),
        "filename_tags": sorted(str(tag) for tag in tags),
    }


def read_wheel_metadata(path: str | Path) -> dict[str, Any]:
    """Read only METADATA, WHEEL, and Playwright's declared browsers contract."""

    wheel_path = Path(path)
    try:
        with zipfile.ZipFile(wheel_path) as archive:
            metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            wheel_paths = [name for name in archive.namelist() if name.endswith(".dist-info/WHEEL")]
            if len(metadata_paths) != 1 or len(wheel_paths) != 1:
                _fail("wheel_metadata_invalid")
            metadata = BytesParser(policy=compat32).parsebytes(archive.read(metadata_paths[0]))
            wheel = BytesParser(policy=compat32).parsebytes(archive.read(wheel_paths[0]))
            browser_path = "playwright/driver/package/browsers.json"
            browsers = None
            if browser_path in archive.namelist():
                browsers = json.loads(archive.read(browser_path).decode("utf-8"))
    except ProvenanceError:
        raise
    except (OSError, KeyError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile):
        _fail("wheel_metadata_invalid")

    name = metadata.get("Name")
    version = metadata.get("Version")
    tags = wheel.get_all("Tag", [])
    if not isinstance(name, str) or not isinstance(version, str) or not tags:
        _fail("wheel_metadata_invalid")
    try:
        parsed_tags = sorted(str(Tag(*tag.split("-", 2))) for tag in tags)
        normalized_version = str(Version(version))
    except (TypeError, ValueError, InvalidVersion):
        _fail("wheel_metadata_invalid")
    return {
        "name": str(canonicalize_name(name)),
        "display_name": name,
        "version": normalized_version,
        "requires_python": metadata.get("Requires-Python"),
        "requires_dist": list(metadata.get_all("Requires-Dist", [])),
        "wheel_tags": parsed_tags,
        "root_is_purelib": wheel.get("Root-Is-Purelib"),
        "browsers": browsers,
    }


def _marker_environment(target: Mapping[str, Any]) -> dict[str, str]:
    required = {
        "implementation_name",
        "platform_python_implementation",
        "python_version",
        "python_full_version",
        "sys_platform",
        "platform_system",
        "os_name",
        "platform_machine",
    }
    if not required.issubset(target) or any(type(target[key]) is not str for key in required):
        _fail("target_invalid")
    return {
        "implementation_name": target["implementation_name"],
        "implementation_version": target["python_full_version"],
        "os_name": target["os_name"],
        "platform_machine": target["platform_machine"],
        "platform_release": "",
        "platform_system": target["platform_system"],
        "platform_version": "",
        "python_full_version": target["python_full_version"],
        "platform_python_implementation": target["platform_python_implementation"],
        "python_version": target["python_version"],
        "sys_platform": target["sys_platform"],
        "extra": "",
    }


def derive_active_dependency_edges(
    wheel_records: Mapping[str, Mapping[str, Any]], target: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Derive active dependency edges from local wheel METADATA for the target."""

    environment = _marker_environment(target)
    edges: list[dict[str, Any]] = []
    for source_name in sorted(wheel_records):
        record = wheel_records[source_name]
        for raw in record["requires_dist"]:
            try:
                requirement = Requirement(raw)
                active = requirement.marker is None or requirement.marker.evaluate(environment=environment)
            except (InvalidRequirement, TypeError, ValueError):
                _fail("dependency_metadata_invalid")
            if not active:
                continue
            dependency = str(canonicalize_name(requirement.name))
            target_record = wheel_records.get(dependency)
            if target_record is None:
                _fail("missing_dependency_artifact")
            try:
                satisfies = not requirement.specifier or requirement.specifier.contains(
                    Version(str(target_record["version"])), prereleases=True
                )
            except (InvalidVersion, TypeError, ValueError):
                _fail("dependency_metadata_invalid")
            if not satisfies:
                _fail("dependency_version_mismatch")
            edges.append(
                {
                    "from": source_name,
                    "to": dependency,
                    "specifier": str(requirement.specifier),
                    "marker": str(requirement.marker) if requirement.marker is not None else None,
                }
            )
    return sorted(edges, key=lambda edge: (edge["from"], edge["to"], edge["specifier"], edge["marker"] or ""))


def _target_tags(target: Mapping[str, Any]) -> tuple[str, str, str]:
    if (
        target.get("implementation") != "cp"
        or target.get("python_version") != "3.11"
        or target.get("abi") != "cp311"
        or target.get("platform") != "win_amd64"
    ):
        _fail("target_mismatch")
    return "cp311", "cp311", "win_amd64"


def _tag_compatible(tag_text: str, target: Mapping[str, Any]) -> bool:
    interpreter, abi, platform = _target_tags(target)
    try:
        tag = Tag(*tag_text.split("-", 2))
    except (TypeError, ValueError):
        _fail("wheel_tag_invalid")
    interpreter_ok = tag.interpreter in {interpreter, "py3", "py311"}
    abi_ok = tag.abi in {abi, "abi3", "none"}
    platform_ok = tag.platform in {platform, "any"}
    return interpreter_ok and abi_ok and platform_ok


def _tag_sets_consistent(filename_tags: Sequence[str], wheel_tags: Sequence[str]) -> bool:
    """Allow an official filename to narrow an otherwise matching WHEEL tag."""

    for filename_text in filename_tags:
        filename_tag = Tag(*filename_text.split("-", 2))
        matched = False
        for wheel_text in wheel_tags:
            wheel_tag = Tag(*wheel_text.split("-", 2))
            same_interpreter = filename_tag.interpreter == wheel_tag.interpreter
            same_abi = filename_tag.abi == wheel_tag.abi
            platform_narrows = wheel_tag.platform in {filename_tag.platform, "any"}
            if same_interpreter and same_abi and platform_narrows:
                matched = True
                break
        if not matched:
            return False
    return True


def _normalized_url(value: Any) -> str:
    if type(value) is not str:
        return ""
    return value.rstrip("/").casefold()


def _fetch_registry(name: str, version: str) -> dict[str, Any]:
    url = f"https://{PYPI_HOST}/pypi/{name}/{version}/json"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "jarvis-provenance-validator/1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.geturl().split("/", 3)[2].casefold() != PYPI_HOST:
                _fail("registry_redirect_forbidden")
            payload = json.load(response, object_pairs_hook=_unique_object)
    except ProvenanceError:
        raise
    except (OSError, ValueError, urllib.error.URLError):
        _fail("registry_unavailable")
    if type(payload) is not dict:
        _fail("registry_record_invalid")
    return payload


def _registry_payload(
    name: str,
    version: str,
    registry_records: Mapping[tuple[str, str], Mapping[str, Any]] | None,
) -> Mapping[str, Any]:
    if registry_records is None:
        return _fetch_registry(name, version)
    payload = registry_records.get((name, version))
    if payload is None:
        _fail("registry_record_missing")
    return payload


def _verify_registry_record(
    artifact: Mapping[str, Any],
    registry_records: Mapping[tuple[str, str], Mapping[str, Any]] | None,
) -> None:
    name = str(canonicalize_name(str(artifact["name"])))
    version = str(artifact["version"])
    payload = _registry_payload(name, version, registry_records)
    info = payload.get("info")
    urls = payload.get("urls")
    if type(info) is not dict or type(urls) is not list:
        _fail("registry_record_invalid")
    candidates = [item for item in urls if type(item) is dict and item.get("filename") == artifact["filename"]]
    if len(candidates) != 1:
        _fail("registry_record_mismatch")
    live = candidates[0]
    recorded = artifact.get("registry")
    if type(recorded) is not dict:
        _fail("registry_record_invalid")
    digests = live.get("digests")
    live_sha = digests.get("sha256") if type(digests) is dict else None
    comparisons = {
        "project_url": info.get("package_url"),
        "release_json_url": f"https://{PYPI_HOST}/pypi/{name}/{version}/json",
        "file_url": live.get("url"),
        "filename": live.get("filename"),
        "size": live.get("size"),
        "sha256": live_sha,
        "packagetype": live.get("packagetype"),
        "upload_time_iso_8601": live.get("upload_time_iso_8601"),
        "requires_python": live.get("requires_python"),
        "author": info.get("author"),
        "author_email": info.get("author_email"),
        "project_urls": info.get("project_urls"),
    }
    for field, expected in comparisons.items():
        if recorded.get(field) != expected:
            _fail("registry_record_mismatch")
    if recorded.get("packagetype") != "bdist_wheel":
        _fail("source_distribution_forbidden")
    file_url = str(recorded.get("file_url", ""))
    if not file_url.startswith(f"https://{PYPI_FILE_HOST}/"):
        _fail("registry_file_host_mismatch")
    project_urls = info.get("project_urls") or {}
    if type(project_urls) is not dict:
        _fail("registry_source_mismatch")
    source = recorded.get("source_repository_url")
    if _normalized_url(source) not in {_normalized_url(value) for value in project_urls.values()}:
        _fail("registry_source_mismatch")
    source_prefix = "https://github.com/"
    if type(source) is not str or not source.casefold().startswith(source_prefix):
        _fail("registry_source_mismatch")
    source_path = source[len(source_prefix) :].strip("/").split("/")
    source_owner = recorded.get("source_owner")
    if type(source_owner) is not str or len(source_path) < 2 or source_owner.casefold() != source_path[0].casefold():
        _fail("registry_source_mismatch")
    if recorded.get("source_owner_type") not in {"Organization", "User"}:
        _fail("registry_source_mismatch")
    if recorded.get("source_repository_archived") is not False:
        _fail("registry_source_mismatch")
    if type(recorded.get("source_repository_checked_at_utc")) is not str:
        _fail("registry_source_mismatch")
    if live_sha != artifact.get("downloaded_sha256"):
        _fail("registry_download_hash_mismatch")


def _canonical_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    if type(edge) is not dict:
        _fail("dependency_edge_invalid")
    try:
        requirement = Requirement(f"x{edge.get('specifier', '')}")
    except (InvalidRequirement, TypeError, ValueError):
        _fail("dependency_edge_invalid")
    marker = edge.get("marker")
    if marker is not None:
        try:
            marker = str(Requirement(f"x; {marker}").marker)
        except (InvalidRequirement, TypeError, ValueError):
            _fail("dependency_edge_invalid")
    return {
        "from": str(canonicalize_name(str(edge.get("from", "")))),
        "to": str(canonicalize_name(str(edge.get("to", "")))),
        "specifier": str(requirement.specifier),
        "marker": marker,
    }


def _approval_scope(
    scope: str, roots: Mapping[str, str], edges: Sequence[Mapping[str, Any]]
) -> set[str]:
    if scope == "python":
        return set()
    if scope not in roots:
        _fail("scope_invalid")
    selected = {scope}
    while True:
        expanded = selected | {edge["to"] for edge in edges if edge["from"] in selected}
        if expanded == selected:
            return selected
        selected = expanded


def _verify_approvals(
    artifacts: Mapping[str, Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    roots: Mapping[str, str],
    scope: str,
    require_status: str,
) -> None:
    expected = require_status.upper()
    if expected not in {"PENDING", "APPROVED"}:
        _fail("approval_requirement_invalid")
    selected = _approval_scope(scope, roots, edges) or set(artifacts)
    for name in sorted(selected):
        artifact = artifacts[name]
        approval = artifact.get("approval")
        if type(approval) is not dict:
            _fail("approval_record_invalid")
        status = approval.get("status")
        if status not in {"PENDING", "APPROVED", "REJECTED"}:
            _fail("approval_record_invalid")
        evidence = (
            approval.get("approved_sha256"),
            approval.get("approved_by"),
            approval.get("approved_at_utc"),
        )
        if status == "PENDING" and any(value is not None for value in evidence):
            _fail("pending_approval_has_evidence")
        if status != expected:
            _fail("approval_status_mismatch")
        if status == "APPROVED":
            if not all(type(value) is str and value for value in evidence):
                _fail("approval_record_invalid")
            approved_hash = approval["approved_sha256"]
            if approved_hash != artifact.get("downloaded_sha256") or approved_hash != artifact.get("registry", {}).get("sha256"):
                _fail("approval_hash_mismatch")


def verify_python_closure(
    manifest: Mapping[str, Any],
    artifacts_dir: str | Path | None = None,
    *,
    scope: str = "python",
    require_status: str = "pending",
    registry_records: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify exact local closure, PyPI evidence, tags, edges, and approvals."""

    if type(manifest) is not dict or manifest.get("schema_version") != SCHEMA_VERSION:
        _fail("manifest_schema_mismatch")
    target = manifest.get("target")
    python_section = manifest.get("python")
    roots_raw = manifest.get("roots")
    if type(target) is not dict or type(python_section) is not dict or type(roots_raw) is not list:
        _fail("manifest_invalid")
    _target_tags(target)
    roots: dict[str, str] = {}
    for root in roots_raw:
        if type(root) is not dict or type(root.get("name")) is not str or type(root.get("version")) is not str:
            _fail("root_identity_mismatch")
        name = str(canonicalize_name(root["name"]))
        if name in roots:
            _fail("root_identity_mismatch")
        roots[name] = root["version"]
    if roots != EXPECTED_ROOTS:
        _fail("root_identity_mismatch")

    directory_value = artifacts_dir if artifacts_dir is not None else manifest.get("artifact_directory")
    if not isinstance(directory_value, (str, Path)):
        _fail("artifact_directory_missing")
    directory = Path(directory_value)
    if not directory.is_absolute() or not directory.is_dir():
        _fail("artifact_directory_missing")
    try:
        files = sorted((item for item in directory.iterdir() if item.is_file()), key=lambda item: item.name.casefold())
    except OSError:
        _fail("artifact_directory_missing")
    non_wheels = [item for item in files if item.suffix.casefold() != ".whl"]
    if any(item.name.casefold().endswith(SDIST_SUFFIXES) for item in non_wheels):
        _fail("source_distribution_forbidden")
    if non_wheels:
        _fail("extra_artifact")

    artifact_list = python_section.get("artifacts")
    if type(artifact_list) is not list or not artifact_list:
        _fail("manifest_invalid")
    manifest_artifacts: dict[str, Mapping[str, Any]] = {}
    for artifact in artifact_list:
        if type(artifact) is not dict or type(artifact.get("name")) is not str or type(artifact.get("version")) is not str:
            _fail("manifest_invalid")
        name = str(canonicalize_name(artifact["name"]))
        if name in manifest_artifacts:
            _fail("duplicate_artifact_identity")
        manifest_artifacts[name] = artifact

    if len(files) < len(artifact_list):
        _fail("missing_artifact")
    if len(files) > len(artifact_list):
        _fail("extra_artifact")

    wheel_records: dict[str, dict[str, Any]] = {}
    for path in files:
        parsed = parse_wheel_artifact(path)
        name = parsed["name"]
        if name in wheel_records:
            _fail("duplicate_artifact_identity")
        metadata = read_wheel_metadata(path)
        if metadata["name"] != name or metadata["version"] != parsed["version"]:
            _fail("wheel_metadata_identity_mismatch")
        wheel_records[name] = {**parsed, **metadata}

    if set(wheel_records) != set(manifest_artifacts):
        if set(manifest_artifacts) - set(wheel_records):
            _fail("missing_artifact")
        _fail("extra_artifact")

    for name in sorted(manifest_artifacts):
        artifact = manifest_artifacts[name]
        local = wheel_records[name]
        if artifact["version"] != local["version"]:
            _fail("artifact_version_mismatch")
        if artifact.get("filename") != local["filename"]:
            _fail("artifact_filename_mismatch")
        if artifact.get("filename_tags") != local["filename_tags"]:
            _fail("filename_tag_mismatch")
        if artifact.get("wheel_tags") != local["wheel_tags"]:
            _fail("wheel_tag_mismatch")
        if not all(_tag_compatible(tag, target) for tag in local["filename_tags"]):
            _fail("filename_tag_incompatible")
        if not all(_tag_compatible(tag, target) for tag in local["wheel_tags"]):
            _fail("wheel_tag_incompatible")
        if not _tag_sets_consistent(local["filename_tags"], local["wheel_tags"]):
            _fail("wheel_tag_inconsistent")
        try:
            size = local["path"].stat().st_size
        except OSError:
            _fail("artifact_unreadable")
        if artifact.get("size") != size:
            _fail("artifact_size_mismatch")
        digest = _sha256(local["path"])
        if artifact.get("downloaded_sha256") != digest:
            _fail("downloaded_hash_mismatch")
        if artifact.get("requires_python") != local["requires_python"]:
            _fail("requires_python_mismatch")
        if artifact.get("all_requires_dist") != local["requires_dist"]:
            _fail("requires_dist_mismatch")
        _verify_registry_record(artifact, registry_records)

    derived_edges = derive_active_dependency_edges(wheel_records, target)
    recorded_edges_raw = python_section.get("dependency_edges")
    if type(recorded_edges_raw) is not list:
        _fail("dependency_edge_invalid")
    recorded_edges = sorted(
        (_canonical_edge(edge) for edge in recorded_edges_raw),
        key=lambda edge: (edge["from"], edge["to"], edge["specifier"], edge["marker"] or ""),
    )
    if recorded_edges != derived_edges:
        _fail("dependency_edge_mismatch")

    reachable = set(roots)
    while True:
        expanded = reachable | {edge["to"] for edge in derived_edges if edge["from"] in reachable}
        if expanded == reachable:
            break
        reachable = expanded
    if reachable != set(wheel_records):
        _fail("unreachable_artifact")
    for root_name, root_version in roots.items():
        if wheel_records[root_name]["version"] != root_version:
            _fail("root_identity_mismatch")

    _verify_approvals(manifest_artifacts, derived_edges, roots, scope, require_status)
    return {
        "status": "PASS",
        "artifact_count": len(wheel_records),
        "edge_count": len(derived_edges),
        "scope": scope,
        "required_status": require_status.upper(),
        "wheel_records": wheel_records,
    }


def verify_chromium_provenance(
    manifest: Mapping[str, Any],
    wheel_records: Mapping[str, Mapping[str, Any]],
    require_status: str = "absent-or-pending",
) -> dict[str, Any]:
    """Verify only the package-declared Chromium contract; never browser bytes."""

    chromium = manifest.get("chromium")
    contract = chromium.get("package_contract") if type(chromium) is dict else None
    playwright = wheel_records.get("playwright")
    if type(contract) is not dict or type(playwright) is not dict:
        _fail("chromium_contract_missing")
    browsers = playwright.get("browsers")
    entries = browsers.get("browsers") if type(browsers) is dict else None
    matches = [entry for entry in entries or [] if type(entry) is dict and entry.get("name") == "chromium"]
    if len(matches) != 1:
        _fail("chromium_contract_missing")
    declared = matches[0]
    expected = {
        "declared_by": "playwright",
        "declared_by_version": playwright["version"],
        "declared_by_wheel": playwright["filename"],
        "metadata_path": "playwright/driver/package/browsers.json",
        "name": declared.get("name"),
        "revision": declared.get("revision"),
        "browser_version": declared.get("browserVersion"),
        "title": declared.get("title"),
        "install_by_default": declared.get("installByDefault"),
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        _fail("chromium_contract_mismatch")
    contract_status = contract.get("approval_status")
    contract_evidence = (contract.get("approved_by"), contract.get("approved_at_utc"))
    if contract_status not in {"PENDING", "APPROVED", "REJECTED"}:
        _fail("chromium_contract_approval_invalid")
    if contract_status == "PENDING" and any(value is not None for value in contract_evidence):
        _fail("chromium_contract_approval_invalid")
    if contract_status == "APPROVED" and not all(type(value) is str and value for value in contract_evidence):
        _fail("chromium_contract_approval_invalid")

    if require_status != "absent-or-pending":
        _fail("chromium_requirement_invalid")
    for field in ("archive", "executable"):
        byte_record = chromium.get(field)
        if type(byte_record) is not dict:
            _fail("chromium_byte_record_invalid")
        if byte_record.get("status") not in {"ABSENT", "PENDING"}:
            _fail("chromium_bytes_premature")
        if byte_record.get("status") == "ABSENT" and any(
            byte_record.get(key) is not None for key in ("filename", "size", "sha256")
        ):
            _fail("chromium_byte_record_invalid")
    return {"status": "PASS", "revision": str(declared["revision"]), "byte_status": "ABSENT_OR_PENDING"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Jarvis Phase 2 package provenance without execution")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--scope", required=True, choices=("python", "cryptography", "playwright"))
    parser.add_argument("--require-status", required=True, choices=("pending", "approved"))
    parser.add_argument("--require-chromium-status", choices=("absent-or-pending",))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        artifact_directory = Path(str(manifest.get("artifact_directory", "")))
        repo_root = args.manifest.resolve().parents[2]
        try:
            artifact_directory.resolve().relative_to(repo_root)
        except ValueError:
            pass
        else:
            _fail("artifact_directory_inside_repository")
        result = verify_python_closure(
            manifest,
            artifact_directory,
            scope=args.scope,
            require_status=args.require_status,
        )
        chromium = None
        if args.require_chromium_status is not None:
            chromium = verify_chromium_provenance(
                manifest, result["wheel_records"], args.require_chromium_status
            )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "scope": args.scope,
                    "required_status": args.require_status.upper(),
                    "artifacts": result["artifact_count"],
                    "dependency_edges": result["edge_count"],
                    "chromium": chromium,
                },
                sort_keys=True,
            )
        )
        return 0
    except ProvenanceError as exc:
        print(f"PROVENANCE_FAIL:{exc.code}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
