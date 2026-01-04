# tokn - Design Decisions

*Modified: 2026-01-05 (v0.7.1)*

`tokn` is a CLI tool for automated API token rotation. This document explains key design decisions and trade-offs.

---

## Backend Storage

**Local (default):** Stores metadata in `~/.config/tokn/registry.json`. Works offline, no dependencies.

**Doppler (optional):** Stores metadata in `TOKN_METADATA` secret. Multi-device sync via cloud.

**Key points:**
- Token values never stored in metadata - only expiry dates and locations
- Local backend has no auto-sync (use Git or manual copy)
- Switch backends: `tokn backend set [local|doppler]`
- Migrate data: `tokn backend migrate --from X --to Y`

## Rotation Strategy

**Atomic batch rotation:** All locations backed up in memory before rotation. Any failure triggers full rollback.

**Provider types:**
- **Auto-rotation:** Cloudflare, Linode, Akamai (API-driven)
- **Manual rotation:** GitHub, Terraform (deprecated APIs or OAuth required)

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
- **Service accounts:** 7-day overlap period (expiry update supported)
- **Open clients (LUNA users):** No overlap (API doesn't allow expiry updates)

**Note:** Uses official `edgegrid-python` library for HMAC-SHA-256 authentication.

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

**Principles:**
- Vendor-first naming
- Token type only when ambiguous (e.g., Cloudflare has User Token vs Account Token)
- Storage location is `--location` concern, not service name
- Auth method is implementation detail

---

## Key Features

**90-day expiry:** All tokens expire 90 days after rotation (default, configurable).

**Multi-location updates:** Single rotation updates all tracked locations (Doppler + local files).

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
