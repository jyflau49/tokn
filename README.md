# tokn

CLI tool for automated API token rotation across multiple services.

## Features

- **Automated rotation** for 3 services (Cloudflare, Linode CLI, Linode Doppler)
- **Guided manual rotation** for 2 services (GitHub, Terraform Account)
- **Multi-location updates** (Doppler + local files)
- **Multi-laptop sync** via Doppler backend
- **Batch rotation** with atomic rollback
- **Token metadata updates** via `tokn update` command
- **Rich terminal UI** with status tracking

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

### 1. Setup Doppler

```bash
doppler login
doppler setup --project tokn --config dev
```

### 2. Track your first token

```bash
tokn track github-pat \
  --service github \
  --rotation-type manual \
  --location "doppler:GITHUB_TOKEN:project=my-infra,config=dev" \
  --location "git-credentials:~/.git-credentials:username=git"
```

### 3. Check status

```bash
tokn list
```

### 4. Rotate tokens

```bash
# Rotate all auto-rotatable tokens
tokn rotate --all

# Rotate specific token
tokn rotate github-pat
```

## Supported Services

| Service | Provider | Auto-Rotate | Locations |
|---------|----------|-------------|-----------|
| GitHub PAT | `github` | ✗ (manual) | Doppler, `~/.git-credentials` |
| Cloudflare API Token | `cloudflare` | ✓ | Doppler |
| Linode CLI Token | `linode-cli` | ✓ | `~/.config/linode-cli` |
| Linode Doppler Token | `linode-doppler` | ✓ | Doppler |
| HCP Terraform Account | `terraform-account` | ✗ (OAuth) | `~/.terraform.d/credentials.tfrc.json` |

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

Sync metadata from Doppler (for multi-laptop workflow).

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

# Monthly rotation (1st of month)
tokn rotate --all

# On second laptop
tokn sync
tokn status
```

## Architecture

```
tokn/
├── core/
│   ├── backend.py      # Doppler metadata storage
│   ├── token.py        # Token models
│   └── rotation.py     # Batch rotation orchestrator
├── providers/          # Service-specific rotation logic
│   ├── github.py
│   ├── cloudflare.py
│   ├── linode.py
│   └── terraform.py
├── locations/          # Multi-location update handlers
│   ├── doppler.py
│   └── local_files.py
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
