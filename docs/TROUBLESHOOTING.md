# Troubleshooting Guide

*Modified: 2026-01-03*

## Common Issues

### Doppler CLI Not Found

**Error:** `RuntimeError: Doppler CLI not found`

**Solution:**
1. Install: `brew install dopplerhq/cli/doppler` (macOS) or see [docs](https://docs.doppler.com/docs/install-cli)
2. Authenticate: `doppler login`
3. Setup: `doppler setup --project tokn --config dev`

### Location Format Error

**Error:** `Invalid location format: doppler-GITHUB_TOKEN`

**Solution:** Use format `type:path` or `type:path:key=val,key=val`

**Examples:**
- `doppler:GITHUB_TOKEN:project=myproj,config=dev`
- `git-credentials:~/.git-credentials:username=git`
- `linode-cli:~/.config/linode-cli`
- `terraform-credentials:~/.terraform.d/credentials.tfrc.json:hostname=app.terraform.io`

### Token Already Exists

**Solution:**
1. Check: `tokn info <name>`
2. Remove if needed: `tokn remove <name>`
3. Track again

### Doppler CLI Error During Rotation

**Common Causes:**
- Not authenticated: Run `doppler login`
- Wrong project/config: Verify with `doppler secrets --project tokn --config dev`
- Missing secret or insufficient permissions

**Solution:**
1. `doppler whoami` - verify authentication
2. `doppler projects` - check project exists
3. `doppler secrets get SECRET_NAME --project PROJECT --config CONFIG` - verify secret
4. Check permissions in Doppler dashboard

### API Error During Rotation

**Common Causes:**
- Invalid/expired token
- Insufficient permissions
- Rate limiting
- Network issues

**Solution:**
1. Verify token in service dashboard
2. Check token permissions/scopes
3. Wait and retry if rate limited
4. Check network connectivity

### GitHub PAT Auto-Rotation Fails

**Error:** `Provider does not support auto-rotation`

**Explanation:** GitHub PATs cannot be programmatically rotated (API limitation).

**Solution:**
1. Use `--rotation-type manual` when tracking
2. Follow manual rotation instructions: `tokn rotate <name>`

### Cloudflare Token Has No Policies

**Error:** `Current token has no policies - cannot replicate`

**Solution:** Create a new token with proper policies in Cloudflare dashboard, then track it.

---

## Debugging

### Check Token Metadata

```bash
tokn info <token-name>
```

Shows provider, rotation type, locations, expiry, last rotation, notes.

### Verify Doppler Metadata

```bash
doppler secrets get TOKN_METADATA --project tokn --config dev --plain | jq
```

### Common Workflow Issues

**Rotation succeeds but token doesn't work:**
1. Verify new token written to all locations: `tokn info <name>`
2. Check file permissions: `ls -la ~/.git-credentials` (should be `-rw-------`)
3. Test token manually with service API
4. Check if service requires token format (e.g., `Bearer` prefix)

**Sync doesn't update local state:**
Sync only reads from Doppler. Use `tokn track` to update metadata.

---

## Security Response

If you suspect token compromise:

1. **Immediately revoke** token in service dashboard
2. **Remove:** `tokn remove <token-name>`
3. **Generate new token** manually
4. **Track new token:** `tokn track ...`
5. **Verify file permissions:** All credential files should be `0600`
6. **Check Doppler access logs**

---

## Known Limitations

- **No offline mode:** Requires Doppler CLI and internet
- **No partial rotation:** All-or-nothing for batch operations
- **No rotation history:** Only tracks last rotation time
- **GitHub PAT:** Manual rotation only (API limitation)
- **Terraform Account:** Manual rotation only (OAuth flow required)
