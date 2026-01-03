# tokn - Architectural Decisions

*Modified: 2026-01-03*

## Overview

`tokn` is a CLI tool for automated API token rotation. This document explains key architectural decisions, security considerations, and trade-offs.

---

## Core Architecture

### Doppler Backend Storage

**Decision:** Use Doppler CLI for metadata storage in a single `TOKN_METADATA` secret.

**Rationale:**
- Built-in multi-device sync via cloud backend
- Leverages existing Doppler authentication
- No custom backend needed

**Trade-off:** Requires internet connection, but gains zero-config sync.

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
- Users rely on `tokn status` to know when tokens need rotation

### Removed Features

**Dry-run:** Removed - showed minimal information. Use `tokn status` to see expiring tokens.

**Terraform Org Provider:** Removed - no official API support for Doppler-TFC integration.

---

## Design Patterns

- **Plugin Architecture:** Providers (rotation logic) + Locations (storage handlers)
- **Pydantic Models:** Type-safe metadata with automatic validation
- **Rich CLI:** Color-coded status, table displays, clear feedback

---

## Lessons Learned

- **Security First:** Always assume credentials will be compromised if readable by others
- **API Deprecation:** Better to be honest about manual rotation than use deprecated APIs
- **Simplicity Wins:** Doppler backend simpler than custom sync, in-memory backups simpler than file cleanup
