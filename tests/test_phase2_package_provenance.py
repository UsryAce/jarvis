from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.verify_phase2_package_provenance import (
    ProvenanceError,
    load_manifest,
    verify_chromium_provenance,
    verify_python_closure,
)


PACKAGES = (
    {
        "name": "cryptography",
        "version": "49.0.0",
        "filename": "cryptography-49.0.0-cp311-abi3-win_amd64.whl",
        "wheel_tag": "cp311-abi3-win_amd64",
        "requires": ("cffi>=2.0.0 ; platform_python_implementation != 'PyPy'",),
        "source": "https://github.com/pyca/cryptography/",
    },
    {
        "name": "cffi",
        "version": "2.1.1",
        "filename": "cffi-2.1.1-cp311-cp311-win_amd64.whl",
        "wheel_tag": "cp311-cp311-win_amd64",
        "requires": ('pycparser; implementation_name != "PyPy"',),
        "source": "https://github.com/python-cffi/cffi",
    },
    {
        "name": "pycparser",
        "version": "3.0",
        "filename": "pycparser-3.0-py3-none-any.whl",
        "wheel_tag": "py3-none-any",
        "requires": (),
        "source": "https://github.com/eliben/pycparser",
    },
    {
        "name": "playwright",
        "version": "1.61.0",
        "filename": "playwright-1.61.0-py3-none-win_amd64.whl",
        # The official Playwright filename narrows its internal purelib tag.
        "wheel_tag": "py3-none-any",
        "requires": ("pyee<14,>=13", "greenlet<4.0.0,>=3.1.1"),
        "source": "https://github.com/Microsoft/playwright-python",
    },
    {
        "name": "pyee",
        "version": "13.0.1",
        "filename": "pyee-13.0.1-py3-none-any.whl",
        "wheel_tag": "py3-none-any",
        "requires": ("typing-extensions",),
        "source": "https://github.com/jfhbrook/pyee",
    },
    {
        "name": "greenlet",
        "version": "3.5.4",
        "filename": "greenlet-3.5.4-cp311-cp311-win_amd64.whl",
        "wheel_tag": "cp311-cp311-win_amd64",
        "requires": (),
        "source": "https://github.com/python-greenlet/greenlet",
    },
    {
        "name": "typing-extensions",
        "version": "4.16.0",
        "filename": "typing_extensions-4.16.0-py3-none-any.whl",
        "wheel_tag": "py3-none-any",
        "requires": (),
        "source": "https://github.com/python/typing_extensions",
    },
)


def _write_wheel(directory: Path, package: dict[str, object]) -> Path:
    path = directory / str(package["filename"])
    dist = str(package["name"]).replace("-", "_")
    metadata = [
        "Metadata-Version: 2.4",
        f"Name: {package['name']}",
        f"Version: {package['version']}",
        "Requires-Python: >=3.10",
    ]
    metadata.extend(f"Requires-Dist: {item}" for item in package["requires"])
    wheel = [
        "Wheel-Version: 1.0",
        "Generator: hostile-fixture",
        "Root-Is-Purelib: true",
        f"Tag: {package['wheel_tag']}",
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{dist}-{package['version']}.dist-info/METADATA", "\n".join(metadata) + "\n")
        archive.writestr(f"{dist}-{package['version']}.dist-info/WHEEL", "\n".join(wheel) + "\n")
        if package["name"] == "playwright":
            archive.writestr(
                "playwright/driver/package/browsers.json",
                json.dumps(
                    {
                        "browsers": [
                            {
                                "name": "chromium",
                                "revision": "1228",
                                "browserVersion": "149.0.7827.55",
                                "title": "Chrome for Testing",
                                "installByDefault": True,
                            }
                        ]
                    }
                ),
            )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[dict[str, object], dict[tuple[str, str], dict[str, object]]]:
    artifacts: list[dict[str, object]] = []
    registry: dict[tuple[str, str], dict[str, object]] = {}
    for package in PACKAGES:
        path = _write_wheel(tmp_path, package)
        digest = _sha256(path)
        size = path.stat().st_size
        filename_tag = str(package["filename"]).removesuffix(".whl").rsplit("-", 3)[-3:]
        source = str(package["source"])
        artifact = {
            "name": package["name"],
            "display_name": package["name"],
            "version": package["version"],
            "requires_python": ">=3.10",
            "all_requires_dist": list(package["requires"]),
            "filename": package["filename"],
            "filename_tags": ["-".join(filename_tag)],
            "wheel_tags": [package["wheel_tag"]],
            "size": size,
            "downloaded_sha256": digest,
            "registry": {
                "project_url": f"https://pypi.org/project/{package['name']}/",
                "release_json_url": f"https://pypi.org/pypi/{package['name']}/{package['version']}/json",
                "file_url": f"https://files.pythonhosted.org/packages/fixture/{package['filename']}",
                "filename": package["filename"],
                "size": size,
                "sha256": digest,
                "packagetype": "bdist_wheel",
                "upload_time_iso_8601": "2026-01-01T00:00:00Z",
                "requires_python": ">=3.10",
                "author": "fixture-author",
                "author_email": None,
                "project_urls": {"Source": source},
                "source_repository_url": source,
                "source_owner": source.split("github.com/", 1)[1].split("/", 1)[0],
                "source_owner_type": "Organization",
                "source_repository_archived": False,
                "source_repository_checked_at_utc": "2026-08-08T00:00:00Z",
            },
            "approval": {
                "status": "PENDING",
                "approved_sha256": None,
                "approved_by": None,
                "approved_at_utc": None,
            },
        }
        artifacts.append(artifact)
        registry[(str(package["name"]).replace("_", "-"), str(package["version"]))] = {
            "info": {
                "name": package["name"],
                "version": package["version"],
                "package_url": artifact["registry"]["project_url"],
                "author": "fixture-author",
                "author_email": None,
                "project_urls": {"Source": source},
            },
            "urls": [
                {
                    "filename": package["filename"],
                    "size": size,
                    "digests": {"sha256": digest},
                    "packagetype": "bdist_wheel",
                    "url": artifact["registry"]["file_url"],
                    "upload_time_iso_8601": "2026-01-01T00:00:00Z",
                    "requires_python": ">=3.10",
                }
            ],
        }

    manifest: dict[str, object] = {
        "schema_version": "jarvis.phase2.package-provenance.v1",
        "generated_at_utc": "2026-08-08T00:00:00Z",
        "artifact_directory": str(tmp_path),
        "target": {
            "implementation": "cp",
            "implementation_name": "cpython",
            "platform_python_implementation": "CPython",
            "python_version": "3.11",
            "python_full_version": "3.11.15",
            "abi": "cp311",
            "platform": "win_amd64",
            "sys_platform": "win32",
            "platform_system": "Windows",
            "os_name": "nt",
            "platform_machine": "AMD64",
        },
        "roots": [
            {"name": "cryptography", "version": "49.0.0"},
            {"name": "playwright", "version": "1.61.0"},
        ],
        "python": {"status": "PENDING", "artifacts": artifacts, "dependency_edges": []},
        "chromium": {
            "status": "PENDING",
            "package_contract": {
                "declared_by": "playwright",
                "declared_by_version": "1.61.0",
                "declared_by_wheel": "playwright-1.61.0-py3-none-win_amd64.whl",
                "metadata_path": "playwright/driver/package/browsers.json",
                "name": "chromium",
                "revision": "1228",
                "browser_version": "149.0.7827.55",
                "title": "Chrome for Testing",
                "install_by_default": True,
                "source_repository_url": "https://github.com/Microsoft/playwright-python",
                "approval_status": "PENDING",
                "approved_by": None,
                "approved_at_utc": None,
            },
            "archive": {"status": "ABSENT", "filename": None, "size": None, "sha256": None},
            "executable": {"status": "ABSENT", "filename": None, "size": None, "sha256": None},
        },
    }
    # Let the validator-derived edge grammar be explicit in the fixture.
    manifest["python"]["dependency_edges"] = [
        {"from": "cffi", "to": "pycparser", "specifier": "", "marker": 'implementation_name != "PyPy"'},
        {
            "from": "cryptography",
            "to": "cffi",
            "specifier": ">=2.0.0",
            "marker": 'platform_python_implementation != "PyPy"',
        },
        {"from": "playwright", "to": "greenlet", "specifier": "<4.0.0,>=3.1.1", "marker": None},
        {"from": "playwright", "to": "pyee", "specifier": "<14,>=13", "marker": None},
        {"from": "pyee", "to": "typing-extensions", "specifier": "", "marker": None},
    ]
    return manifest, registry


def _assert_code(code: str, manifest: dict[str, object], registry: dict, **kwargs: object) -> None:
    with pytest.raises(ProvenanceError) as rejected:
        verify_python_closure(manifest, registry_records=registry, **kwargs)
    assert rejected.value.code == code
    assert str(rejected.value) == code


def test_complete_pending_closure_and_chromium_contract_pass(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)

    result = verify_python_closure(manifest, registry_records=registry, require_status="pending")
    chromium = verify_chromium_provenance(manifest, result["wheel_records"], "absent-or-pending")

    assert result["artifact_count"] == 7
    assert result["edge_count"] == 5
    assert chromium["revision"] == "1228"


def test_load_manifest_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":"a","schema_version":"b"}', encoding="utf-8")
    with pytest.raises(ProvenanceError) as rejected:
        load_manifest(path)
    assert rejected.value.code == "manifest_duplicate_key"


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        (lambda manifest, directory: (directory / manifest["python"]["artifacts"][0]["filename"]).unlink(), "missing_artifact"),
        (lambda manifest, directory: (directory / "extra-1.0-py3-none-any.whl").write_bytes(b"not-a-wheel"), "extra_artifact"),
        (lambda manifest, directory: (directory / "source-1.0.tar.gz").write_bytes(b"sdist"), "source_distribution_forbidden"),
        (lambda manifest, directory: manifest["python"]["artifacts"].append(copy.deepcopy(manifest["python"]["artifacts"][0])), "duplicate_artifact_identity"),
        (lambda manifest, directory: manifest["python"]["dependency_edges"].pop(), "dependency_edge_mismatch"),
        (lambda manifest, directory: manifest["python"]["dependency_edges"].append({"from": "pyee", "to": "greenlet", "specifier": "", "marker": None}), "dependency_edge_mismatch"),
        (lambda manifest, directory: manifest["python"]["artifacts"][0].__setitem__("filename", "cryptography-49.0.0-cp311-abi3-win32.whl"), "artifact_filename_mismatch"),
        (lambda manifest, directory: manifest["python"]["artifacts"][0].__setitem__("size", 1), "artifact_size_mismatch"),
        (lambda manifest, directory: manifest["python"]["artifacts"][0].__setitem__("downloaded_sha256", "0" * 64), "downloaded_hash_mismatch"),
        (lambda manifest, directory: manifest["python"]["artifacts"][0]["registry"].__setitem__("sha256", "1" * 64), "registry_record_mismatch"),
        (lambda manifest, directory: manifest["python"]["artifacts"][0]["registry"].__setitem__("source_repository_url", "https://example.invalid/substitute"), "registry_source_mismatch"),
        (lambda manifest, directory: manifest["python"]["artifacts"][0]["registry"].__setitem__("source_owner", "substitute"), "registry_source_mismatch"),
        (lambda manifest, directory: manifest["roots"][0].__setitem__("version", "48.0.1"), "root_identity_mismatch"),
    ),
)
def test_hostile_closure_drift_fails_closed(tmp_path: Path, mutation, code: str) -> None:
    manifest, registry = _fixture(tmp_path)
    mutation(manifest, tmp_path)
    _assert_code(code, manifest, registry)


def test_incompatible_filename_tag_fails_closed(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)
    artifact = manifest["python"]["artifacts"][0]
    old = tmp_path / artifact["filename"]
    new = tmp_path / "cryptography-49.0.0-cp311-abi3-manylinux_2_28_x86_64.whl"
    old.rename(new)
    artifact["filename"] = new.name
    artifact["filename_tags"] = ["cp311-abi3-manylinux_2_28_x86_64"]
    artifact["size"] = new.stat().st_size
    artifact["downloaded_sha256"] = _sha256(new)
    registry[("cryptography", "49.0.0")]["urls"][0].update(
        filename=new.name,
        size=new.stat().st_size,
        digests={"sha256": _sha256(new)},
    )
    artifact["registry"].update(
        filename=new.name,
        size=new.stat().st_size,
        sha256=_sha256(new),
    )
    _assert_code("filename_tag_incompatible", manifest, registry)


def test_wheel_tag_drift_fails_closed(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)
    artifact = next(item for item in manifest["python"]["artifacts"] if item["name"] == "playwright")
    artifact["wheel_tags"] = ["py3-none-win32"]
    _assert_code("wheel_tag_mismatch", manifest, registry)


def test_pending_evidence_cannot_satisfy_approved_check(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)
    _assert_code("approval_status_mismatch", manifest, registry, scope="cryptography", require_status="approved")


def test_pending_approval_fields_cannot_be_inferred(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)
    approval = manifest["python"]["artifacts"][0]["approval"]
    approval["approved_sha256"] = manifest["python"]["artifacts"][0]["downloaded_sha256"]
    _assert_code("pending_approval_has_evidence", manifest, registry)


def test_approved_hash_must_equal_registry_and_download(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)
    for artifact in manifest["python"]["artifacts"]:
        artifact["approval"].update(
            status="APPROVED",
            approved_sha256=artifact["downloaded_sha256"],
            approved_by="human",
            approved_at_utc="2026-08-08T00:00:00Z",
        )
    manifest["python"]["artifacts"][0]["approval"]["approved_sha256"] = "f" * 64
    _assert_code("approval_hash_mismatch", manifest, registry, scope="cryptography", require_status="approved")


def test_chromium_bytes_cannot_be_prematurely_approved(tmp_path: Path) -> None:
    manifest, registry = _fixture(tmp_path)
    result = verify_python_closure(manifest, registry_records=registry)
    manifest["chromium"]["archive"].update(status="APPROVED", filename="chromium.zip", size=1, sha256="0" * 64)
    with pytest.raises(ProvenanceError) as rejected:
        verify_chromium_provenance(manifest, result["wheel_records"], "absent-or-pending")
    assert rejected.value.code == "chromium_bytes_premature"
