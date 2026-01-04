# tokn

CLI tool for simple API token rotation across multiple providers.

## Features

- **Automated rotation** for 3 providers (Cloudflare, Linode, Akamai)
- **Manual rotation** for 2 providers (GitHub, Terraform Account)
- **Pluggable backends** - Local (default) or Doppler for multi-device sync
- **Multi-location updates** (Doppler + local files)

## Installation

```bash
uv tool install .
```

For development:

```bash
uv sync
uv run tokn --help
```

## Quick Start

### 1. Track your first token (local backend - default)

```bash
tokn track linode-cli-pat \
  --service linode-cli \
  --rotation-type auto \
  --location "linode-cli:~/.config/linode-cli"
```

### 2. Check status

```bash
tokn list
```

### 3. Rotate tokens

```bash
# Rotate all auto-rotatable tokens
tokn rotate --all

# Rotate specific token
tokn rotate linode-cli-pat
```

## Supported Services

| Service | Provider | Auto-Rotate | Locations |
|---------|----------|-------------|-----------|
| GitHub PAT | `github` | ✗ (manual) | Doppler, `~/.git-credentials` |
| Cloudflare API Token | `cloudflare` | ✓ | Doppler |
| Linode CLI Token | `linode-cli` | ✓ | `~/.config/linode-cli` |
| Linode Doppler Token | `linode-doppler` | ✓ | Doppler |
| HCP Terraform Account | `terraform-account` | ✗ (manual) | `~/.terraform.d/credentials.tfrc.json` |
| Akamai EdgeGrid | `akamai-edgegrid` | ✓ | `~/.edgerc` |

**Notes:**
- Cloudflare tokens require `account_id` in location metadata
- All auto-rotated tokens expire 90 days after rotation
- Multiple `--location` flags supported for updating same token across locations

## Commands

### `tokn track`

Track a new token for rotation.

```bash
tokn track <name> \
  --service <provider> \
  --rotation-type [auto|manual] \
  --location "type:path:key=value" \
  --expiry-days 90 \
  --notes "Optional notes"
```

**Location formats:**
- Doppler: `doppler:SECRET_NAME:project=proj,config=cfg`
- Doppler (Cloudflare): `doppler:SECRET_NAME:project=proj,config=cfg,account_id=abc123`
- Git credentials: `git-credentials:~/.git-credentials:username=git`
- Linode CLI: `linode-cli:~/.config/linode-cli`
- Terraform: `terraform-credentials:~/.terraform.d/credentials.tfrc.json:hostname=app.terraform.io`
- Akamai EdgeGrid: `edgerc:~/.edgerc:section=default`

### `tokn list`

List all tracked tokens.

```bash
tokn list                      # All tokens (rich styled)
tokn list --expiring           # Only expiring/expired
tokn list --format simple      # Tabulate format (copy-friendly)
tokn list --format plain       # Plain text (automation-friendly)
```

### `tokn rotate`

Rotate tokens.

```bash
tokn rotate --all              # Rotate all auto tokens
tokn rotate <name>             # Rotate specific token
```

### `tokn sync`

Sync metadata from current backend.

```bash
tokn sync
```

### `tokn update`

Update a tracked token's metadata (expiry, locations, notes).

```bash
tokn update <name> --expiry-days 90           # Update expiry
tokn update <name> --add-location "doppler:NEW_SECRET:project=proj,config=cfg"
tokn update <name> --remove-location "doppler:OLD_SECRET"
tokn update <name> --notes "Updated notes"
```

### `tokn describe`

Show detailed information about a token.

```bash
tokn describe <name>                 # Rich styled output
tokn describe <name> --format plain  # Plain text (automation-friendly)
```

### `tokn remove`

Remove a tracked token.

```bash
tokn remove <name>
```

### `tokn backend`

Manage metadata storage backend.

```bash
tokn backend show                                     # Show current backend
tokn backend set local                                # Switch to local backend
tokn backend set doppler --project tokn --config dev  # Switch to Doppler backend
tokn backend migrate --from doppler --to local        # Migrate data between backends
```

**Backend types:**
- **local** (default): Solo developer, works offline, no external dependencies
- **doppler**: Multi-device sync, team collaboration via cloud

## Example Workflow

```bash
# Track all 5 tokens (one-time setup)
tokn track github-pat --service github --rotation-type manual \
  --location "doppler:GITHUB_TOKEN:project=my-infra,config=dev" \
  --location "git-credentials:~/.git-credentials:username=git"

tokn track cloudflare-token --service cloudflare --rotation-type auto \
  --location "doppler:CLOUDFLARE_API_TOKEN:project=magictracker,config=prod,account_id=abc123def456"

tokn track linode-cli --service linode-cli --rotation-type auto \
  --location "linode-cli:~/.config/linode-cli"

tokn track linode-doppler --service linode-doppler --rotation-type auto \
  --location "doppler:LINODE_TOKEN:project=magictracker,config=prod"

tokn track terraform-account --service terraform-account --rotation-type manual \
  --location "terraform-credentials:~/.terraform.d/credentials.tfrc.json"

# On second laptop (if using Doppler backend)
tokn backend set doppler --project tokn --config dev
tokn sync
tokn list
```

## Architecture

```
tokn/
├── core/
│   ├── backend/        # Pluggable metadata storage
│   │   ├── base.py     # MetadataBackend interface
│   │   ├── local.py    # Local file backend (default)
│   │   ├── doppler.py  # Doppler cloud backend
│   │   └── factory.py  # Backend factory + config
│   ├── token.py        # Token models
│   └── rotation.py     # Batch rotation orchestrator
├── providers/          # Service-specific rotation logic
│   ├── github.py
│   ├── cloudflare.py
│   ├── linode.py
│   ├── terraform.py
│   └── akamai.py
├── locations/          # Multi-location update handlers
│   ├── doppler.py
│   ├── local_files.py
│   └── edgerc.py
└── cli.py             # Click CLI interface
```

## Security

- **Metadata only** - Token values never stored, read from Doppler/files on-demand
- **Secure file permissions** - All credential files created with `0600` (owner-only)
- **In-memory backups** - Rollback uses memory, no plaintext written to disk
- **All-or-nothing rotation** - Automatic rollback if any location update fails
- **No token logging** - Token values never printed to console or logs

See `docs/EXPLAIN.md` for detailed security architecture.

## License

MIT
