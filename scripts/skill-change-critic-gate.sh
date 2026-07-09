#!/usr/bin/env bash
#
# Skill-change Critic gate — mechanical regression + agent verdict verification.
# Implements AGENTS.md §11.1 + §12 Critic Test & Regression Assessment.
#
# Agent workflow (MANDATORY before marking a skill/repo change done):
#   1. bash scripts/skill-change-critic-gate.sh classify
#   2. bash scripts/skill-change-critic-gate.sh template > .runtime/audit/skill-change-verdict.json
#      → Agent edits: tests_accurate, accuracy_rationale, accuracy_issues (if any)
#   3. bash scripts/skill-change-critic-gate.sh verify --verdict .runtime/audit/skill-change-verdict.json --run
#   4. Exit 0 required; attach verdict + commands to completion summary (RT-5 / RT-6)
#
# Usage:
#   skill-change-critic-gate.sh classify [--git-base REF]
#   skill-change-critic-gate.sh template  [--git-base REF] [--verdict PATH]
#   skill-change-critic-gate.sh verify    --verdict PATH [--run] [--git-base REF]

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERDICT_DEFAULT="${PROJECT_ROOT}/.runtime/audit/skill-change-verdict.json"
GIT_BASE="HEAD"
MODE=""
VERDICT_PATH=""
DO_RUN=false

usage() {
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        classify|template|verify) MODE="$1"; shift ;;
        --git-base) GIT_BASE="$2"; shift 2 ;;
        --verdict) VERDICT_PATH="$2"; shift 2 ;;
        --run) DO_RUN=true; shift ;;
        -h|--help) usage 0 ;;
        *) echo "Unknown argument: $1" >&2; usage 1 ;;
    esac
done

[[ -n "$MODE" ]] || usage 1
[[ "$MODE" != "verify" || -n "$VERDICT_PATH" ]] || { echo "ERROR: verify requires --verdict PATH" >&2; exit 2; }

VERDICT_PATH="${VERDICT_PATH:-$VERDICT_DEFAULT}"

# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

collect_changed_files() {
    if git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        {
            git -C "$PROJECT_ROOT" diff --name-only "$GIT_BASE" 2>/dev/null || true
            git -C "$PROJECT_ROOT" diff --name-only --cached "$GIT_BASE" 2>/dev/null || true
            git -C "$PROJECT_ROOT" ls-files --others --exclude-standard 2>/dev/null || true
        } | sort -u | grep -v '^$' || true
    else
        echo "ERROR: not a git repository: $PROJECT_ROOT" >&2
        exit 2
    fi
}

classify_changes() {
    local files="$1"
    local signal="docs_only"
    local -a suites=()
    local rationale=""

    local has_behavior=false
    local skillopt_shared=false
    local gcl_runner=false
    local gen_skillopt=false
    local multi_overlay=0
    local langfuse_script=false
    local -a overlay_skills=()

    while IFS= read -r f || [[ -n "$f" ]]; do
        f="${f//$'\n'/}"
        [[ -z "$f" ]] && continue
        case "$f" in
            alicloud-runtime-harness-ops/scripts/harness-core-lib.sh|\
            alicloud-runtime-harness-ops/scripts/harness-paths.sh|\
            alicloud-runtime-harness-ops/scripts/harness_runtime.py|\
            alicloud-runtime-harness-ops/test-harness-integration.sh|\
            alicloud-skillopt-ops/scripts/skillopt-core-lib.sh|\
            alicloud-skillopt-ops/scripts/skillopt-paths.sh|\
            alicloud-skillopt-ops/scripts/skillopt_runtime.py|\
            alicloud-skillopt-ops/test-skillopt-integration.sh|\
            alicloud-runtime-harness-ops/SKILL.md|\
            alicloud-skillopt-ops/SKILL.md|\
            scripts/lib/runtime-harness-discover.sh|\
            scripts/test-runtime-harness-naming-contract.sh|\
            .github/workflows/ci.yml)
                has_behavior=true; skillopt_shared=true ;;
            .scripts/migrate-wrappers-harness-lib.sh|\
            .scripts/invert-harness-libs.sh|\
            .scripts/gen-skillopt-legacy-shims.sh)
                has_behavior=true; gen_skillopt=true; skillopt_shared=true ;;
            .scripts/gen-skillopt.sh)
                has_behavior=true; gen_skillopt=true; skillopt_shared=true ;;
            alicloud-gcl-runner-ops/scripts/gcl_runner.py|\
            alicloud-gcl-runner-ops/scripts/gcl_runner_test.py)
                has_behavior=true; gcl_runner=true ;;
            scripts/test-multi-skill-session.sh)
                has_behavior=true; langfuse_script=true ;;
            scripts/test-mcp-context-adapters.sh|\
            scripts/test-mcp-context-harness-bridge.sh|\
            scripts/test-mcp-context-*.sh|\
            scripts/mcp-context/*|\
            scripts/lib/mcp-context-*.sh|\
            scripts/lib/mcp-context-*.json|\
            scripts/fixtures/mcp-context/*)
                has_behavior=true
                suites+=("bash scripts/test-mcp-context-adapters.sh")
                suites+=("bash scripts/test-mcp-context-harness-bridge.sh")
                signal="mcp_context_tel"
                rationale="MCP context_metadata adapters; five-platform L1 + harness bridge"
                ;;
            scripts/lib/otel-traceparent.sh|\
            scripts/test-otel-traceparent-bridge.sh|\
            scripts/test-agent-turn-x14-x15-bridge.sh|\
            scripts/agent-turn/*|\
            scripts/lib/cursor-usage-api.schema.json|\
            scripts/fixtures/agent-turn/*|\
            assets/hooks/cursor/after-agent-response.sh)
                has_behavior=true
                suites+=("bash scripts/test-otel-traceparent-bridge.sh")
                suites+=("bash scripts/test-ide-agent-turn-bridge.sh")
                suites+=("bash scripts/test-agent-turn-x14-x15-bridge.sh")
                signal="otel_traceparent_tel"
                rationale="W3C TRACEPARENT + X-14/X-15 agent turn bridge regression"
                ;;
            scripts/token_rollup.py|\
            scripts/token_rollup_test.py|\
            scripts/test-token-rollup.sh|\
            scripts/fixtures/token-rollup/*)
                has_behavior=true
                suites+=("python3 scripts/check_py310_compat.py scripts/token_rollup.py scripts/token_rollup_test.py")
                suites+=("cd scripts && python3 -m unittest token_rollup_test -v")
                suites+=("bash scripts/test-token-rollup.sh")
                signal="tel_token_rollup"
                rationale="TEL Phase 5 token_rollup.py + unittest fixtures"
                ;;
            scripts/skill_evolution/*|scripts/test-skill-evolution-milestone-a.sh|scripts/test-skill-evolution-milestone-b.sh|scripts/test-skill-evolution-train-smoke.sh)
                has_behavior=true
                suites+=("python3 scripts/check_py310_compat.py scripts/skill_evolution/export_trajectories.py scripts/skill_evolution/build_trainable_seed.py scripts/skill_evolution/build_dataset.py scripts/skill_evolution/benchmark_smoke_test.py scripts/skill_evolution/benchmark/alicloud_ops/dataloader.py scripts/skill_evolution/benchmark/alicloud_ops/query_resolver.py scripts/skill_evolution/benchmark/alicloud_ops/trajectories.py scripts/skill_evolution/benchmark/alicloud_ops/reflect.py scripts/skill_evolution/benchmark/alicloud_ops/adapter.py scripts/skill_evolution/benchmark/alicloud_ops/rollout.py scripts/skill_evolution/benchmark/alicloud_ops/scorer.py scripts/skill_evolution/train_ci.py")
                suites+=("bash scripts/test-skill-evolution-milestone-a.sh")
                suites+=("bash scripts/test-skill-evolution-milestone-b.sh")
                suites+=("bash scripts/test-skill-evolution-train-smoke.sh")
                signal="skill_evolution_milestone_b"
                rationale="MS SkillOpt Milestone A/B + train CI smoke (mock rollout, trajectories reflect)"
                ;;
            */scripts/skillopt-lib.sh|*/scripts/harness-lib.sh|\
            */scripts/*-skillopt-wrapper.sh|*/scripts/*-harness-wrapper.sh|\
            */test-skillopt-backward-compatibility.sh)
                has_behavior=true
                local skill
                skill="$(echo "$f" | cut -d/ -f1)"
                overlay_skills+=("$skill")
                ;;
            scripts/skill-change-critic-gate.sh|scripts/test-skill-change-critic-gate.sh)
                has_behavior=true
                suites+=("bash -n scripts/skill-change-critic-gate.sh")
                suites+=("bash scripts/test-skill-change-critic-gate.sh")
                signal="critic_gate_script"
                rationale="critic gate script + smoke tests"
                ;;
            AGENTS.md|docs/*.md|*/references/prompt-templates.md|*/SKILL.md|TODO.md)
                ;; # docs — alone does not flip has_behavior
            *)
                [[ "$f" == *.md ]] || has_behavior=true ;;
        esac
    done <<< "$files"

    # dedupe overlay skills
    if [[ ${#overlay_skills[@]} -gt 0 ]]; then
        local -a uniq=()
        local s u seen
        for s in "${overlay_skills[@]}"; do
            seen=false
            for u in "${uniq[@]+"${uniq[@]}"}"; do [[ "$u" == "$s" ]] && seen=true && break; done
            $seen || uniq+=("$s")
        done
        overlay_skills=("${uniq[@]}")
        multi_overlay=${#overlay_skills[@]}
    fi

    if $has_behavior; then
        if $gcl_runner; then
            signal="gcl_runner"
            suites+=("python3 alicloud-gcl-runner-ops/scripts/gcl_runner_test.py")
            rationale="gcl_runner.py behavior changed; unit suite asserts critique/test_assessment/decide"
        fi
        if $skillopt_shared || $gen_skillopt || [[ $multi_overlay -ge 3 ]]; then
            signal="cross_skill_skillopt"
            suites+=("export ALIYUN_SKILLS_ROOT=\"$PROJECT_ROOT\" && bash alicloud-runtime-harness-ops/test-harness-integration.sh")
            suites+=("bash scripts/test-runtime-harness-naming-contract.sh")
            suites+=("bash alicloud-ecs-ops/test-skillopt-backward-compatibility.sh")
            suites+=("bash alicloud-cms-ops/test-skillopt-backward-compatibility.sh")
            rationale="shared SkillOpt or multi-skill overlay change; integration + ecs/cms representatives"
        elif [[ $multi_overlay -eq 1 ]]; then
            signal="skillopt_overlay"
            local skill="${overlay_skills[0]}"
            suites+=("export ALIYUN_SKILLS_ROOT=\"$PROJECT_ROOT\" && bash alicloud-runtime-harness-ops/test-harness-integration.sh")
            if [[ -f "$PROJECT_ROOT/$skill/test-skillopt-backward-compatibility.sh" ]]; then
                suites+=("bash $skill/test-skillopt-backward-compatibility.sh")
            fi
            rationale="single-skill SkillOpt overlay; shared integration + product backward-compat"
        elif [[ $multi_overlay -eq 2 ]]; then
            signal="skillopt_overlay_multi"
            suites+=("export ALIYUN_SKILLS_ROOT=\"$PROJECT_ROOT\" && bash alicloud-runtime-harness-ops/test-harness-integration.sh")
            for skill in "${overlay_skills[@]}"; do
                [[ -f "$PROJECT_ROOT/$skill/test-skillopt-backward-compatibility.sh" ]] && \
                    suites+=("bash $skill/test-skillopt-backward-compatibility.sh")
            done
            rationale="two-skill overlay change; integration + both product tests"
        fi
        if $langfuse_script; then
            suites+=("bash scripts/test-multi-skill-session.sh --local")
            rationale="${rationale:+$rationale; }test-multi-skill-session.sh changed"
        fi
        if [[ "$signal" == "docs_only" ]]; then
            signal="behavior_other"
            [[ ${#suites[@]} -eq 0 ]] && rationale="behavioral change detected; agent must name accurate suites in verdict"
        fi
    else
        signal="docs_only"
        rationale="no scripts/runtime behavior paths in diff; zero behavioral delta"
    fi

    # dedupe suites
    local -a final_suites=()
    local item u seen2
    for item in "${suites[@]+"${suites[@]}"}"; do
        seen2=false
        for u in "${final_suites[@]+"${final_suites[@]}"}"; do [[ "$u" == "$item" ]] && seen2=true && break; done
        $seen2 || final_suites+=("$item")
    done

    local regression_required=false
    [[ ${#final_suites[@]} -gt 0 ]] && regression_required=true

    # emit classification as JSON (no jq required)
    printf '{'
    printf '"change_signal":"%s",' "$signal"
    printf '"regression_required":%s,' "$($regression_required && echo true || echo false)"
    printf '"regression_rationale":%s,' "$(json_str "$rationale")"
    printf '"changed_files":['
    local first=true
    while IFS= read -r f || [[ -n "$f" ]]; do
        f="${f//$'\n'/}"
        [[ -z "$f" ]] && continue
        $first || printf ','
        first=false
        printf '%s' "$(json_str "$f")"
    done <<< "$files"
    printf '],'
    printf '"regression_suites":['
    first=true
    for item in "${final_suites[@]+"${final_suites[@]}"}"; do
        $first || printf ','
        first=false
        printf '%s' "$(json_str "$item")"
    done
    printf ']'
    printf '}\n'
}

json_str() {
    python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<<"${1:-}"
}

# ---------------------------------------------------------------------------
# Template / verify
# ---------------------------------------------------------------------------

emit_template() {
    local classification="$1"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"

    python3 - "$classification" "$ts" <<'PY'
import json, sys
cls = json.loads(sys.argv[1])
ts = sys.argv[2]
doc = {
    "verdict_version": "1.0.0",
    "generated_at": ts,
    "change_signal": cls["change_signal"],
    "mechanical_regression_required": cls["regression_required"],
    "mechanical_regression_suites": cls["regression_suites"],
    "mechanical_regression_rationale": cls["regression_rationale"],
    "changed_files": cls["changed_files"],
    # --- Agent MUST complete (accuracy over coverage) ---
    "tests_accurate": None,
    "accuracy_rationale": "REQUIRED: if this change introduced a bug, which tests would fail and why?",
    "accuracy_issues": [],
    "regression_required": cls["regression_required"],
    "regression_suites": cls["regression_suites"],
    "regression_rationale": cls["regression_rationale"] or "agent explains smallest accurate suite or skip reason",
    "regression_runs_passed": None,
    "regression_evidence": [],
}
print(json.dumps(doc, indent=2, ensure_ascii=False))
PY
}

verify_verdict() {
    local classification="$1"
    [[ -f "$VERDICT_PATH" ]] || { echo "ERROR: verdict not found: $VERDICT_PATH" >&2; exit 2; }

    python3 - "$VERDICT_PATH" "$classification" "$PROJECT_ROOT" "$DO_RUN" <<'PY'
import json, os, subprocess, sys
from pathlib import Path

verdict_path, cls_json, root, do_run = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "true"
cls = json.loads(cls_json)
root = Path(root)
v = json.loads(Path(verdict_path).read_text(encoding="utf-8"))
errors = []

def err(msg):
    errors.append(msg)

ta = v.get("tests_accurate")
if ta is None:
    err("tests_accurate is null — agent must set true/false with accuracy_rationale")
elif ta is False:
    issues = v.get("accuracy_issues") or []
    if not issues:
        err("tests_accurate=false but accuracy_issues is empty — list concrete test fixes")
if not (v.get("accuracy_rationale") or "").strip() or "REQUIRED:" in v.get("accuracy_rationale", ""):
    err("accuracy_rationale missing or still placeholder")

mech_req = cls["regression_required"]
agent_req = v.get("regression_required")
if mech_req and agent_req is False:
  skip = (v.get("regression_rationale") or "").strip()
  if not skip or len(skip) < 20:
    err("mechanical gate requires regression but verdict sets regression_required=false without substantive skip rationale")

suites = v.get("regression_suites") or cls.get("regression_suites") or []
if v.get("regression_required") or mech_req:
    if not suites:
        err("regression required but regression_suites is empty")
    evidence = []
    if do_run:
        for cmd in suites:
            print(f"[RUN] {cmd}")
            r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True)
            passed = r.returncode == 0
            evidence.append({"suite": cmd, "passed": passed, "exit_code": r.returncode})
            if not passed:
                err(f"regression suite failed (exit {r.returncode}): {cmd}")
                if r.stderr:
                    print(r.stderr[-2000:], file=sys.stderr)
        v["regression_evidence"] = evidence
        v["regression_runs_passed"] = all(e["passed"] for e in evidence)
        Path(verdict_path).write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        if v.get("regression_runs_passed") is not True:
            ev = v.get("regression_evidence") or []
            if not ev or not all(isinstance(e, dict) and e.get("passed") for e in ev):
                err("regression required but regression_runs_passed is not true — re-run with --run")

if errors:
    print("CRITIC GATE: FAIL", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print("CRITIC GATE: PASS")
print(f"  change_signal: {v.get('change_signal')}")
print(f"  tests_accurate: {ta}")
print(f"  regression_required: {v.get('regression_required')}")
if suites:
    print(f"  suites: {len(suites)}")
sys.exit(0)
PY
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

mkdir -p "$(dirname "$VERDICT_PATH")"
FILES="$(collect_changed_files)"
[[ -n "$FILES" ]] || { echo "WARN: no changed files detected (git base: $GIT_BASE)" >&2; FILES=""; }

CLASSIFICATION="$(classify_changes "$FILES")"

case "$MODE" in
    classify)
        echo "$CLASSIFICATION" | python3 -m json.tool
        ;;
    template)
        emit_template "$CLASSIFICATION" > "$VERDICT_PATH"
        echo "Wrote template: $VERDICT_PATH"
        echo "Edit tests_accurate + accuracy_rationale, then:"
        echo "  bash scripts/skill-change-critic-gate.sh verify --verdict $VERDICT_PATH --run"
        ;;
    verify)
        verify_verdict "$CLASSIFICATION"
        ;;
esac
