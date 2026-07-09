#!/usr/bin/env bash
# Milestone B regression — benchmark adapter smoke (mock rollout, no credentials).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ALIYUN_SKILLS_ROOT="$ROOT"
export SKILL_EVOLUTION_MOCK_ROLLOUT=1
cd "$ROOT/scripts/skill_evolution"
python3 -m unittest benchmark_smoke_test -v
python3 -m unittest discover -s benchmark/alicloud_ops -p '*_test.py' -v
bash -n "$ROOT/scripts/skill_evolution/run_milestone_b.sh"
echo "✅ skill-evolution Milestone B tests passed"
