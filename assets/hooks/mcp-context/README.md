# MCP context hook templates (TEL Phase 4.5)

Merge into `.cursor/hooks.json` (example):

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      { "command": "assets/hooks/mcp-context/cursor-scan-loaded.sh" }
    ],
    "postToolUse": [
      {
        "command": "assets/hooks/mcp-context/cursor-post-mcp.sh",
        "matcher": "MCP"
      }
    ]
  }
}
```

Sidecar output: `.runtime/token/context/mcp-context-latest.json`  
Consumed by `harness-core-lib.sh` → `trace.context_metadata.mcp`.

Run tests: `bash scripts/test-mcp-context-adapters.sh`
