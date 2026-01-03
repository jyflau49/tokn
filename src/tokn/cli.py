"""CLI interface for tokn."""

from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from tokn.core.backend import DopplerBackend
from tokn.core.rotation import RotationOrchestrator
from tokn.core.token import RotationType, TokenLocation, TokenMetadata, TokenStatus

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """tokn - Automated monthly API token rotation."""
    pass


@cli.command()
@click.argument("name")
@click.option(
    "--service",
    required=True,
    type=click.Choice([
        "github",
        "cloudflare",
        "linode-cli",
        "linode-doppler",
        "terraform-account",
        "terraform-org"
    ]),
    help="Service provider"
)
@click.option("--rotation-type", type=click.Choice(["auto", "manual"]), default="auto")
@click.option(
    "--location",
    multiple=True,
    help="Location in format 'type:path' (can specify multiple)"
)
@click.option("--expiry-days", type=int, default=30, help="Days until expiry")
@click.option("--notes", default="", help="Additional notes")
def track(
    name: str,
    service: str,
    rotation_type: str,
    location: tuple,
    expiry_days: int,
    notes: str,
):
    """Track a new token."""
    backend = DopplerBackend()
    registry = backend.load_registry()

    if registry.get_token(name):
        console.print(f"[red]Token '{name}' already exists[/red]")
        return

    locations = []
    for loc in location:
        if ":" not in loc:
            console.print(f"[red]Invalid location format: {loc}. Use 'type:path'[/red]")
            return

        parts = loc.split(":", 2)
        loc_type = parts[0]
        loc_path = parts[1]
        metadata = {}

        if len(parts) == 3:
            for pair in parts[2].split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    metadata[key.strip()] = value.strip()

        locations.append(TokenLocation(type=loc_type, path=loc_path, metadata=metadata))

    if not locations:
        console.print("[red]At least one location is required[/red]")
        return

    token_metadata = TokenMetadata(
        name=name,
        service=service,
        rotation_type=RotationType(rotation_type),
        locations=locations,
        expires_at=datetime.now() + timedelta(days=expiry_days),
        notes=notes
    )

    registry.add_token(token_metadata)
    backend.save_registry(registry)

    console.print(f"[green]✓[/green] Token '{name}' tracked successfully")


@cli.command()
@click.option(
    "--all",
    "rotate_all",
    is_flag=True,
    help="Rotate all auto-rotatable tokens"
)
@click.option("--auto-only", is_flag=True, default=True, help="Skip manual tokens")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be rotated without doing it"
)
@click.argument("token_name", required=False)
def rotate(rotate_all: bool, auto_only: bool, dry_run: bool, token_name: str):
    """Rotate tokens."""
    orchestrator = RotationOrchestrator()
    backend = DopplerBackend()

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

    if rotate_all:
        results = orchestrator.rotate_all(auto_only=auto_only, dry_run=dry_run)

        if results["success"]:
            console.print("[green]Successfully rotated:[/green]")
            for item in results["success"]:
                console.print(f"  ✓ {item['name']}")
                for loc in item["locations"]:
                    console.print(f"    - {loc}")

        if results["failed"]:
            console.print("\n[red]Failed to rotate:[/red]")
            for item in results["failed"]:
                console.print(f"  ✗ {item['name']}: {item['error']}")

        if results["manual"]:
            console.print("\n[yellow]Manual rotation required:[/yellow]")
            for item in results["manual"]:
                console.print(f"  ⚠ {item['name']}")
                console.print(f"{item['instructions']}")

    elif token_name:
        registry = backend.load_registry()
        token = registry.get_token(token_name)

        if not token:
            console.print(f"[red]Token '{token_name}' not found[/red]")
            return

        success, message, locations = orchestrator.rotate_token(token, dry_run)

        if success:
            console.print(f"[green]✓[/green] {message}")
            for loc in locations:
                console.print(f"  - {loc}")
        else:
            console.print(f"[red]✗[/red] {message}")

    else:
        console.print("[red]Specify --all or provide a token name[/red]")


@cli.command()
@click.option("--expiring", is_flag=True, help="Show only expiring tokens")
def status(expiring: bool):
    """Show status of all tracked tokens."""
    backend = DopplerBackend()
    registry = backend.load_registry()

    tokens = registry.list_tokens()
    if not tokens:
        console.print("[yellow]No tokens tracked yet[/yellow]")
        return

    table = Table(title="Token Status")
    table.add_column("Name", style="cyan")
    table.add_column("Service", style="magenta")
    table.add_column("Type", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Expires", style="yellow")
    table.add_column("Last Rotated", style="white")

    for token in tokens:
        if expiring and token.status == TokenStatus.ACTIVE:
            continue

        status_emoji = {
            TokenStatus.ACTIVE: "✓",
            TokenStatus.EXPIRING_SOON: "⚠",
            TokenStatus.EXPIRED: "✗"
        }

        status_color = {
            TokenStatus.ACTIVE: "green",
            TokenStatus.EXPIRING_SOON: "yellow",
            TokenStatus.EXPIRED: "red"
        }

        expiry_str = "N/A"
        if token.expires_at:
            days = token.days_until_expiry
            if days is not None:
                expiry_str = f"{days} days"

        last_rotated_str = "Never"
        if token.last_rotated:
            last_rotated_str = token.last_rotated.strftime("%Y-%m-%d")

        table.add_row(
            token.name,
            token.service,
            token.rotation_type.value,
            (
                f"[{status_color[token.status]}]"
                f"{status_emoji[token.status]} {token.status.value}"
                f"[/{status_color[token.status]}]"
            ),
            expiry_str,
            last_rotated_str
        )

    console.print(table)

    if registry.last_sync:
        sync_time = registry.last_sync.strftime('%Y-%m-%d %H:%M:%S')
        console.print(f"\n[dim]Last sync: {sync_time}[/dim]")


@cli.command()
def sync():
    """Sync metadata from Doppler."""
    backend = DopplerBackend()
    registry = backend.sync()

    console.print(f"[green]✓[/green] Synced {len(registry.tokens)} tokens from Doppler")
    if registry.last_sync:
        sync_time = registry.last_sync.strftime('%Y-%m-%d %H:%M:%S')
        console.print(f"[dim]Last sync: {sync_time}[/dim]")


@cli.command()
@click.argument("name")
def remove(name: str):
    """Remove a tracked token."""
    backend = DopplerBackend()
    registry = backend.load_registry()

    if registry.remove_token(name):
        backend.save_registry(registry)
        console.print(f"[green]✓[/green] Token '{name}' removed")
    else:
        console.print(f"[red]Token '{name}' not found[/red]")


@cli.command()
@click.argument("name")
def info(name: str):
    """Show detailed information about a token."""
    backend = DopplerBackend()
    registry = backend.load_registry()

    token = registry.get_token(name)
    if not token:
        console.print(f"[red]Token '{name}' not found[/red]")
        return

    console.print(f"\n[bold cyan]{token.name}[/bold cyan]")
    console.print(f"Service: {token.service}")
    console.print(f"Rotation Type: {token.rotation_type.value}")
    console.print(f"Status: {token.status.value}")

    if token.expires_at:
        expiry_date = token.expires_at.strftime('%Y-%m-%d')
        console.print(f"Expires: {expiry_date} ({token.days_until_expiry} days)")

    if token.last_rotated:
        last_rot = token.last_rotated.strftime('%Y-%m-%d %H:%M:%S')
        console.print(f"Last Rotated: {last_rot}")

    console.print("\nLocations:")
    for loc in token.locations:
        console.print(f"  - {loc.type}: {loc.path}")
        if loc.metadata:
            for key, value in loc.metadata.items():
                console.print(f"    {key}: {value}")

    if token.notes:
        console.print(f"\nNotes: {token.notes}")


if __name__ == "__main__":
    cli()
