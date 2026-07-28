# SecretRef Rules

SecretRef entries identify where a secret is managed without storing the secret value.

## Allowed Fields

- `name` - stable reference name used by manifests.
- `provider` - secret manager or credential source, such as `macos-keychain`, `github-actions`, or `supabase-vault`.
- `scope` - environment or service boundary.
- `owner` - responsible team or account.
- `lookup` - non-secret lookup path, item label, or vault key name.
- `rotation` - expected rotation cadence or review interval.

## Forbidden Fields

- Raw token, password, cookie, private key, refresh token, or API key values.
- Base64-encoded secret values.
- Full `.env` file contents.
- Screenshots or command output containing credentials.

## Example

```yaml
secretRefs:
  - name: alert-hub.webhook
    provider: macos-keychain
    scope: local-ops
    owner: ops
    lookup: chumji-ops/alert-hub/webhook
    rotation: review-quarterly
```

## Alert Hub Shadow References

These entries are names and lookup metadata only for the inactive shadow import in `services/alert-hub`.

```yaml
secretRefs:
  - name: alert-hub.telegram-token
    provider: local-file
    scope: earthquake-alert-production
    owner: ops
    lookup: /Users/ops/.config/earthquake-alert/telegram-token
    rotation: approval-required
  - name: alert-hub.telegram-chat-id
    provider: deployment-config
    scope: earthquake-alert-production
    owner: ops
    lookup: /Users/ops/.config/earthquake-alert/config.json
    rotation: approval-required
  - name: alert-hub.launchdaemon-config
    provider: macos-launchd
    scope: earthquake-alert-production
    owner: ops
    lookup: com.chumji.earthquake-alert
    rotation: approval-required
```
