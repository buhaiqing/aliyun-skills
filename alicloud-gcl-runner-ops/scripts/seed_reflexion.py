#!/usr/bin/env python3
"""
seed_reflexion.py — Seed Reflexion memory with synthetic GCL trace data.

Generates realistic failure and success patterns, stores them in
.runtime/reflexion/{reflexion.json,success_patterns.json}, and regenerates
docs/failure-patterns.md and docs/success-patterns.md.

Design:
  - Builds patterns directly (not via reflexion_store/success_store per-iteration),
    writing the store atomically so the seed is idempotent: running twice
    produces identical store contents and reports.
  - Reuses gcl_reflexion module functions for store path resolution, hash
    computation, and report generation.
  - Python 3.10+ stdlib only (depends on gcl_reflexion.py in the same directory).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcl_reflexion import (
    _empty_reflexion_store,
    _empty_success_store,
    _now_iso,
    _reflexion_root,
    _save_store,
    _save_success_store,
    compute_command_hash,
    reflexion_report,
    success_report,
)


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

def _build_failure_store() -> dict:
    """Build the failure store with 8 seed patterns across 4 categories.

    Returns a dict ready to pass to _save_store().
    """
    store = _empty_reflexion_store()

    # -- cli_parameter (6 patterns) --
    store["cli_parameter"] = [
        # 1. alicloud-ecs-ops DeleteInstance: MissingParameter
        {
            "category": "cli_parameter",
            "skill": "alicloud-ecs-ops",
            "command": "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxxxx",
            "error": "MissingParameter: The parameter InstanceId is required",
            "root_cause": "Missing required parameter InstanceId (.N suffix needed for RepeatList)",
            "fix": "Add .N suffix: --InstanceId.1 i-bp1xxxxxxxxxxxx; RepeatList params need numbered suffix",
            "count": 5,
            "first_seen": "2026-05-15T10:30:00Z",
            "last_seen": "2026-07-08T16:30:00Z",
            "source": "gcl-runner",
            "git_commit": "a1b2c3d4e5f6789012345678abcdef0123456789",
        },
        # 2. alicloud-rds-ops DeleteDBInstance: InvalidParameter
        {
            "category": "cli_parameter",
            "skill": "alicloud-rds-ops",
            "command": "aliyun rds DeleteDBInstance --DBInstanceId mydb",
            "error": "InvalidParameter: The specified parameter DBInstanceId is not valid",
            "root_cause": "InvalidParameter -- DBInstanceId must follow 'rm-xxxxx' or 'rr-xxxxx' format",
            "fix": "Verify DBInstanceId format via aliyun rds DescribeDBInstances; IDs start with rm-/rr-/pgm-/rdm- etc.",
            "count": 3,
            "first_seen": "2026-05-20T14:00:00Z",
            "last_seen": "2026-07-09T09:45:00Z",
            "source": "gcl-runner",
            "git_commit": "b2c3d4e5f6789012345678abcdef0123456789a",
        },
        # 3. alicloud-ecs-ops CreateInstance: InvalidParameterValue
        {
            "category": "cli_parameter",
            "skill": "alicloud-ecs-ops",
            "command": "aliyun ecs CreateInstance --InstanceType ecs.g6.large --RegionId cn-hangzhou",
            "error": "InvalidParameterValue: The specified InstanceType is not available in this region",
            "root_cause": "InvalidParameterValue -- InstanceType not available in the target region",
            "fix": "Run aliyun ecs DescribeInstanceTypes --RegionId to list available types; choose a valid type for the region",
            "count": 4,
            "first_seen": "2026-03-05T11:30:00Z",
            "last_seen": "2026-07-10T08:00:00Z",
            "source": "gcl-runner",
            "git_commit": "c3d4e5f6789012345678abcdef0123456789ab",
        },
        # 4. alicloud-slb-ops SetBackendServers: MissingParam
        {
            "category": "cli_parameter",
            "skill": "alicloud-slb-ops",
            "command": "aliyun slb SetBackendServers --LoadBalancerId lb-xxx --BackendServers [{}]",
            "error": "MissingParam: The parameter BackendServers is missing or invalid",
            "root_cause": "MissingParam -- BackendServers JSON array format is incorrect",
            "fix": "Wrap BackendServers as JSON string array: --BackendServers '[{\"ServerId\":\"i-xxx\",\"Weight\":100}]'",
            "count": 2,
            "first_seen": "2026-06-01T09:00:00Z",
            "last_seen": "2026-07-05T13:20:00Z",
            "source": "gcl-runner",
            "git_commit": "d4e5f6789012345678abcdef0123456789abc",
        },
        # 5. alicloud-vpc-ops DeleteVpc: ResourceNotFound
        {
            "category": "cli_parameter",
            "skill": "alicloud-vpc-ops",
            "command": "aliyun vpc DeleteVpc --VpcId vpc-unknown",
            "error": "ResourceNotFound: The specified VpcId does not exist in this region",
            "root_cause": "ResourceNotFound -- VpcId not found; may be in a different region or already deleted",
            "fix": "Verify VpcId via aliyun vpc DescribeVpcs --RegionId; check cross-region resource references",
            "count": 3,
            "first_seen": "2026-04-22T16:45:00Z",
            "last_seen": "2026-07-06T11:10:00Z",
            "source": "gcl-runner",
            "git_commit": "e5f6789012345678abcdef0123456789abcd",
        },
        # 6. alicloud-kms-ops ScheduleKeyDeletion: QuotaExceeded
        {
            "category": "cli_parameter",
            "skill": "alicloud-kms-ops",
            "command": "aliyun kms ScheduleKeyDeletion --KeyId mk-xxx --PendingWindowInDays 7",
            "error": "QuotaExceeded: Maximum number of scheduled key deletions exceeded",
            "root_cause": "QuotaExceeded -- too many KMS keys pending deletion simultaneously",
            "fix": "Cancel pending deletions with CancelKeyDeletion, or request quota increase from Alibaba Cloud",
            "count": 2,
            "first_seen": "2026-06-15T10:30:00Z",
            "last_seen": "2026-07-07T15:50:00Z",
            "source": "gcl-runner",
            "git_commit": "f6789012345678abcdef0123456789abcde",
        },
    ]

    # -- runtime (1 pattern: SAFETY_FAIL) --
    store["runtime"] = [
        {
            "category": "runtime",
            "skill": "alicloud-redis-ops",
            "operation": "FlushInstance",
            "failure_pattern": "safety=0 during FlushInstance",
            "root_cause": "Destructive operation flushed all keys without pre-flight confirmation",
            "prevention": "Add pre-flight guard: prompt user confirmation before FlushInstance; require --Force flag",
            "count": 2,
            "first_seen": "2026-05-12T07:00:00Z",
            "last_seen": "2026-06-28T10:15:00Z",
            "source": "gcl-runner",
            "git_commit": "1234567890abcdef1234567890abcdef12345678",
        },
    ]

    # -- max_iter (1 pattern) --
    store["max_iter"] = [
        {
            "category": "max_iter",
            "skill": "alicloud-ecs-ops",
            "operation": "DescribeInstances",
            "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "failing_dimensions": "correctness",
            "best_score": "4.0",
            "low_dimensions": "correctness=0.3",
            "scores": "count=5 sum=4.0",
            "fix": "Review failing dimensions; increase --max-iter or refine operation parameters",
            "count": 3,
            "first_seen": "2026-05-18T13:00:00Z",
            "last_seen": "2026-07-10T06:40:00Z",
            "source": "gcl-runner",
            "git_commit": "234567890abcdef1234567890abcdef123456789",
        },
    ]

    return store


def _build_success_store() -> dict:
    """Build the success pattern store with 4 seed patterns.

    Returns a dict ready to pass to _save_success_store().
    """
    store = _empty_success_store()
    now = _now_iso()

    store["patterns"] = [
        # 1. alicloud-ecs-ops DeleteInstance: hard-won PASS after 3 iters
        {
            "skill": "alicloud-ecs-ops",
            "operation": "DeleteInstance",
            "command_excerpt": "aliyun ecs DeleteInstance --InstanceId.1 i-bp1xxxxxxxxxxxx --Force true",
            "command_hash": compute_command_hash(
                "aliyun ecs DeleteInstance --InstanceId.1 i-bp1xxxxxxxxxxxx --Force true"
            ),
            "capture_reason": "multi_iter",
            "iterations": 3,
            "scores_summary": "correctness=0.7 safety=1.0 idempotency=1.0 traceability=0.8 spec_compliance=1.0",
            "scores_min": 0.7,
            "preflight_had_traps": True,
            "trap_count": 2,
            "hint": "PASS after 3 iterations: InstanceId .N suffix after MissingParameter fix; added Force flag after destructive-op gate",
            "source": "gcl-runner",
            "count": 1,
            "first_seen": now,
            "last_seen": now,
            "execution_path": "control-plane",
        },
        # 2. alicloud-rds-ops CreateDBInstance: scored recovery from 0.5 to 1.0
        {
            "skill": "alicloud-rds-ops",
            "operation": "CreateDBInstance",
            "command_excerpt": (
                "aliyun rds CreateDBInstance --Engine MySQL --EngineVersion 8.0 "
                "--DBInstanceClass mysql.n2.medium.1 --DBInstanceStorage 20"
            ),
            "command_hash": compute_command_hash(
                "aliyun rds CreateDBInstance --Engine MySQL --EngineVersion 8.0 "
                "--DBInstanceClass mysql.n2.medium.1 --DBInstanceStorage 20 --RegionId cn-hangzhou"
            ),
            "capture_reason": "score_recovery",
            "iterations": 2,
            "scores_summary": "correctness=1.0 safety=1.0 idempotency=1.0 traceability=1.0 spec_compliance=0.5",
            "scores_min": 0.5,
            "preflight_had_traps": False,
            "trap_count": 0,
            "hint": "Score recovery 0.5 -> 1.0: Added DBInstanceNetType and SecurityIPList params after spec_compliance critique",
            "source": "gcl-runner",
            "count": 1,
            "first_seen": now,
            "last_seen": now,
            "execution_path": "control-plane",
        },
        # 3. alicloud-slb-ops AddBackendServers: trap-informed pass
        {
            "skill": "alicloud-slb-ops",
            "operation": "AddBackendServers",
            "command_excerpt": (
                "aliyun slb AddBackendServers --LoadBalancerId lb-xxx "
                "--BackendServers '[{\"ServerId\":\"i-xxx\",\"Weight\":100}]'"
            ),
            "command_hash": compute_command_hash(
                "aliyun slb AddBackendServers --LoadBalancerId lb-xxx "
                "--BackendServers '[{\"ServerId\":\"i-xxx\",\"Weight\":100}]'"
            ),
            "capture_reason": "traps_informed",
            "iterations": 1,
            "scores_summary": "correctness=1.0 safety=1.0 idempotency=1.0 traceability=1.0 spec_compliance=1.0",
            "scores_min": 1.0,
            "preflight_had_traps": True,
            "trap_count": 1,
            "hint": "Single-iteration PASS with trap: BackendServers JSON format hint from known traps prevented MissingParam error",
            "source": "gcl-runner",
            "count": 1,
            "first_seen": now,
            "last_seen": now,
            "execution_path": "control-plane",
        },
        # 4. alicloud-ecs-ops CreateSnapshot: multi_iter pass
        {
            "skill": "alicloud-ecs-ops",
            "operation": "CreateSnapshot",
            "command_excerpt": "aliyun ecs CreateSnapshot --DiskId d-xxx --SnapshotName daily-backup --Description 'Daily auto snapshot'",
            "command_hash": compute_command_hash(
                "aliyun ecs CreateSnapshot --DiskId d-xxx --SnapshotName daily-backup "
                "--Description 'Daily auto snapshot'"
            ),
            "capture_reason": "multi_iter",
            "iterations": 2,
            "scores_summary": "correctness=1.0 safety=0.8 idempotency=1.0 traceability=1.0 spec_compliance=1.0",
            "scores_min": 0.8,
            "preflight_had_traps": False,
            "trap_count": 0,
            "hint": "PASS after 2 iterations: DiskId format validated; --Description length under limit; Category=Standard set explicitly",
            "source": "gcl-runner",
            "count": 1,
            "first_seen": now,
            "last_seen": now,
            "execution_path": "control-plane",
        },
    ]

    return store


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    root = _reflexion_root()

    # Resolve repo root from script location.
    scripts_dir = Path(__file__).resolve().parent
    repo_root = scripts_dir.parents[1]  # aliyun-skills/
    fail_docs = repo_root / "docs" / "failure-patterns.md"
    succ_docs = repo_root / "docs" / "success-patterns.md"

    # Override SKILLS_DIR so report generation writes to the correct docs/.
    os.environ.setdefault("SKILLS_DIR", str(repo_root))

    # ---- Clear and seed failure store ----
    fail_store = _build_failure_store()
    _save_store(fail_store, root)
    cli_count = len(fail_store["cli_parameter"])
    rtm_count = len(fail_store["runtime"])
    max_count = len(fail_store["max_iter"])
    print(f"[SEED] Failure store written: {cli_count} cli_parameter, {rtm_count} runtime, {max_count} max_iter")

    # ---- Clear and seed success store ----
    succ_store = _build_success_store()
    _save_success_store(succ_store, root)
    pat_count = len(succ_store["patterns"])
    print(f"[SEED] Success store written: {pat_count} patterns")

    # ---- Regenerate docs ----
    rc1 = reflexion_report(root=root, output_path=str(fail_docs))
    rc2 = success_report(root=root, output_path=str(succ_docs))

    if rc1 == 0 and rc2 == 0:
        print(f"[SEED] Reports regenerated:\n  {fail_docs}\n  {succ_docs}")
        return 0

    print(f"[SEED] Report generation failed (failure={rc1}, success={rc2})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())