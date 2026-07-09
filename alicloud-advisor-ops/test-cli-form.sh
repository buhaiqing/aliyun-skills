#!/bin/bash
# Regression test: advisor CLI accepts kebab-case, rejects PascalCase.
# Captured failure pattern from Layer 1 memory (5x GetProductList FAILED)
# was caused by SKILL.md teaching the wrong CLI form. This test prevents
# regression of that specific failure mode.
#
# Strategy: stub aliyun CLI to avoid real cloud calls; we only assert the
# CLI accepts kebab-case form and rejects PascalCase form for the same
# operation. This mirrors the real aliyun-cli behavior observed on
# 2026-06-21 against plugin aliyun-cli-advisor v0.4.0.
set -euo pipefail

SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SDIR/scripts/advisor-skillopt-wrapper.sh"

PASS=0
FAIL=0
ok()  { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== alicloud-advisor-ops CLI form regression ==="

# --- Stub aliyun that mirrors real behavior for our test ---
# The wrapper invokes: aliyun advisor <subcommand> [flags...]
# We pick out the first non-flag positional arg as the subcommand.
STUB_DIR="$(mktemp -d)"
trap "rm -rf $STUB_DIR" EXIT
cat >"$STUB_DIR/aliyun" <<'EOF'
#!/bin/bash
# Skip global aliyun flags like --RegionId, --profile, etc.
op=""
for arg in "$@"; do
    case "$arg" in
        --*) ;;
        advisor) continue ;;
        *) if [[ -z "$op" ]]; then op="$arg"; fi ;;
    esac
done
if [[ "$op" =~ ^[A-Z] ]]; then
    kebab=$(echo "$op" | sed -E 's/([A-Z])/-\L\1/g' | sed 's/^-//')
    echo "ERROR: '$op' is not a valid api. See 'aliyun help advisor'." >&2
    echo "Did you mean:" >&2
    echo "  $kebab" >&2
    exit 2
fi
echo '{"RequestId":"stub","Data":"ok"}'
exit 0
EOF
chmod +x "$STUB_DIR/aliyun"

# --- Case 1: PascalCase must fail (the historical bug) ---
if PATH="$STUB_DIR:$PATH" bash "$WRAPPER" GetProductList >/dev/null 2>&1; then
    bad "PascalCase GetProductList was accepted (should be rejected)"
else
    ok "PascalCase GetProductList rejected (exit non-zero)"
fi

# --- Case 2: kebab-case must succeed (the fix) ---
if PATH="$STUB_DIR:$PATH" bash "$WRAPPER" get-product-list >/dev/null 2>&1; then
    ok "kebab-case get-product-list accepted"
else
    bad "kebab-case get-product-list rejected (should pass)"
fi

# --- Case 3: another read operation (DescribeAdvices) ---
if PATH="$STUB_DIR:$PATH" bash "$WRAPPER" DescribeAdvices >/dev/null 2>&1; then
    bad "PascalCase DescribeAdvices was accepted"
else
    ok "PascalCase DescribeAdvices rejected"
fi
if PATH="$STUB_DIR:$PATH" bash "$WRAPPER" describe-advices >/dev/null 2>&1; then
    ok "kebab-case describe-advices accepted"
else
    bad "kebab-case describe-advices rejected"
fi

# --- Case 4: docs consistency check: SKILL.md must NOT teach PascalCase ---
# (Allow PascalCase inside RAM policy snippets and frontmatter API spec names,
# but Quick Start and Pre-flight tables must use kebab-case.)
SKILL="$SDIR/SKILL.md"
if grep -E '^\s*aliyun advisor GetProductList\s*$' "$SKILL" >/dev/null; then
    bad "SKILL.md still has bare 'aliyun advisor GetProductList' line"
else
    ok "SKILL.md has no bare PascalCase CLI invocation"
fi
if grep -E '`aliyun advisor GetProductList`' "$SKILL" >/dev/null; then
    bad "SKILL.md Quick Start / Pre-flight still references PascalCase CLI"
else
    ok "SKILL.md Quick Start / Pre-flight uses kebab-case CLI"
fi

# --- Case 5: references/cli-usage.md GetProductList section ---
CLI_DOC="$SDIR/references/cli-usage.md"
if grep -E '^\s*aliyun advisor GetProductList\s*$' "$CLI_DOC" >/dev/null; then
    bad "references/cli-usage.md still shows 'aliyun advisor GetProductList' example"
else
    ok "references/cli-usage.md uses kebab-case example"
fi

# --- Case 6: GLOBAL scan for any leftover PascalCase CLI form ---
# This regression test guards the entire skill. Earlier fixes only covered
# Quick Start / Pre-flight tables, but Execution Flows and Operation
# chapters in references/cli-usage.md, well-architected-assessment.md,
# and core-concepts.md still taught PascalCase forms. This scan catches
# any future reintroduction in any .md file under this skill.
LEFTOVER=$(grep -rnE 'aliyun advisor [A-Z][a-zA-Z]+ ' "$SDIR" 2>/dev/null \
    | grep -v "\.bak$" \
    | grep -v "/.runtime/" \
    || true)
if [[ -n "$LEFTOVER" ]]; then
    bad "residual PascalCase CLI invocations remain:"
    echo "$LEFTOVER" | sed 's/^/      /'
else
    ok "no PascalCase CLI invocations remain anywhere in skill"
fi

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
