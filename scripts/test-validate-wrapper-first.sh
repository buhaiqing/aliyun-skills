#!/bin/bash
# scripts/test-validate-wrapper-first.sh
# Smoke test for scripts/validate-wrapper-first.sh.
# Creates a temporary skill directory with both compliant and non-compliant
# SKILL.md files, runs the validator, and asserts the right exit codes.
#
# Usage:
#   bash scripts/test-validate-wrapper-first.sh
#
# Exit codes:
#   0  all assertions pass
#   1  an assertion failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATOR="$SCRIPT_DIR/validate-wrapper-first.sh"

if [[ ! -x "$VALIDATOR" ]]; then
    echo "❌ Validator not found or not executable: $VALIDATOR"
    exit 1
fi

# Use a scratch dir under repo .runtime (gitignored)
SCRATCH="$REPO_ROOT/.runtime/test-validate-wrapper-first"
rm -rf "$SCRATCH"
mkdir -p "$SCRATCH"

# Cleanup happens only at the very end (after all assertions)
cleanup_scratch() { rm -rf "$SCRATCH"; }

# Copy a real skill to start with, then mutate
mkdir -p "$SCRATCH/alicloud-test-good-ops/scripts"
mkdir -p "$SCRATCH/alicloud-test-bad-ops/scripts"
mkdir -p "$SCRATCH/alicloud-test-bare-aliyun-ops/scripts"

# Good: has Runtime Rules + MANDATORY + fallback + graceful wrapper
cat > "$SCRATCH/alicloud-test-good-ops/SKILL.md" <<'EOF'
# Test Good Skill

## Runtime Rules
| CLI path | MANDATORY: Use wrapper script ./scripts/test-good-skillopt-wrapper.sh; fallback to native aliyun test-good | ref |
EOF

cat > "$SCRATCH/alicloud-test-good-ops/scripts/test-good-skillopt-wrapper.sh" <<'EOF'
#!/bin/bash
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLOPT_LOADED=false
if [ -f "$SCRIPT_DIR/skillopt-lib.sh" ]; then
    source "$SCRIPT_DIR/skillopt-lib.sh"
    SKILLOPT_LOADED=true
fi
PRODUCT="test-good"
SUBCMD="$1"; shift
if [ "$SKILLOPT_LOADED" = true ]; then
    skillopt_wrap "$PRODUCT" "$SUBCMD" "$@"
else
    aliyun "$PRODUCT" "$SUBCMD" "$@"
fi
EOF
chmod +x "$SCRATCH/alicloud-test-good-ops/scripts/test-good-skillopt-wrapper.sh"

# Bad: no Runtime Rules
cat > "$SCRATCH/alicloud-test-bad-ops/SKILL.md" <<'EOF'
# Test Bad Skill
No runtime rules here.
EOF
cat > "$SCRATCH/alicloud-test-bad-ops/scripts/test-bad-skillopt-wrapper.sh" <<'EOF'
#!/bin/bash
source "$SCRIPT_DIR/skillopt-lib.sh"
EOF
chmod +x "$SCRATCH/alicloud-test-bad-ops/scripts/test-bad-skillopt-wrapper.sh"

# Bare-aliyun: has Runtime Rules but uses bare aliyun in scripts/
cat > "$SCRATCH/alicloud-test-bare-aliyun-ops/SKILL.md" <<'EOF'
# Test Bare Aliyun Skill
## Runtime Rules
| CLI path | MANDATORY: Use wrapper; fallback to native aliyun test-bare-aliyun. | ref |
EOF
cat > "$SCRATCH/alicloud-test-bare-aliyun-ops/scripts/test-bare-aliyun-skillopt-wrapper.sh" <<'EOF'
#!/bin/bash
source "$SCRIPT_DIR/skillopt-lib.sh"
EOF
# The actual violation: bare aliyun call in scripts/
cat > "$SCRATCH/alicloud-test-bare-aliyun-ops/scripts/run-direct.sh" <<'EOF'
#!/bin/bash
# This is a violation: should be routed through wrapper
aliyun test-bare-aliyun DescribeSomething
EOF
chmod +x "$SCRATCH/alicloud-test-bare-aliyun-ops/scripts/test-bare-aliyun-skillopt-wrapper.sh"

# ---------- assertion helpers ----------
failed=0
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        echo "  ✓ $desc"
    else
        echo "  ✗ $desc: expected=$expected actual=$actual"
        failed=1
    fi
}

# ---------- Test 1: good skill passes ----------
echo "=== Test 1: good skill has 0 P0 violations ==="
rc=0
bash "$VALIDATOR" --skill "$SCRATCH/alicloud-test-good-ops" --json > "$SCRATCH/out1.json" 2>&1 || rc=$?
violations=$(python3 -c "import json; d=json.load(open('$SCRATCH/out1.json')); print(d['violations'])" 2>/dev/null || echo "ERR")
assert_eq "exit code" "0" "$rc"
assert_eq "violations count" "0" "$violations"

# ---------- Test 2: bad skill reports multiple P0 violations ----------
echo "=== Test 2: bad skill (no Runtime Rules) reports P0 violations ==="
rc=0
bash "$VALIDATOR" --skill "$SCRATCH/alicloud-test-bad-ops" --json > "$SCRATCH/out2.json" 2>&1 || rc=$?
violations=$(python3 -c "import json; d=json.load(open('$SCRATCH/out2.json')); print(d['violations'])" 2>/dev/null || echo "ERR")
rules=$(python3 -c "import json; d=json.load(open('$SCRATCH/out2.json')); print(','.join(sorted(v['rule'] for v in d['details']['violations'])))" 2>/dev/null || echo "ERR")
assert_eq "exit code" "1" "$rc"
# Bad skill: no Runtime Rules, no wrapper-first, no fallback → 3 violations
assert_eq "violations count" "3" "$violations"
assert_eq "rules triggered" "missing_fallback_note,missing_runtime_rules_section,missing_wrapper_first_declaration" "$rules"

# ---------- Test 3: bare aliyun reports bare_aliyun_in_scripts ----------
echo "=== Test 3: bare aliyun call in scripts/ reports P0 violation ==="
rc=0
bash "$VALIDATOR" --skill "$SCRATCH/alicloud-test-bare-aliyun-ops" --json > "$SCRATCH/out3.json" 2>&1 || rc=$?
violations=$(python3 -c "import json; d=json.load(open('$SCRATCH/out3.json')); print(d['violations'])" 2>/dev/null || echo "ERR")
rule=$(python3 -c "import json; d=json.load(open('$SCRATCH/out3.json')); v=d['details']['violations']; print(v[0]['rule'] if v else 'none')" 2>/dev/null || echo "ERR")
assert_eq "exit code" "1" "$rc"
assert_eq "violations count" "1" "$violations"
assert_eq "rule" "bare_aliyun_in_scripts" "$rule"

# ---------- Test 4: --strict-warnings triggers exit 1 when warnings exist ----------
echo "=== Test 4: --strict-warnings fails on P1 warnings (no graceful fallback) ==="
# Test-bad-ops has no SKILLOPT_LOADED, so it has 1+ warnings
rc=0
bash "$VALIDATOR" --skill "$SCRATCH/alicloud-test-bad-ops" --strict-warnings > "$SCRATCH/out4.txt" 2>&1 || rc=$?
# Bad skill has missing_runtime_rules_section (P0) + missing wrapper_not_graceful (P1)
# So even without --strict-warnings it fails on P0. With --strict-warnings it
# also fails. Just verify the flag doesn't break anything.
assert_eq "exit code (with P0)" "1" "$rc"

# ---------- Test 5: unknown skill ----------
echo "=== Test 5: unknown skill returns 2 (usage error) ==="
rc=0
bash "$VALIDATOR" --skill "/tmp/alicloud-does-not-exist-$$" >/dev/null 2>&1 || rc=$?
assert_eq "exit code" "2" "$rc"

# ---------- Cleanup ----------
cleanup_scratch

if [[ $failed -eq 0 ]]; then
    echo ""
    echo "✅ All tests passed"
    exit 0
else
    echo ""
    echo "❌ Some tests failed"
    exit 1
fi
