# Runtime Harness Integration for alicloud-oss-ops

This skill uses the **shared overlay pattern**: `scripts/harness-lib.sh` (canonical;
legacy `skillopt-lib.sh` symlink) sources
[`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md).

## Self-Repair Capabilities

1. **Throttling** (`Throttling.User`) — exponential backoff & reduced frequency
2. **Invalid Parameters** (`InvalidParameter`) — fixes JSON syntax
3. **Resource Not Found** (`ResourceNotFound`) — verifies resource existence
4. **Permission Errors** (`Forbidden`/`NoPermission`) — suggests RAM policy
5. **Connection Failures** (`ConnectionTimeout`) — retries with increased timeout
6. **Quota Exceeded** (`QuotaExceeded`) — notifies user of limits

## Environment Variable Loading

The wrapper and `skillopt-lib.sh` **automatically load** `.env` on every invocation. Manual `source ../.env` is optional.

| Priority (high → low) | Source |
|----------------------|--------|
| 1 | Parent-shell `export` (already set before wrapper runs) |
| 2 | CLI flags (`--skillopt-langfuse-enable`, etc.) |
| 3 | Repo-root `.env` (`aliyun-skills/.env`) |
| 4 | Skill-local `.env` (`alicloud-oss-ops/.env`) |
| 5 | Built-in defaults (`SKILLOPT_LANGFUSE_ENABLED=false`, etc.) |

Implementation: `_skillopt_load_env_file` in `scripts/skillopt-lib.sh` (AGENTS.md §15.7 L2/L3):

- Safe read: `while IFS= read -r line || [[ -n "$line" ]]` (last line without newline)
- Never override: `${!key+x}` — only unset variables are imported from file
- Wrapper pre-loads `.env` before `skillopt_wrap`; `skillopt_init` reloads safely (idempotent)

Typical variables:

```ini
ALIBABA_CLOUD_ACCESS_KEY_ID=...
ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
SKILLOPT_LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

> **Security:** Never commit `.env`. See [Integration — Environment Variable Loading](integration.md#environment-variable-loading).

## Usage

### Direct Command
```bash
aliyun oss DescribeInstances --skillopt-enable --RegionId cn-hangzhou
```

### Wrapper Script
```bash
cd alicloud-oss-ops
# .env is auto-loaded from repo root or skill directory — no manual source needed
./scripts/oss-skillopt-wrapper.sh ls
```

## Langfuse Tracing

Enable distributed tracing for OSS CLI operations (read-only `ls` recommended for smoke tests):

```bash
cd alicloud-oss-ops
# .env auto-loaded; only needed if you want to verify vars in current shell
# source ../.env

./scripts/oss-skillopt-wrapper.sh ls \
  --skillopt-langfuse-enable \
  --skillopt-session-id sess-debug-$(date +%s)
```

| Flag | Purpose |
|------|---------|
| `--skillopt-langfuse-enable` | Mirror traces to Langfuse (local trace always written) |
| `--skillopt-langfuse-disable` | Disable Langfuse remote mirror |
| `--skillopt-session-id <id>` | Correlate multi-step workflows |
| `--skillopt-enable` | Enable auto-repair (read-only actions only) |

Trace name format (Langfuse mirror): `alicloud-oss-ops oss <action>`. **Local canonical**: `${SKILLS_DIR}/.runtime/traces/alicloud-oss-ops/trace-*.json` (always). Langfuse validate: `GET ${LANGFUSE_HOST}/api/public/traces/{trace_id}`. TTL: `make memory-maintain-apply` (default 7d).

When `SKILLOPT_LANGFUSE_ENABLED=true` is set in repo-root `.env`, Langfuse is enabled automatically — no `--skillopt-langfuse-enable` flag required. Explicit CLI flags and parent-shell exports always override `.env`.

> **Note:** OSS `ls` returns table text (not JSON). Trace output encoding uses `jq -Rs` for multiline CLI responses.

## Reference

- [Runtime Harness integration guide](../../docs/harness-integration-guide.md)
- [Runtime Harness glossary](../../docs/runtime-harness-glossary.md)
- See also [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt) — offline skill-document training, orthogonal to Runtime Harness

