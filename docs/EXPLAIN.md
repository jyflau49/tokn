# tokn - Architectural Decisions

*Modified: 2026-01-04 (v0.6.1)*

## Overview

`tokn` is a CLI tool for automated API token rotation. This document explains key architectural decisions, security considerations, and trade-offs.

---

## Core Architecture

### Pluggable Backend Storage (v0.5.0)

**Decision:** Abstract backend interface with local as default, Doppler as optional.

**Context:** Originally tokn required Doppler for all operations. Users needed Doppler CLI installed and internet connection even for solo development.

**Implementation:**
- `MetadataBackend` abstract base class in `core/backend/base.py`
- `LocalBackend`: Stores registry as JSON in `~/.config/tokn/registry.json`
- `DopplerBackend`: Stores registry in Doppler secret `TOKN_METADATA`
- Factory pattern in `core/backend/factory.py` with config file support
- Config stored in `~/.config/tokn/config.toml`

**Rationale:**
- **Local default:** Works offline, no external dependencies, ideal for solo developers
- **Doppler optional:** Multi-device sync, team collaboration via cloud
- **Terraform-inspired:** Follows proven backend pattern from Terraform
- **Explicit migration:** `tokn backend migrate` requires user intent

**Trade-offs:**
- Local backend has no automatic sync (user must manually copy or use Git)
- More code to maintain (backend abstraction layer)
- Config file adds complexity

**Migration:**
```bash
# Migrate from Doppler to local
tokn backend migrate --from doppler --to local

# Migrate from local to Doppler
tokn backend migrate --from local --to doppler
```

### Provider Plugin Architecture

**Decision:** Abstract provider interface with `supports_auto_rotation` flag.

**Rationale:**
- Clean separation between auto-rotatable and manual services
- Easy to add new providers
- Manual providers provide guided instructions

### Atomic Batch Rotation

**Decision:** Backup all locations before rotation, rollback all on any failure.

**Rationale:**
- Prevents partial rotation (some locations updated, others not)
- All-or-nothing semantics are easier to reason about
- User can retry without manual cleanup

---

## Security Decisions

### In-Memory Backups Only

**Decision:** Store backup content in memory, never write backup files to disk.

**Rationale:**
- Original design created `.tokn-backup` files with plaintext tokens - unacceptable risk
- Memory sufficient for credential file sizes (< 1KB)
- No cleanup required - backups disappear when process exits

### Secure File Permissions (0600)

**Decision:** Enforce `0600` (owner read/write only) on all credential files.

**Rationale:**
- Prevents other users on system from reading tokens
- Standard practice for credential files (SSH, Git, etc.)

### Token Storage

- **Never stored:** Actual token values
- **Stored:** Only expiry dates, last rotation timestamps, location paths
- **Read:** Tokens read from Doppler/files only when needed

---

## Provider-Specific Decisions

### GitHub PAT Manual Rotation

**Decision:** Mark GitHub provider as manual-only with guided instructions.

**Rationale:**
- GitHub deprecated `/authorizations` API endpoint
- Fine-grained PATs require OAuth flow (user interaction by design)
- Manual rotation with tracking better than no tracking

**Alternative Considered:** GitHub App with installation tokens - rejected as too complex for personal use.

### Cloudflare Token Rotation

**Decision:** Use Roll Token endpoint (regenerate value) + Update Token endpoint (set expiry).

**Rationale:**
- Roll endpoint preserves all permissions (including token management)
- Initial create/delete approach created sub-tokens that lost permissions
- Supports continuous rotation without manual intervention

### Standardized 90-Day Expiry

**Decision:** All tokens expire 90 days after rotation.

**Rationale:**
- Consistent behavior across all providers
- Balances security (regular rotation) with convenience (quarterly)
- Aligns with common enterprise security policies

### Akamai EdgeGrid Rotation (v0.6.0, v0.6.1)

**Decision:** Use create-and-overlap strategy with credential type detection.

**Context:** Akamai API credentials use EdgeGrid authentication (HMAC-SHA-256). Each API client can have multiple credentials. Two credential types exist:
- **Service accounts:** Support expiry updates via API
- **Open clients (LUNA users):** Cannot update expiry via API

**Implementation:**
- `AkamaiEdgeGridProvider` in `providers/akamai.py`
- `EdgercHandler` in `locations/edgerc.py` for `.edgerc` file management
- Uses `requests` + `edgegrid-python` (official Akamai library)

**Rotation Flow:**
1. List credentials, find current by `clientToken`
2. Create new credential (new `clientSecret` + `clientToken`)
3. Attempt to update old credential expiry to +7 days
   - **Service accounts:** Expiry updated, 7-day overlap period
   - **Open clients (LUNA):** Update fails, immediately delete old credential
4. Update `.edgerc` section with new credentials

**Rationale:**
- **7-day overlap (service accounts):** Safe period to verify new credential works
- **Immediate delete (open clients):** Cannot update expiry, safe to remove immediately
- **Credential type detection:** Gracefully handle API limitation via error response
- **Section isolation:** Only updates specified `.edgerc` section, preserves others
- **Official library:** EdgeGrid auth is complex (HMAC signing) - use battle-tested code

**Trade-offs:**
- Uses `requests` library (Akamai only) while rest of tokn uses `httpx`
- Different behavior for service accounts vs open clients
- Relies on error detection for credential type (no explicit type field in API)

**Usage:**
```bash
tokn track akamai-default \
  --service akamai-edgegrid \
  --rotation-type auto \
  --location "edgerc:~/.edgerc:section=default"

tokn rotate akamai-default
```

---

## Feature Decisions

### Token Update Command

**Decision:** Add `tokn update` command for modifying tracked token metadata.

**Rationale:**
- Allows fixing location typos without re-tracking
- Enables manual expiry updates after manual rotation
- Supports adding/removing locations incrementally

### Auto-Update Expiry After Rotation

**Decision:** Add `expires_at` field to `RotationResult` and update metadata after successful rotation.

**Rationale:**
- Accurate expiry tracking is critical for token lifecycle management
- Users rely on `tokn list` to know when tokens need rotation

### Removed Features

**Dry-run:** Removed - showed minimal information. Use `tokn list` to see expiring tokens.

**Terraform Org Provider:** Removed - no official API support for Doppler-TFC integration.

---

## UX Decisions (v0.4.0)

### Progress Indicators

**Decision:** Add spinner progress indicators to all long-running operations.

**Rationale:**
- API calls can take 5-30 seconds - users need feedback
- TTY-aware: auto-disabled in pipes/CI environments
- Transient mode: disappears after completion

**Implementation:** `tokn/utils/progress.py` using rich Progress with SpinnerColumn.

### Output Format Options

**Decision:** Add `--format` option to `list` and `describe` commands.

**Options:**
- `rich` (default): Styled tables with colors and emojis
- `simple`: Tabulate with minimal borders (copy-friendly)
- `plain`: No borders (automation-friendly)

**Rationale:**
- Rich output for interactive use (beautiful UI)
- Plain/simple for scripting and CI/CD pipelines
- Follows other tools' patterns for consistency

### Command Naming (status→list, info→describe)

**Decision:** Rename `tokn status` to `tokn list` and `tokn info` to `tokn describe`.

**Rationale:**
- Aligns with kubectl convention (`get`/`describe`)
- Aligns with other tools' conventions for consistency
- "list" implies multiple items, "describe" implies single item details
- More action-oriented and semantically clear

### Stderr for Errors

**Decision:** Write error messages to stderr, success messages to stdout.

**Rationale:**
- Standard Unix convention
- Allows piping stdout without error noise
- Exit code 1 for errors enables scripting

---

## Design Patterns

- **Plugin Architecture:** Providers (rotation logic) + Locations (storage handlers)
- **Backend Abstraction:** Pluggable metadata storage (local/doppler)
- **Pydantic Models:** Type-safe metadata with automatic validation
- **Rich CLI:** Color-coded status, table displays, progress spinners
- **Dual Console:** stderr for errors, stdout for success output
- **Factory Pattern:** Backend instantiation via config-driven factory
- **Overlap Strategy:** For Akamai, update old credential expiry instead of immediate delete

---

## Lessons Learned

- **Security First:** Always assume credentials will be compromised if readable by others
- **API Deprecation:** Better to be honest about manual rotation than use deprecated APIs
- **Local Default:** External dependencies should be optional, not required
- **Terraform Pattern:** Backend abstraction is a proven pattern worth adopting
- **Use Official Libraries:** For complex auth (EdgeGrid), use official libraries over reimplementation
- **Overlap Strategy:** Safe credential rotation requires overlap period, not immediate revocation
