"""CLI interface for tokn."""

import sys
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table
from tabulate import tabulate

from tokn import __version__
from tokn.core.backend import get_backend, get_config, save_config
from tokn.core.backend.factory import migrate_backend
from tokn.core.rotation import RotationOrchestrator
from tokn.core.token import RotationType, TokenLocation, TokenMetadata, TokenStatus
from tokn.utils.progress import progress_spinner

console = Console(stderr=True)
stdout_console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """tokn - Automated API token rotation."""
    pass


@cli.command()
@click.argument("name")
@click.option(
    "--service",
    required=True,
    type=click.Choice(
        [
            "github",
            "cloudflare",
            "linode-cli",
            "linode-doppler",
            "terraform-account",
            "akamai-edgegrid",
        ]
    ),
    help="Service provider",
)
@click.option("--rotation-type", type=click.Choice(["auto", "manual"]), default="auto")
@click.option(
    "--location",
    multiple=True,
    help="Location in format 'type:path' (can specify multiple)",
)
@click.option("--expiry-days", type=int, default=90, help="Days until expiry")
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
    backend = get_backend()
    registry = backend.load_registry()

    if registry.get_token(name):
        console.print(f"[red]Token '{name}' already exists[/red]", style="red")
        sys.exit(1)

    locations = []
    for loc in location:
        if ":" not in loc:
            console.print(f"[red]Invalid location format: {loc}. Use 'type:path'[/red]")
            sys.exit(1)

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
        sys.exit(1)

    token_metadata = TokenMetadata(
        name=name,
        service=service,
        rotation_type=RotationType(rotation_type),
        locations=locations,
        expires_at=datetime.now() + timedelta(days=expiry_days),
        notes=notes,
    )

    registry.add_token(token_metadata)
    backend.save_registry(registry)

    stdout_console.print("[green]✓ Token tracked successfully[/green]")
    stdout_console.print(f"  [cyan]Name:[/cyan] {name}")
    stdout_console.print(f"  [cyan]Service:[/cyan] {service}")
    stdout_console.print(f"  [cyan]Type:[/cyan] {rotation_type}")


@cli.command()
@click.option(
    "--all", "rotate_all", is_flag=True, help="Rotate all auto-rotatable tokens"
)
@click.option("--auto-only", is_flag=True, default=True, help="Skip manual tokens")
@click.argument("token_name", required=False)
def rotate(rotate_all: bool, auto_only: bool, token_name: str):
    """Rotate tokens."""
    orchestrator = RotationOrchestrator()
    backend = get_backend()

    if rotate_all:
        with progress_spinner("Rotating tokens"):
            results = orchestrator.rotate_all(auto_only=auto_only)

        if results["success"]:
            stdout_console.print("[bold green]✓ Successfully rotated:[/bold green]")
            for item in results["success"]:
                stdout_console.print(f"  [green]•[/green] [cyan]{item['name']}[/cyan]")
                for loc in item["locations"]:
                    stdout_console.print(f"    [dim]→[/dim] {loc}")

        if results["failed"]:
            console.print("\n[bold red]✗ Failed to rotate:[/bold red]")
            for item in results["failed"]:
                console.print(
                    f"  [red]•[/red] [cyan]{item['name']}[/cyan]: "
                    f"[red]{item['error']}[/red]"
                )

        if results["manual"]:
            stdout_console.print(
                "\n[bold yellow]⚠ Manual rotation required:[/bold yellow]"
            )
            for item in results["manual"]:
                stdout_console.print(
                    f"  [yellow]•[/yellow] [cyan]{item['name']}[/cyan]"
                )
                stdout_console.print(f"[dim]{item['instructions']}[/dim]")

    elif token_name:
        registry = backend.load_registry()
        token = registry.get_token(token_name)

        if not token:
            console.print(f"[red]✗ Token not found:[/red] [cyan]{token_name}[/cyan]")
            sys.exit(1)

        # Type guard: token is guaranteed to be TokenMetadata here
        assert token is not None

        with progress_spinner(f"Rotating {token_name}", "~5s"):
            success, message, locations = orchestrator.rotate_token(token)

        if success:
            stdout_console.print(f"[green]✓ {message}[/green]")
            for loc in locations:
                stdout_console.print(f"  [dim]→[/dim] {loc}")
        else:
            console.print(f"[red]✗ {message}[/red]")
            sys.exit(1)

    else:
        console.print("[red]Specify --all or provide a token name[/red]")
        sys.exit(1)


@cli.command("list")
@click.option("--expiring", is_flag=True, help="Show only expiring tokens")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "simple", "plain"]),
    default="rich",
    help="Output format (rich=styled, simple=tabulate, plain=no borders)",
)
def list_tokens(expiring: bool, output_format: str):
    """List all tracked tokens."""
    backend = get_backend()
    registry = backend.load_registry()

    tokens = registry.list_tokens()
    if not tokens:
        console.print(
            "[yellow]No tokens tracked yet. Use[/yellow] "
            "[cyan]tokn track[/cyan] [yellow]to get started.[/yellow]"
        )
        return

    # Filter if --expiring
    if expiring:
        tokens = [t for t in tokens if t.status != TokenStatus.ACTIVE]

    # Prepare data rows
    rows = []
    for token in tokens:
        status_emoji = {
            TokenStatus.ACTIVE: "✓",
            TokenStatus.EXPIRING_SOON: "⚠",
            TokenStatus.EXPIRED: "✗",
        }

        expiry_str = "N/A"
        if token.expires_at:
            days = token.days_until_expiry
            if days is not None:
                expiry_str = f"{days} days"

        last_rotated_str = "Never"
        if token.last_rotated:
            last_rotated_str = token.last_rotated.strftime("%Y-%m-%d")

        rows.append(
            {
                "name": token.name,
                "service": token.service,
                "type": token.rotation_type.value,
                "status": token.status.value,
                "status_emoji": status_emoji[token.status],
                "expires": expiry_str,
                "last_rotated": last_rotated_str,
            }
        )

    # Output based on format
    if output_format == "rich":
        _print_rich_table(rows, registry)
    else:
        tablefmt = "simple" if output_format == "simple" else "plain"
        _print_tabulate_table(rows, tablefmt)
        if registry.last_sync:
            sync_time = registry.last_sync.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\nLast sync: {sync_time}")


def _print_rich_table(rows: list, registry) -> None:
    """Print tokens as rich styled table."""
    status_color = {
        "active": "green",
        "expiring_soon": "yellow",
        "expired": "red",
    }

    table = Table(
        title="[bold]Token Status[/bold]", show_header=True, header_style="bold"
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Service", style="magenta")
    table.add_column("Type", style="blue")
    table.add_column("Status")
    table.add_column("Expires", style="yellow")
    table.add_column("Last Rotated", style="dim")

    for row in rows:
        color = status_color[row["status"]]
        table.add_row(
            row["name"],
            row["service"],
            row["type"],
            f"[{color}]{row['status_emoji']} {row['status']}[/{color}]",
            row["expires"],
            row["last_rotated"],
        )

    stdout_console.print(table)

    if registry.last_sync:
        sync_time = registry.last_sync.strftime("%Y-%m-%d %H:%M:%S")
        stdout_console.print(f"\n[dim]Last sync: {sync_time}[/dim]")


def _print_tabulate_table(rows: list, tablefmt: str) -> None:
    """Print tokens as tabulate table."""
    table_data = [
        [
            row["name"],
            row["service"],
            row["type"],
            f"{row['status_emoji']} {row['status']}",
            row["expires"],
            row["last_rotated"],
        ]
        for row in rows
    ]
    headers = ["Name", "Service", "Type", "Status", "Expires", "Last Rotated"]
    print(tabulate(table_data, headers=headers, tablefmt=tablefmt))


@cli.command()
def sync():
    """Sync metadata from backend."""
    backend = get_backend()

    with progress_spinner(f"Syncing from {backend.backend_type} backend"):
        registry = backend.sync()

    stdout_console.print(f"[green]✓ Synced from {backend.backend_type} backend[/green]")
    stdout_console.print(f"  [cyan]Tokens:[/cyan] {len(registry.tokens)}")
    if registry.last_sync:
        sync_time = registry.last_sync.strftime("%Y-%m-%d %H:%M:%S")
        stdout_console.print(f"  [cyan]Last sync:[/cyan] [dim]{sync_time}[/dim]")


@cli.command()
@click.argument("name")
def remove(name: str):
    """Remove a tracked token."""
    backend = get_backend()
    registry = backend.load_registry()

    if registry.remove_token(name):
        backend.save_registry(registry)
        stdout_console.print(f"[green]✓ Token removed:[/green] [cyan]{name}[/cyan]")
    else:
        console.print(f"[red]✗ Token not found:[/red] [cyan]{name}[/cyan]")
        sys.exit(1)


@cli.command()
@click.argument("name")
@click.option("--expiry-days", type=int, help="Update days until expiry")
@click.option(
    "--location",
    multiple=True,
    help="Replace locations (use multiple times for multiple locations)",
)
@click.option("--add-location", help="Add a new location")
@click.option("--remove-location", help="Remove a location by type:path")
@click.option("--notes", help="Update notes")
def update(
    name: str,
    expiry_days: int | None,
    location: tuple,
    add_location: str | None,
    remove_location: str | None,
    notes: str | None,
):
    """Update a tracked token's metadata."""
    backend = get_backend()
    registry = backend.load_registry()

    token = registry.get_token(name)
    if not token:
        console.print(f"[red]✗ Token not found:[/red] [cyan]{name}[/cyan]")
        sys.exit(1)

    # Type guard: token is guaranteed to be TokenMetadata here
    assert token is not None

    changes_made = []

    # Update expiry
    if expiry_days is not None:
        token.expires_at = datetime.now() + timedelta(days=expiry_days)
        changes_made.append(f"expiry set to {expiry_days} days")

    # Replace all locations
    if location:
        new_locations = []
        for loc in location:
            if ":" not in loc:
                console.print(f"[red]Invalid location format: {loc}[/red]")
                sys.exit(1)
            parts = loc.split(":", 2)
            loc_type = parts[0]
            loc_path = parts[1]
            metadata = {}
            if len(parts) == 3:
                for pair in parts[2].split(","):
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        metadata[key.strip()] = value.strip()
            new_locations.append(
                TokenLocation(type=loc_type, path=loc_path, metadata=metadata)
            )
        token.locations = new_locations
        changes_made.append(f"locations replaced ({len(new_locations)} total)")

    # Add a location
    if add_location:
        if ":" not in add_location:
            console.print(f"[red]Invalid location format: {add_location}[/red]")
            sys.exit(1)
        parts = add_location.split(":", 2)
        loc_type = parts[0]
        loc_path = parts[1]
        metadata = {}
        if len(parts) == 3:
            for pair in parts[2].split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    metadata[key.strip()] = value.strip()
        token.locations.append(
            TokenLocation(type=loc_type, path=loc_path, metadata=metadata)
        )
        changes_made.append(f"added location {loc_type}:{loc_path}")

    # Remove a location
    if remove_location:
        original_count = len(token.locations)
        token.locations = [
            loc
            for loc in token.locations
            if f"{loc.type}:{loc.path}" != remove_location
        ]
        if len(token.locations) < original_count:
            changes_made.append(f"removed location {remove_location}")
        else:
            console.print(f"[yellow]Location not found: {remove_location}[/yellow]")

    # Update notes
    if notes is not None:
        token.notes = notes
        changes_made.append("notes updated")

    if not changes_made:
        console.print("[yellow]No changes specified. Use --help for options.[/yellow]")
        return

    registry.add_token(token)
    backend.save_registry(registry)

    stdout_console.print(f"[green]✓ Token updated:[/green] [cyan]{name}[/cyan]")
    for change in changes_made:
        stdout_console.print(f"  [dim]→[/dim] {change}")


@cli.command("describe")
@click.argument("name")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "simple", "plain"]),
    default="rich",
    help="Output format (rich=styled, simple=tabulate, plain=no borders)",
)
def describe(name: str, output_format: str):
    """Show detailed information about a token."""
    backend = get_backend()
    registry = backend.load_registry()

    token = registry.get_token(name)
    if not token:
        console.print(f"[red]✗ Token not found:[/red] [cyan]{name}[/cyan]")
        sys.exit(1)

    if output_format == "rich":
        _print_rich_describe(token)
    else:
        tablefmt = "simple" if output_format == "simple" else "plain"
        _print_tabulate_describe(token, tablefmt)


def _print_rich_describe(token) -> None:
    """Print token details as rich styled output."""
    status_color = {
        TokenStatus.ACTIVE: "green",
        TokenStatus.EXPIRING_SOON: "yellow",
        TokenStatus.EXPIRED: "red",
    }
    status_style = status_color[token.status]

    stdout_console.print(f"\n[bold cyan]{token.name}[/bold cyan]")
    stdout_console.print(f"[cyan]Service:[/cyan] {token.service}")
    stdout_console.print(f"[cyan]Rotation Type:[/cyan] {token.rotation_type.value}")
    stdout_console.print(
        f"[cyan]Status:[/cyan] [{status_style}]{token.status.value}[/{status_style}]"
    )

    if token.expires_at:
        expiry_date = token.expires_at.strftime("%Y-%m-%d")
        stdout_console.print(
            f"[cyan]Expires:[/cyan] {expiry_date} "
            f"[dim]({token.days_until_expiry} days)[/dim]"
        )

    if token.last_rotated:
        last_rot = token.last_rotated.strftime("%Y-%m-%d %H:%M:%S")
        stdout_console.print(f"[cyan]Last Rotated:[/cyan] {last_rot}")

    stdout_console.print("\n[cyan]Locations:[/cyan]")
    for loc in token.locations:
        stdout_console.print(
            f"  [green]•[/green] [magenta]{loc.type}[/magenta]: {loc.path}"
        )
        if loc.metadata:
            for key, value in loc.metadata.items():
                stdout_console.print(f"    [dim]{key}:[/dim] {value}")

    if token.notes:
        stdout_console.print(f"\n[cyan]Notes:[/cyan] [dim]{token.notes}[/dim]")


def _print_tabulate_describe(token, tablefmt: str) -> None:
    """Print token details as tabulate table."""
    expiry_str = "N/A"
    if token.expires_at:
        expiry_date = token.expires_at.strftime("%Y-%m-%d")
        expiry_str = f"{expiry_date} ({token.days_until_expiry} days)"

    last_rotated_str = "Never"
    if token.last_rotated:
        last_rotated_str = token.last_rotated.strftime("%Y-%m-%d %H:%M:%S")

    # Main info table
    info_data = [
        ["Name", token.name],
        ["Service", token.service],
        ["Rotation Type", token.rotation_type.value],
        ["Status", token.status.value],
        ["Expires", expiry_str],
        ["Last Rotated", last_rotated_str],
    ]
    if token.notes:
        info_data.append(["Notes", token.notes])

    print(tabulate(info_data, tablefmt=tablefmt))

    # Locations table
    print("\nLocations:")
    loc_data = []
    for loc in token.locations:
        meta_str = ", ".join(f"{k}={v}" for k, v in loc.metadata.items())
        loc_data.append([loc.type, loc.path, meta_str or "-"])
    print(tabulate(loc_data, headers=["Type", "Path", "Metadata"], tablefmt=tablefmt))


# Backend management commands
@cli.group()
def backend():
    """Manage metadata storage backend.

    tokn supports two backends:
    - local: Solo developer, offline-capable, no external dependencies
    - doppler: Multi-device sync, team collaboration via cloud
    """
    pass


@backend.command("show")
def backend_show():
    """Show current backend configuration."""
    config = get_config()
    current_backend = config.get("backend", "local")

    stdout_console.print("[bold]Backend Configuration[/bold]\n")
    stdout_console.print(f"[cyan]Current backend:[/cyan] {current_backend}")

    if current_backend == "local":
        local_config = config.get("local", {})
        data_dir = local_config.get("data_dir", "~/.config/tokn")
        stdout_console.print(f"[cyan]Data directory:[/cyan] {data_dir}")
        stdout_console.print(
            "\n[dim]Local backend: Solo developer, works offline[/dim]"
        )
    elif current_backend == "doppler":
        doppler_config = config.get("doppler", {})
        project = doppler_config.get("project", "tokn")
        doppler_env = doppler_config.get("config", "dev")
        stdout_console.print(f"[cyan]Doppler project:[/cyan] {project}")
        stdout_console.print(f"[cyan]Doppler config:[/cyan] {doppler_env}")
        stdout_console.print(
            "\n[dim]Doppler backend: Multi-device sync, team collaboration[/dim]"
        )

    # Show token count
    try:
        backend_instance = get_backend()
        registry = backend_instance.load_registry()
        stdout_console.print(f"\n[cyan]Tokens stored:[/cyan] {len(registry.tokens)}")
    except Exception as e:
        console.print(f"\n[yellow]Could not load registry: {e}[/yellow]")


@backend.command("migrate")
@click.option(
    "--from",
    "from_backend",
    required=True,
    type=click.Choice(["local", "doppler"]),
    help="Source backend",
)
@click.option(
    "--to",
    "to_backend",
    required=True,
    type=click.Choice(["local", "doppler"]),
    help="Destination backend",
)
@click.option("--force", is_flag=True, help="Overwrite existing data in destination")
def backend_migrate(from_backend: str, to_backend: str, force: bool):
    """Migrate metadata between backends.

    Examples:
        tokn backend migrate --from doppler --to local
        tokn backend migrate --from local --to doppler
    """
    if from_backend == to_backend:
        console.print(f"[red]Source and destination are the same: {from_backend}[/red]")
        sys.exit(1)

    # Check if destination has data
    if not force:
        try:
            dest = get_backend(to_backend)
            dest_registry = dest.load_registry()
            if dest_registry.tokens:
                console.print(
                    f"[yellow]Destination backend '{to_backend}' already has "
                    f"{len(dest_registry.tokens)} token(s).[/yellow]"
                )
                console.print("[yellow]Use --force to overwrite.[/yellow]")
                sys.exit(1)
        except Exception:
            pass  # Destination doesn't exist or can't be read, OK to proceed

    with progress_spinner(f"Migrating from {from_backend} to {to_backend}"):
        success, message, token_count = migrate_backend(from_backend, to_backend)

    if success:
        stdout_console.print(f"[green]✓ {message}[/green]")
        stdout_console.print(f"  [cyan]Active backend:[/cyan] {to_backend}")
    else:
        console.print(f"[red]✗ {message}[/red]")
        sys.exit(1)


@backend.command("set")
@click.argument("backend_type", type=click.Choice(["local", "doppler"]))
@click.option("--project", help="Doppler project (for doppler backend)")
@click.option("--config", "doppler_config", help="Doppler config (for doppler backend)")
@click.option("--data-dir", help="Data directory (for local backend)")
def backend_set(
    backend_type: str,
    project: str | None,
    doppler_config: str | None,
    data_dir: str | None,
):
    """Set the active backend without migrating data.

    Use 'tokn backend migrate' to move data between backends.

    Examples:
        tokn backend set local
        tokn backend set doppler --project tokn --config dev
    """
    config = get_config()
    config["backend"] = backend_type

    if backend_type == "doppler":
        if project:
            config.setdefault("doppler", {})["project"] = project
        if doppler_config:
            config.setdefault("doppler", {})["config"] = doppler_config
    elif backend_type == "local":
        if data_dir:
            config.setdefault("local", {})["data_dir"] = data_dir

    save_config(config)

    stdout_console.print(f"[green]✓ Backend set to:[/green] {backend_type}")

    # Warn if no data in new backend
    try:
        backend_instance = get_backend()
        registry = backend_instance.load_registry()
        if not registry.tokens:
            console.print(
                f"[yellow]Note: No tokens found in {backend_type} backend.[/yellow]"
            )
            console.print(
                "[yellow]Use 'tokn backend migrate' to move data "
                "from another backend.[/yellow]"
            )
    except Exception as e:
        console.print(f"[yellow]Warning: Could not verify backend: {e}[/yellow]")


if __name__ == "__main__":
    cli()
