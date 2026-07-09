# CLI — Function Compute (FC 3.0) (`aliyun fc-open`)

## Install and config

- Install: `aliyun` CLI (Go binary, no runtime dependencies)
- The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json`
- No dedicated `aliyun fc` subcommand exists. **FC uses ROA REST API via `fc-open`**.

## ROA Conventions (agent execution)

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.items[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun fc-open GET /services | jq '{services: [.services[]? | {name: .serviceName, qualifier: .qualifier}]}'
```

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

## GPU Functions (vLLM & Batch)

GPU functions use the same `fc-open` paths; request bodies include `gpuConfig` + `customContainerConfig` (no `code` ZIP). Full scenario examples: [gpu-inference.md §10](gpu-inference.md#10-cli--api--sdk-by-scenario).

| Goal | Example `aliyun fc-open` invocation | Notes |
|------|-------------------------------------|-------|
| Create GPU + vLLM container | `POST /2023-03-30/functions --body '{...gpuConfig,customContainerConfig...}'` | See gpu-inference.md §10.2 |
| Set min instances (warm) | `PUT "/2023-03-30/functions/{name}/scaling-config?qualifier=LATEST" --body '{"minInstances":1}'` | §10.3 |
| Scale to zero (sparse) | Same with `"minInstances": 0` | Quasi-real-time |
| Resident GPU pool | `PUT .../scaling-config` with `residentPoolId`, `enableOnDemandScaling: false` | Immutable instance type at create |
| HTTP trigger (OpenAI API) | `POST /2023-03-30/functions/{name}/triggers` `triggerType: http` | §10.4; use `urlInternet` for curl |
| OSS batch trigger | `POST .../triggers` `triggerType: oss` | §10.6 |
| Async batch job | `POST .../invocations --header "x-fc-invocation-type=Async"` | §10.5 |
| Async config + DLQ | `PUT /2023-03-30/functions/{name}/async-invoke-config` | §10.5 |
| List GPU functions | `GET /2023-03-30/functions` + `jq 'select(.gpuConfig)'` | §10.7 |
| Get scaling config | `GET "/2023-03-30/functions/{name}/scaling-config?qualifier=LATEST"` | |
| Enable LLM metrics | `PUT /2023-03-30/functions/{name}` with `logConfig.enableLlmMetrics: true` | Custom SLS project required |

**Not via `fc-open`:** Function AI Model Service (managed vLLM) — use [Function AI console](https://cap.console.aliyun.com/).

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
