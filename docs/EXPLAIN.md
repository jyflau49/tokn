# tokn - Architectural Decisions and Design Rationale

*Modified: 2026-01-03*

## Overview

`tokn` is a CLI tool for automated monthly API token rotation across multiple services. This document explains the major architectural decisions, security considerations, and trade-offs made during development.

---

## Major Architectural Decisions

### 1. Doppler as Backend Storage

**Date:** 2026-01-03

**Context:** Need to sync token metadata across multiple laptops without storing actual tokens.

**Decision:** Use Doppler CLI for metadata storage in a single `TOKN_METADATA` secret.

**Rationale:**
- User already uses Doppler for secrets management
- Built-in multi-device sync via cloud backend
- No need to implement custom sync mechanism
- Leverages existing Doppler authentication
- Metadata stored as JSON for flexibility

**Trade-offs:**
- **Sacrificed:** Offline capability - requires Doppler CLI and internet connection
- **Gained:** Zero-config sync, secure storage, no custom backend needed

**Implementation:**
```python
class DopplerBackend:
    METADATA_SECRET = "TOKN_METADATA"  # Single JSON blob
    
    def load_registry(self) -> TokenRegistry:
        data = self._run_doppler(["get", self.METADATA_SECRET])
        return TokenRegistry.model_validate(json.loads(data))
```

---

### 2. In-Memory Backups (No Disk Files)

**Date:** 2026-01-03

**Context:** Original design created `.tokn-backup` files containing plaintext tokens on disk.

**Decision:** Store backup content in memory, never write backup files to disk.

**Rationale:**
- **Security:** Backup files contained plaintext tokens - unacceptable risk
- Rollback still needed for atomic operations
- Memory is sufficient for credential file sizes (< 1KB typically)
- No cleanup required - backups disappear when process exits

**Trade-offs:**
- **Sacrificed:** Ability to inspect backups after process crash
- **Gained:** No plaintext tokens written to disk, simpler cleanup

**Implementation:**
```python
def backup_token(self, path: str, **kwargs) -> str | None:
    """Return current file content as backup (in-memory)."""
    return file_path.read_text()  # Content, not file path

def rollback_token(self, path: str, backup: str, **kwargs) -> bool:
    """Restore from in-memory backup content."""
    file_path.write_text(backup)  # Write content directly
```

---

### 3. Secure File Permissions (0600)

**Date:** 2026-01-03

**Context:** Credential files created with default permissions (often 0644 - world-readable).

**Decision:** Enforce `0600` (owner read/write only) on all credential files.

**Rationale:**
- Prevents other users on system from reading tokens
- Standard security practice for credential files
- Git, SSH, and other tools use same approach
- Minimal performance impact

**Trade-offs:**
- **Sacrificed:** None - this is pure security gain
- **Gained:** Protection against local privilege escalation

**Implementation:**
```python
SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0600

def write_token(self, path: str, token: str, **kwargs) -> bool:
    file_path.write_text(token_content)
    os.chmod(file_path, SECURE_FILE_MODE)  # Always enforce
```

---

### 4. GitHub PAT Manual Rotation

**Date:** 2026-01-03

**Context:** GitHub deprecated `/authorizations` API endpoint. Fine-grained PATs cannot be programmatically rotated without OAuth App.

**Decision:** Mark GitHub provider as manual-only with guided instructions.

**Rationale:**
- GitHub's OAuth flow requires user interaction (by design)
- Deprecated API would break in future
- Manual rotation is still better than no tracking
- Provides step-by-step instructions to reduce friction

**Trade-offs:**
- **Sacrificed:** Full automation for GitHub tokens
- **Gained:** Future-proof implementation, accurate user expectations

**Alternative Considered:** GitHub App with installation tokens (short-lived, auto-rotate) - rejected as too complex for personal use case.

---

### 5. Provider Plugin Architecture

**Date:** 2026-01-03

**Context:** Different services have different rotation APIs and capabilities.

**Decision:** Abstract provider interface with `supports_auto_rotation` flag.

**Rationale:**
- Clean separation between auto-rotatable and manual services
- Easy to add new providers
- Consistent error handling across providers
- Manual providers can still provide guided instructions

**Trade-offs:**
- **Sacrificed:** Simplicity of single rotation path
- **Gained:** Flexibility, extensibility, accurate capability signaling

**Implementation:**
```python
class TokenProvider(ABC):
    @property
    @abstractmethod
    def supports_auto_rotation(self) -> bool:
        pass
    
    def get_manual_instructions(self) -> str:
        """Override for manual providers"""
```

---

### 6. Atomic Batch Rotation with Rollback

**Date:** 2026-01-03

**Context:** Rotating multiple tokens can fail partway through, leaving inconsistent state.

**Decision:** Backup all locations before rotation, rollback all on any failure.

**Rationale:**
- Prevents partial rotation (some locations updated, others not)
- User can retry without manual cleanup
- All-or-nothing semantics are easier to reason about

**Trade-offs:**
- **Sacrificed:** Ability to partially succeed (e.g., 5/6 tokens rotated)
- **Gained:** Consistency, predictability, easier error recovery

**Implementation:**
```python
def rotate_token(self, token_metadata: TokenMetadata) -> tuple[bool, str, list[str]]:
    backups = {}
    try:
        # Backup all locations first
        for location in token_metadata.locations:
            backups[location] = self._backup_location(location)
        
        # Rotate and update
        result = provider.rotate(current_token)
        for location in token_metadata.locations:
            self._update_location(location, result.new_token)
        
        return True, "Success", updated_locations
    except Exception:
        self._rollback_all(backups)  # Restore all on any error
        return False, "Error", []
```

---

### 7. Cloudflare Policy Preservation

**Date:** 2026-01-03

**Context:** Original implementation created new tokens without copying existing policies.

**Decision:** Fetch current token details, copy policies to new token.

**Rationale:**
- New token must have same permissions as old token
- Cloudflare API requires explicit policy specification
- Prevents accidental permission loss

**Trade-offs:**
- **Sacrificed:** One extra API call per rotation
- **Gained:** Correct permissions, no manual policy reconfiguration

---

## Security Considerations

### Token Storage
- **Never stored:** Actual token values are never stored in metadata
- **Stored:** Only expiry dates, last rotation timestamps, location paths
- **Read:** Tokens read from Doppler/files only when needed for rotation

### File Permissions
- All credential files created with `0600` (owner-only)
- Prevents other users on system from reading tokens
- Applied consistently across all location handlers

### Backup Strategy
- In-memory only - no plaintext tokens written to disk
- Backups cleared when process exits
- Rollback still available for atomic operations

### Error Handling
- Generic exception catching prevents token leakage in error messages
- Failed rotations trigger automatic rollback
- No tokens logged or printed to console

---

## Design Patterns

### 1. Plugin Architecture
- Providers: Service-specific rotation logic
- Locations: Storage-specific read/write handlers
- Easy to extend with new services or storage types

### 2. Pydantic Models
- Type-safe token metadata
- Automatic validation
- JSON serialization for Doppler storage

### 3. CLI with Rich
- Color-coded status indicators
- Table-based status display
- Clear success/failure feedback

---

## Future Enhancements

### Considered but Deferred
1. **Local caching** - Metadata cached locally for offline status checks
   - Deferred: Adds complexity, Doppler CLI is fast enough
   
2. **Rotation scheduling** - Cron-like automatic rotation
   - Deferred: User prefers manual trigger on 1st of month
   
3. **Notification system** - Email/Slack alerts for expiring tokens
   - Deferred: Rich CLI output is sufficient for now

### Potential Additions
1. **GitHub App support** - True auto-rotation via GitHub App
2. **More providers** - AWS IAM, Azure AD, etc.
3. **Rotation history** - Track past rotations with timestamps
4. **Dry-run improvements** - Show exactly what would change

---

## Lessons Learned

### Security First
- Initial implementation had backup files on disk - caught in review
- File permissions were missing - added during security audit
- Always assume credentials will be compromised if readable by others

### API Deprecation
- GitHub's `/authorizations` endpoint taught us to check API status
- Better to be honest about manual rotation than use deprecated APIs
- Document alternatives (OAuth App, GitHub App) for future

### Simplicity Wins
- Doppler backend simpler than custom sync mechanism
- In-memory backups simpler than file cleanup
- Provider abstraction cleaner than if/else chains

### Testing Matters
- Security-focused tests caught permission issues
- Provider tests documented expected behavior
- Location handler tests verified rollback logic

---

## References

- [Doppler CLI Documentation](https://docs.doppler.com/docs/cli)
- [GitHub Fine-grained PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Cloudflare API Tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Linode API](https://www.linode.com/docs/api/)
- [Terraform Cloud API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs)
