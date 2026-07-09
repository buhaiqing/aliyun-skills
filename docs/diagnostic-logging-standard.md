# Diagnostic Logging Standard (MANDATORY for data-plane ops)

> **Scope**: This standard applies to scripts executed via Cloud Assistant or other remote data-plane channels.
> It does **not** apply to SkillOpt runtime logs, which use their own JSON Lines / plain-text format (see [`harness-observability-architecture.md`](./harness-observability-architecture.md)).

All scripts executed via Cloud Assistant or other remote channels MUST use a consistent log format:

```
[HH:MM:SS] [PHASE] key=value
```

## Log Phase Prefix

| PHASE | Meaning | Example |
|-------|---------|---------|
| `DIAG` | Diagnostic info / environment snapshot | `[DIAG] PHASE=env-snapshot`, `[DIAG] OS=Ubuntu 22.04` |
| `INSTALL` | Installation process | `[INSTALL] pkg_manager=apt`, `[INSTALL] exit code 0` |
| `EXEC` | Command being executed | `[EXEC] redis-cli -h host -p 6379 DEL key` |
| `RESULT` | Key result key-value pairs | `[RESULT] INSTALL=SUCCESS`, `[RESULT] NETWORK=REACHABLE` |
| `WARN` | Warning | `[WARN] redis-cli not found, installing...` |
| `ERROR` | Error classification | `[ERROR] TYPE=AUTH_FAILED FIX=Check password` |
| `SUMMARY` | Final summary | `[SUMMARY] Result: (integer) 1` |

## Error Classification (ERROR TYPE)

```
[ERROR] TYPE={category} FIX={one-line action}
```

Built-in error types (Redis example — extend per product):

| ERROR TYPE | Meaning | FIX |
|------------|---------|-----|
| `AUTH_FAILED` | Password required but not provided | Check redis password |
| `WRONG_PASSWORD` | Incorrect password | Verify credentials |
| `CLUSTER_MOVED` | Key not on this node (cluster mode) | Use redis-cli -c |
| `CONNECTION_REFUSED` | Port unreachable | Port closed or instance down |
| `TIMEOUT` | Connection timeout | Network latency or congestion |
| `UNKNOWN_COMMAND` | Syntax error | Check syntax |

Products may extend this TYPE list, but every TYPE MUST include an actionable FIX.

## Exit Code Convention

| ExitCode | Meaning | Agent Action | Human Intervention |
|:--------:|---------|-------------|:------------------:|
| 0 | Success | Read SUMMARY and return | No |
| 10-19 | Environment check failed | Auto-remediation (e.g. install) | No |
| 20-29 | Installation failed | Output `[DIAG] disk/mem/network` | Yes |
| 30-39 | Network issue | Output DNS/connection diagnostics | Yes |
| 40-49 | Command execution failed | Output `[ERROR] TYPE=... FIX=...` | Yes |