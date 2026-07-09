#!/usr/bin/env bash
# Milestone A regression — skill evolution export pipeline.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/scripts/skill_evolution"
python3 -m unittest \
  export_trajectories_test \
  build_dataset_test \
  build_trainable_seed_test \
  benchmark_smoke_test \
  -v
bash -n "$ROOT/scripts/skill_evolution/run_milestone_a.sh"
echo "✅ skill-evolution Milestone A tests passed"
