"""Main CLI for JARVIS."""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.core.jarvis import Jarvis

console = Console()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_LEGACY_ENV_NAME = b"NVIDIA_API_KEY"


def _safe_code(exc: BaseException, fallback: str) -> str:
    candidate = getattr(exc, "code", None)
    return candidate if isinstance(candidate, str) and _SAFE_CODE.fullmatch(candidate) else fallback


def _control_store():
    from src.core.control_store import ControlStore

    database = Path(config.get("trust.database_path", "data/control.db"))
    backup_directory = Path(
        config.get("trust.backup_directory", "data/backups")
    )
    if not database.is_absolute():
        database = PROJECT_ROOT / database
    if not backup_directory.is_absolute():
        backup_directory = PROJECT_ROOT / backup_directory
    return ControlStore(
        database,
        backup_directory=backup_directory,
        backup_retention_count=int(
            config.get("trust.backup_retention_count", 5)
        ),
        backup_retention_bytes=int(
            config.get("trust.backup_retention_bytes", 536_870_912)
        ),
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cutover_row(store, provider: str):
    with store._lock:
        return store._require_connection().execute(
            """SELECT provider, active_credential_id, provider_generation,
                      source_kind, completed_at, restart_required
               FROM provider_cutovers WHERE provider = ?""",
            (provider,),
        ).fetchone()


def _append_migration_audit(
    tx,
    audit_service,
    *,
    action: str,
    outcome: str,
    status: str,
    reason_code: str,
    correlation_id: str,
    safe_id: str,
    applied: bool,
):
    return tx.append_audit(
        audit_service,
        actor_id="operator-cli",
        session_digest="credential-migration",
        event_type="migration",
        action=action,
        outcome=outcome,
        correlation_id=correlation_id,
        causation_id=correlation_id,
        subject="nvidia",
        revision=1,
        payload={
            "safe_id": safe_id,
            "status": status,
            "applied": applied,
            "reason_code": reason_code,
            "correlation_id": correlation_id,
        },
    )


def _legacy_assignment(raw_line: bytes) -> bool:
    candidate = raw_line.lstrip()
    if candidate.startswith(b"export "):
        candidate = candidate[7:].lstrip()
    key, separator, _value = candidate.partition(b"=")
    return bool(separator) and key.strip() == _LEGACY_ENV_NAME


def _dotenv_secret(path: Path) -> bytearray | None:
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        for raw_line in stream:
            if not _legacy_assignment(raw_line):
                continue
            value = raw_line.partition(b"=")[2].strip()
            if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in {b"'", b'"'}:
                value = value[1:-1]
            return bytearray(value) if value else None
    return None


def _yaml_secret(path: Path) -> bytearray | None:
    if not path.is_file():
        return None
    in_nvidia = False
    with path.open("rb") as stream:
        for raw_line in stream:
            stripped = raw_line.lstrip()
            if not stripped or stripped.startswith(b"#"):
                continue
            indentation = len(raw_line) - len(stripped)
            key, separator, value = stripped.partition(b":")
            if indentation == 0:
                in_nvidia = bool(separator) and key.strip() == b"nvidia"
                continue
            if not in_nvidia or key.strip() != b"api_key" or not separator:
                continue
            candidate = value.split(b"#", 1)[0].strip()
            if len(candidate) >= 2 and candidate[:1] == candidate[-1:] and candidate[:1] in {b"'", b'"'}:
                candidate = candidate[1:-1]
            if not candidate or candidate.startswith(b"${"):
                return None
            return bytearray(candidate)
    return None


def _read_legacy_source() -> tuple[str, Path | None, bytearray] | None:
    dotenv_path = PROJECT_ROOT / ".env"
    material = _dotenv_secret(dotenv_path)
    if material is not None:
        return "dotenv", dotenv_path, material
    for name in ("config.yaml", "settings.yaml", "default.yaml"):
        candidate = PROJECT_ROOT / "config" / name
        material = _yaml_secret(candidate)
        if material is not None:
            return "yaml", candidate, material
    if "NVIDIA_API_KEY" in os.environ:
        material = bytearray(os.environ["NVIDIA_API_KEY"].encode("utf-8"))
        if material:
            return "environment", None, material
    return None


def _rewrite_without_legacy_source(path: Path, source_kind: str) -> None:
    temporary = path.with_name(f".{path.name}.jarvis-migrate-{uuid.uuid4().hex}.tmp")
    in_nvidia = False
    try:
        with path.open("rb") as source, temporary.open("xb") as destination:
            for raw_line in source:
                remove = False
                if source_kind == "dotenv":
                    remove = _legacy_assignment(raw_line)
                else:
                    stripped = raw_line.lstrip()
                    if stripped and not stripped.startswith(b"#"):
                        indentation = len(raw_line) - len(stripped)
                        key, separator, _value = stripped.partition(b":")
                        if indentation == 0:
                            in_nvidia = bool(separator) and key.strip() == b"nvidia"
                        elif in_nvidia and separator and key.strip() == b"api_key":
                            remove = True
                if not remove:
                    destination.write(raw_line)
            destination.flush()
            os.fsync(destination.fileno())
        os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remove_legacy_source(source_kind: str, path: Path | None) -> None:
    if source_kind == "environment":
        if "NVIDIA_API_KEY" in os.environ:
            del os.environ["NVIDIA_API_KEY"]
        return
    if path is None:
        raise RuntimeError("legacy_source_invalid")
    _rewrite_without_legacy_source(path, source_kind)


def _disable_runtime_legacy_fallback() -> None:
    if "NVIDIA_API_KEY" in os.environ:
        del os.environ["NVIDIA_API_KEY"]
    loaded = getattr(config, "_config", None)
    if isinstance(loaded, dict) and isinstance(loaded.get("nvidia"), dict):
        loaded["nvidia"].pop("api_key", None)


def _nvidia_validator(*, provider: str, secret: memoryview, correlation_id: str) -> str:
    """Validate through the approved client without exposing provider details."""

    from src.clients.nvidia_client import NVIDIAClient
    from src.clients.provider_factory import ProviderSafeError

    async def probe() -> str:
        immutable_copy = bytes(secret).decode("utf-8")
        client = None
        try:
            client = NVIDIAClient(api_key=immutable_copy, timeout=10)
            await client.list_models()
            return "valid"
        except ProviderSafeError as exc:
            return {
                "forbidden_scope": "scope_forbidden",
                "stale_generation": "indeterminate",
                "credential_unrecoverable": "indeterminate",
            }.get(exc.code, exc.code)
        except (OSError, TimeoutError, asyncio.TimeoutError):
            return "indeterminate"
        except Exception:
            return "indeterminate"
        finally:
            immutable_copy = ""
            if client is not None:
                await client.close()

    return asyncio.run(probe())


@click.group()
@click.version_option(version="1.0.0", prog_name="JARVIS")
def cli():
    """JARVIS - Your Local AI Assistant powered by NVIDIA models."""
    pass


@cli.command()
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
def serve(host, port):
    """Start the JARVIS web server."""
    console.print(Panel.fit(
        "🤖 [bold cyan]JARVIS Web Server[/bold cyan]\n"
        "Starting server...",
        border_style="cyan"
    ))

    # Import here to avoid circular imports
    import uvicorn

    # Use 0.0.0.0 in production/Docker to bind to all interfaces
    default_host = "0.0.0.0" if os.getenv("DOCKER_CONTAINER") else "localhost"
    default_port = int(config.get("ui.port", 8080))
    uvicorn.run(
        "src.ui.app:app",
        host=host or config.get("ui.host", default_host),
        port=port or default_port,
        reload=not os.getenv("DOCKER_CONTAINER"),
    )


@cli.command()
def chat():
    """Start interactive chat with JARVIS."""
    console.print(Panel.fit(
        "[JARVIS] [bold cyan]JARVIS Interactive Chat[/bold cyan]\n"
        "Type 'exit' or 'quit' to leave\n"
        "Type 'help' for commands",
        border_style="cyan"
    ))

    asyncio.run(_run_chat())


async def _run_chat():
    """Run the chat loop."""
    jarvis = Jarvis()
    await jarvis.initialize()

    console.print("[green]JARVIS is ready![/green]")

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if user_input.lower() in ("exit", "quit", "bye"):
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() in ("help", "?"):
                _show_help()
                continue

            if user_input.lower() == "status":
                status = jarvis.get_status()
                console.print(f"[green]Status: {status}[/green]")
                continue

            if user_input.lower().startswith("model "):
                model = user_input[6:].strip()
                console.print(f"[yellow]Model switching not yet implemented[/yellow]")
                continue

            console.print("[dim]JARVIS is thinking...[/dim]")
            response = await jarvis.chat(user_input)
            console.print(f"[bold green]JARVIS[/bold green]: {response}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    await jarvis.shutdown()


def _show_help():
    """Show help message."""
    console.print(Panel("""
[bold]Available Commands:[/bold]
  [cyan]help[/cyan] / [cyan]?[/cyan]     - Show this help
  [cyan]exit[/cyan] / [cyan]quit[/cyan]   - Exit chat
  [cyan]status[/cyan]       - Show system status
  [cyan]model <name>[/cyan] - Switch model (not implemented)

[bold]Example Queries:[/bold]
  "What's the weather in New York?"
  "Search for Python asyncio tutorial"
  "Run python code: print('hello')"
  "Remember my preferred meeting time is 9 AM"
  "What did I ask you to remember?"
  "Calculate 15 * 23 + 45"
  "Show me system info"
  "List files in current directory"
""", title="Help", border_style="green"))


@cli.command()
@click.argument("message")
def ask(message):
    """Ask JARVIS a single question."""
    asyncio.run(_ask_once(message))


async def _ask_once(message: str):
    """Ask a single question."""
    jarvis = Jarvis()
    await jarvis.initialize()

    response = await jarvis.chat(message)
    console.print(f"[bold green]JARVIS[/bold green]: {response}")

    await jarvis.shutdown()


@cli.command()
def models():
    """List available NVIDIA models."""
    from src.models.nvidia_models import get_models_by_type, ModelType

    console.print(Panel.fit("[bold]Available NVIDIA Models[/bold]", border_style="cyan"))

    for model_type in ModelType:
        models = get_models_by_type(model_type)
        if models:
            console.print(f"\n[bold]{model_type.value.upper()}[/bold]")
            for model in models:
                console.print(f"  • [cyan]{model.id}[/cyan] - {model.name}")
                console.print(f"    {model.description}")
                console.print(f"    Context: {model.context_window:,} | Output: {model.max_output}")


@cli.command()
def configure():
    """Deprecated plaintext configuration entry point."""
    click.echo("PLAINTEXT_CONFIGURE_DISABLED")
    click.echo("Use `jarvis trust bootstrap` and `jarvis credentials migrate-legacy`.")
    raise click.exceptions.Exit(2)


@cli.group()
def trust():
    """Bootstrap and verify the local trust authority."""


@trust.command("bootstrap")
def trust_bootstrap():
    """Store only a salted verifier from hidden operator input."""
    from src.security.auth import SessionService

    unlock_value = click.prompt(
        "Operator unlock value",
        hide_input=True,
        confirmation_prompt="Repeat operator unlock value",
        type=str,
    )
    store = None
    try:
        store = _control_store()
        SessionService(store).configure_bootstrap(unlock_value)
        click.echo("TRUST_BOOTSTRAP_CONFIGURED")
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        raise click.ClickException(_safe_code(exc, "trust_bootstrap_failed")) from None
    finally:
        unlock_value = ""
        if store is not None:
            store.close()


@trust.command("verify")
@click.option("--quiet", is_flag=True, help="Return status through the exit code only.")
def trust_verify(quiet: bool):
    """Verify ACL, database, audit, identity, and durable control truth."""
    from src.core.audit import AuditService
    from src.core.control import ControlService

    store = None
    try:
        store = _control_store()
        audit = AuditService(store, protector=store.protector)
        verification = audit.verify_chain()
        snapshot = ControlService(store, audit_service=audit).snapshot()
        if not verification.valid:
            raise RuntimeError("audit_integrity_invalid")
        if not quiet:
            click.echo(
                "TRUST_VERIFY_OK "
                f"events={verification.checked_events} "
                f"control_state={snapshot.state.value} revision={snapshot.revision}"
            )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        if not quiet:
            click.echo(f"TRUST_VERIFY_FAILED code={_safe_code(exc, 'trust_verify_failed')}")
        raise click.exceptions.Exit(20)
    finally:
        if store is not None:
            store.close()


@trust.command("backup")
@click.option(
    "--destination",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False, resolve_path=True),
)
def trust_backup(destination: Path):
    """Create and verify an online backup in the protected backup directory."""
    store = None
    try:
        store = _control_store()
        manifest = store.create_online_backup(destination)
        click.echo(
            "TRUST_BACKUP_OK "
            f"verified={str(manifest.verified).lower()} "
            f"schema_version={manifest.schema_version} "
            f"audit_sequence={manifest.audit_sequence}"
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        raise click.ClickException(_safe_code(exc, "trust_backup_failed")) from None
    finally:
        if store is not None:
            store.close()


@trust.command("restore")
@click.option(
    "--candidate",
    required=True,
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
)
@click.confirmation_option(
    prompt="The backend must be stopped. Restore this verified candidate?"
)
def trust_restore(candidate: Path):
    """Verify, then atomically restore while the backend is stopped."""
    store = None
    try:
        store = _control_store()
        store.verify_restore_candidate(candidate)
        store.close()
        result = store.restore_verified(candidate)
        if not result.swapped:
            raise RuntimeError("restore_swap_failed")
        click.echo(
            "TRUST_RESTORE_OK swapped=true "
            f"recovery_created={str(result.recovery_artifact is not None).lower()}"
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        raise click.ClickException(_safe_code(exc, "trust_restore_failed")) from None
    finally:
        if store is not None:
            store.close()


@cli.group()
def credentials():
    """Manage backend-only provider credential migration state."""


@credentials.command("migrate-legacy")
@click.option("--provider", type=click.Choice(["nvidia"]), required=True)
@click.option("--label", default="Legacy NVIDIA import", show_default=True)
def credentials_migrate_legacy(provider: str, label: str):
    """Import a detected legacy value without argv, shell, or output exposure."""
    from src.core.audit import AuditService
    from src.core.credentials import CredentialError, CredentialService, CredentialState

    if not bool(config.get("credentials.legacy_env_migration_enabled", True)):
        raise click.ClickException("legacy_migration_disabled")
    source = _read_legacy_source()
    if source is None:
        click.echo("LEGACY_MIGRATION_NOT_APPLIED code=legacy_source_absent")
        raise click.exceptions.Exit(3)
    source_kind, source_path, secret_buffer = source
    store = None
    correlation_id = f"migration-{uuid.uuid4()}"
    try:
        store = _control_store()
        if _cutover_row(store, provider) is not None:
            _disable_runtime_legacy_fallback()
            click.echo("LEGACY_CUTOVER_ALREADY_COMPLETE restart_required=false")
            return
        audit = AuditService(store, protector=store.protector)
        service = CredentialService(
            store,
            protector=store.protector,
            audit_service=audit,
            validator=_nvidia_validator,
        )
        pending = service.add(
            provider=provider,
            label=label,
            secret_buffer=secret_buffer,
            actor_id="operator-cli",
            client_request_id=f"{correlation_id}:add",
        )
        validated = service.validate(
            pending.credential_id,
            expected_version=pending.version,
            client_request_id=f"{correlation_id}:validate",
            actor_id="operator-cli",
        )
        if validated.state is not CredentialState.VALID:
            click.echo(
                "LEGACY_MIGRATION_ROLLED_BACK "
                f"display_id={validated.display_id} state={validated.state.value} "
                f"version={validated.version} generation={validated.provider_generation} "
                f"correlation_id={validated.correlation_id or correlation_id}"
            )
            raise click.exceptions.Exit(4)
        promoted = service.promote(
            validated.credential_id,
            expected_version=validated.version,
            client_request_id=f"{correlation_id}:promote",
            actor_id="operator-cli",
        )
        with store.immediate_transaction() as tx:
            tx.execute(
                """INSERT INTO provider_cutovers(
                       provider, active_credential_id, provider_generation,
                       source_kind, completed_at, restart_required
                   ) VALUES(?, ?, ?, ?, ?, 1)""",
                (
                    provider,
                    promoted.credential_id,
                    promoted.provider_generation,
                    source_kind,
                    _timestamp(),
                ),
            )
            cutover_event = _append_migration_audit(
                tx,
                audit,
                action="legacy_credential_cutover",
                outcome="accepted",
                status="active",
                reason_code="protected_credential_promoted",
                correlation_id=correlation_id,
                safe_id=promoted.display_id,
                applied=True,
            )
        _disable_runtime_legacy_fallback()
        source_removed = False
        if click.confirm("Remove the detected legacy source now?", default=False):
            try:
                _remove_legacy_source(source_kind, source_path)
                source_removed = True
            except BaseException:
                click.echo("LEGACY_SOURCE_REMOVE_FAILED code=source_remove_failed")
        click.echo(
            "LEGACY_CUTOVER_COMPLETE "
            f"display_id={promoted.display_id} state={promoted.state.value} "
            f"version={promoted.version} generation={promoted.provider_generation} "
            f"correlation_id={correlation_id} audit_id={cutover_event.event_id} "
            f"source_removed={str(source_removed).lower()} restart_required=true"
        )
    except CredentialError as exc:
        click.echo(f"LEGACY_MIGRATION_NOT_APPLIED code={_safe_code(exc, 'migration_failed')}")
        raise click.exceptions.Exit(5)
    except click.exceptions.Exit:
        raise
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        click.echo(f"LEGACY_MIGRATION_NOT_APPLIED code={_safe_code(exc, 'migration_failed')}")
        raise click.exceptions.Exit(5)
    finally:
        secret_buffer[:] = b"\x00" * len(secret_buffer)
        if store is not None:
            store.close()


@credentials.command("rollback-legacy")
@click.option("--provider", type=click.Choice(["nvidia"]), required=True)
@click.option("--credential-id", required=True)
@click.option("--expected-version", required=True, type=click.IntRange(min=1))
@click.confirmation_option(prompt="Revoke this failed legacy import candidate?")
def credentials_rollback_legacy(provider: str, credential_id: str, expected_version: int):
    """Explicitly revoke a non-active failed migration candidate."""
    from src.core.audit import AuditService
    from src.core.credentials import CredentialService, CredentialState

    store = None
    try:
        store = _control_store()
        service = CredentialService(
            store,
            protector=store.protector,
            audit_service=AuditService(store, protector=store.protector),
        )
        current = service.get(credential_id)
        if current.provider != provider or current.state is CredentialState.ACTIVE:
            raise RuntimeError("rollback_not_allowed")
        revoked = service.revoke(
            credential_id,
            expected_version=expected_version,
            client_request_id=f"migration-rollback-{uuid.uuid4()}",
            actor_id="operator-cli",
        )
        click.echo(
            "LEGACY_MIGRATION_ROLLBACK_OK "
            f"display_id={revoked.display_id} state={revoked.state.value} "
            f"version={revoked.version} generation={revoked.provider_generation}"
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        raise click.ClickException(_safe_code(exc, "legacy_rollback_failed")) from None
    finally:
        if store is not None:
            store.close()


@credentials.command("cutover-status")
@click.option("--provider", type=click.Choice(["nvidia"]), required=True)
@click.option("--quiet", is_flag=True)
def credentials_cutover_status(provider: str, quiet: bool):
    """Return only protected active generation and restart state."""
    from src.core.audit import AuditService
    from src.core.credentials import CredentialService, CredentialState

    store = None
    try:
        store = _control_store()
        row = _cutover_row(store, provider)
        if row is None:
            if not quiet:
                click.echo("CREDENTIAL_CUTOVER_PENDING")
            raise click.exceptions.Exit(30)
        service = CredentialService(
            store,
            protector=store.protector,
            audit_service=AuditService(store, protector=store.protector),
        )
        active = service.active_for_provider(provider)
        if (
            active.state is not CredentialState.ACTIVE
            or active.credential_id != str(row["active_credential_id"])
            or active.provider_generation != int(row["provider_generation"])
        ):
            raise RuntimeError("cutover_active_mismatch")
        if not quiet:
            click.echo(
                "CREDENTIAL_CUTOVER_READY "
                f"display_id={active.display_id} generation={active.provider_generation} "
                f"restart_required={str(bool(row['restart_required'])).lower()}"
            )
        if bool(row["restart_required"]):
            raise click.exceptions.Exit(31)
    except click.exceptions.Exit:
        raise
    except BaseException as exc:
        if not quiet:
            click.echo(f"CREDENTIAL_CUTOVER_FAILED code={_safe_code(exc, 'cutover_verify_failed')}")
        raise click.exceptions.Exit(32)
    finally:
        if store is not None:
            store.close()


@credentials.command("mark-restarted", hidden=True)
@click.option("--provider", type=click.Choice(["nvidia"]), required=True)
def credentials_mark_restarted(provider: str):
    """Acknowledge a verified sanitized backend restart."""
    from src.core.audit import AuditService

    store = None
    try:
        store = _control_store()
        audit = AuditService(store, protector=store.protector)
        row = _cutover_row(store, provider)
        if row is None:
            raise RuntimeError("cutover_not_complete")
        correlation_id = f"restart-{uuid.uuid4()}"
        with store.immediate_transaction() as tx:
            tx.execute(
                "UPDATE provider_cutovers SET restart_required = 0 WHERE provider = ?",
                (provider,),
            )
            _append_migration_audit(
                tx,
                audit,
                action="legacy_credential_restart",
                outcome="accepted",
                status="ready",
                reason_code="sanitized_process_verified",
                correlation_id=correlation_id,
                safe_id="provider-nvidia",
                applied=True,
            )
        click.echo("CREDENTIAL_RESTART_ACKNOWLEDGED")
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, click.Abort)):
            raise
        raise click.ClickException(_safe_code(exc, "restart_ack_failed")) from None
    finally:
        if store is not None:
            store.close()


@cli.command()
def test():
    """Test the active protected NVIDIA credential."""
    asyncio.run(_test_api())


async def _test_api():
    """Test API connection through the active opaque credential handle."""
    from src.clients.nvidia_client import NVIDIAClient
    from src.clients.provider_factory import ProviderFactory
    from src.core.audit import AuditService
    from src.core.credentials import CredentialService

    console.print("[dim]Testing NVIDIA API...[/dim]")
    store = None
    client = None
    try:
        store = _control_store()
        service = CredentialService(
            store,
            protector=store.protector,
            audit_service=AuditService(store, protector=store.protector),
        )
        active = service.active_for_provider("nvidia")
        client = NVIDIAClient(
            provider_factory=ProviderFactory(credential_service=service),
            credential_handle=active.credential_id,
            expected_generation=active.provider_generation,
        )
        async with client:
            response = await client.chat_completion(
                messages=[{"role": "user", "content": "Hello, respond with 'OK'"}],
                max_tokens=10,
            )
            if not response.get("choices"):
                raise RuntimeError("provider_response_invalid")
            console.print(
                "[green]PROVIDER_TEST_OK[/green] "
                f"display_id={active.display_id} generation={active.provider_generation}"
            )
    except Exception as e:
        console.print(
            f"[red]PROVIDER_TEST_FAILED code={_safe_code(e, 'provider_test_failed')}[/red]"
        )
        raise click.exceptions.Exit(1)
    finally:
        if client is not None:
            await client.close()
        if store is not None:
            store.close()


@cli.command()
def init():
    """Initialize JARVIS project structure."""
    dirs = [
        "data/memory",
        "data/cache",
        "logs",
        "config",
    ]

    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"[green]Created {d}[/green]")

    console.print("[bold green]JARVIS initialized![/bold green]")
    console.print("Next steps:")
    console.print("  1. Run: python main.py trust bootstrap")
    console.print(
        "  2. If needed, run: python main.py credentials migrate-legacy --provider nvidia"
    )
    console.print("  3. Restart the backend, then run: python main.py test")


if __name__ == "__main__":
    cli()
