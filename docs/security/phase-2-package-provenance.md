# Phase 2 Package Provenance Receipt

Status: **PYTHON CLOSURES APPROVED; CHROMIUM BYTES PENDING**
Generated: `2026-08-11T05:15:25Z`
Canonical machine record: [`phase-2-package-provenance.json`](phase-2-package-provenance.json)

This receipt records completed blocking approvals for the exact cryptography and Playwright Python closures plus the package-declared Chromium source/revision contract. Chromium archive and executable bytes remain absent and unapproved, so this receipt does not authorize a Chromium process to start.

## Download-only target

- Roots: exactly `cryptography==49.0.0` and `playwright==1.61.0`
- Target: CPython 3.11, ABI `cp311`, Windows x64 (`win_amd64`)
- Review directory outside the repository: `C:\Users\Usry\AppData\Local\Temp\jarvis-phase2-plan05-20260808T164151`
- Resolver: `python -m pip download --only-binary=:all: --platform win_amd64 --python-version 3.11 --implementation cp --abi cp311 cryptography==49.0.0 playwright==1.61.0`
- Result: seven wheels and no source distributions
- Installation: not performed
- Playwright browser installation: not performed
- Downloaded executable launch: not performed

The first resolver transfer stalled while fetching the 37.8 MB Playwright wheel. That process was stopped without producing a destination artifact. The exact PyPI `files.pythonhosted.org` URL was then fetched into the external review directory, its `37,844,846` bytes independently hashed to the PyPI SHA-256, and the same pip download-only command was rerun successfully. Pip reported the exact Playwright file already downloaded, resolved the same graph, materialized the other six wheels, and ended with `Successfully downloaded cryptography playwright greenlet pyee cffi pycparser typing-extensions`.

## Exact CPython 3.11 Windows x64 wheel closure

All registry links below are official PyPI release records. Each source URL is the source repository declared by that live PyPI project metadata; the GitHub owner and public, non-archived repository identity were also checked on `2026-08-08`.

| Closure | Identity | Exact wheel | Filename tag | WHEEL tag | Bytes | PyPI SHA-256 / local SHA-256 | Official project and source | Approval |
|---|---|---|---|---|---:|---|---|---|
| cryptography | `cryptography==49.0.0` | `cryptography-49.0.0-cp311-abi3-win_amd64.whl` | `cp311-abi3-win_amd64` | `cp311-abi3-win_amd64` | 3,810,026 | `e5dfc1e64de5677cec922ffa8da89c546d0415bf6efdf081842e5d44c84e1f0e` | [PyPI](https://pypi.org/project/cryptography/) · [PyCA source](https://github.com/pyca/cryptography/) | **APPROVED** |
| cryptography | `cffi==2.1.1` | `cffi-2.1.1-cp311-cp311-win_amd64.whl` | `cp311-cp311-win_amd64` | `cp311-cp311-win_amd64` | 185,096 | `42f6930c31dc7f50732c9ae793c2786c7b6b044195967bbdde40bb9be81c4cc0` | [PyPI](https://pypi.org/project/cffi/) · [python-cffi source](https://github.com/python-cffi/cffi) | **APPROVED** |
| cryptography | `pycparser==3.0` | `pycparser-3.0-py3-none-any.whl` | `py3-none-any` | `py3-none-any` | 48,172 | `b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992` | [PyPI](https://pypi.org/project/pycparser/) · [eliben source](https://github.com/eliben/pycparser) | **APPROVED** |
| Playwright | `playwright==1.61.0` | `playwright-1.61.0-py3-none-win_amd64.whl` | `py3-none-win_amd64` | `py3-none-any` | 37,844,846 | `35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597` | [PyPI](https://pypi.org/project/playwright/) · [Microsoft source](https://github.com/Microsoft/playwright-python) | **APPROVED** |
| Playwright | `greenlet==3.5.4` | `greenlet-3.5.4-cp311-cp311-win_amd64.whl` | `cp311-cp311-win_amd64` | `cp311-cp311-win_amd64` | 246,434 | `dc418cf4c873357964d6624445ed09472e50def990c65dd4e76fc3ba8cd9cef6` | [PyPI](https://pypi.org/project/greenlet/) · [python-greenlet source](https://github.com/python-greenlet/greenlet) | **APPROVED** |
| Playwright | `pyee==13.0.1` | `pyee-13.0.1-py3-none-any.whl` | `py3-none-any` | `py3-none-any` | 15,659 | `af2f8fede4171ef667dfded53f96e2ed0d6e6bd7ee3bb46437f77e3b57689228` | [PyPI](https://pypi.org/project/pyee/) · [jfhbrook source](https://github.com/jfhbrook/pyee) | **APPROVED** |
| Playwright | `typing-extensions==4.16.0` | `typing_extensions-4.16.0-py3-none-any.whl` | `py3-none-any` | `py3-none-any` | 45,571 | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | [PyPI](https://pypi.org/project/typing-extensions/) · [Python source](https://github.com/python/typing_extensions) | **APPROVED** |

The SHA-256 value shown once in each row is equal across the live PyPI release JSON record and a fresh local calculation over the retained wheel bytes. The JSON receipt records both values independently.

### Tag note requiring human attention

The official Playwright Windows artifact is named with the restrictive filename tag `py3-none-win_amd64`, while its internal `WHEEL` metadata declares `py3-none-any`. This is not silently normalized away. The validator records and checks both exact values and permits only the explicit relationship in which the filename narrows an otherwise matching interpreter/ABI WHEEL tag. Any change to either tag, an incompatible target, or a relationship other than that narrowing fails closed.

## Active dependency edges

Markers were evaluated for CPython 3.11 on Windows x64 with no extras selected.

| From | Active requirement | Resolved artifact |
|---|---|---|
| `cryptography==49.0.0` | `cffi>=2.0.0; platform_python_implementation != "PyPy"` | `cffi==2.1.1` |
| `cffi==2.1.1` | `pycparser; implementation_name != "PyPy"` | `pycparser==3.0` |
| `playwright==1.61.0` | `greenlet<4.0.0,>=3.1.1` | `greenlet==3.5.4` |
| `playwright==1.61.0` | `pyee<14,>=13` | `pyee==13.0.1` |
| `pyee==13.0.1` | `typing-extensions` | `typing-extensions==4.16.0` |

Inactive optional or target-false requirements remain recorded in the JSON under each artifact's `all_requires_dist`; they are not silently discarded.

## Package-declared Chromium contract

The Playwright wheel was inspected as a ZIP archive only. `playwright/driver/package/browsers.json` declares:

- Browser name: `chromium`
- Revision: `1228`
- Browser version: `149.0.7827.55`
- Title: `Chrome for Testing`
- Installed by default by a future Playwright browser-install action: `true`
- Declaring wheel: `playwright-1.61.0-py3-none-win_amd64.whl`

Chromium archive bytes: **ABSENT**  
Chromium executable bytes: **ABSENT**  
Chromium source-contract approval: **APPROVED**

No archive or executable hash is invented. Plan 02-06 must collect those exact bytes without execution, hash them, and stop at its own blocking approval before the first Chromium process may start.

## Environment baseline and non-installation evidence

Before this task, the active `python` environment already contained unrelated `cryptography==48.0.1`; it did not contain `cryptography==49.0.0` or `playwright==1.61.0`. A pre-existing Playwright cache also contained Chromium revision `1208`, headless-shell revision `1208`, FFmpeg revision `1011`, and winldd revision `1007` from unrelated earlier work. Therefore this receipt makes the precise claim that this task installed or added none of the reviewed package/browser artifacts; it does not make the false claim that the machine was globally free of Chromium bytes.

The only package operation in this task was `pip download`. No `pip install`, Playwright browser install, Chromium process, or downloaded executable was run.

## Validator gate

The fail-closed validator:

- opens wheels only as ZIP archives;
- derives identities, all active edges, and Chromium revision metadata from local wheel metadata;
- requires the exact two roots and complete reachable closure;
- rejects source distributions, duplicates, missing/extra files or edges, incompatible/drifted tags, filenames, sizes, publishers/sources, and hashes;
- refetches official PyPI JSON for CLI verification;
- recalculates every retained wheel SHA-256;
- rejects PENDING evidence when APPROVED is requested;
- requires `approved_sha256 == registry.sha256 == downloaded_sha256` after explicit human approval; and
- leaves both Chromium archive and executable byte records absent or pending.

Current result:

```text
21 hostile/positive tests passed
cryptography scope: PASS (complete 7-artifact closure, 5 active edges; 3 scoped artifacts APPROVED)
playwright scope: PASS (complete 7-artifact closure, 5 active edges; 4 scoped artifacts APPROVED; Chromium archive/executable ABSENT)
```

## Blocking human decision 1: cryptography closure — APPROVED

The human operator replied with the exact phrase `approved`. That decision is recorded only for the complete exact cryptography closure:

- `cryptography==49.0.0`: `e5dfc1e64de5677cec922ffa8da89c546d0415bf6efdf081842e5d44c84e1f0e`
- `cffi==2.1.1`: `42f6930c31dc7f50732c9ae793c2786c7b6b044195967bbdde40bb9be81c4cc0`
- `pycparser==3.0`: `b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992`

Approval was recorded by `human_operator` at `2026-08-08T22:13:48Z`. The canonical manifest requires each approved SHA-256 to equal both the official PyPI registry SHA-256 and the independently calculated downloaded-byte SHA-256.

This cryptography decision does not approve Playwright or any Chromium source or bytes.

## Blocking human decision 2: Playwright closure and Chromium source contract — APPROVED

The human operator explicitly approved the complete exact Playwright closure and only the package-declared Chromium source/revision contract:

- `playwright==1.61.0`: `35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597`
- `greenlet==3.5.4`: `dc418cf4c873357964d6624445ed09472e50def990c65dd4e76fc3ba8cd9cef6`
- `pyee==13.0.1`: `af2f8fede4171ef667dfded53f96e2ed0d6e6bd7ee3bb46437f77e3b57689228`
- `typing-extensions==4.16.0`: `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8`
- Declared Chromium contract: revision `1228`, browser version `149.0.7827.55`, `Chrome for Testing`, declared by the approved Playwright wheel

Approval was recorded by `human_operator` at `2026-08-11T05:15:25Z`. Every approved Python SHA-256 equals both the official PyPI registry SHA-256 and the independently calculated retained-wheel SHA-256.

Chromium archive and executable bytes remain **ABSENT** and are not approved by this decision. Plan 02-06 must collect and hash those exact bytes without execution, then stop at its separate blocking human approval before the first Chromium process starts.
