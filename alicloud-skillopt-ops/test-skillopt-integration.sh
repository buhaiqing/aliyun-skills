#!/bin/bash
# Legacy integration test shim (PR-8) — delegates to canonical harness integration test.
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")/../alicloud-runtime-harness-ops" && pwd)/test-harness-integration.sh" "$@"
