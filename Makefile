# aliyun-skills — 仓库级维护命令
#
# 运行时产物统一写入 ${SKILLS_DIR}/.runtime/（见 AGENTS.md §13），默认 gitignore。
# 清理入口在本 Makefile，默认 dry-run；真正删除须 make runtime-clean-apply。

SKILLS_DIR ?= $(CURDIR)
export SKILLS_DIR

REPO_CLEANUP := scripts/runtime_cleanup.py

.PHONY: help runtime-layout runtime-clean runtime-clean-apply

help:
	@echo "aliyun-skills — runtime maintenance"
	@echo ""
	@echo "  make runtime-layout          显示 .runtime/terraform-ops/ 布局"
	@echo "  make runtime-clean           预览将清理的运行时目录（dry-run，默认）"
	@echo "  make runtime-clean-apply     实际删除（.runtime/ + 各 skill legacy 路径）"
	@echo ""
	@echo "环境变量: SKILLS_DIR=$(SKILLS_DIR)"

runtime-layout:
	@python3 $(REPO_CLEANUP) --show-layout

runtime-clean:
	@python3 $(REPO_CLEANUP)

runtime-clean-apply:
	@python3 $(REPO_CLEANUP) --apply
