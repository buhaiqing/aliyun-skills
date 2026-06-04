# alicloud-topo-discovery Phase 3: Remaining 13 Resource Types

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) to implement.

**Goal:** Extend export-hcl field mappings to cover all 18 resource types (currently 5/18 after Plan 1).

**Architecture:** Each resource type has its own MappingSpec in `mappings.py` + field-mapping doc + fixture JSON. They share the same FieldMapper, SensitiveMasker, and DependencyInference lib modules.

**Tech Stack:** Same as Phase 1 (Python 3.10+, no new dependencies).

**Spec Ref:** `docs/superpowers/specs/2026-06-04-topo-discovery-upgrade-design.md` §3.2.2

---

## Resource Priority Order

Implement in batches of 3-4 types. Each batch = 1 commit.

### Batch A: Network + Security (4 types, 3 days)
1. NAT Gateway (#5)
2. EIP (Elastic IP, #4)
3. SecurityGroup (#7 — with rules)
4. ACK (Container Service, #9)

### Batch B: Database + Storage (4 types, 3 days)
5. PolarDB (#11)
6. Redis (#12)
7. OSS Bucket (#13)
8. NAS FileSystem (#16)

### Batch C: IAM + Audit + Compute (3 types, 2 days)
9. RAM Role (#10)
10. KMS Key (#14)
11. ActionTrail (#15)

### Batch D: Serverless + Network (2 types, 2 days)
12. FC Service + Function (#17)
13. VPN Connection + SAG (#18)

Total: ~10 working days (within spec's 3-week estimate).

---

## Per-Type Task Template

Each resource type follows the same pattern (12+1 = 13 repetitions):

### For each type `{rt}`:

**Files:**
- Create: `references/field-mappings/{rt}.md` — mapping table
- Create: `tests/fixtures/{rt}.json` — minimal valid Aliyun API response
- Create or modify: `tests/test_resource_mappings.py` — add test class
- Modify: `scripts/lib/mappings.py` — add MAPPINGS[{rt}] entry

**Steps:**
1. Research API response structure (`aliyun {product} Describe{Type} --output json`)
2. Write fixture JSON with representative fields
3. Write field-mapping doc with HCL attribute table
4. Add MappingSpec to mappings.py
5. Add integration test class
6. Run all tests
7. Commit

**Block name convention:** `{rt}_{name_slug}`; stable import ID: `{product}:{region}:{resource_id}`

---

## Detailed MappingSpecs

### Batch A

**NAT Gateway** (`alicloud_nat_gateway`):
- `Name→name`, `Description→description`, `NatType→nat_type`, `InternetChargeType→internet_charge_type`
- Block: `nat_{name_slug}`. Import: `nat:{region}:{nat_gateway_id}`

**EIP** (`alicloud_eip`):
- `Name→name`, `Bandwidth→bandwidth(int)`, `InternetChargeType→internet_charge_type`, `InstanceChargeType→instance_charge_type`
- Block: `eip_{name_slug}`. Import: `eip:{region}:{allocation_id}`

**SecurityGroup** (`alicloud_security_group`):
- `SecurityGroupName→name`, `Description→description`, `SecurityGroupType→security_group_type`
- SecurityGroupRules (separate resource `alicloud_security_group_rule`): `Direction→direction`, `PortRange→port_range`, `SourceCidrIp→cidr_ip`, `Policy→policy`
- Block: `sg_{name_slug}`. Import: `security_group:{region}:{sg_id}`
- Rules: `sg_rule_{sg_name_slug}_{direction}_{port}`. Import: `security_group_rule:{region}:{sg_id}:{rule_id}`

**ACK** (`alicloud_cs_kubernetes`):
- `Name→name`, `ClusterType→cluster_type`, `Version→version`, `VpcId→vpc_id`, `VSwitchIds.VSwitchId[0]→vswitch_ids(list)`, `WorkerNumber→worker_number(int)`
- Block: `ack_{name_slug}`. Import: `cs:{region}:{cluster_id}`

### Batch B

**PolarDB** (`alicloud_polardb_cluster`): similar to RDS pattern.
- `DBClusterDescription→description`, `DBType→db_type`, `DBVersion→db_version`, `DBNodeClass→db_node_class`, `DBNodeStorage→db_node_storage(int)`,

**Redis** (`alicloud_redis_instance`):
- `InstanceName→instance_name`, `InstanceClass→instance_class`, `EngineVersion→engine_version`, `ConnectionDomain→connection_domain`, `Port→port(int)`,

**OSS Bucket** (`alicloud_oss_bucket`):
- `Name→bucket`, `StorageClass→storage_class`, `LocationConstraint→location`,

**NAS** (`alicloud_nas_file_system`):
- `Description→description`, `StorageType→storage_type`, `ProtocolType→protocol_type`,

### Batch C

**RAM Role** (`alicloud_ram_role`):
- `RoleName→name`, `Description→description`, `Arn→arn`, `AssumeRolePolicyDocument→assume_role_policy`,

**KMS Key** (`alicloud_kms_key`):
- `KeyId→key_id`, `KeySpec→key_spec`, `KeyUsage→usage`, `Description→description`, `Origin→origin`,

**ActionTrail** (`alicloud_actiontrail`):
- `Name→name`, `OssBucketName→oss_bucket_name`, `OssKeyPrefix→oss_key_prefix`, `Status→status(bool, active/disabled)`,

### Batch D

**FC** (`alicloud_fc_service` + `alicloud_fc_function`): 2 resources.
- Service: `Name→name`, `Description→description`
- Function: `Name→name`, `Runtime→runtime`, `MemorySize→memory_size(int)`,

**VPN/SAG** (`alicloud_vpn_connection` + `alicloud_sag`):
- VPN: `Name→name`, `LocalSubnet→local_subnet`, `RemoteSubnet→remote_subnet`,
- SAG: `Name→name`, `CidrBlock→cidr_block`,

---

## Verification

```bash
# Per-type: verify specific type
pytest alicloud-topo-discovery/tests/test_resource_mappings.py -k "TestNatMapping" -v

# All types
pytest alicloud-topo-discovery/tests/test_resource_mappings.py -v

# Full suite
pytest alicloud-topo-discovery/tests/ -q --tb=short
```

---

## AC Coverage

| AC | Before | After Phase 3 |
|----|--------|---------------|
| AC-6 Resource type coverage | 5/18 | **18/18** |

## Key Risks

1. **API response variance**: Some APIs return different structures by region/account. Fixtures must represent the most common shape.
2. **OSS bucket info**: Requires different API (`oss GetBucketInfo` not `aliyun oss` CLI). Use a wrapper script.
3. **KMS key material**: `Origin` field may be absent for default keys. Use `required=False` defaults.
4. **FC service+function**: Requires 2 separate Describe calls. The mapper handles one spec per call, so we need 2 MappingSpec entries.