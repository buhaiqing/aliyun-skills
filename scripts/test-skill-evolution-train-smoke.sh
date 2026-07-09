#!/usr/bin/env bash
# SkillOpt train CI smoke — mock rollout + stub reflect; asserts best_skill.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ALIYUN_SKILLS_ROOT="$ROOT"
export SKILL_EVOLUTION_MOCK_ROLLOUT=1

if ! python3 -c "import skillopt" 2>/dev/null; then
  echo "[INFO] installing skillopt for CI smoke..."
  pip3 install --user 'skillopt>=0.1.0'
fi

cd "$ROOT/scripts/skill_evolution"
python3 -m unittest train_smoke_test -v
echo "✅ skill-evolution SkillOpt train CI smoke passed"
