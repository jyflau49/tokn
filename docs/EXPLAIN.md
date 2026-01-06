# tokn - Design Decisions

*Modified: 2026-01-06 (v0.9.1)*

`tokn` is a CLI tool for simple API token management. This document explains key design details.

---

## Backend Storage

**Local (default):** Stores metadata in `~/.config/tokn/registry.json`. Works offline, no dependencies.

**Doppler (optional):** Stores metadata in `TOKN_METADATA` secret. Multi-device sync via cloud.

**Requirements:**
- Doppler backend and location require [Doppler CLI](https://docs.doppler.com/docs/install-cli) installed and authenticated
- Run `doppler login` after installation

**High Availability:**
- Doppler CLI automatically saves encrypted fallback snapshots at `$HOME/.doppler/fallback`
- Falls back to local snapshot after 50-60 second timeout if Doppler.com is unreachable
- Enables offline operation after initial sync

**Key points:**
- Token values never stored in metadata - only expiry dates and locations
- Local backend has no auto-sync (use Git or manual copy)
- Switch backends: `tokn backend set [local|doppler]`
- Migrate data: `tokn backend migrate --from X --to Y`

## Rotation Strategy

**Atomic batch rotation:** All locations backed up in memory before rotation. Any failure triggers full rollback.

**Provider types:**
- **Auto-rotation:** Cloudflare, Linode, Akamai (API-driven)
- **Manual rotation:** GitHub, Terraform, Postman (no rotation API available)

---

## Security

**File permissions:** All credential files created with `0600` (owner-only read/write).

**Backups:** Stored in memory only during rotation. Never written to disk.

**Token storage:** Token values never stored in metadata. Only expiry dates and location paths tracked.

---

## Provider-Specific Details

### GitHub
**Manual only.** GitHub deprecated `/authorizations` API. Fine-grained PATs require OAuth flow.

### Cloudflare
**Auto-rotation.** Uses Roll Token (regenerate) + Update Token (set expiry). Preserves all permissions.

### Linode
**Auto-rotation.** Creates new PAT, revokes old one. Standard create-and-delete pattern.

### Terraform
**Manual only.** No official API for account token rotation.

### Akamai
**Auto-rotation.** Create-and-overlap strategy:

1. Create new credential (`clientSecret` + `clientToken`)
2. Update old credential expiry to +7 days (service accounts only)
3. Update `.edgerc` section

**Credential types:**
- **SERVICE_ACCOUNT:** 7-day overlap period (expiry update supported)
- **USER_CLIENT (LUNA):** No overlap (API doesn't allow expiry updates)

**Note:** Uses official `edgegrid-python` library for HMAC-SHA-256 authentication.

### Postman (v0.9.0)
**Manual only.** Postman API keys cannot be programmatically rotated - no public API endpoint exists.

**Postman Environment location (v0.9.1):** Store credentials in Postman Environments for API testing workflows.
- Uses Postman API (`PUT /environments/{id}`) to update variables
- Requires `POSTMAN_API_KEY` environment variable (security: no API keys in metadata)
- Cross-compatible with all services (GitHub, Cloudflare, Linode, Terraform, Akamai, Postman)
- Similar to `.edgerc` sections - each environment stores multiple variables

---

## Service Naming (v0.7.0)

**Pattern:** `{vendor}[-{token-type-if-ambiguous}]`

| Service | Name |
|---------|------|
| GitHub PAT | `github` |
| Cloudflare Account Token | `cloudflare-account-token` |
| Linode PAT | `linode` |
| Terraform Account Token | `terraform` |
| Akamai API Client | `akamai` |
| Postman API Key | `postman` |

**Principles:**
- Vendor-first naming
- Token type only when ambiguous
- Storage location is `--location` concern, not service name
- Auth method is implementation detail

---

## Key Features

**90-day expiry:** All tokens expire 90 days after rotation (default).

**Multi-location updates:** Single rotation updates all tracked locations.

**Metadata tracking:** Expiry dates auto-updated after successful rotation.

**Update command:** Modify metadata without re-tracking (`tokn update`).

---

## UX Design

**Progress indicators:** Spinners for long operations (5-30s API calls). TTY-aware, auto-disabled in pipes.

**Output formats:** `--format [rich|simple|plain]` for interactive vs automation use.

**Command naming:** Follows kubectl convention (`list`, `describe`).

**Error handling:** Errors to stderr, success to stdout. Exit code 1 for failures.

---

## Architecture Patterns

- **Plugin architecture:** Providers (rotation logic) + Locations (storage handlers)
- **Backend abstraction:** Pluggable metadata storage (local/doppler)
- **Pydantic models:** Type-safe metadata with validation
- **Factory pattern:** Config-driven backend instantiation
- **Overlap strategy:** Safe rotation with grace period (Akamai service accounts)
