#!/usr/bin/env bash
# Milestone A orchestrator — export trajectories, trainable seed, dataset.
set -euo pipefail

SKILL="${1:-alicloud-ecs-ops}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ALIYUN_SKILLS_ROOT="$ROOT"
DIR="$ROOT/scripts/skill_evolution"

python3 "$DIR/export_trajectories.py" --skill "$SKILL"
python3 "$DIR/build_trainable_seed.py" --skill "$SKILL"
python3 "$DIR/build_dataset.py" --skill "$SKILL"

echo "[SUMMARY] outputs under $ROOT/.runtime/skill-evolution/$SKILL/"
if command -v skillopt >/dev/null 2>&1; then
  echo "[HINT] Optional offline training: see $DIR/README.md"
else
  echo "[HINT] pip install skillopt  # optional for Microsoft SkillOpt training loop"
fi
