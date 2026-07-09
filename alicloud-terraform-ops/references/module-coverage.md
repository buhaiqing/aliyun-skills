# Module Coverage — Developer Reference

> Manifest spec and extension workflow for NL2HCL module-first generation.
> Agent constraints: [../AGENTS.md](../AGENTS.md) §4.

---

## 1. Problem

NL2HCL and Import use **different HCL strategies**. Without a gate:

- User asks for MongoDB + VPC → only VPC may be generated
- Import supports `mongodb` but NL2HCL has no `addon-mongodb` → silent gap

---

## 2. Manifest — `assets/module-coverage.json`

Each entry key is a Terraform resource type (`alicloud_*`).

| Field | Type | Meaning |
|-------|------|---------|
| `registry_name` | string \| null | Key in `resource_registry.py` |
| `nl2hcl_module` | string \| null | Subdir under `modules/`; `null` = NL2HCL blocked |
| `import_supported` | bool | Import path available |
| `registry_level` | string | `full` / `partial` / `planned` (doc only) |
| `keywords` | string[] | Regex fragments scanned on raw request |
| `note` | string | Optional (e.g. SG bundled in compute-ecs) |

---

## 3. Runtime Gate

`scripts/module_coverage.py`:

```python
report = check_nl2hcl_coverage(intent, request)
if report.must_halt:
    sys.exit(6)  # COVERAGE_GAP
```

Triggered from:

- `nl2hcl_generator.py` — before HCL generation
- `terraform_ops.py create` — HITL create path

### HALT conditions

1. **Keyword without intent** — keyword hit, not in `parse_intent()` output
2. **Intent without module** — `nl2hcl_module` is null

### User-facing remediation (auto-generated)

- Import existing: `terraform_ops import -t <registry_name> -i <id>`
- Add module: follow AGENTS.md §4.2 four-piece checklist
- Manual HCL: outside module-first (discouraged)

---

## 4. Developer Verification

```bash
cd alicloud-terraform-ops/scripts

# Consistency gate (run before every PR touching modules/manifest)
python3 module_coverage.py --verify

# Simulate a request
python3 module_coverage.py --check-request "创建 VPC 和 MongoDB 集群"
# Expect exit 6 + HALT message
```

`--verify` checks:

| Check | Failure example |
|-------|-----------------|
| `nl2hcl_module` dir exists | `addon-foo/main.tf` missing |
| `registry_name` ↔ registry | name not in `_REGISTRY` |
| `RESOURCE_PATTERNS` ↔ manifest | pattern maps to type with `nl2hcl_module: null` |
| `modules/*` referenced | orphan module dir |

---

## 5. Adding a New NL2HCL Module (Example: `addon-mongodb`)

### Step 1 — Module template

```
modules/addon-mongodb/
├── main.tf
├── variables.tf
├── outputs.tf
└── versions.tf
```

### Step 2 — Manifest

```json
"alicloud_mongodb_instance": {
  "registry_name": "mongodb",
  "nl2hcl_module": "addon-mongodb",
  "import_supported": true,
  "keywords": ["mongodb", "mongo", "文档数据库"]
}
```

### Step 3 — `module_catalog.py`

- Extend `plan_modules()` when `alicloud_mongodb_instance` in intent
- Add `render_main_tf()` block or wire through `web-stack`

### Step 4 — `nl2hcl_generator.py`

```python
r"mongodb|mongo|文档数据库": "alicloud_mongodb_instance",
```

### Step 5 — Tests + verify

```bash
python3 module_coverage.py --verify
python3 -m unittest test_module_coverage test_module_first -v
```

---

## 6. Import-Only Resources

Keep `nl2hcl_module: null`. Gate ensures create HALTs; Import uses `resource_registry` PreFlight.

Document in manifest `registry_level: partial` and known_issues in registry.

---

## 7. Coverage Matrix (current)

| Product | NL2HCL module | Import |
|---------|---------------|--------|
| VPC/VSwitch | vpc-network | ✅ |
| ECS/SG | compute-ecs | ✅ |
| RDS/Redis/SLB/NAT/EIP/Disk/Route | addon-* | ✅ |
| MongoDB/OSS/PolarDB | ❌ | ✅ partial |
| Elasticsearch/ESS | ❌ | ❌ planned |

See live matrix: `python3 -c "from resource_registry import get_registry; print(get_registry().generate_support_matrix())"`
