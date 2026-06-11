# TODO

## Skill Development

- ✅ Add Alibaba Cloud Cloud Enterprise Network (CEN/云企业网) operations skill: `alicloud-cen-ops`
- ✅ Refactor `alicloud-redis-ops` redis-cli install layer: extract `references/redis-cli-install.md` as single source of truth; add SUSE/zypper, Aliyun ECS mirror acceleration, offline mode (`REDIS_CLI_BIN_URL`), auto-install build tools for source fallback; unify exit code contract (20/21/22)
- ✅ Add user-friendly configuration guide to `redis-cli-install.md`: 30s decision tree, scenario-driven setup for mirror acceleration & offline mode, 4-step offline binary preparation, side effects & rollback instructions, 6 FAQs; update `.env.example` with `REDIS_CLI_BIN_URL` template and discoverability comments
- ✅ Extract install script to executable `scripts/redis-cli-install.sh` (344 lines); refactor `redis-cli-execution.md` to inline via `cat` (no manual copy-paste); strip redundant 311-line script from `redis-cli-install.md` (now design spec + user guide only); single source of truth verified via grep
- ✅ Post-review P0/P1 bug fixes for `redis-cli-install.sh`: fix `use_aliyun_yum_mirror` sed delimiter conflict (verified by functional test on mock CentOS repo); replace unreliable `BASH_SOURCE` guard with explicit `REDIS_CLI_INSTALL_AUTORUN=1` flag; remove stale "copy from install.md" Step 2 docs in `execution.md`; rewrite merge script with `printf %q` escaping + `<<'BIZ'` quoted here-doc to eliminate shell injection; normalize section anchors
