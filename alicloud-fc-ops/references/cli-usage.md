# CLI — Function Compute (FC 3.0) (`aliyun fc-open`)

## Install and config

- Install: `aliyun` CLI (Go binary, no runtime dependencies)
- The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json`
- No dedicated `aliyun fc` subcommand exists. **FC uses ROA REST API via `fc-open`**.

## ROA Conventions (agent execution)

FC 3.0 uses ROA-style API. All CLI commands use the `fc-open` product pattern:

```bash
aliyun fc-open <METHOD> /2023-03-30/<path> [--body "..."] [--header "..."]
```

- `METHOD`: GET, POST, PUT, DELETE
- `path`: REST path (not OperationName)
- `--body`: JSON body for POST/PUT operations
- `--header`: Additional HTTP headers for auth type, qualifier, etc.
- Output is **JSON by default** — no `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction

## Command Map

| Goal | Example `aliyun fc-open` invocation | Notes |
|------|-------------------------------------|-------|
| List all functions | `aliyun fc-open GET /2023-03-30/functions` | JSON output by default |
| List by prefix | `aliyun fc-open GET "/2023-03-30/functions?prefix=my-"` | Filter by name prefix |
| Paginate | `aliyun fc-open GET "/2023-03-30/functions?limit=50&nextToken=xxx"` | nextToken from response |
| Filter by runtime | `aliyun fc-open GET "/2023-03-30/functions?runtime=python3.10"` | |
| Filter by tag | `aliyun fc-open GET "/2023-03-30/functions?tag.filter.1.key=env&tag.filter.1.value=production"` | |
| Get function | `aliyun fc-open GET /2023-03-30/functions/{name}` | |
| Get by qualifier | `aliyun fc-open GET "/2023-03-30/functions/{name}?qualifier={qual}"` | version/alias |
| Create function | `aliyun fc-open POST /2023-03-30/functions --body '{...}'` | code via OSS |
| Update function | `aliyun fc-open PUT /2023-03-30/functions/{name} --body '{...}'` | partial body OK |
| Delete function | `aliyun fc-open DELETE /2023-03-30/functions/{name}` | **irreversible** |
| Invoke (sync) | `aliyun fc-open POST /2023-03-30/functions/{name}/invocations --body '{...}' --header "x-fc-invocation-type=Sync"` | |
| Invoke (async) | Same with `Async` header | |
| Create trigger | `aliyun fc-open POST /2023-03-30/functions/{name}/triggers --body '{...}'` | |
| List triggers | `aliyun fc-open GET /2023-03-30/functions/{name}/triggers` | |
| Provision config | `aliyun fc-open PUT /2023-03-30/functions/{name}/provision-config --body '{"qualifier": "alias", "target": 1}'` | |
| List provision configs | `aliyun fc-open GET /2023-03-30/provision-configs` | |
| Async config | `aliyun fc-open PUT /2023-03-30/functions/{name}/async-invoke-config --body '{"maxAsyncEventAgeInSeconds": 7200, "maximumRetryAttempts": 2}'` | |
| List sessions | `aliyun fc-open GET /2023-03-30/sessions` | FC 3.0 stateful feature |
| Create VPC binding | See SDK path (complex body) | Best via SDK |
| Upload to OSS | `aliyun oss cp <local> oss://<bucket>/<prefix>/<name>.zip --force` | Pre-deploy step |
| Get function code | `aliyun fc-open GET /2023-03-30/functions/{name}/code` | Download code URL |

## CLI + SDK Coverage Gap

| Operation | Available via `fc-open`? | Notes |
|-----------|-------------------------|-------|
| CRUD functions | yes | All CRUD via POST/GET/PUT/DELETE |
| Invoke | yes | Sync and async via header |
| Triggers | yes | Full CRUD |
| Provision config | yes | CRUD via fc-open |
| Async config | yes | CRUD via fc-open |
| Concurrency config | yes | CRUD via fc-open |
| Scaling config | yes | CRUD via fc-open |
| Sessions | yes | Full CRUD |
| VPC binding | partial | Complex body; SDK recommended |
| Layers | yes | Full CRUD via fc-open |
