# Changelog

All notable changes to `alicloud-arch-advisor` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.0] - 2026-06-11

### 🔒 Security
- **F-001** Fixed command injection vulnerability in `interactive-wizard.sh` by adding double quotes around all parameter variables in `bash` calls

### ✨ Added
- **Advanced Progress Bar Features**:
  - Nested progress bars (main task + sub-tasks) with `progress_nested_*` functions
  - Progress state persistence and resume capability (`progress_persistence_*`, `progress_resume`)
  - Graphical progress bar with terminal capability detection (iTerm2/TrueColor/256color/basic)
  - Spinner animation (`spinner_start` / `spinner_stop`)
- **Error Handling Module** (`scripts/error-handler.sh`):
  - 12 error type classifications (CREDENTIAL, QUOTA, NETWORK, PERMISSION, etc.)
  - `handle_error` / `handle_warning` functions with structured output
  - `classify_error` for automatic error type detection
  - `retry_operation` with exponential backoff
  - `safe_exec` wrapper for safe command execution
- **Unit Test Framework** (`scripts/test-framework.sh`):
  - 6 assertion types (equals, not_equals, contains, etc.)
  - Test grouping and summary reporting
  - Pass rate calculation
- **Test Suite** (`tests/test-core-functions.sh`):
  - 31 unit tests covering cost estimation, progress bar, error classification, terminal detection, input validation, architecture patterns
  - 100% pass rate

### 🔧 Changed
- **F-002** Enhanced cost estimation in `recommend.sh` with instance type-aware pricing (g6.xlarge, g6.2xlarge, g6.4xlarge, g6.8xlarge, g6.16xlarge, etc.)
- **F-003** Added `GLOBAL_TIMEOUT=1800` (30 minutes) and `timeout` command wrapper in `assess.sh`
- Common.sh now includes 4 major sections: Colors, Logging, Progress Bars (with nested/persistence/graphic), Error Handling

### 📊 Statistics
- New files: 4 (error-handler.sh, test-framework.sh, test-core-functions.sh, test-progress-advanced.sh)
- New functions: 30+ (progress_*, classify_error, handle_error, retry_operation, etc.)
- Lines added: ~1,200
- Test coverage: 31 tests, 100% pass

---

## [1.3.0] - 2026-06-11

### ✨ Added
- Multi-language support (中英文切换) via `scripts/i18n.sh`
- Language detection from `ARCH_ADVISOR_LANG` or `LANG` environment variables
- Translation dictionary for ~80 strings (common, wizard menu, parameters, execution messages, validation, recommend steps)
- `t()` translation function with printf-style argument substitution
- `switch_language` runtime language switcher
- Default language: Chinese (zh_CN), fallback to English (en_US)

---

## [1.2.0] - 2026-06-11

### ✨ Added
- Interactive Wizard (`scripts/interactive-wizard.sh`):
  - Three modes: Architecture Analysis (A), WAF Assessment (B), Recommendation (C)
  - Smart parameter collection with validation
  - Confirmation step before execution
  - 30-minute timeout protection
- Progress bar in `recommend.sh` (7 steps with progress tracking)
- Color UI with ANSI codes (RED, GREEN, YELLOW, BLUE, CYAN)
- Common functions: `progress_start`, `progress_update`, `progress_complete`

### 🔧 Changed
- Component availability validation in `recommend.sh` (Step 4.5)
  - ECS instance type validation
  - RDS class validation
  - Redis instance type validation
  - Automatic fallback to smaller specs

---

## [1.1.0] - 2026-06-11

### 🔧 Changed
- Token efficiency optimization in SKILL.md
  - Mode descriptions simplified
  - Tables compressed
  - Section headers standardized
  - Token budget: ~8000 → ~5000 (-37.5%)

### ✨ Added
- WAF Integration table with 5 pillars (Security, Reliability, Performance, Cost, Efficiency)
- Data source dependency documentation
- Updated Changelog (this file)

---

## [1.0.0] - 2026-06-07

### ✨ Initial Release
- Three operating modes:
  - **Mode A**: Architecture reverse engineering (analysis)
  - **Mode B**: WAF maturity assessment (5-pillar evaluation)
  - **Mode C**: Architecture recommendation (scenario-based blueprints)
- Core scripts:
  - `scripts/common.sh` - Shared utilities
  - `scripts/assess.sh` - Mode A + B execution
  - `scripts/recommend.sh` - Mode C execution
- Reference data:
  - 6 scenario templates (ecommerce, saas, data-platform, microservice, serverless, game)
  - WAF rule engine
  - Architecture pattern detection (single-node, 3-tier, microservice, etc.)
- GCL integration (optional, max_iter=5)

---

## Versioning Strategy

- **Major version (X.0.0)**: Breaking changes, major feature additions
- **Minor version (1.X.0)**: New features, backward-compatible
- **Patch version (1.0.X)**: Bug fixes, documentation updates

## Upgrade Guide

### From 1.3.0 to 1.4.0
- New files added: `error-handler.sh`, `test-framework.sh`, `tests/test-core-functions.sh`
- No breaking changes to existing APIs
- Optional: Run `./tests/test-core-functions.sh` to verify

### From 1.2.0 to 1.3.0
- New file added: `i18n.sh`
- Set `ARCH_ADVISOR_LANG=en_US` to use English
- No breaking changes

### From 1.1.0 to 1.2.0
- New file added: `interactive-wizard.sh`
- No breaking changes to existing CLI usage
