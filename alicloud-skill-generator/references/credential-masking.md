# Credential Security & Masking (Mandatory)

## Core Rule

**NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs.

**Masking format:** Show only the first 4 characters followed by `****` (e.g., `abcd****`). This applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.

## Masking Rules by Execution Path

| Path | Safe Pattern | Unsafe Pattern |
|------|-------------|----------------|
| Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` | Raw credential value in output |
| Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
| Log files | `[INFO] Credentials: Secret=abcd****` | `[INFO] AK Secret: LTAI5t...` |
| Verification | `test -n "$var" && echo "Secret is set"` (existence check only) | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
| Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |

**Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

## Key Principles

- `{{env.*}}` placeholders MUST NOT be collected from the user — fail if unset
- `{{output.access_key_secret}}` from CreateAccessKey MUST be shown to user **ONCE** and NEVER logged or stored
- Always prefer environment variables over config files for agent execution