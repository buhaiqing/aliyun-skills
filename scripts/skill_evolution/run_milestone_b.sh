#!/usr/bin/env bash
# Milestone B orchestrator — sync A outputs, run benchmark smoke (mock rollout).
set -euo pipefail

SKILL="${1:-alicloud-ecs-ops}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ALIYUN_SKILLS_ROOT="$ROOT"
DIR="$ROOT/scripts/skill_evolution"
BENCH="$DIR/benchmark/alicloud_ops"
DATASET="$ROOT/.runtime/skill-evolution/$SKILL/dataset.jsonl"
SEED="$ROOT/.runtime/skill-evolution/$SKILL/trainable_seed.md"
INITIAL="$ROOT/.runtime/skill-evolution/$SKILL/initial.md"
SPLITS="$ROOT/.runtime/skill-evolution/$SKILL/splits"

if [[ ! -f "$DATASET" ]]; then
  echo "[INFO] dataset missing — running Milestone A for $SKILL"
  bash "$DIR/run_milestone_a.sh" "$SKILL"
fi

if [[ ! -f "$SEED" ]]; then
  echo "[ERROR] trainable_seed.md not found: $SEED" >&2
  exit 1
fi

mkdir -p "$(dirname "$INITIAL")"
cp "$SEED" "$INITIAL"
echo "[SYNC] $SEED → $INITIAL"

python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '$BENCH')
from dataloader import materialize_skillopt_splits
materialize_skillopt_splits(Path('$DATASET'), Path('$SPLITS'))
print('[SYNC] splits → $SPLITS')
"

export SKILL_EVOLUTION_MOCK_ROLLOUT=1
cd "$DIR"
python3 -m unittest benchmark_smoke_test -v
python3 -m unittest discover -s benchmark/alicloud_ops -p '*_test.py' -v

echo "[SUMMARY] Milestone B smoke passed for $SKILL"
echo "[HINT] bash scripts/test-skill-evolution-train-smoke.sh  # SkillOpt train CI (mock)"
