# aliyun-skills — 仓库级维护命令
#
# 运行时产物统一写入 ${SKILLS_DIR}/.runtime/（见 AGENTS.md §13），默认 gitignore。
# 清理入口在本 Makefile，默认 dry-run；真正删除须 make runtime-clean-apply。

SKILLS_DIR ?= $(CURDIR)
export SKILLS_DIR

REPO_CLEANUP := scripts/runtime_cleanup.py
VALIDATE_SCRIPT := scripts/validate_all_skills.py
GCL_SCRIPTS := alicloud-gcl-runner-ops/scripts
# Layer 3 Doctor ephemeral work dir (gitignored under .runtime/)
DOCTOR_WORK := $(SKILLS_DIR)/.runtime/doctor/work
DOCTOR_SINCE_DAYS ?= 7
DOCTOR_SKILL ?=
DOCTOR_OP ?=
SINCE_DAYS ?= 7
SINCE_MINUTES ?=
SESSION_ID ?=
FORMAT ?=
OUTPUT ?=
LANGFUSE_TOKEN_SCRIPT ?= python3 scripts/langfuse_token_report.py
LANGFUSE_TOKEN_ENV_FILE ?= LANGFUSE_ENV_FILE=.env

export ALIYUN_SKILLS_ROOT := $(SKILLS_DIR)

SKILL ?= alicloud-ecs-ops

.PHONY: help lint lint-fix test test-coverage test-integration validate fmt build dev-up clean \
        runtime-layout runtime-clean runtime-clean-apply \
        runtime-clean-memory-fixtures runtime-clean-memory-fixtures-apply \
        memory-maintain memory-maintain-apply \
        doctor doctor-history doctor-weekly doctor-weekly-apply \
        docker-build docker-dev docker-test ci \
        skill-evolution-a skill-evolution-b skill-evolution-all

# ===========================================
# Help
# ===========================================
help:
	@echo "aliyun-skills — Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make lint              Lint all SKILL.md files"
	@echo "  make lint-fix          Auto-fix lint errors where possible"
	@echo "  make test              Run all tests (Python unittest + pytest)"
	@echo "  make test-coverage     Run tests with coverage report"
	@echo "  make validate          Validate all skill directory structures"
	@echo "  make validate-strict   Validate with warnings as errors"
	@echo "  make fmt               Format all code (Python + Go)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build      Build all Docker images"
	@echo "  make docker-dev        Start development container"
	@echo "  make docker-test       Run tests in Docker container"
	@echo ""
	@echo "CI/CD:"
	@echo "  make ci                Run full CI pipeline locally"
	@echo ""
	@echo "Runtime Cleanup:"
	@echo "  make runtime-layout    Show .runtime/ layout"
	@echo "  make runtime-clean     Preview cleanup (dry-run)"
	@echo "  make runtime-clean-apply  Execute cleanup"
	@echo "  make memory-maintain      Layer 1+2 TTL + L1→L2 promote + trace TTL (dry-run)"
	@echo "  make memory-maintain-apply  Layer 1+2 TTL + L1→L2 promote + trace TTL (apply)"
	@echo "      GCL_REFLEXION_REPORT_ON_MAINTAIN=true  optional: regenerate failure-patterns.md + success-patterns.md"
	@echo "  make runtime-clean-memory-fixtures        Preview memory fixture purge (dry-run)"
	@echo "  make runtime-clean-memory-fixtures-apply  Execute memory fixture purge"
	@echo ""
	@echo "Layer 3 Doctor (manual):"
	@echo "  make doctor DOCTOR_SKILL=alicloud-ecs-ops [DOCTOR_OP=DeleteInstance]"
	@echo "      R2 read-only: Layer 1+2+3 pre-flight slots (no writes)"
	@echo "  make doctor-history DOCTOR_SKILL=alicloud-ecs-ops [DOCTOR_OP=...]"
	@echo "      Layer 3 only: strategy_retrieve JSON from docs/strategy-baseline.json"
	@echo "  make doctor-weekly              Preview weekly review (dry-run, no writes)"
	@echo "  make doctor-weekly-apply        Full local weekly (writes baseline + report + token rollup)"
	@echo ""
	@echo "Langfuse Token Consumption:"
	@echo "  make langfuse-token-report SINCE_DAYS=7"
	@echo "      Pull traces from Langfuse, aggregate by sessionID (default: last 7 days)"
	@echo "  make langfuse-token-report SESSION_ID=sess-xxx SINCE_DAYS=7"
	@echo "      Drill down on a single sessionID"
	@echo ""
	@echo ""
	@echo "Skill Evolution:"
	@echo "  make skill-evolution-a     Run Milestone A (export trajectories + dataset)"
	@echo "  make skill-evolution-b     Run Milestone B (benchmark smoke test)"
	@echo "  make skill-evolution-all   Run A + B end-to-end (default SKILL=$(SKILL))"
	@echo "      SKILL=alicloud-rds-ops  Override target skill"


# ===========================================
# Linting
# ===========================================
lint:
	@echo "==> Linting SKILL.md files..."
	@npx markdownlint-cli2 "alicloud-*/SKILL.md" || true

lint-fix:
	@echo "==> Auto-fixing lint errors..."
	@npx markdownlint-cli2-fix "alicloud-*/SKILL.md" || true

# ===========================================
# Testing
# ===========================================
test:
	@echo "==> Running GCL runner tests..."
	@cd alicloud-gcl-runner-ops/scripts && python3 -m unittest gcl_runner_test -v
	@echo ""
	@echo "==> Running topo-discovery tests (if pytest available)..."
	@cd alicloud-topo-discovery && python3 -m pytest tests/ -v --tb=short 2>/dev/null || echo "pytest not available, skipping"
	@echo ""
	@echo "==> Running shared product-skill doc/contract tests..."
	@python3 -m pytest scripts/skill_docs_test.py -v --tb=short
	@echo ""
	@echo "==> Running wrapper-first integration + doc-compliance gates..."
	@$(MAKE) test-integration

test-coverage:
	@echo "==> Running tests with coverage..."
	@cd alicloud-topo-discovery && pytest --cov=scripts --cov-report=html --cov-report=term-missing || true

# ===========================================
# Wrapper-First Integration & Doc-Compliance Gates
# ===========================================
# GCL golden gate: a REAL wrapper must emit a trace carrying the 4 mandatory
# signals (trace_id/session_id/user_id/llm_usage), every wrapper-skill SKILL.md
# must declare the MANDATORY wrapper-first rule, and the rollup golden suite
# (incl. G6) must pass.
test-integration:
	@echo "==> Integration: real wrapper emits 4-signal trace..."
	@bash scripts/test-wrapper-first-integration.sh
	@echo ""
	@echo "==> Doc-compliance: every wrapper-skill declares MANDATORY wrapper-first..."
	@bash scripts/validate-wrapper-first-docs.sh
	@echo ""
	@echo "==> Wrapper-coverage audit: no traces escape the wrapper (CI closure)..."
	@rm -rf "$(CURDIR)/.runtime/audit-ci" && mkdir -p "$(CURDIR)/.runtime/audit-ci"
	@bash scripts/audit-wrapper-coverage.sh "$(CURDIR)/.runtime/audit-ci"
	@echo ""
	@echo "==> Rollup golden tests (G1-G6)..."
	@bash scripts/test-token-rollup.sh
	@echo "==> Langfuse reporting: 4-signal trace reaches Langfuse (skips if no creds)..."
	@$(MAKE) langfuse-token-report-test
# Separate target for test-integration gate; loads .env so Langfuse creds are available.
langfuse-token-report-test:
	@$(LANGFUSE_TOKEN_ENV_FILE) bash scripts/test-langfuse-reporting.sh

# ===========================================
# Validation
# ===========================================
validate:
	@echo "==> Validating skill structures..."
	@python3 $(VALIDATE_SCRIPT)

validate-strict:
	@echo "==> Validating skill structures (strict mode)..."
	@python3 $(VALIDATE_SCRIPT) --strict

# ===========================================
# Formatting
# ===========================================
fmt:
	@echo "==> Formatting Python code..."
	@ruff format . 2>/dev/null || echo "ruff not installed, skipping Python format"
	@echo "==> Formatting Go code..."
	@find . -name "*.go" -exec gofmt -w {} \; 2>/dev/null || echo "gofmt not available, skipping Go format"

# ===========================================
# Docker
# ===========================================
docker-build:
	@echo "==> Building Docker images..."
	@docker build --target runtime -t aliyun-skills:runtime .
	@docker build --target dev -t aliyun-skills:dev .
	@docker build --target agent -t aliyun-skills:agent .

docker-dev:
	@echo "==> Starting development environment..."
	@docker compose --profile dev up -d
	@echo "Container 'aliyun-skills-dev' is running. Attach with:"
	@echo "  docker exec -it aliyun-skills-dev /bin/bash"

docker-test:
	@echo "==> Running tests in Docker..."
	@docker compose --profile test run --rm test

# ===========================================
# CI Pipeline (Local)
# ===========================================
ci: lint test validate docker-build
	@echo "==> CI pipeline completed"

# ===========================================
# Runtime Cleanup
# ===========================================
runtime-layout:
	@python3 $(REPO_CLEANUP) --show-layout

runtime-clean:
	@python3 $(REPO_CLEANUP)

runtime-clean-apply:
	@python3 $(REPO_CLEANUP) --apply

memory-maintain:
	@python3 $(REPO_CLEANUP) --maintain-memory

memory-maintain-apply:
	@python3 $(REPO_CLEANUP) --maintain-memory --apply

# Selective: remove test-fixture entries from .runtime/memory/ without
# touching real wrapper-lite / GCL traces (identified by trace_path
# starting with /var/folders/). Use this if a test leaked fixture data
# past the _GCLRunnerMemoryIsolated mixin.
runtime-clean-memory-fixtures:
	@python3 $(REPO_CLEANUP) --purge-memory-fixtures

runtime-clean-memory-fixtures-apply:
	@python3 $(REPO_CLEANUP) --purge-memory-fixtures --apply

# ===========================================
# Langfuse Token Consumption Report
# Pulls traces from Langfuse, aggregates by sessionID.
# Requires LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY (set in .env).
# Usage:
#   make langfuse-token-report SINCE_DAYS=7
#   make langfuse-token-report SESSION_ID=sess-xxx SINCE_DAYS=30
#   make langfuse-token-report FORMAT=json OUTPUT=report.json SINCE_DAYS=30
# ===========================================

langfuse-token-report:
	@# Show built-in help when no time window is given (origin=file means Makefile default)
	@if [ "$(origin SINCE_DAYS)" = "file" ] && [ "$(origin SINCE_MINUTES)" = "file" ] && [ "$(origin FROM_DATE)" = "file" ]; then \
		echo "Usage:"; \
		echo "  make langfuse-token-report SINCE_DAYS=7"; \
		echo "  make langfuse-token-report SESSION_ID=sess-xxx SINCE_DAYS=7"; \
		echo "  make langfuse-token-report FORMAT=json OUTPUT=report.json SINCE_DAYS=30"; \
		echo ""; \
		echo "Options:"; \
		echo "  SINCE_DAYS=N       Last N days (default: 7)"; \
		echo "  SINCE_MINUTES=N    Last N minutes (overrides SINCE_DAYS)"; \
		echo "  FROM_DATE=YYYY-MM-DD   Start date (overrides SINCE_DAYS/SINCE_MINUTES)"; \
		echo "  TO_DATE=YYYY-MM-DD     End date"; \
		echo "  SESSION_ID=xxx     Drill down on a single sessionID"; \
		echo "  FORMAT=json|table  Output format (default: table)"; \
		echo "  OUTPUT=file        Write output to file"; \
		echo ""; \
		echo "Aggregation dimensions: session_id, skill, user_id"; \
		echo "Metrics: trace_count, prompt_tokens, completion_tokens, total_tokens"; \
		echo ""; \
		echo "Requires: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY in .env"; \
		exit 0; \
	fi
	@if [ "x$(SESSION_ID)" != "x" ]; then \
		echo "==> Drilling down on session_id=$(SESSION_ID) (since=$(or $(SINCE_MINUTES),$(SINCE_DAYS))$(if $(SINCE_MINUTES),min,d))..."; \
		$(LANGFUSE_TOKEN_ENV_FILE) $(LANGFUSE_TOKEN_SCRIPT) session \
			--session-id "$(SESSION_ID)" \
			$(if $(SINCE_MINUTES),--since-minutes $(SINCE_MINUTES),--since-days $(or $(SINCE_DAYS),7)); \
	else \
		echo "==> Aggregating token usage by sessionID..."; \
		$(LANGFUSE_TOKEN_ENV_FILE) $(LANGFUSE_TOKEN_SCRIPT) pull \
			$(if $(SINCE_MINUTES),--since-minutes $(SINCE_MINUTES),--since-days $(or $(SINCE_DAYS),7)) \
			$(if $(OUTPUT),--output $(OUTPUT),) \
			$(if $(FORMAT),--format $(FORMAT),); \
	fi

# ===========================================
# Local Token Session Report
# ===========================================

local-token-report:
	@# Show help when no time window is given (origin=file = Makefile default, not user-overridden)
	@if [ "$(origin SINCE_DAYS)" = "file" ] && [ "$(origin SINCE_MINUTES)" = "file" ]; then \
		echo "Usage:"; \
		echo "  make local-token-report SINCE_DAYS=7"; \
		echo "  make local-token-report SINCE_MINUTES=120"; \
		echo "  make local-token-report SINCE_DAYS=30 FORMAT=json OUTPUT=report.json"; \
		echo ""; \
		echo "Options:"; \
		echo "  SINCE_DAYS=N       Last N days (default: 7)"; \
		echo "  SINCE_MINUTES=N    Last N minutes (overrides SINCE_DAYS)"; \
		echo "  FORMAT=json|table  Output format (default: table)"; \
		echo "  OUTPUT=file        Write JSON output to file"; \
		echo ""; \
		echo "Aggregation dimensions: session_id, skill, user_id"; \
		echo "Metrics: trace_count, prompt_tokens, completion_tokens, total_tokens"; \
		echo ""; \
		echo "Data source: .runtime/token/cache/normalized-records.jsonl"; \
		echo "  (auto-runs rollup if cache does not exist)"; \
		exit 0; \
	fi
	@echo "==> Aggregating local token usage by sessionID..."
	@python3 scripts/token_rollup.py local-token-report \
		$(if $(SINCE_MINUTES),--since-minutes $(SINCE_MINUTES),--since-days $(or $(SINCE_DAYS),7)) \
		$(if $(FORMAT),--format $(FORMAT),) \
		$(if $(OUTPUT),--output $(OUTPUT),)


# ===========================================
# Layer 3 Doctor (manual local entrypoints)
# Mirrors .github/workflows/doctor-weekly.yml for IDE / CLI use.
# ===========================================

doctor:
	@test -n "$(DOCTOR_SKILL)" || (echo "Usage: make doctor DOCTOR_SKILL=alicloud-ecs-ops [DOCTOR_OP=DeleteInstance]" >&2; exit 1)
	@python3 $(GCL_SCRIPTS)/memory_preflight.py \
		--skill "$(DOCTOR_SKILL)" \
		$(if $(DOCTOR_OP),--operation "$(DOCTOR_OP)",) \
		--skills-root "$(SKILLS_DIR)" \
		--format slots

doctor-history:
	@test -n "$(DOCTOR_SKILL)" || (echo "Usage: make doctor-history DOCTOR_SKILL=alicloud-ecs-ops [DOCTOR_OP=DeleteInstance]" >&2; exit 1)
	@python3 $(GCL_SCRIPTS)/gcl_strategy.py retrieve \
		--skill "$(DOCTOR_SKILL)" \
		$(if $(DOCTOR_OP),--operation "$(DOCTOR_OP)",)

doctor-weekly:
	@mkdir -p "$(DOCTOR_WORK)"
	@echo "==> Layer 3 weekly preview (dry-run, since=$(DOCTOR_SINCE_DAYS)d)"
	@python3 $(GCL_SCRIPTS)/git_collect.py \
		--since-days $(DOCTOR_SINCE_DAYS) \
		--repo-root "$(SKILLS_DIR)" \
		--output "$(DOCTOR_WORK)/git_signals.json"
	@python3 $(GCL_SCRIPTS)/gcl_strategy.py weekly \
		--since-days $(DOCTOR_SINCE_DAYS) \
		--repo-root "$(SKILLS_DIR)"

doctor-weekly-apply:
	@mkdir -p "$(DOCTOR_WORK)"
	@echo "==> Layer 3 weekly review (apply, since=$(DOCTOR_SINCE_DAYS)d)"
	@$(MAKE) memory-maintain-apply
	@if [ -f "$(SKILLS_DIR)/.runtime/reflexion/reflexion.json" ]; then \
		python3 $(GCL_SCRIPTS)/gcl_reflexion.py report \
			--reflexion-root "$(SKILLS_DIR)/.runtime/reflexion"; \
	fi
	@python3 $(GCL_SCRIPTS)/gcl_strategy.py rollup \
		--apply --since-days $(DOCTOR_SINCE_DAYS) --repo-root "$(SKILLS_DIR)"
	@python3 scripts/token_rollup.py rollup \
		--apply --since-days $(DOCTOR_SINCE_DAYS) --repo-root "$(SKILLS_DIR)"
	@python3 scripts/token_rollup.py maintain \
		--apply --repo-root "$(SKILLS_DIR)"
	@python3 $(GCL_SCRIPTS)/git_collect.py \
		--since-days $(DOCTOR_SINCE_DAYS) \
		--repo-root "$(SKILLS_DIR)" \
		--output "$(DOCTOR_WORK)/git_signals.json"
	@python3 $(GCL_SCRIPTS)/gcl_strategy.py weekly \
		--apply --since-days $(DOCTOR_SINCE_DAYS) --repo-root "$(SKILLS_DIR)"
	@python3 $(GCL_SCRIPTS)/strategy_synthesize.py \
		--baseline "$(SKILLS_DIR)/docs/strategy-baseline.json"
	@python3 $(GCL_SCRIPTS)/gcl_strategy.py report \
		--baseline "$(SKILLS_DIR)/docs/strategy-baseline.json" \
		--output "$(SKILLS_DIR)/docs/strategy-report.md"
	@echo "==> Done. Review docs/strategy-report.md (commit manually if desired)."

# ===========================================
# Skill Evolution (Microsoft SkillOpt flywheel)
# ===========================================
# Milestone A: export trajectories + build trainable seed + dataset
skill-evolution-a:
	@echo "==> Running Milestone A for $(SKILL)..."
	@bash scripts/skill_evolution/run_milestone_a.sh $(SKILL)

# Milestone B: sync initial.md + materialize splits + benchmark smoke test
skill-evolution-b:
	@echo "==> Running Milestone B for $(SKILL)..."
	@bash scripts/skill_evolution/run_milestone_b.sh $(SKILL)

# End-to-end: A then B
skill-evolution-all: skill-evolution-a skill-evolution-b
	@echo "==> Milestone A + B completed for $(SKILL)"
	@echo "    Outputs: .runtime/skill-evolution/$(SKILL)/"

# ===========================================
# Build (Legacy alias)
# ===========================================
build: docker-build
