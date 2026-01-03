# tokn

CLI tool for automated monthly API token rotation across multiple services.

## Features

- **Automated rotation** for 3 services (Cloudflare, Linode×2, Terraform Org)
- **Guided manual rotation** for 3 services (GitHub, Terraform Account)
- **Multi-location updates** (Doppler + local files)
- **Multi-laptop sync** via Doppler backend
- **Batch rotation** with atomic rollback
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
tokn status
```

### 4. Rotate tokens

```bash
# Rotate all auto-rotatable tokens
tokn rotate --all

# Rotate specific token
tokn rotate github-pat

# Dry run
tokn rotate --all --dry-run
```

## Supported Services

| Service | Provider | Auto-Rotate | Locations |
|---------|----------|-------------|-----------|
| GitHub PAT | `github` | ✗ (manual) | Doppler, `~/.git-credentials` |
| Cloudflare API Token | `cloudflare` | ✓ | Doppler |
| Linode CLI Token | `linode-cli` | ✓ | Doppler, `~/.config/linode-cli` |
| Linode Doppler Token | `linode-doppler` | ✓ | Doppler |
| HCP Terraform Account | `terraform-account` | ✗ (OAuth) | `~/.terraform.d/credentials.tfrc.json` |
| HCP Terraform Org | `terraform-org` | ✓ | Doppler |

**Note:** GitHub PATs cannot be programmatically rotated without an OAuth App. The tool provides guided manual rotation instructions.

## Commands

### `tokn track`

Track a new token for rotation.

```bash
tokn track <name> \
  --service <provider> \
  --rotation-type [auto|manual] \
  --location "type:path:key=value" \
  --expiry-days 30 \
  --notes "Optional notes"
```

**Location formats:**
- Doppler: `doppler:SECRET_NAME:project=proj,config=cfg`
- Git credentials: `git-credentials:~/.git-credentials:username=git`
- Linode CLI: `linode-cli:~/.config/linode-cli`
- Terraform: `terraform-credentials:~/.terraform.d/credentials.tfrc.json:hostname=app.terraform.io`

### `tokn status`

Show status of all tracked tokens.

```bash
tokn status              # All tokens
tokn status --expiring   # Only expiring/expired
```

### `tokn rotate`

Rotate tokens.

```bash
tokn rotate --all              # Rotate all auto tokens
tokn rotate --all --dry-run    # Preview changes
tokn rotate <name>             # Rotate specific token
```

### `tokn sync`

Sync metadata from Doppler (for multi-laptop workflow).

```bash
tokn sync
```

### `tokn info`

Show detailed information about a token.

```bash
tokn info <name>
```

### `tokn remove`

Remove a tracked token.

```bash
tokn remove <name>
```

## Example Workflow

```bash
# Track all 6 tokens (one-time setup)
tokn track github-pat --service github --rotation-type manual \
  --location "doppler:GITHUB_TOKEN:project=my-infra,config=dev" \
  --location "git-credentials:~/.git-credentials:username=git"

tokn track cloudflare-token --service cloudflare --rotation-type auto \
  --location "doppler:CLOUDFLARE_API_TOKEN:project=magictracker,config=prod"

tokn track linode-cli --service linode-cli --rotation-type auto \
  --location "doppler:LINODE_CLI_TOKEN:project=my-infra,config=dev" \
  --location "linode-cli:~/.config/linode-cli"

tokn track linode-doppler --service linode-doppler --rotation-type auto \
  --location "doppler:LINODE_TOKEN:project=magictracker,config=prod"

tokn track terraform-account --service terraform-account --rotation-type manual \
  --location "terraform-credentials:~/.terraform.d/credentials.tfrc.json"

tokn track terraform-org --service terraform-org --rotation-type auto \
  --location "doppler:TF_CLOUD_TOKEN:project=personal,config=dev:org_name=magictracker-org"

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

- **No token storage** - Tokens read from Doppler/files on-demand
- **Metadata only** - Only expiry dates and rotation history stored
- **Secure file permissions** - All credential files created with `0600` (owner-only)
- **In-memory backups** - No plaintext tokens written to disk during rollback
- **Atomic operations** - Rollback on partial failures
- **No logging** - Tokens never printed to console or logs

See `docs/EXPLAIN.md` for detailed security architecture.

## License

MIT
