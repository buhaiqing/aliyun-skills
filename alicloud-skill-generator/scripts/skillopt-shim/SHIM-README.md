# SkillOpt Shim — Runtime Enforcement for Wrapper-First CLI

> **Why this exists:** The aliyun-skills `SKILL.md` files declare that all CLI
> operations for wrapped products (oss, ecs, rds, redis, mongodb, slb, vpc, ack,
> cms) MUST go through the per-skill `*-skillopt-wrapper.sh` for SkillOpt
> self-repair, Langfuse tracing, and circuit-breaker protection. Documentation
> rules don't enforce themselves — agents (and humans) bypass them.
>
> This shim is the **runtime enforcement layer**. Once sourced, it is
> *physically impossible* to invoke `aliyun <product>` for a wrapped product
> without going through the wrapper. There is no "I'll just do it quickly"
> path.

## What it does

Defines a shell function named `aliyun` that:

1. Examines the first positional arg of every `aliyun` invocation.
2. If it's a wrapped product (oss, ecs, rds, redis, mongodb, slb, vpc, ack, cms,
   plus their CLI aliases `r-kvstore`, `dds`, `cs`), routes the call through
   the per-skill wrapper.
3. If it's an unwrapped product (sts, ram, polardb, ...), passes through to
   the native `aliyun` binary.
4. If the first arg is a flag (`--version`, `--profile`, ...) or empty,
   passes through — this is a documented limitation; use `aliyun <product> <action>`
   (product-first) form to be intercepted.

The shim is **invisible** to the user: `aliyun oss ls` produces the same
output as before, but now it goes through
`./alicloud-oss-ops/scripts/oss-skillopt-wrapper.sh oss ls` instead of the
raw CLI.

## Install

### Option A — Persistent (recommended for daily use)

```bash
./enable.sh            # adds a source block to ~/.zshrc and ~/.bashrc
exec $SHELL            # reload
type aliyun            # should print: aliyun is a function
```

To uninstall:

```bash
./enable.sh uninstall
```

### Option B — Per-session

```bash
source /path/to/aliyun-skills/alicloud-skill-generator/scripts/skillopt-shim/aliyun-shim.sh
```

### Option C — Per-invocation (CI / scripts)

```bash
SKILLOPT_SHIM_LOG=1 bash -c '
  source /path/to/aliyun-shim.sh
  aliyun oss ls
'
```

## Observability

| Variable | Default | Effect |
|----------|---------|--------|
| `SKILLOPT_SHIM_LOG` | `0` | Set to `1` to enable structured logging |
| `SKILLOPT_SHIM_LOG_FILE` | `<repo>/.runtime/skillopt-shim.log` | Override log path |

Each intercepted call logs a line like:

```
[2026-06-17T17:30:00+0800] INTERCEPT product=oss skill=alicloud-oss-ops wrapper=/abs/path/oss-skillopt-wrapper.sh wrapper_arg=oss
```

Use this to audit that no direct (non-intercepted) `aliyun <product>` calls
are being made. Add it to your CI as a regression test:

```bash
# CI: every call to aliyun <product> in agent logs must show INTERCEPT.
grep -E "^[^I].*aliyun (oss|ecs|rds|redis|mongodb|slb|vpc|ack|cms) " .runtime/skillopt-shim.log
# (Above should produce no output — any non-INTERCEPT call is a violation.)
```

## Escape hatch

When the shim is in the way (debugging wrapper behavior, working outside an
aliyun-skills checkout, intentionally bypassing SkillOpt), use `command`:

```bash
command aliyun oss ls   # bypasses the shim, calls native binary
```

`command` is a POSIX shell builtin that skips function lookup, so the shim
is invisible. The native binary always wins.

## Test

```bash
./test-skillopt-shim.sh                  # test all registered products
./test-skillopt-shim.sh oss mongodb      # test specific products
```

The test:
- Does NOT make cloud calls (uses a non-existent subcommand).
- Verifies each product's INTERCEPT line is logged.
- Verifies passthrough products (sts, ram) are not intercepted.
- Verifies the escape hatch (`command aliyun`) bypasses the shim.
- Verifies flag-first invocations correctly pass through.

Expected: 15 passes (12 products + 2 passthroughs + 1 escape hatch + 1 documented limit), 0 fails.

## Adding a new wrapped product

When a new skill gets SkillOpt integration, add entries to the registry in
`aliyun-shim.sh`:

```bash
_SKILLOPT_SHIM_REGISTRY=(
  # ...
  "newprod:alicloud-newprod-ops:newprod-skillopt-wrapper.sh:newprod"
  "newprod-alias:alicloud-newprod-ops:newprod-skillopt-wrapper.sh:newprod"
)
```

Then run `./test-skillopt-shim.sh newprod` to verify.

## Limitations (known, documented)

| Limitation | Workaround |
|------------|------------|
| `aliyun --profile X <product> <action>` (flag-first) is not intercepted | Use `aliyun <product> <action> --profile X` (product-first) or `command aliyun ...` |
| CWD must be inside an `aliyun-skills` checkout for interception | If outside, shim warns and passes through to native; this is intentional — the shim cannot find the wrapper otherwise |
| Only intercepts registered products | Add new products to the registry when wrapping a new skill |
| Not exported across subshells automatically | Use `enable.sh` to source persistently; otherwise pass `bash -c 'source aliyun-shim.sh; ...'` explicitly |
| Macros / `time` / `xargs aliyun` may bypass the shim | The shim is a shell function — anything that doesn't go through the function lookup table will bypass. For `xargs`, invoke via `bash -c 'aliyun ...'` per item |
| Log file write failures are silent | The shim never blocks user commands due to logging failures. Use a writable path or set `SKILLOPT_SHIM_LOG_FILE` |

## Maintenance

- This file is **shared infrastructure** owned by `alicloud-skill-generator`
  (the meta-skill). It is NOT per-product.
- When the SKILL.md of any wrapped product changes its wrapper path or
  product code, update the registry here.
- When a new skill gets SkillOpt integration, add a registry entry here
  AND update the new skill's `SKILL.md` Runtime Rules to reference this shim.
- CI should run `./test-skillopt-shim.sh` on every PR that touches
  `alicloud-*-ops/scripts/*-skillopt-wrapper.sh` or this file.
