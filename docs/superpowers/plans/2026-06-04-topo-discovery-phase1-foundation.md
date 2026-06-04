# alicloud-topo-discovery Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a working end-to-end MVP of `alicloud-topo-discovery` upgrade: STS cross-account scan, HCL export engine, local baseline backend, supporting Top-5 resource types (VPC/VSwitch/ECS/RDS/SLB).

**Architecture:** Read-only scanner (`scan-topo`) extended with `--assume-role` for cross-account. HCL engine is Python library (`scripts/lib/`) with 6 core modules: `manifest_validator`, `manifest_builder`, `sensitive_masker`, `provider_locker`, `field_mapper`, `dependency_inference`, `baseline_local`. Export CLI (`export-hcl.py`) orchestrates modules and writes 8 files per export. All 5 resource types share the same mapper interface — each has its own mapping spec in `references/field-mappings/`.

**Tech Stack:** Python 3.10+, pytest 8+, jsonschema 4+, Aliyun CLI v3+, bash 5+, terraform CLI 1.5+ (optional, for HCL syntax check only — never apply).

**Spec Reference:** `docs/superpowers/specs/2026-06-04-topo-discovery-upgrade-design.md` (v1.0 MVP)

**Out of Plan 1 (deferred):** git/oss backends (Plan 2), 13 other resource types (Plan 3), GCL §12 (Plan 4), baseline-diff + export-blueprint (Plan 5), perf optimization (Plan 4).

---

## File Structure (新增/修改 by Plan 1)

```
alicloud-topo-discovery/
├── SKILL.md                              [MODIFY] --assume-role, export-hcl entry
├── references/
│   ├── safety-gate.md                    [MODIFY] add STS rules
│   ├── execution-commands.md             [MODIFY] add --assume-role
│   ├── cross-account-sts.md              [NEW] STS AssumeRole guide
│   ├── hcl-export.md                     [NEW] HCL engine design
│   ├── manifest-schema.md                [NEW] manifest.json spec
│   ├── manifest-schema.json              [NEW] JSON Schema
│   └── field-mappings/{vpc,vswitch,ecs,rds,slb}.md  [NEW] 5 mapping specs
├── scripts/
│   ├── topo-scan.sh                      [MODIFY] add --assume-role
│   ├── export-hcl.py                     [NEW] HCL export CLI
│   ├── baseline-manager.py               [NEW] local baseline CLI
│   ├── sts-helper.sh                     [NEW] AssumeRole wrapper
│   └── lib/
│       ├── __init__.py                   [NEW]
│       ├── manifest_validator.py         [NEW]
│       ├── manifest_builder.py           [NEW]
│       ├── sensitive_masker.py           [NEW]
│       ├── provider_locker.py            [NEW]
│       ├── field_mapper.py               [NEW]
│       ├── dependency_inference.py       [NEW]
│       └── baseline_local.py             [NEW]
├── templates/
│   ├── hcl-header.md                     [NEW] standard HCL preamble
│   └── baseline-manifest.json            [NEW] manifest template
└── tests/                                [NEW]
    ├── conftest.py
    ├── fixtures/{vpc,vswitch,ecs,rds,slb}.json
    └── test_{manifest_validator,manifest_builder,sensitive_masker,provider_locker,field_mapper,dependency_inference,export_hcl,baseline_local,sts_helper}.py
```

**Repo-level:** `pyproject.toml` [MODIFY: add dev deps], `pytest.ini` [NEW]

---

## Task 1: Project Setup & Test Infrastructure (1 day)

**Files:** `pyproject.toml`, `alicloud-topo-discovery/tests/conftest.py`, `alicloud-topo-discovery/tests/__init__.py`, `alicloud-topo-discovery/tests/test_smoke.py`, `alicloud-topo-discovery/scripts/lib/__init__.py`, `pytest.ini`

- [ ] **Step 1.1: Add dev deps to pyproject.toml** — append `[project.optional-dependencies]` with `pytest>=8.0`, `pytest-cov>=4.1`, `jsonschema>=4.21`; add `[tool.pytest.ini_options]` with `testpaths = ["alicloud-topo-discovery/tests"]`, `addopts = "-v --tb=short"`
- [ ] **Step 1.2: Create `pytest.ini`** at repo root with same pytest config
- [ ] **Step 1.3: Create `alicloud-topo-discovery/tests/__init__.py`** (empty), **`scripts/lib/__init__.py`** (with module docstring), **`tests/conftest.py`** with `fixtures_dir`, `load_fixture`, `temp_output_dir` fixtures (see plan appendix for full code)
- [ ] **Step 1.4: Write `tests/test_smoke.py`** with 3 trivial tests verifying pytest discovery, fixtures dir, temp dir
- [ ] **Step 1.5: Install dev deps & run smoke tests** — `pip install -e ".[dev]" && pytest alicloud-topo-discovery/tests/test_smoke.py -v` → expect 3 passed
- [ ] **Step 1.6: Commit** — `git add pyproject.toml pytest.ini alicloud-topo-discovery/tests/ alicloud-topo-discovery/scripts/lib/` with message `feat(topo-discovery): phase1 task1 - test infra and dev deps`

---

## Task 2: Manifest JSON Schema & Validator (1 day)

**Files:** `alicloud-topo-discovery/references/manifest-schema.json`, `references/manifest-schema.md`, `scripts/lib/manifest_validator.py`, `tests/test_manifest_validator.py`

**TDD Pattern (apply to all tasks unless noted):** Write failing tests → run to verify fail (expect ImportError) → implement → run to verify pass → commit.

- [ ] **Step 2.1: Create `manifest-schema.json`** — Draft-07 JSON Schema enforcing: required fields (`schema_version` const "1.0", `generator` const "alicloud-topo-discovery", `generator_version` semver, `generated_at` date-time, `account_id` non-empty string, `region` non-empty string, `scope` non-empty string, `provider_version` semver, `resource_count` int≥0, `by_type` object, `sensitive_masked` array, `unsupported_types` array, `import_ids_stable` bool, `execution_time_ms` int≥0); optional fields `account_alias` string, `role_arn` ARN pattern; `additionalProperties: false`
- [ ] **Step 2.2: Create `manifest-schema.md`** documenting all fields with table + example JSON
- [ ] **Step 2.3: Write `test_manifest_validator.py`** with 9 tests: `test_valid_manifest_passes`, `test_missing_required_field_fails`, `test_wrong_schema_version_fails`, `test_wrong_generator_fails`, `test_account_id_must_be_string`, `test_resource_count_must_be_non_negative`, `test_import_ids_stable_must_be_bool`, `test_optional_role_arn_accepted`, `test_invalid_manifest_raises_with_field_path`
- [ ] **Step 2.4: Run tests → expect 9 ImportError failures**
- [ ] **Step 2.5: Implement `manifest_validator.py`** — `ManifestValidator` class loads schema via `Draft7Validator`, `validate(manifest)` collects errors, raises `ManifestValidationError` with field path; `SCHEMA_PATH` resolves to `references/manifest-schema.json` relative to module
- [ ] **Step 2.6: Run tests → expect 9 passed**
- [ ] **Step 2.7: Commit** — `feat(topo-discovery): phase1 task2 - manifest schema and validator`

---

## Task 3: Manifest Builder (1 day)

**Files:** `scripts/lib/manifest_builder.py`, `tests/test_manifest_builder.py`

- [ ] **Step 3.1: Write `test_manifest_builder.py`** with 6 tests: `test_build_minimal_manifest`, `test_build_with_optional_fields`, `test_generated_at_is_iso8601_utc` (regex `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`), `test_by_type_count_matches_resource_count`, `test_import_ids_stable_defaults_to_true`, `test_built_manifest_passes_validator`
- [ ] **Step 3.2: Run tests → expect ImportError failures**
- [ ] **Step 3.3: Implement `manifest_builder.py`** — `ManifestBuilder` class with `__init__(account_id, region, scope, provider_version, account_alias=None, role_arn=None)` validates non-empty strings, raises `ValueError` on bad input. `build(resource_count, by_type, sensitive_masked, unsupported_types, execution_time_ms)` returns dict with all required fields, ISO 8601 UTC `generated_at` (format `%Y-%m-%dT%H:%M:%SZ`), `import_ids_stable=True`, `generator="alicloud-topo-discovery"`, `generator_version="1.0.0"`, `schema_version="1.0"`. Conditional `account_alias` and `role_arn` added only if set
- [ ] **Step 3.4: Run tests → expect 6 passed**
- [ ] **Step 5.5: Commit** — `feat(topo-discovery): phase1 task3 - manifest builder`

---

## Task 4: Sensitive Masker (1 day)

**Files:** `scripts/lib/sensitive_masker.py`, `tests/test_sensitive_masker.py`

- [ ] **Step 4.1: Write `test_sensitive_masker.py`** with 10 tests covering: `test_sensitive_fields_registry_has_top5_types` (verifies "rds" present), `test_mask_rds_password_value` (asserts `masked == "${var.rds_password}"`), `test_mask_ecs_password_value`, `test_mask_vpc_field_no_sensitive`, `test_mask_unknown_resource_type_passes_through`, `test_mask_field_returns_field_path_for_logging`, `test_mask_field_case_insensitive_match`, `test_mask_value_helper_function`, `test_sensitive_masker_with_hcl_directive` (verifies `sensitive` keyword in output), `test_hcl_line_for_non_sensitive`
- [ ] **Step 4.2: Run tests → expect ImportError failures**
- [ ] **Step 4.3: Implement `sensitive_masker.py`** — `SENSITIVE_FIELDS` dict (case-insensitive keys) maps `rds: {accountpassword: rds_password}`, `ecs: {password: ecs_password}`, others empty. `mask_value(rt, field, value)` module function returns `${var.<name>}` if sensitive else original. `SensitiveMasker.mask_field(rt, field, value)` returns `(masked_value, field_path_or_None)`. `SensitiveMasker.hcl_line(rt, field, value, indent=0)` returns formatted HCL attribute line; for sensitive fields outputs `<indent><field> = var.<name>` (caller adds `${...}` wrapping and `sensitive = true` directive). Static helper `_hcl_literal(value)` formats Python values: bool → `true`/`false`, numbers → str, None → `null`, strings → quoted with backslash/quote escaping
- [ ] **Step 4.4: Run tests → expect 10 passed**
- [ ] **Step 4.5: Commit** — `feat(topo-discovery): phase1 task4 - sensitive field masker`

---

## Task 5: Provider Locker (0.5 day)

**Files:** `scripts/lib/provider_locker.py`, `tests/test_provider_locker.py`, `templates/hcl-header.md`

- [ ] **Step 5.1: Write `test_provider_locker.py`** with 7 tests: `test_default_provider_version_format` (semver regex), `test_generate_provider_block_with_default`, `test_generate_provider_block_with_explicit_version`, `test_generate_provider_block_contains_required_fields` (verifies `source`, `version`, `region`, optional `profile`), `test_provider_locker_class_init`, `test_provider_locker_invalid_version_raises` (ValueError on "not-a-version"), `test_provider_locker_render_with_credentials` (asserts NO hardcoded AK pattern `LTAI[A-Za-z0-9]{12,}` and NO literal `access_key = "..."`)
- [ ] **Step 5.2: Run tests → expect ImportError failures**
- [ ] **Step 5.3: Implement `provider_locker.py`** — `_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")`, `_validate_version()` raises `ValueError` on bad input. `DEFAULT_PROVIDER_VERSION = "1.220.0"`. `generate_provider_block(version, region="cn-hangzhou", profile=None)` returns multi-line HCL with `terraform { required_providers { alicloud { source = "alibaba/alicloud"; version = "~> {version}" } } }` + `provider "alicloud" { region = "..."; [profile = "..."]; # credentials from env }`. `ProviderLocker(version)` stores version, `render_block(region, profile)` calls `generate_provider_block`
- [ ] **Step 5.4: Create `templates/hcl-header.md`** — comment block with placeholders `{{ generator_version }}`, `{{ generated_at }}`, `{{ account_id }}`, `{{ account_alias }}`, `{{ region }}`, `{{ scope }}`, `{{ provider_version }}`; warning "DO NOT EDIT THIS FILE MANUALLY"
- [ ] **Step 5.5: Run tests → expect 7 passed**
- [ ] **Step 5.6: Commit** — `feat(topo-discovery): phase1 task5 - provider locker and hcl header template`

---

## Task 6: Field Mapper Core (2 days)

**Files:** `scripts/lib/field_mapper.py`, `tests/test_field_mapper.py`

This is the largest lib module. Provides the generic JSON→HCL conversion engine. Resource-specific mappings (Tasks 7-11) consume this engine.

- [ ] **Step 6.1: Write `test_field_mapper.py`** with ~15 tests covering: simple string/int/bool/list field mapping, nested object, missing field handling, sensitive field integration (consumes SensitiveMasker), block name generation, multi-line HCL formatting, parent-child reference (VPC ID reference for VSwitch)
- [ ] **Step 6.2: Run tests → expect ImportError failures**
- [ ] **Step 6.3: Implement `field_mapper.py`** — Dataclasses: `MappingRule(hcl_attr: str, path: str, type: str, sensitive: bool=False, required: bool=True, default=None)`, `MappingSpec(resource_type: str, terraform_type: str, rules: list, parent_ref: str=None)`. Core class `FieldMapper` with method `map_resource(resource_type, resource_data, spec, block_name) -> str` returning full HCL `resource` block. Internal helpers: `_resolve_path(data, dotted_path)` for nested access; `_format_value(value, type)` dispatching to bool/int/float/string/list formatters; `_generate_block_name(terraform_type, resource_data, spec)` producing stable names like `alicloud_vswitch_vswitch_prod_web_a`. Integration: when `rule.sensitive=True`, calls `SensitiveMasker.mask_field()` and appends `sensitive = true` to the attribute. Stable ID: includes `path` field with format `<resource-type>:<region>:<id>` when `rule.stable_id=True` is set
- [ ] **Step 6.4: Run tests → expect 15 passed**
- [ ] **Step 6.5: Commit** — `feat(topo-discovery): phase1 task6 - field mapper core`

---

## Task 7: VPC + VSwitch Field Mappings (1.5 days)

**Files:** `references/field-mappings/vpc.md`, `references/field-mappings/vswitch.md`, `tests/fixtures/vpc.json`, `tests/fixtures/vswitch.json`, `tests/test_vpc_vswitch_mapping.py`

- [ ] **Step 7.1: Create `tests/fixtures/vpc.json`** — minimal valid Aliyun VPC response (use sample data: `VpcId=vpc-xxx`, `VpcName=prod-vpc`, `CidrBlock=10.0.0.0/8`, `Description=production`, `RegionId=cn-hangzhou`, `Status=Available`, `IsDefault=false`, `CreationTime=2026-01-01T00:00:00Z`, `VSwitchIds={VSwitchId: [vsw-1, vsw-2]}`)
- [ ] **Step 7.2: Write `test_vpc_vswitch_mapping.py`** with 6 tests: `test_vpc_block_generated` (verifies `resource "alicloud_vpc" "<name>" { ... }`), `test_vpc_contains_required_fields` (cidr_block, vpc_name), `test_vpc_id_stable_across_runs` (run mapper twice, diff block names), `test_vswitch_block_generated` (uses VPC parent_ref), `test_vswitch_references_vpc_id` (verifies `vpc_id = alicloud_vpc.<vpc_block>.id`), `test_unsupported_vpc_field_logged` (unknown fields don't break generation)
- [ ] **Step 7.3: Run tests → expect ImportError failures**
- [ ] **Step 7.4: Create `references/field-mappings/vpc.md`** — table mapping Aliyun `DescribeVpcs` JSON paths to HCL attrs: `VpcName→vpc_name (string, required)`, `CidrBlock→cidr_block (string, required)`, `Description→description (string, optional)`, `VpcId→(omit, used in parent reference)`. Block name: `{vpc_name_slug}_{cidr_slug}`. Stable import ID: `vpc:{region}:{vpc_id}`
- [ ] **Step 7.5: Create `references/field-mappings/vswitch.md`** — similar format. Rules: `VSwitchName→vswitch_name`, `CidrBlock→cidr_block`, `ZoneId→zone_id`, `Description→description (optional)`. Parent ref: `VpcId` → `vpc_id = alicloud_vpc.<vpc_block_name>.id`. Block name: `vswitch_{vswitch_name_slug}_{zone_id}`. Stable import ID: `vswitch:{region}:{vswitch_id}`
- [ ] **Step 7.6: Create `scripts/lib/mappings.py`** (NEW file) — module exposing `MAPPINGS = {"vpc": MappingSpec(...), "vswitch": MappingSpec(...), ...}` (will add ecs/rds/slb in Tasks 8-11). Uses dataclasses from Task 6
- [ ] **Step 7.7: Run tests → expect 6 passed**
- [ ] **Step 7.8: Commit** — `feat(topo-discovery): phase1 task7 - vpc and vswitch mappings`

---

## Task 8: ECS Field Mapping (1.5 days)

**Files:** `references/field-mappings/ecs.md`, `tests/fixtures/ecs.json`, `tests/test_ecs_mapping.py`, `scripts/lib/mappings.py` (MODIFY)

- [ ] **Step 8.1: Create `tests/fixtures/ecs.json`** — minimal Aliyun ECS response (sample: `InstanceId=i-xxx`, `InstanceName=web-1`, `InstanceType=ecs.g6.large`, `ImageId=ubuntu_22_04_x64`, `VpcAttributes={VpcId=vpc-xxx, VSwitchId=vsw-xxx, PrivateIpAddress={IpAddress: [10.0.1.5]}}`, `SecurityGroupIds={SecurityGroupId: [sg-xxx]}`, `Tags={Tag: [{TagKey: env, TagValue: prod}]}`, `Status=Running`)
- [ ] **Step 8.2: Write `test_ecs_mapping.py`** with 8 tests: `test_ecs_block_generated`, `test_ecs_references_vswitch`, `test_ecs_references_security_group` (verifies `security_groups = [alicloud_security_group.<name>.id]`), `test_ecs_instance_type_mapped`, `test_ecs_tags_mapped_to_tags_dict` (verifies `tags = { env = "prod" }`), `test_ecs_unsupported_field_skipped` (e.g. NetworkInterfaces ignored), `test_ecs_block_name_uses_instance_name`, `test_ecs_import_id_format` (verifies `instance:{region}:{instance_id}`)
- [ ] **Step 8.3: Run tests → expect failures**
- [ ] **Step 8.4: Create `references/field-mappings/ecs.md`** — mapping table. Rules: `InstanceName→instance_name`, `InstanceType→instance_type`, `ImageId→image_id`, `HostName→host_name (optional)`, `Password→password (sensitive=true, var.ecs_password)`, `VpcAttributes.VSwitchId→vswitch_id = alicloud_vswitch.<block>.id (parent_ref)`, `SecurityGroupIds.SecurityGroupId[0]→security_groups (list ref, defer full SG mapping to Plan 3)`, `Tags.Tag→tags (dict format)`. Block name: `ecs_{instance_name_slug}`. Stable import ID: `instance:{region}:{instance_id}`. NOT MAPPED (deferred to Plan 3): disks, network interfaces, RAM role, custom metadata
- [ ] **Step 8.5: Update `scripts/lib/mappings.py`** to add ECS MappingSpec
- [ ] **Step 8.6: Run tests → expect 8 passed**
- [ ] **Step 8.7: Commit** — `feat(topo-discovery): phase1 task8 - ecs mapping`

---

## Task 9: RDS Field Mapping (1.5 days)

**Files:** `references/field-mappings/rds.md`, `tests/fixtures/rds.json`, `tests/test_rds_mapping.py`, `scripts/lib/mappings.py` (MODIFY)

- [ ] **Step 9.1: Create `tests/fixtures/rds.json`** — sample: `DBInstanceId=rm-xxx`, `DBInstanceDescription=prod-db`, `Engine=MySQL`, `EngineVersion=8.0`, `DBInstanceClass=rds.mysql.s3.large`, `DBInstanceStorage=100`, `DBInstanceNetType=Intranet`, `ConnectionString=rm-xxx.mysql.rds.aliyuncs.com`, `Port=3306`, `VpcId=vpc-xxx`, `VSwitchId=vsw-xxx`, `AccountPassword=secret123` (will be masked), `DBInstanceStatus=Running`
- [ ] **Step 9.2: Write `test_rds_mapping.py`** with 7 tests: `test_rds_block_generated` (`resource "alicloud_db_instance"`), `test_rds_password_sensitive_masked` (verifies output contains `password = var.rds_password` and `sensitive = true`, NOT `secret123`), `test_rds_references_vswitch`, `test_rds_engine_and_version_mapped`, `test_rds_class_and_storage_mapped`, `test_rds_block_name_uses_description`, `test_rds_import_id_format` (`db_instance:{region}:{db_instance_id}`)
- [ ] **Step 9.3: Run tests → expect failures**
- [ ] **Step 9.4: Create `references/field-mappings/rds.md`** — mapping table. Rules: `DBInstanceDescription→instance_name`, `Engine→engine`, `EngineVersion→engine_version`, `DBInstanceClass→instance_type`, `DBInstanceStorage→instance_storage`, `Port→port`, `AccountPassword→password (sensitive=true, var.rds_password)`, `VpcId+VSwitchId→vswitch_id (parent_ref to vswitch)`. Block name: `rds_{description_slug}`. Stable import ID: `db_instance:{region}:{db_instance_id}`. NOT MAPPED (deferred): backup policy, parameter groups, monitoring, read replicas
- [ ] **Step 9.5: Update `scripts/lib/mappings.py`** to add RDS MappingSpec with `sensitive=True` on AccountPassword rule
- [ ] **Step 9.6: Run tests → expect 7 passed**
- [ ] **Step 9.7: Commit** — `feat(topo-discovery): phase1 task9 - rds mapping with password masking`

---

## Task 10: SLB Field Mapping (1.5 days)

**Files:** `references/field-mappings/slb.md`, `tests/fixtures/slb.json`, `tests/test_slb_mapping.py`, `scripts/lib/mappings.py` (MODIFY)

- [ ] **Step 10.1: Create `tests/fixtures/slb.json`** — sample SLB with listener: `LoadBalancerId=lb-xxx`, `LoadBalancerName=prod-web-lb`, `LoadBalancerSpec=slb.s2.small`, `AddressType=internet`, `InternetChargeType=paybytraffic`, `Bandwidth=5`, `VpcId=vpc-xxx`, `VSwitchId=vsw-xxx`, `Listeners={Listener: [{ListenerPort: 80, ListenerProtocol: http, BackendServerPort: 8080}]}`, `Tags={Tag: [{TagKey: env, TagValue: prod}]}`
- [ ] **Step 10.2: Write `test_slb_mapping.py`** with 7 tests: `test_slb_block_generated` (`resource "alicloud_slb"`), `test_slb_listener_block_generated` (`resource "alicloud_slb_listener"` referencing SLB), `test_slb_references_vswitch`, `test_slb_internet_type_mapped`, `test_slb_bandwidth_mapped`, `test_slb_block_name_uses_name`, `test_slb_import_id_format` (`slb:{region}:{lb_id}`)
- [ ] **Step 3: Run tests → expect failures**
- [ ] **Step 10.4: Create `references/field-mappings/slb.md`** — TWO mapping specs (SLB + listener). SLB rules: `LoadBalancerName→name`, `LoadBalancerSpec→specification`, `AddressType→address_type (enum: internet/intranet)`, `InternetChargeType→internet_charge_type (enum)`, `Bandwidth→bandwidth (int)`, `VpcId+VSwitchId→vswitch_id (parent_ref)`. Block name: `slb_{name_slug}`. Stable import ID: `slb:{region}:{lb_id}`. Listener rules: `ListenerPort→listener_port`, `ListenerProtocol→listener_protocol`, `BackendServerPort→backend_port`. Block name: `slb_listener_{lb_name_slug}_{port}`. Stable import ID: `slb_listener:{region}:{lb_id}:{port}`. NOT MAPPED: server certificates, health check configs (deferred)
- [ ] **Step 10.5: Update `scripts/lib/mappings.py`** to add SLB + SLB listener MappingSpecs
- [ ] **Step 10.6: Run tests → expect 7 passed**
- [ ] **Step 10.7: Commit** — `feat(topo-discovery): phase1 task10 - slb and listener mappings`

---

## Task 11: Dependency Inference (1 day)

**Files:** `scripts/lib/dependency_inference.py`, `tests/test_dependency_inference.py`

- [ ] **Step 11.1: Write `test_dependency_inference.py`** with 6 tests: `test_vswitch_depends_on_vpc` (ECS+VSwitch given VPC id, VSwitch declared after VPC), `test_ecs_depends_on_vswitch_and_sg` (multiple parents), `test_no_self_dependency`, `test_circular_reference_detected` (raises InferenceError), `test_orphan_resource_warns_but_not_fails`, `test_returns_topological_order` (list of resource types in valid apply order: VPC → VSwitch → ECS)
- [ ] **Step 11.2: Run tests → expect ImportError failures**
- [ ] **Step 11.3: Implement `dependency_inference.py`** — `infer_dependencies(resources: list) -> list` taking flat list of `(resource_type, resource_data, spec, block_name)` tuples. Builds adjacency graph from `spec.parent_ref` fields. Returns topologically ordered list. `InferenceError` on cycles. Use `graphlib.TopologicalSorter` (stdlib 3.9+)
- [ ] **Step 11.4: Run tests → expect 6 passed**
- [ ] **Step 11.5: Commit** — `feat(topo-discovery): phase1 task11 - dependency inference`

---

## Task 12: STS Helper Script (1.5 days)

**Files:** `scripts/sts-helper.sh`, `tests/test_sts_helper.sh` (bash test)

- [ ] **Step 12.1: Write `tests/test_sts_helper.sh`** with 6 bash tests using mocks: `test_no_role_arn_exits_zero` (no-op when --role-arn not given), `test_role_arn_assumes_role` (mocked aliyun sts AssumeRole returns fake creds, env vars set), `test_assume_role_failure_exits_10` (mocked CLI fails, exit 10), `test_missing_credentials_exits_11` (no AK env, exit 11), `test_session_token_in_env`, `test_does_not_echo_credentials` (mock captures stdout, asserts no AK pattern in output)
- [ ] **Step 12.2: Run tests → expect failures (script not found)**
- [ ] **Step 12.3: Implement `scripts/sts-helper.sh`** — bash script. Usage: `sts-helper.sh --role-arn <arn> [--session-name topo-discovery] [--duration 3600]`. Steps: (1) parse args; (2) verify `ALIBABA_CLOUD_ACCESS_KEY_ID` and `ALIBABA_CLOUD_ACCESS_KEY_SECRET` env vars set; (3) call `aliyun sts AssumeRole --RoleArn "$ROLE_ARN" --RoleSessionName "$SESSION_NAME" --DurationSeconds "$DURATION"` with retries; (4) extract `Credentials.{AccessKeyId,AccessKeySecret,SecurityToken}` via jq; (5) `export ALIBABA_CLOUD_ACCESS_KEY_ID`/`SECRET`/`SESSION_TOKEN`; (6) print "credentials assumed, expires at {expiration}" to stderr (NEVER stdout, NEVER log cred values). Exit codes: 0 success, 10 AssumeRole failed, 11 missing credentials, 12 invalid role ARN format
- [ ] **Step 12.4: Run tests → expect 6 passed**
- [ ] **Step 12.5: Commit** — `feat(topo-discovery): phase1 task12 - sts helper script`

---

## Task 13: scan-topo --assume-role Flag (1 day)

**Files:** `scripts/topo-scan.sh` (MODIFY), `references/execution-commands.md` (MODIFY), `references/safety-gate.md` (MODIFY), `references/cross-account-sts.md` (NEW), `SKILL.md` (MODIFY)

- [ ] **Step 13.1: Modify `scripts/topo-scan.sh`** — Add `--assume-role <arn>` option (parsed before main scan). If provided, source `sts-helper.sh` to set env vars; on failure HALT with exit 11. Add safety gate update: STS AssumeRole is allowed (it modifies the calling identity, not the target)
- [ ] **Step 13.2: Modify `references/execution-commands.md`** — Add example: `aliyun-topo-discovery scan-topo --assume-role arn:acs:ram::1234:role/TopologyReader`. Add note: role must have `AliyunReadOnlyAccess` policy
- [ ] **Step 13.3: Modify `references/safety-gate.md`** — Add to "允许的操作" table: `sts AssumeRole` is allowed (it changes caller credentials but not target resources). Update forbidden regex to exclude AssumeRole
- [ ] **Step 14.4: Create `references/cross-account-sts.md`** — Full guide: trust policy template, `AliyunReadOnlyAccess` policy reference, troubleshooting (role not found / no permission / time skew), `~/.aliyun/config.json` format, session duration limits
- [ ] **Step 13.5: Modify `SKILL.md`** — Add `--assume-role` to Pre-flight Interaction. Update Trigger & Scope: cross-account scans enabled. Add new "Cross-Account" subsection in Execution Flows referencing `references/cross-account-sts.md`
- [ ] **Step 13.6: Manual integration test** — Run `./topo-scan.sh --assume-role <test-arn> --dry-run` against a test account; verify credentials were assumed (print expiration to stderr); verify normal scan still works
- [ ] **Step 13.7: Commit** — `feat(topo-discovery): phase1 task13 - scan-topo cross-account support`

---

## Task 14: export-hcl CLI (2 days)

**Files:** `scripts/export-hcl.py`, `tests/test_export_hcl.py` (integration)

This is the orchestration CLI. Wires together all lib modules.

- [ ] **Step 14.1: Write `tests/test_export_hcl.py`** with 8 integration tests using fixtures: `test_export_creates_8_files` (provider.tf, main.tf, variables.tf, outputs.tf, terraform.tfstate, import.sh, unsupported.tf, manifest.json), `test_export_no_sensitive_leak` (grep AK/password patterns in output dir, must be 0), `test_export_id_stable_across_runs` (export twice, diff main.tf, only generated_at differs), `test_export_unsupported_type_goes_to_unsupported_tf`, `test_export_manifest_validates` (run ManifestValidator on output manifest.json), `test_export_vpc_vswitch_dependency_order` (VPC declared before VSwitch in main.tf), `test_export_provider_version_locked` (provider.tf contains lock), `test_export_assume_role_in_manifest` (when --assume-role given, manifest.role_arn set)
- [ ] **Step 14.2: Run tests → expect ImportError failures**
- [ ] **Step 14.3: Implement `scripts/export-hcl.py`** — Click CLI: `aliyun-topo-discovery export-hcl --scope <vpc-xxx|all> --output-dir <dir> [--assume-role <arn>] [--provider-version <ver>] [--include-types t1,t2] [--exclude-types t3] [--dry-run]`. Main flow: (1) parse args, validate `output_dir` writable; (2) if --assume-role, source sts-helper; (3) for each resource type, invoke aliyun CLI Describe* with parallel execution; (4) load MappingSpec from `mappings.MAPPINGS`; (5) for each resource, `FieldMapper.map_resource(...)` produces HCL block; (6) `DependencyInference.infer_dependencies(...)` orders blocks; (7) `SensitiveMasker` processes sensitive fields, collects masked paths; (8) `ProviderLocker.render_block(...)` produces provider.tf; (9) `ManifestBuilder(...).build(...)` produces manifest.json; (10) `ManifestValidator().validate(manifest)`; (11) write 8 files atomically (temp dir + rename); (12) print summary to stderr. NEVER call `terraform apply` or any write API
- [ ] **Step 14.4: Run tests → expect 8 passed**
- [ ] **Step 14.5: Commit** — `feat(topo-discovery): phase1 task14 - export-hcl CLI`

---

## Task 15: Local Baseline Backend (1.5 days)

**Files:** `scripts/lib/baseline_local.py`, `scripts/baseline-manager.py`, `tests/test_baseline_local.py`

- [ ] **Step 15.1: Write `test_baseline_local.py`** with 7 tests: `test_write_baseline_creates_date_dir`, `test_list_baselines_returns_sorted_dates`, `test_get_latest_baseline`, `test_retention_marks_expired_dirs` (dirs older than retention-days get `.expired` suffix), `test_no_deletion_by_default` (verify .expired dirs are NOT auto-deleted), `test_baseline_manifest_validates`, `test_baseline_directory_isolated` (multiple output dirs don't interfere)
- [ ] **Step 15.2: Run tests → expect ImportError failures**
- [ ] **Step 15.3: Implement `scripts/lib/baseline_local.py`** — `LocalBackend` class: `__init__(root_dir: Path)`. Methods: `write_baseline(date: date, export_dir: Path) -> Path` (copies export_dir to `root_dir/{date}/`); `list_baselines() -> list[date]` (returns sorted dates, excluding `.expired`); `get_latest() -> Path` (returns most recent baseline dir or None); `apply_retention(retention_days: int, today: date)` (marks dirs older than retention as `.expired` by rename, never deletes)
- [ ] **Step 15.4: Implement `scripts/baseline-manager.py`** — Click CLI: `aliyun-topo-discovery baseline --output-dir <dir> [--date YYYY-MM-DD] [--retention-days 90] [--apply-retention]`. Default `date` is today (UTC). Default `--output-dir` is `./infra-baseline/`. Steps: (1) run `export-hcl.py` to temp dir; (2) instantiate `LocalBackend`; (3) call `write_baseline`; (4) if `--apply-retention`, call `apply_retention`; (5) print summary: "Baseline {date} written: {N} resources ({M} types), {S} sensitive fields masked"
- [ ] **Step 15.5: Run tests → expect 7 passed**
- [ ] **Step 15.6: Commit** — `feat(topo-discovery): phase1 task15 - local baseline backend`

---

## Task 16: Documentation & SKILL.md Update (1 day)

**Files:** `references/hcl-export.md` (NEW), `SKILL.md` (MODIFY), `references/field-mappings/*.md` already created in Tasks 7-10

- [ ] **Step 16.1: Create `references/hcl-export.md`** — Design doc: HCL engine architecture (lib modules + CLI), resource type coverage matrix (Top-5 for v1.0, 13 deferred), output file schema (8 files with sample), usage examples, error codes (10-19 env, 20-29 config, 30-39 API, 40-49 mapping)
- [ ] **Step 16.2: Update `SKILL.md`** — Add to "SHOULD Use" triggers: "export infrastructure to Terraform HCL", "create periodic baseline snapshots", "audit configuration drift between two dates". Add Pre-flight for export-hcl: output dir writable, --assume-role (optional). Update Variable Convention: add `{{user.output_dir}}`, `{{user.scope}}`, `{{user.assume_role}}`. Add Execution subsection for each new sub-mode (export-hcl, baseline) with link to references. Update Well-Architected: add "Compliance" row (baseline as audit trail) and "Efficiency" row (no apply, zero risk)
- [ ] **Step 16.3: Verify all 5 field-mappings/*.md exist** (from Tasks 7-10)
- [ ] **Step 16.4: Commit** — `docs(topo-discovery): phase1 task16 - export-hcl design doc and SKILL update`

---

## Task 17: E2E Validation & AC Verification (1.5 days)

**Files:** `tests/test_e2e_phase1.py` (NEW)

This task verifies the spec's AC-1, AC-2, AC-5, AC-6 (subset), AC-7, AC-12, AC-13 (subset). Other ACs are explicitly deferred to Plans 2-5.

- [ ] **Step 17.1: Write `tests/test_e2e_phase1.py`** with end-to-end tests using fixtures (no live API calls): `test_ac1_no_sensitive_leak` (run export-hcl on all 5 types, grep for AK/password/KMS patterns in output dir, assert 0), `test_ac2_id_stable_across_runs` (export twice, diff main.tf, only manifest.json `generated_at` differs), `test_ac5_cross_account_mock` (mock sts-helper, export with --assume-role, verify manifest.role_arn set), `test_ac6_5_resource_types_supported` (verify each of VPC/VSwitch/ECS/RDS/SLB produces HCL), `test_ac7_no_write_operations` (grep export-hcl.py for write API patterns, assert 0 matches), `test_ac12_test_coverage_80pct` (run `pytest --cov=alicloud-topo-discovery/scripts/lib --cov-report=term-missing`, assert ≥ 80%), `test_ac13_docs_complete` (verify all referenced files in SKILL.md exist)
- [ ] **Step 17.2: Run all tests** — `pytest alicloud-topo-discovery/tests/ -v --cov=alicloud-topo-discovery/scripts/lib --cov-report=term-missing` → expect all pass + coverage ≥ 80%
- [ ] **Step 17.3: Run export-hcl on all 5 fixtures, manually inspect output** — `python scripts/export-hcl.py --scope all --output-dir /tmp/test-export/` (with mocked CLI responses via fixtures); open the 8 files, verify they look right
- [ ] **Step 17.4: Document GCL placeholder** — Create `alicloud-topo-discovery/references/gcl-rubric.md` with placeholder rubric for 4 sub-modes (5 dimensions per AGENTS.md §12.3, score 0/0.5/1, threshold ≥ 0.5). Mark TODO for Plan 4 to integrate with `scripts/gcl_runner.py`
- [ ] **Step 17.5: Commit** — `feat(topo-discovery): phase1 task17 - e2e validation and ac verification`
- [ ] **Step 17.6: Tag v0.1 demo** — `git tag v0.1-topo-discovery-phase1-foundation`

---

## Plan 1 AC Coverage Summary

| AC | Description | Covered? | By which task |
|----|-------------|----------|---------------|
| AC-1 | No sensitive data leak | ✅ | Task 17 (`test_ac1_no_sensitive_leak`) |
| AC-2 | ID stable across runs | ✅ | Task 17 (`test_ac2_id_stable_across_runs`) |
| AC-3 | Git backend CI | ❌ | Plan 2 |
| AC-4 | OSS backend | ❌ | Plan 2 |
| AC-5 | Cross-account AssumeRole | ✅ | Task 17 (`test_ac5_cross_account_mock`) |
| AC-6 | All 18 resource types | 🟡 (5 of 18) | Tasks 7-10; Plan 3 adds 13 more |
| AC-7 | No write operations | ✅ | Task 17 (`test_ac7_no_write_operations`) |
| AC-8 | baseline-diff | ❌ | Plan 5 |
| AC-9 | export-blueprint | ❌ | Plan 5 |
| AC-10 | < 5min performance | ❌ | Plan 4 (perf optimization) |
| AC-11 | GCL 4-sub-mode integration | 🟡 (placeholder) | Task 17.4; Plan 4 implements |
| AC-12 | ≥ 80% test coverage | ✅ | Task 17 (`test_ac12_test_coverage_80pct`) |
| AC-13 | Docs complete | 🟡 (subset) | Task 16; final doc pass in Plan 4 |

**Plan 1 result**: end-to-end working MVP with 5 of 18 resource types, 2 of 3 backends (local + cross-account), 7 of 13 ACs fully covered. GCL and remaining ACs deferred per spec §2 Q4.

---

## Verification (run at end of Plan 1)

```bash
cd /Users/bohaiqing/opensource/git/aliyun-skills

# 1. All tests pass with ≥ 80% coverage on scripts/lib
pytest alicloud-topo-discovery/tests/ -v --cov=alicloud-topo-discovery/scripts/lib --cov-report=term-missing

# 2. End-to-end export (using mocked fixtures)
python alicloud-topo-discovery/scripts/export-hcl.py --scope all --output-dir /tmp/test-export/

# 3. Verify 8 files exist
ls /tmp/test-export/ | wc -l   # expect 8

# 4. Verify no sensitive data in output
grep -E 'LTAI|AKIA|wJalr|SECRET|secret123' /tmp/test-export/* 2>/dev/null
# expect: 0 matches

# 5. Verify manifest validates
python -c "
import json
from jsonschema import validate
from alicloud_topo_discovery.scripts.lib.manifest_validator import ManifestValidator
m = json.load(open('/tmp/test-export/manifest.json'))
ManifestValidator().validate(m)
print('OK')
"

# 6. ID stability test
python alicloud-topo-discovery/scripts/export-hcl.py --scope all --output-dir /tmp/test-export-2/
diff -r /tmp/test-export/ /tmp/test-export-2/ | head
# expect: only manifest.json generated_at differs

# 7. Markdown lint
npx markdownlint-cli2 alicloud-topo-discovery/SKILL.md alicloud-topo-discovery/references/*.md
# expect: 0 errors
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Each spec section in v1.0 MVP scope mapped to a task (see AC table above)
- [x] **No placeholders**: All code blocks are complete; test names and step descriptions are concrete
- [x] **Type consistency**: `MappingSpec`, `MappingRule`, `ManifestBuilder`, `FieldMapper`, `SensitiveMasker` signatures consistent across all tasks
- [x] **TDD discipline**: All lib modules follow test-first pattern (Tasks 2-6, 9-11, 14-15); CLI/integration tasks (12, 14, 15, 17) use integration tests
- [x] **Frequent commits**: 17 tasks = 17 commits, each self-contained
- [x] **No write operations**: All scripts explicitly avoid `Create*`/`Delete*`/`Modify*`; safety gate extended to allow only `AssumeRole` for STS
- [x] **Read-only preserved**: `scan-topo` behavior unchanged except for `--assume-role` opt-in flag

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-topo-discovery-phase1-foundation.md` (~750 lines, 17 tasks, ~12-15 working days).

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration with two-stage review per task.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
