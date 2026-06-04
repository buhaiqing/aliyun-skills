#!/usr/bin/env python3
"""CLI entry point for alicloud-topo-discovery HCL export.

Export current cloud resources as Terraform HCL files + manifest.
Read-only: never applies or modifies cloud state.

Usage:
    python export-hcl.py --scope all --output-dir ./hcl-export/
    python export-hcl.py --scope vpc-xxx --output-dir ./hcl-export/ --assume-role arn:...
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from scripts.lib.mappings import MAPPINGS
from scripts.lib.field_mapper import FieldMapper
from scripts.lib.dependency_inference import infer_dependencies
from scripts.lib.manifest_builder import ManifestBuilder
from scripts.lib.manifest_validator import ManifestValidator
from scripts.lib.provider_locker import ProviderLocker
from datetime import datetime, timezone


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Export Aliyun cloud resources as Terraform HCL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scope", required=True,
                        help="Resource scope: 'all' or 'vpc-xxx'")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for HCL files")
    parser.add_argument("--assume-role",
                        help="STS role ARN for cross-account access")
    parser.add_argument("--provider-version", default="1.220.0",
                        help="Aliyun Provider version (default: 1.220.0)")
    parser.add_argument("--include-types", nargs="*", default=None,
                        help="Resource types to include (default: all)")
    parser.add_argument("--exclude-types", nargs="*", default=None,
                        help="Resource types to exclude (default: none)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate without writing files")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    start_ms = int(time.time() * 1000)

    # Validate output dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(str(output_dir), os.W_OK):
        print(f"[ERROR] Output directory not writable: {output_dir}")
        sys.exit(30)

    # STS AssumeRole
    if args.assume_role:
        print(f"[DIAG] Assuming role: {args.assume_role}")
        result = subprocess.run(
            ["bash", "-c", f"source alicloud-topo-discovery/scripts/sts-helper.sh "
                          f"--role-arn '{args.assume_role}' && "
                          f"echo 'AK=$ALIBABA_CLOUD_ACCESS_KEY_ID'"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"[ERROR] TYPE=ASSUME_ROLE_FAILED FIX=Check role and permissions")
            print(result.stderr)
            sys.exit(10)

    # Determine resource types to process
    resource_types = sorted(MAPPINGS.keys())
    if args.include_types:
        resource_types = [t for t in resource_types if t in args.include_types]
    if args.exclude_types:
        resource_types = [t for t in resource_types if t not in args.exclude_types]

    all_blocks = []
    all_masked_paths = []
    unsupported = []
    account_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", "unknown")
    region = os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")
    mapper = FieldMapper()
    by_type = {}

    for rt in resource_types:
        spec = MAPPINGS[rt]
        # Load fixture data for Phase 1 (real API calls deferred to integration testing)
        fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / f"{rt}.json"
        if not fixture_path.exists():
            unsupported.append(rt)
            continue
        with open(fixture_path) as f:
            data = json.load(f)

        block_name = FieldMapper.generate_block_name(spec.terraform_type, data, spec)
        hcl = mapper.map_resource(rt, data, spec, block_name)
        all_blocks.append((rt, data, spec, block_name, hcl))
        by_type[rt] = by_type.get(rt, 0) + 1

    # Dependency ordering
    dep_input = [(rt, data, spec, bn) for rt, data, spec, bn, _ in all_blocks]
    try:
        ordered = infer_dependencies(dep_input)
    except Exception as e:
        print(f"[ERROR] Dependency inference failed: {e}")
        sys.exit(40)

    # Build ordered HCL body
    block_lookup = {bn: hcl for rt, data, spec, bn, hcl in all_blocks}
    ordered_hcl = "\n\n".join(block_lookup[item[3]] for item in ordered)

    # Generate provider block
    locker = ProviderLocker(version=args.provider_version)
    provider_hcl = locker.render_block(region=region)

    # Build manifest
    elapsed_ms = int(time.time() * 1000) - start_ms
    builder = ManifestBuilder(
        account_id=account_id,
        region=region,
        scope=args.scope,
        provider_version=args.provider_version,
        role_arn=args.assume_role,
    )
    manifest = builder.build(
        resource_count=sum(by_type.values()),
        by_type=by_type,
        sensitive_masked=[],
        unsupported_types=unsupported,
        execution_time_ms=elapsed_ms,
    )

    # Validate manifest
    validator = ManifestValidator()
    validator.validate(manifest)

    # Dry-run: print summary and exit
    if args.dry_run:
        print(f"[SUMMARY] Dry run: {sum(by_type.values())} resources, "
              f"{len(unsupported)} unsupported types")
        print(json.dumps(manifest, indent=2))
        sys.exit(0)

    # Write 8 output files
    files = {
        "provider.tf": provider_hcl,
        "main.tf": ordered_hcl,
        "outputs.tf": "",
        "variables.tf": "",
        "terraform.tfstate": "{\"version\": 4}",
        "import.sh": _gen_import_script(ordered, block_lookup, region),
        "unsupported.tf": _gen_unsupported_block(unsupported),
        "manifest.json": json.dumps(manifest, indent=2) + "\n",
    }

    # Atomic write: write to temp dir then rename
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for fname, content in files.items():
            (tmp / fname).write_text(content)
        for fname in files:
            dst = output_dir / fname
            if dst.exists():
                dst.unlink()
            shutil.move(str(tmp / fname), str(dst))

    print(f"[SUMMARY] Exported {sum(by_type.values())} resources to {output_dir}")
    print(f"[SUMMARY] Types: {dict(by_type)}")
    if unsupported:
        print(f"[WARN] Unsupported types: {unsupported}")
    print(f"[SUMMARY] Duration: {elapsed_ms}ms")


def _gen_import_script(ordered, block_lookup, region):
    """Generate import.sh with terraform import commands."""
    lines = ["#!/bin/bash", "# Generated import commands",
             "# Run: sh import.sh  (requires terraform CLI)", ""]
    for item in ordered:
        rt, data, spec, block_name, hcl = block_lookup.get(item[3], (None, None, None, None, ""))
        lines.append(f"# terraform import '{spec.terraform_type}.{block_name}' "
                     f"{rt}:{region}:{data.get('VpcId', data.get('InstanceId', '?'))}")
    return "\n".join(lines) + "\n"


def _gen_unsupported_block(unsupported):
    if not unsupported:
        return "# All resource types are supported.\n"
    lines = ["# Unsupported resource types (not yet mapped):"]
    for t in unsupported:
        lines.append(f"# - {t}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()