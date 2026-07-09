#!/bin/bash
# Regression test: alicloud-polar-postgresql-ops wrapper does not self-block.
set -euo pipefail

SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SDIR/scripts/polardb-postgresql-skillopt-wrapper.sh"

PASS=0; FAIL=0
ok()  { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== alicloud-polar-postgresql-ops wrapper self-call regression ==="

STUB_DIR="$(mktemp -d)"
trap "rm -rf $STUB_DIR" EXIT
cat >"$STUB_DIR/aliyun" <<'EOF'
#!/bin/bash
echo '{"Items":{"DBCluster":[{"DBClusterId":"pc-pg-stub"}]}}'
exit 0
EOF
chmod +x "$STUB_DIR/aliyun"

if PATH="$STUB_DIR:$PATH" bash "$WRAPPER" DescribeDBClusters --RegionId cn-hangzhou >/tmp/wrap.out 2>&1; then
    if grep -q 'WRAPPER REQUIRED' /tmp/wrap.out; then
        bad "wrapper hit P0 self-block"
    elif grep -q 'pc-pg-stub' /tmp/wrap.out; then
        ok "wrapper reached aliyun stub (pc-pg-stub)"
    else
        bad "wrapper produced unexpected output: $(cat /tmp/wrap.out | head -3)"
    fi
else
    bad "wrapper failed (rc=$?)"
fi

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
