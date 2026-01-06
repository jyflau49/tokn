# tokn

CLI tool for simple API token lifecycle management across multiple providers.

## Features

- **Automated rotation** for 3 providers (Akamai, Cloudflare, Linode)
- **Manual rotation** for 3 providers (GitHub, Postman, Terraform)
- **Pluggable backends** - Local (default) or Doppler for multi-device sync
- **Multi-location updates** (local files + Doppler)

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
tokn track linode-local \
  --service linode \
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
tokn rotate linode-local
```

## Supported Services

| Service | Provider | Auto-Rotate | Locations |
|---------|----------|-------------|-----------|
| GitHub PAT | `github` | ✗ (manual) | Doppler, `~/.git-credentials`, Postman Environment |
| Cloudflare Account Token | `cloudflare-account-token` | ✓ | Doppler, Postman Environment |
| Linode PAT | `linode` | ✓ | `~/.config/linode-cli`, Doppler, Postman Environment |
| Terraform Account Token | `terraform` | ✗ (manual) | `~/.terraform.d/credentials.tfrc.json`, Postman Environment |
| Akamai API Client | `akamai` | ✓ | `~/.edgerc`, Doppler, Postman Environment |
| Postman API Key | `postman` | ✗ (manual) | Doppler, Postman Environment |
| Other/Custom | `other` | ✗ (manual) | Any (optional) |

**Notes:**
- **Other/Custom service**: For unsupported providers. Locations are optional. Use `--notes` for custom rotation instructions.
- **Postman Environment** location is cross-compatible with all services
- **Doppler** locations require [Doppler CLI](https://docs.doppler.com/docs/install-cli) installed and authenticated
- **Doppler backend limit**: 50KB per secret (~79 tokens with typical complexity)
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

**Location format examples:**
- Doppler: `doppler:SECRET_NAME:project=proj,config=cfg`
- Doppler (Linode): `doppler:TF_VAR_SECRET_NAME:project=proj,config=cfg`
- Doppler (Cloudflare): `doppler:SECRET_NAME:project=proj,config=cfg,account_id=abc123`
- Git credentials (local): `git-credentials:~/.git-credentials:username=git`
- Linode CLI (local): `linode-cli:~/.config/linode-cli`
- Terraform (local): `terraform-credentials:~/.terraform.d/credentials.tfrc.json:hostname=app.terraform.io`
- Akamai EdgeGrid (local): `edgerc:~/.edgerc:section=default`
- Postman Environment: `postman-env:VAR_NAME:environment_id=env-uid` (requires `POSTMAN_API_KEY` env var)

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
tokn update <name> --expiry-days 90
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
- **doppler**: Multi-device sync, team collaboration via doppler

## Example Workflow

```bash
# Track 5 tokens (one-time setup)
tokn track github-pat --service github --rotation-type manual \
  --location "doppler:GITHUB_TOKEN:project=my-infra,config=dev" \
  --location "git-credentials:~/.git-credentials:username=git"

tokn track cloudflare-token --service cloudflare-account-token --rotation-type auto \
  --location "doppler:CLOUDFLARE_API_TOKEN:project=magictracker,config=prod,account_id=abc123def456"

tokn track linode-local --service linode --rotation-type auto \
  --location "linode-cli:~/.config/linode-cli"

tokn track linode-cloud --service linode --rotation-type auto \
  --location "doppler:LINODE_TOKEN:project=magictracker,config=prod"

tokn track terraform-token --service terraform --rotation-type manual \
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
│   ├── akamai.py
│   └── postman.py
├── locations/          # Multi-location update handlers
│   ├── doppler.py
│   ├── local_files.py
│   ├── edgerc.py
│   └── postman_env.py
└── cli.py             # Click CLI interface
```

## Security

- **Metadata only** - Token values never stored, read from Doppler/files on-demand
- **Secure file permissions** - All credential files created with `0600` (owner-only)
- **In-memory backups** - Rollback uses memory, no plaintext written to disk
- **All-or-nothing rotation** - Automatic rollback if any location update fails
- **No token logging** - Token values never printed to console or logs

See `docs/EXPLAIN.md` for more architecture details.

## License

MIT
