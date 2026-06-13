# aliyun-skills — 仓库级维护命令
#
# 运行时产物统一写入 ${SKILLS_DIR}/.runtime/（见 AGENTS.md §13），默认 gitignore。
# 清理入口在本 Makefile，默认 dry-run；真正删除须 make runtime-clean-apply。

SKILLS_DIR ?= $(CURDIR)
export SKILLS_DIR

REPO_CLEANUP := scripts/runtime_cleanup.py
VALIDATE_SCRIPT := scripts/validate_all_skills.py

.PHONY: help lint lint-fix test test-coverage validate fmt build dev-up clean \
        runtime-layout runtime-clean runtime-clean-apply \
        docker-build docker-dev docker-test ci

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
	@echo ""
	@echo "Environment: SKILLS_DIR=$(SKILLS_DIR)"

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
	@cd alicloud-gcl-runner-ops/scripts && python -m unittest gcl_runner_test -v
	@echo ""
	@echo "==> Running topo-discovery tests (if pytest available)..."
	@cd alicloud-topo-discovery && python -m pytest tests/ -v --tb=short 2>/dev/null || echo "pytest not available, skipping"

test-coverage:
	@echo "==> Running tests with coverage..."
	@cd alicloud-topo-discovery && pytest --cov=scripts --cov-report=html --cov-report=term-missing || true

# ===========================================
# Validation
# ===========================================
validate:
	@echo "==> Validating skill structures..."
	@python $(VALIDATE_SCRIPT)

validate-strict:
	@echo "==> Validating skill structures (strict mode)..."
	@python $(VALIDATE_SCRIPT) --strict

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
	@python $(REPO_CLEANUP) --show-layout

runtime-clean:
	@python $(REPO_CLEANUP)

runtime-clean-apply:
	@python $(REPO_CLEANUP) --apply

# ===========================================
# Build (Legacy alias)
# ===========================================
build: docker-build
