# Troubleshooting Guide

*Modified: 2026-01-03*

## Common Issues

### Doppler CLI Not Found

**Error:**
```
RuntimeError: Doppler CLI not found. Please install it:
  macOS: brew install dopplerhq/cli/doppler
  Linux: https://docs.doppler.com/docs/install-cli
Then run: doppler login
```

**Solution:**
1. Install Doppler CLI:
   - macOS: `brew install dopplerhq/cli/doppler`
   - Linux: See [Doppler CLI Installation](https://docs.doppler.com/docs/install-cli)
2. Authenticate: `doppler login`
3. Setup project: `doppler setup --project tokn --config dev`

---

### Invalid Service Provider

**Error:**
```
Error: Invalid value for '--service': 'invalid-service' is not one of 'github', 'cloudflare', 'linode-cli', 'linode-doppler', 'terraform-account', 'terraform-org'.
```

**Solution:**
Use one of the supported service providers. See `tokn track --help` for the full list.

---

### Location Format Error

**Error:**
```
Invalid location format: doppler-GITHUB_TOKEN. Use 'type:path'
```

**Solution:**
Location format must be `type:path` or `type:path:key=val,key=val`.

**Examples:**
- `doppler:GITHUB_TOKEN:project=myproj,config=dev`
- `git-credentials:~/.git-credentials:username=git`
- `linode-cli:~/.config/linode-cli`
- `terraform-credentials:~/.terraform.d/credentials.tfrc.json:hostname=app.terraform.io`

---

### Token Already Exists

**Error:**
```
Token 'github-pat' already exists
```

**Solution:**
1. Check existing token: `tokn info github-pat`
2. Remove if needed: `tokn remove github-pat`
3. Track again with new configuration

---

### Doppler CLI Error During Rotation

**Error:**
```
Doppler CLI error: ...
```

**Common Causes:**
1. **Not authenticated:** Run `doppler login`
2. **Wrong project/config:** Verify with `doppler secrets --project tokn --config dev`
3. **Missing secret:** The token doesn't exist in Doppler at the specified location
4. **Permission denied:** Your Doppler token doesn't have write access

**Solution:**
1. Verify authentication: `doppler whoami`
2. Check project exists: `doppler projects`
3. Verify secret exists: `doppler secrets get SECRET_NAME --project PROJECT --config CONFIG`
4. Check permissions in Doppler dashboard

---

### API Error During Rotation

**Error:**
```
API error during rotation: ...
```

**Common Causes:**
1. **Invalid token:** Current token is expired or revoked
2. **Insufficient permissions:** Token doesn't have permission to create new tokens
3. **Rate limiting:** Too many API requests
4. **Network issues:** Cannot reach API endpoint

**Solution:**
1. Verify current token is valid (check in service dashboard)
2. Check token permissions/scopes
3. Wait and retry if rate limited
4. Check network connectivity

---

### File Not Found Error

**Error:**
```
File not found: ...
```

**Solution:**
1. Verify the file path is correct
2. Check file exists: `ls -la ~/.config/linode-cli`
3. Create parent directories if needed
4. Verify you have read/write permissions

---

### GitHub PAT Auto-Rotation Fails

**Error:**
```
Provider does not support auto-rotation
```

**Explanation:**
GitHub PATs cannot be programmatically rotated without an OAuth App. This is a GitHub API limitation.

**Solution:**
1. Use `--rotation-type manual` when tracking GitHub tokens
2. Follow manual rotation instructions: `tokn rotate github-pat`
3. Consider using GitHub App installation tokens for true auto-rotation

---

### Cloudflare Token Has No Policies

**Error:**
```
Current token has no policies - cannot replicate
```

**Solution:**
The current Cloudflare token has no permissions assigned. Create a new token with proper policies in the Cloudflare dashboard, then track it with tokn.

---

### Terraform Org Token Missing org_name

**Error:**
```
org_name required for Terraform Org token rotation
```

**Solution:**
Include `org_name` in location metadata:
```bash
tokn track terraform-org \
  --service terraform-org \
  --rotation-type auto \
  --location "doppler:TF_TOKEN:project=proj,config=dev:org_name=my-org"
```

---

## Debugging Tips

### Enable Verbose Output

Currently tokn doesn't have a verbose flag, but you can check:
1. Doppler CLI directly: `doppler secrets --project tokn --config dev`
2. Token status: `tokn status`
3. Token details: `tokn info <token-name>`

### Check Token Metadata

```bash
tokn info <token-name>
```

Shows:
- Service provider
- Rotation type (auto/manual)
- All locations
- Expiry date
- Last rotation time
- Notes

### Verify Doppler Metadata

```bash
doppler secrets get TOKN_METADATA --project tokn --config dev --plain | jq
```

Shows the raw JSON metadata stored in Doppler.

### Test Rotation with Dry Run

```bash
tokn rotate --all --dry-run
```

Shows what would be rotated without actually doing it.

---

## Getting Help

### Check Logs

Tokn doesn't write logs by default. Errors are printed to stderr.

### Verify Installation

```bash
tokn --version
doppler --version
```

### Check Configuration

```bash
# Verify Doppler setup
doppler whoami
doppler projects

# Check tracked tokens
tokn status
```

### Common Workflow Issues

**Problem:** Rotation succeeds but token doesn't work

**Checklist:**
1. Verify new token was written to all locations: `tokn info <name>`
2. Check file permissions: `ls -la ~/.git-credentials` (should be `-rw-------`)
3. Test token manually with the service API
4. Check if service requires token format (e.g., `Bearer` prefix)

**Problem:** Sync doesn't update local state

**Solution:**
Sync only reads from Doppler. If you made changes locally, they won't be synced. Use `tokn track` to update metadata.

---

## Security Checklist

If you suspect token compromise:

1. **Immediately revoke** the compromised token in the service dashboard
2. **Remove from tokn:** `tokn remove <token-name>`
3. **Generate new token** manually
4. **Track new token:** `tokn track ...`
5. **Verify file permissions:** All credential files should be `0600` (owner read/write only)
6. **Check Doppler access logs** for unauthorized access

---

## Performance Issues

### Rotation Takes Too Long

**Normal duration:** 5-30 seconds per token (depends on API response time)

**If slower:**
1. Check network connectivity
2. Verify API endpoints are reachable
3. Check for rate limiting (wait and retry)

### Sync is Slow

**Normal duration:** 1-3 seconds

**If slower:**
1. Check Doppler CLI performance: `time doppler secrets get TOKN_METADATA`
2. Verify network connectivity
3. Check Doppler service status

---

## Known Limitations

1. **No offline mode:** Requires Doppler CLI and internet connection
2. **No partial rotation:** All-or-nothing for batch operations
3. **No rotation history:** Only tracks last rotation time
4. **GitHub PAT:** Manual rotation only (API limitation)
5. **Terraform Account:** Manual rotation only (OAuth flow required)

---

## Report Issues

For bugs or feature requests, please open an issue on GitHub with:
- tokn version (`tokn --version`)
- Operating system
- Error message (sanitize any sensitive data)
- Steps to reproduce
