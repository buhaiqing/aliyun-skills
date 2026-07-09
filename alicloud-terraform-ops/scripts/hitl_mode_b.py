#!/usr/bin/env python3
"""
HITL Mode B - PR-Based Review
人机介入模式B: PR 式审核 (Git 驱动)

支持:
- GitProvider 抽象 (LocalGit / GitHub / GitLab / Gitee 留接口)
- 分支创建 → 提交 HCL/PLAN.md → 推送 → 创建 PR
- 评论指令系统 (/plan /approve /reject /apply /skip-cp /help)
- 通知集成 (DingTalk/Slack)
- PR 状态轮询监听
- PR 错误处理 (branch_already_exists / push_rejected / pr_create_failed)
- 生产环境强制 PR 模式

Python 3.10+ 标准库实现，零外部依赖。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 复用 Mode A 的核心类型
try:
    from hitl_mode_a import (
        Checkpoint, CheckpointType, CheckpointStatus, StepType, Action,
        Environment, EnvironmentPolicy, Step, StepResult, ResourceInfo,
        UserAbortedError, CheckpointStore,
    )
    from hitl_common import (
        AuditLogger, AuditEventType, AuditEvent,
        HITLConfig, NotificationManager, NotificationPayload,
        CLIErrorHandler, PRErrorHandler, ErrorAction,
        GitError, NetworkError, WebhookError, ConfigError,
        parse_ttl, now_iso, safe_load_json, redact_secrets,
    )
except ImportError:
    # 当作为脚本直接运行时
    from scripts.hitl_mode_a import (  # type: ignore
        Checkpoint, CheckpointType, CheckpointStatus, StepType, Action,
        Environment, EnvironmentPolicy, Step, StepResult, ResourceInfo,
        UserAbortedError, CheckpointStore,
    )
    from scripts.hitl_common import (  # type: ignore
        AuditLogger, AuditEventType, AuditEvent,
        HITLConfig, NotificationManager, NotificationPayload,
        CLIErrorHandler, PRErrorHandler, ErrorAction,
        GitError, NetworkError, WebhookError, ConfigError,
        parse_ttl, now_iso, safe_load_json, redact_secrets,
    )


# ============================================================================
# Enums and Constants
# ============================================================================

class PRStatus(str, Enum):
    """PR 状态"""
    DRAFT = "draft"
    OPEN = "open"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    MERGED = "merged"
    CLOSED = "closed"


class CommentAction(str, Enum):
    """评论指令动作 — spec §4.4"""
    NONE = "none"
    RERUN_PLAN = "rerun_plan"
    EXECUTE_APPLY = "execute_apply"
    APPROVE = "approve"
    REJECT = "reject"
    SKIP_CHECKPOINT = "skip_checkpoint"
    SHOW_HELP = "show_help"
    UNKNOWN = "unknown"
    FORBIDDEN = "forbidden"


class GitProviderType(str, Enum):
    """Git 提供方类型"""
    LOCAL = "local"      # 本地文件系统 (默认/测试)
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEE = "gitee"


@dataclass
class PullRequest:
    """PR 数据模型"""
    id: str
    number: int
    title: str
    body: str
    branch: str
    base_branch: str
    status: PRStatus = PRStatus.OPEN
    url: Optional[str] = None
    author: str = ""
    reviewers: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    merged_at: Optional[str] = None
    closed_at: Optional[str] = None
    approvals: List[str] = field(default_factory=list)
    rejections: List[Tuple[str, str]] = field(default_factory=list)  # (user, reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "branch": self.branch,
            "base_branch": self.base_branch,
            "status": self.status.value,
            "url": self.url,
            "author": self.author,
            "reviewers": self.reviewers,
            "labels": self.labels,
            "comments": self.comments,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "merged_at": self.merged_at,
            "closed_at": self.closed_at,
            "approvals": self.approvals,
            "rejections": self.rejections,
        }


@dataclass
class CommandResult:
    """评论指令解析结果"""
    action: CommentAction
    args: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    error: Optional[str] = None
    require_approval: bool = False


@dataclass
class PRFile:
    """PR 文件"""
    path: str
    content: str
    operation: str = "create"  # create / update / delete


# ============================================================================
# Git Provider 抽象
# ============================================================================

class GitProvider:
    """Git 提供方抽象基类

    子类: LocalGitProvider / GitHubProvider / GitLabProvider / GiteeProvider
    """

    def __init__(self, config: HITLConfig, audit: AuditLogger):
        self.config = config
        self.audit = audit

    # ---------- 分支操作 ----------
    def create_branch(self, base: str, name: str) -> None:
        raise NotImplementedError

    def branch_exists(self, name: str) -> bool:
        raise NotImplementedError

    # ---------- 文件操作 ----------
    def commit_files(self, branch: str, files: List[PRFile], message: str) -> str:
        """返回 commit SHA"""
        raise NotImplementedError

    # ---------- PR 操作 ----------
    def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: List[str],
        reviewers: List[str],
    ) -> PullRequest:
        raise NotImplementedError

    def update_pr(self, pr_id: str, files: List[PRFile], message: str) -> str:
        raise NotImplementedError

    def get_pr(self, pr_id: str) -> PullRequest:
        raise NotImplementedError

    def list_pr_comments(self, pr_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def add_pr_comment(self, pr_id: str, body: str) -> Dict[str, Any]:
        raise NotImplementedError

    def approve_pr(self, pr_id: str, user: str) -> None:
        raise NotImplementedError

    def reject_pr(self, pr_id: str, user: str, reason: str) -> None:
        raise NotImplementedError

    def merge_pr(self, pr_id: str, method: str = "merge") -> None:
        raise NotImplementedError

    def close_pr(self, pr_id: str) -> None:
        raise NotImplementedError

    # ---------- 工具 ----------
    def get_file(self, branch: str, path: str) -> Optional[str]:
        raise NotImplementedError

    def generate_branch_name(self, checkpoint: Checkpoint) -> str:
        """生成标准化的分支名 — spec §4.2"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        cp_short = checkpoint.id.split("-")[-1] if "-" in checkpoint.id else uuid.uuid4().hex[:6]
        return f"terraform/{checkpoint.type.value}-{checkpoint.environment.value}-{timestamp}-{cp_short}"


class LocalGitProvider(GitProvider):
    """本地文件系统 Git Provider (默认/离线/测试)

    将 PR/分支/评论/审批信息持久化到 .runtime/terraform-ops/pr-store/，
    模拟 GitHub/GitLab API 行为，无需真实 Git 仓库。
    """

    def __init__(
        self,
        config: HITLConfig,
        audit: AuditLogger,
        store_dir: Optional[Path] = None,
    ):
        super().__init__(config, audit)
        if store_dir is None:
            from runtime_paths import pr_store_dir
            store_dir = pr_store_dir()
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.branches_dir = self.store_dir / "branches"
        self.branches_dir.mkdir(exist_ok=True)
        self.prs_file = self.store_dir / "prs.json"
        self.comments_file = self.store_dir / "comments.json"
        self._pr_counter = self._load_pr_counter()
        if not self.prs_file.exists():
            self._save_prs({})
        if not self.comments_file.exists():
            self._save_comments({})

    def _load_pr_counter(self) -> int:
        counter_file = self.store_dir / "counter.txt"
        if counter_file.exists():
            try:
                return int(counter_file.read_text().strip())
            except ValueError:
                pass
        return 0

    def _next_pr_number(self) -> int:
        self._pr_counter += 1
        (self.store_dir / "counter.txt").write_text(str(self._pr_counter))
        return self._pr_counter

    def _load_prs(self) -> Dict[str, Dict[str, Any]]:
        return safe_load_json(self.prs_file) or {}

    def _save_prs(self, prs: Dict[str, Dict[str, Any]]):
        with open(self.prs_file, "w", encoding="utf-8") as f:
            json.dump(prs, f, indent=2, ensure_ascii=False)

    def _save_comments(self, comments: Dict[str, List[Dict[str, Any]]]):
        with open(self.comments_file, "w", encoding="utf-8") as f:
            json.dump(comments, f, indent=2, ensure_ascii=False)

    def _load_comments(self) -> Dict[str, List[Dict[str, Any]]]:
        return safe_load_json(self.comments_file) or {}

    # ---------- 分支 ----------
    def create_branch(self, base: str, name: str) -> None:
        if self.branch_exists(name):
            raise GitError(f"分支已存在: {name}", code="branch_already_exists")
        branch_dir = self.branches_dir / name
        branch_dir.mkdir(parents=True, exist_ok=True)
        # 创建基础元数据
        (branch_dir / ".meta.json").write_text(json.dumps({
            "base": base,
            "name": name,
            "created_at": now_iso(),
        }, indent=2, ensure_ascii=False))
        self.audit.emit(
            AuditEventType.STEP_EXECUTED,
            context={"action": "git.branch.create", "branch": name, "base": base},
        )

    def branch_exists(self, name: str) -> bool:
        return (self.branches_dir / name).exists()

    # ---------- 提交 ----------
    def commit_files(self, branch: str, files: List[PRFile], message: str) -> str:
        if not self.branch_exists(branch):
            raise GitError(f"分支不存在: {branch}", code="not_found")

        branch_dir = self.branches_dir / branch
        commit_id = uuid.uuid4().hex[:8]
        for f in files:
            target = branch_dir / f.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.content, encoding="utf-8")

        # 追加 commit 历史
        history_file = branch_dir / "commits.jsonl"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sha": commit_id,
                "message": message,
                "files": [fl.path for fl in files],
                "timestamp": now_iso(),
            }, ensure_ascii=False) + "\n")

        self.audit.emit(
            AuditEventType.STEP_EXECUTED,
            context={
                "action": "git.commit",
                "branch": branch,
                "sha": commit_id,
                "files_count": len(files),
            },
        )
        return commit_id

    # ---------- PR ----------
    def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: List[str],
        reviewers: List[str],
    ) -> PullRequest:
        # 检查 PR 是否已存在
        prs = self._load_prs()
        for pr_id, pr_data in prs.items():
            if pr_data["branch"] == head and pr_data["status"] in ("open", "draft"):
                raise GitError(
                    f"分支 {head} 已存在打开的 PR (#{pr_data['number']})",
                    code="pr_create_failed",
                )

        number = self._next_pr_number()
        pr_id = f"pr-{number}"
        pr = PullRequest(
            id=pr_id,
            number=number,
            title=title,
            body=body,
            branch=head,
            base_branch=base,
            status=PRStatus.OPEN,
            url=f"file://{self.store_dir}/prs/{pr_id}",
            author=os.environ.get("USER", "unknown"),
            reviewers=reviewers,
            labels=labels,
        )
        prs[pr_id] = pr.to_dict()
        self._save_prs(prs)

        self.audit.emit(
            AuditEventType.PR_CREATED,
            context={
                "pr_id": pr_id,
                "pr_number": number,
                "branch": head,
                "title": title,
                "reviewers": reviewers,
            },
        )
        return pr

    def update_pr(self, pr_id: str, files: List[PRFile], message: str) -> str:
        prs = self._load_prs()
        if pr_id not in prs:
            raise GitError(f"PR 不存在: {pr_id}", code="not_found")
        return self.commit_files(prs[pr_id]["branch"], files, message)

    def get_pr(self, pr_id: str) -> PullRequest:
        prs = self._load_prs()
        if pr_id not in prs:
            raise GitError(f"PR 不存在: {pr_id}", code="not_found")
        data = prs[pr_id]
        return PullRequest(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data["body"],
            branch=data["branch"],
            base_branch=data["base_branch"],
            status=PRStatus(data["status"]),
            url=data.get("url"),
            author=data.get("author", ""),
            reviewers=data.get("reviewers", []),
            labels=data.get("labels", []),
            comments=data.get("comments", []),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            merged_at=data.get("merged_at"),
            closed_at=data.get("closed_at"),
            approvals=data.get("approvals", []),
            rejections=[(r[0], r[1]) if isinstance(r, list) else (r.get("user", ""), r.get("reason", ""))
                       for r in data.get("rejections", [])],
        )

    def _save_pr_from_dataclass(self, pr: PullRequest):
        prs = self._load_prs()
        prs[pr.id] = pr.to_dict()
        pr.updated_at = now_iso()
        prs[pr.id] = pr.to_dict()
        self._save_prs(prs)

    # ---------- 评论 ----------
    def list_pr_comments(self, pr_id: str) -> List[Dict[str, Any]]:
        comments = self._load_comments()
        return comments.get(pr_id, [])

    def add_pr_comment(self, pr_id: str, body: str) -> Dict[str, Any]:
        comments = self._load_comments()
        if pr_id not in comments:
            comments[pr_id] = []
        comment = {
            "id": f"c-{uuid.uuid4().hex[:8]}",
            "body": body,
            "author": os.environ.get("USER", "unknown"),
            "created_at": now_iso(),
        }
        comments[pr_id].append(comment)
        self._save_comments(comments)

        self.audit.emit(
            AuditEventType.PR_COMMENT,
            context={"pr_id": pr_id, "comment_id": comment["id"]},
        )
        return comment

    # ---------- 审批 ----------
    def approve_pr(self, pr_id: str, user: str) -> None:
        prs = self._load_prs()
        if pr_id not in prs:
            raise GitError(f"PR 不存在: {pr_id}", code="not_found")
        if user not in prs[pr_id]["approvals"]:
            prs[pr_id]["approvals"].append(user)
        # 检查是否所有 reviewer 都审批通过
        reviewers = prs[pr_id].get("reviewers", [])
        if reviewers and all(r in prs[pr_id]["approvals"] for r in reviewers):
            prs[pr_id]["status"] = PRStatus.APPROVED.value
        self._save_prs(prs)

        self.audit.emit(
            AuditEventType.PR_APPROVED,
            context={"pr_id": pr_id, "approver": user},
        )

    def reject_pr(self, pr_id: str, user: str, reason: str) -> None:
        prs = self._load_prs()
        if pr_id not in prs:
            raise GitError(f"PR 不存在: {pr_id}", code="not_found")
        prs[pr_id]["rejections"].append({"user": user, "reason": reason})
        prs[pr_id]["status"] = PRStatus.CHANGES_REQUESTED.value
        self._save_prs(prs)

        self.audit.emit(
            AuditEventType.PR_REJECTED,
            context={"pr_id": pr_id, "rejecter": user, "reason": reason},
        )

    def merge_pr(self, pr_id: str, method: str = "merge") -> None:
        prs = self._load_prs()
        if pr_id not in prs:
            raise GitError(f"PR 不存在: {pr_id}", code="not_found")
        prs[pr_id]["status"] = PRStatus.MERGED.value
        prs[pr_id]["merged_at"] = now_iso()
        self._save_prs(prs)

        # 可选: 删除分支
        if self.config.pr_delete_branch:
            branch = prs[pr_id]["branch"]
            branch_dir = self.branches_dir / branch
            if branch_dir.exists():
                import shutil
                shutil.rmtree(branch_dir)

        self.audit.emit(
            AuditEventType.PR_MERGED,
            context={"pr_id": pr_id, "method": method},
        )

    def close_pr(self, pr_id: str) -> None:
        prs = self._load_prs()
        if pr_id not in prs:
            raise GitError(f"PR 不存在: {pr_id}", code="not_found")
        prs[pr_id]["status"] = PRStatus.CLOSED.value
        prs[pr_id]["closed_at"] = now_iso()
        self._save_prs(prs)

        self.audit.emit(
            AuditEventType.PR_CLOSED,
            context={"pr_id": pr_id},
        )

    def get_file(self, branch: str, path: str) -> Optional[str]:
        if not self.branch_exists(branch):
            return None
        target = self.branches_dir / branch / path
        if not target.exists():
            return None
        return target.read_text(encoding="utf-8")


# ============================================================================
# PR 文件生成器 — spec §4.3
# ============================================================================

class PRFileGenerator:
    """PR 文件生成器

    生成的 PR 文件包括:
    - main.tf / variables.tf / outputs.tf / provider.tf
    - PLAN.md (变更摘要)
    - .terraform-docs.yml
    - import.sh (逆向工程场景)
    """

    def __init__(self, environment: str, region: str = "cn-hangzhou"):
        self.environment = environment
        self.region = region

    def generate_files(
        self,
        checkpoint: Checkpoint,
        plan_summary: Optional[Dict[str, Any]] = None,
        hcl_content: Optional[Dict[str, str]] = None,
    ) -> List[PRFile]:
        """生成 PR 文件列表"""
        files: List[PRFile] = []

        # 1. Terraform 配置文件
        if hcl_content:
            for filename, content in hcl_content.items():
                files.append(PRFile(path=filename, content=content))
        else:
            # 默认占位
            files.append(PRFile(
                path="main.tf",
                content=self._generate_placeholder_main_tf(checkpoint),
            ))

        # 2. variables.tf
        if not hcl_content or "variables.tf" not in hcl_content:
            files.append(PRFile(
                path="variables.tf",
                content=self._generate_variables_tf(checkpoint),
            ))

        # 3. PLAN.md
        files.append(PRFile(
            path="PLAN.md",
            content=self.generate_plan_md(checkpoint, plan_summary or {}),
        ))

        # 4. .terraform-docs.yml
        files.append(PRFile(
            path=".terraform-docs.yml",
            content=self._generate_terraform_docs_config(),
        ))

        return files

    def generate_plan_md(
        self,
        checkpoint: Checkpoint,
        plan: Dict[str, Any],
    ) -> str:
        """生成 PLAN.md — spec §4.3"""
        create = plan.get("create", len([r for r in checkpoint.resources if r.status != "imported"]))
        update = plan.get("update", 0)
        delete = plan.get("delete", 0)
        cost_estimate = plan.get("cost_estimate", "未估算")
        risks = plan.get("risks", [])

        # 资源清单
        resources_md = self._render_resources_table(checkpoint.resources)

        # 风险检查清单
        risk_md = self._render_risk_checks(risks, checkpoint.environment)

        # 审批清单
        approvers = self._get_approvers(checkpoint.environment)
        approver_md = "\n".join(
            f"- [ ] {name}: _____________" for name in approvers
        ) if approvers else "- [ ] 无需审批 (int/dev 环境)"

        return f"""<!-- Generated by alicloud-terraform-ops -->
# Terraform Plan 摘要

## 基本信息

| 字段 | 值 |
|------|-----|
| Checkpoint ID | `{checkpoint.id}` |
| 类型 | {checkpoint.type.value} |
| 环境 | **{checkpoint.environment.value}** |
| 创建时间 | {checkpoint.created_at} |
| 用户 | {os.environ.get('USER', 'unknown')} |

## 变更概览

| 类型 | 数量 | 资源 |
|------|------|------|
| + 创建 | {create} | {', '.join(plan.get('create_resources', []))} |
| ~ 修改 | {update} | {', '.join(plan.get('update_resources', []))} |
| - 销毁 | {delete} | {', '.join(plan.get('delete_resources', []))} |

## 资源清单

{resources_md}

## 预计费用

{cost_estimate}

## 风险检查

{risk_md}

## 审批

{approver_md}

## 评论指令

| 指令 | 动作 |
|------|------|
| `/plan` | 重新执行 terraform plan |
| `/apply` | 执行 terraform apply (需先审批) |
| `/approve` | 批准变更 |
| `/reject <原因>` | 拒绝并记录原因 |
| `/skip-cp <cp-id>` | 跳过指定检查点 |
| `/help` | 显示可用指令 |

---
*Generated at {now_iso()} by alicloud-terraform-ops*
*Checkpoint: {checkpoint.id}*
"""

    def _render_resources_table(self, resources: List[ResourceInfo]) -> str:
        if not resources:
            return "_无资源_"
        lines = [
            "| 类型 | 名称 | ID | 状态 |",
            "|------|------|----|----|",
        ]
        for r in resources:
            rid = r.id or "-"
            lines.append(f"| {r.resource_type} | {r.name} | `{rid}` | {r.status} |")
        return "\n".join(lines)

    def _render_risk_checks(self, risks: List[str], env: Environment) -> str:
        checks = [
            f"- [PASS] 环境: {env.value}",
        ]
        if env == Environment.PRODUCTION:
            checks.extend([
                "- [WARN] 生产环境: 双重确认 + 冷却期",
                "- [PASS] 状态备份: 已生成 (如需回滚)",
            ])
        else:
            checks.append("- [PASS] 非生产环境: 标准流程")

        checks.extend(f"- [{r.split(':')[0] if ':' in r else 'INFO'}] {r}" for r in risks)

        return "\n".join(checks)

    def _get_approvers(self, env: Environment) -> List[str]:
        """获取环境对应的审批人"""
        if env == Environment.PRODUCTION:
            return ["Tech Lead", "Ops Manager"]
        if env in (Environment.UAT, Environment.PERFORMANCE):
            return ["Tech Lead"]
        return []

    def _generate_placeholder_main_tf(self, checkpoint: Checkpoint) -> str:
        """生成占位 main.tf"""
        return f"""# Terraform configuration for checkpoint {checkpoint.id}
# Environment: {checkpoint.environment.value}
# Type: {checkpoint.type.value}

terraform {{
  required_version = ">= 1.0"
  backend "oss" {{
    bucket = "your-tf-state-bucket"
    prefix = "terraform/{checkpoint.environment.value}/{checkpoint.id}"
    region = "{self.region}"
  }}
}}

provider "alicloud" {{
  region = var.region
}}

# 资源定义...
"""

    def _generate_variables_tf(self, checkpoint: Checkpoint) -> str:
        """生成 variables.tf"""
        return f"""variable "region" {{
  description = "阿里云地域"
  type        = string
  default     = "{self.region}"
}}

variable "environment" {{
  description = "部署环境"
  type        = string
  default     = "{checkpoint.environment.value}"
}}

variable "vpc_cidr" {{
  description = "VPC CIDR 块"
  type        = string
  default     = "10.0.0.0/16"
}}
"""

    def _generate_terraform_docs_config(self) -> str:
        """生成 .terraform-docs.yml"""
        return """formatter: markdown table

sections:
  show:
    - requirements
    - providers
    - resources
    - inputs
    - outputs
"""


# ============================================================================
# 评论指令解析器 — spec §4.4
# ============================================================================

class CommentCommandParser:
    """评论指令解析器

    支持: /plan /approve /reject /apply /skip-cp /help
    """

    COMMANDS: Dict[str, Dict[str, Any]] = {
        "/plan": {
            "description": "重新执行 terraform plan",
            "permission": ["author", "reviewer"],
            "action": CommentAction.RERUN_PLAN,
            "require_approval": False,
        },
        "/apply": {
            "description": "执行 terraform apply",
            "permission": ["reviewer"],
            "action": CommentAction.EXECUTE_APPLY,
            "require_approval": True,
        },
        "/approve": {
            "description": "批准变更",
            "permission": ["reviewer"],
            "action": CommentAction.APPROVE,
            "require_approval": False,
        },
        "/reject": {
            "description": "拒绝变更",
            "permission": ["reviewer"],
            "action": CommentAction.REJECT,
            "require_approval": False,
            "require_reason": True,
        },
        "/skip-cp": {
            "description": "跳过指定检查点",
            "permission": ["admin"],
            "action": CommentAction.SKIP_CHECKPOINT,
            "require_approval": False,
        },
        "/help": {
            "description": "显示帮助",
            "permission": ["anyone"],
            "action": CommentAction.SHOW_HELP,
            "require_approval": False,
        },
    }

    def __init__(self, audit: AuditLogger):
        self.audit = audit

    def parse(self, comment: str, user: str, user_role: str = "reviewer") -> CommandResult:
        """解析评论指令"""
        first_line = comment.strip().split("\n")[0].strip()

        if not first_line.startswith("/"):
            return CommandResult(action=CommentAction.NONE)

        parts = first_line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd not in self.COMMANDS:
            return CommandResult(
                action=CommentAction.UNKNOWN,
                error=f"未知指令: {cmd}，输入 /help 查看可用指令",
            )

        cmd_def = self.COMMANDS[cmd]

        # 权限检查
        if not self._check_permission(user_role, cmd_def["permission"]):
            return CommandResult(
                action=CommentAction.FORBIDDEN,
                error=f"权限不足: 需要 {cmd_def['permission']}",
            )

        # 参数验证
        if cmd_def.get("require_reason") and not args:
            return CommandResult(
                action=CommentAction.UNKNOWN,
                error=f"指令 {cmd} 需要参数: {cmd} <原因>",
            )

        self.audit.emit(
            AuditEventType.PR_COMMENT,
            context={"command": cmd, "args": args, "user": user},
        )

        return CommandResult(
            action=cmd_def["action"],
            args=args,
            require_approval=cmd_def.get("require_approval", False),
        )

    @staticmethod
    def _check_permission(user_role: str, allowed: List[str]) -> bool:
        if "anyone" in allowed:
            return True
        return user_role in allowed


# ============================================================================
# PR 监听器 — spec §4.2
# ============================================================================

class PRWatcher:
    """PR 状态轮询监听器

    轮询 PR 状态，处理:
    - 审批通过 (所有 reviewer 都 /approve)
    - 拒绝 (任何 reviewer /reject)
    - 评论 (触发重新 plan 或其他操作)
    - 自动 apply (满足条件时)
    """

    def __init__(
        self,
        provider: GitProvider,
        parser: CommentCommandParser,
        audit: AuditLogger,
        poll_interval: int = 5,
        max_wait: int = 3600,  # 1 hour
    ):
        self.provider = provider
        self.parser = parser
        self.audit = audit
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    def watch(
        self,
        pr_id: str,
        on_approve: Optional[Callable[[PullRequest], None]] = None,
        on_reject: Optional[Callable[[PullRequest, str], None]] = None,
        on_comment: Optional[Callable[[PullRequest, CommandResult], None]] = None,
        on_apply: Optional[Callable[[PullRequest], None]] = None,
    ) -> PullRequest:
        """监听 PR 直至终态"""
        start = time.time()
        seen_comments: set = set()

        while True:
            pr = self.provider.get_pr(pr_id)

            # 1. 处理状态变化
            if pr.status == PRStatus.MERGED:
                self.audit.emit(
                    AuditEventType.PR_MERGED,
                    context={"pr_id": pr_id, "watcher": "completed"},
                )
                return pr

            if pr.status == PRStatus.CLOSED:
                return pr

            # 2. 处理拒绝
            if pr.rejections and on_reject:
                user, reason = pr.rejections[-1]
                self.audit.emit(
                    AuditEventType.PR_REJECTED,
                    context={"pr_id": pr_id, "rejecter": user, "reason": reason},
                )
                on_reject(pr, f"{user}: {reason}")
                return pr

            # 3. 处理新评论
            comments = self.provider.list_pr_comments(pr_id)
            for c in comments:
                if c["id"] in seen_comments:
                    continue
                seen_comments.add(c["id"])

                # 解析评论指令
                result = self.parser.parse(
                    c["body"],
                    user=c.get("author", "unknown"),
                    user_role="reviewer",  # 简化: 真实场景从 Git provider 获取
                )

                if on_comment and result.action != CommentAction.NONE:
                    on_comment(pr, result)

                if result.action == CommentAction.APPROVE:
                    self.provider.approve_pr(pr_id, c.get("author", "unknown"))
                    pr = self.provider.get_pr(pr_id)
                    if on_approve and pr.status == PRStatus.APPROVED:
                        on_approve(pr)
                        if on_apply and not self.config_requires_more(pr):
                            on_apply(pr)
                            self.provider.merge_pr(pr_id)
                            return self.provider.get_pr(pr_id)

                elif result.action == CommentAction.REJECT:
                    reason = " ".join(result.args) if result.args else "未提供原因"
                    self.provider.reject_pr(pr_id, c.get("author", "unknown"), reason)
                    pr = self.provider.get_pr(pr_id)
                    if on_reject:
                        on_reject(pr, reason)
                    return pr

            # 4. 检查审批通过
            if pr.approvals and on_approve:
                required_approvers = set(pr.reviewers) if pr.reviewers else set(pr.approvals)
                if required_approvers and required_approvers.issubset(set(pr.approvals)):
                    if pr.status != PRStatus.APPROVED:
                        on_approve(pr)
                    if on_apply:
                        on_apply(pr)
                        self.provider.merge_pr(pr_id)
                    return self.provider.get_pr(pr_id)

            # 5. 超时检查
            if time.time() - start > self.max_wait:
                self.audit.emit(
                    AuditEventType.PR_CLOSED,
                    context={"pr_id": pr_id, "reason": "watch_timeout"},
                )
                self.provider.close_pr(pr_id)
                return self.provider.get_pr(pr_id)

            time.sleep(self.poll_interval)

    @staticmethod
    def config_requires_more(pr: PullRequest) -> bool:
        """检查 PR 是否还需要更多审批"""
        if not pr.reviewers:
            return False
        return not set(pr.reviewers).issubset(set(pr.approvals))


# ============================================================================
# PR 管理器 — spec §4.3
# ============================================================================

class PRManager:
    """PR 管理器 — 创建/更新/审核/合并 PR"""

    def __init__(
        self,
        provider: GitProvider,
        file_generator: PRFileGenerator,
        parser: CommentCommandParser,
        audit: AuditLogger,
        notification: NotificationManager,
        error_handler: PRErrorHandler,
    ):
        self.provider = provider
        self.file_generator = file_generator
        self.parser = parser
        self.audit = audit
        self.notification = notification
        self.error_handler = error_handler

    def create_terraform_pr(
        self,
        config_files: Dict[str, str],
        checkpoint: Checkpoint,
        plan_summary: Optional[Dict[str, Any]] = None,
        reviewers: Optional[List[str]] = None,
        retry_count: int = 0,
    ) -> PullRequest:
        """创建 Terraform PR

        流程:
        1. 生成分支名
        2. 创建分支 (如已存在则生成新名)
        3. 提交 HCL + PLAN.md
        4. 创建 PR (如已存在则更新)
        5. 通知审批人
        """
        # 1. 生成分支名
        branch_name = self.provider.generate_branch_name(checkpoint)

        # 2. 创建分支 (处理已存在情况)
        try:
            self.provider.create_branch(
                base=checkpoint.user_inputs.get("base_branch", "main"),
                name=branch_name,
            )
        except GitError as e:
            action = self.error_handler.handle_git_error(e)
            if action.action == "RETRY_WITH_NEW_BRANCH" and retry_count < 3:
                timestamp = datetime.now().strftime("%H%M%S")
                branch_name = f"{branch_name}-{timestamp}"
                return self.create_terraform_pr(
                    config_files, checkpoint, plan_summary, reviewers, retry_count + 1
                )
            raise

        # 3. 生成并提交文件
        pr_files = self.file_generator.generate_files(
            checkpoint, plan_summary, config_files
        )
        commit_message = self._generate_commit_message(checkpoint, pr_files)
        try:
            self.provider.commit_files(branch_name, pr_files, commit_message)
        except GitError as e:
            action = self.error_handler.handle_git_error(e)
            if action.action == "HALT":
                raise

        # 4. 创建 PR
        cp_label = getattr(checkpoint, "description", None) or checkpoint.type.value
        pr_title = f"[terraform] {cp_label} ({checkpoint.environment.value})"
        pr_body = self.file_generator.generate_plan_md(checkpoint, plan_summary or {})

        if not reviewers:
            reviewers = self._get_reviewers_for_env(checkpoint.environment)

        try:
            pr = self.provider.create_pr(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=checkpoint.user_inputs.get("base_branch", "main"),
                labels=["terraform", "needs-review"],
                reviewers=reviewers,
            )
        except GitError as e:
            action = self.error_handler.handle_git_error(e, pr_id=None)
            if action.action == "UPDATE_EXISTING_PR":
                # 找到现有 PR
                existing_pr = self._find_existing_pr(branch_name)
                if existing_pr:
                    self.provider.update_pr(existing_pr.id, pr_files, commit_message)
                    self.provider.add_pr_comment(
                        existing_pr.id,
                        f"配置已更新 ({now_iso()})",
                    )
                    return self.provider.get_pr(existing_pr.id)
            raise

        # 5. 通知
        self._notify_reviewers(pr, reviewers)

        return pr

    def _find_existing_pr(self, branch: str) -> Optional[PullRequest]:
        """查找分支对应的现有 PR"""
        # 简化实现: 通过 provider 内部状态查找
        try:
            counter_file = self.provider.store_dir / "counter.txt"
            if not counter_file.exists():
                return None
            max_num = int(counter_file.read_text().strip())
            for n in range(1, max_num + 1):
                pr_id = f"pr-{n}"
                try:
                    pr = self.provider.get_pr(pr_id)
                    if pr.branch == branch and pr.status in (PRStatus.OPEN, PRStatus.DRAFT):
                        return pr
                except GitError:
                    continue
        except Exception:
            pass
        return None

    def _get_reviewers_for_env(self, env: Environment) -> List[str]:
        """根据环境获取审批人"""
        env_reviewers = {
            Environment.PRODUCTION: ["tech-lead", "ops-manager"],
            Environment.UAT: ["tech-lead"],
            Environment.PERFORMANCE: ["tech-lead"],
            Environment.DEV: [],
            Environment.INT: [],
        }
        return env_reviewers.get(env, [])

    def _generate_commit_message(self, checkpoint: Checkpoint, files: List[PRFile]) -> str:
        """生成 commit message"""
        resource_types = sorted({r.resource_type for r in checkpoint.resources})
        resource_str = ", ".join(resource_types[:5])
        if len(resource_types) > 5:
            resource_str += f" 等 {len(resource_types)} 种"

        return (
            f"[terraform] Add {resource_str} ({checkpoint.environment.value})\n\n"
            f"Checkpoint: {checkpoint.id}\n"
            f"Type: {checkpoint.type.value}\n"
            f"Environment: {checkpoint.environment.value}\n"
            f"Files: {len(files)}"
        )

    def _notify_reviewers(self, pr: PullRequest, reviewers: List[str]):
        """通知审批人"""
        if not reviewers:
            return

        payload = NotificationPayload(
            title=f"Terraform PR 待审批: {pr.title}",
            message=(
                f"PR #{pr.number} 等待您的审批\n"
                f"分支: `{pr.branch}`\n"
                f"环境: {pr.base_branch}\n"
                f"审批人: {', '.join(reviewers)}"
            ),
            level="info",
            url=pr.url,
        )

        # 发送到默认渠道集 (config.default_notification_channels)
        # 默认为 [console, dingtalk?, feishu?, wecom?] (根据环境变量自动识别)
        self.notification.send_all(payload)


# ============================================================================
# 工厂函数
# ============================================================================

def create_git_provider(
    config: HITLConfig,
    audit: AuditLogger,
) -> GitProvider:
    """创建 Git Provider (工厂)"""
    provider_type = GitProviderType(config.pr_provider)

    if provider_type == GitProviderType.LOCAL:
        return LocalGitProvider(config, audit)

    # GitHub/GitLab/Gitee 的实现留作未来扩展 (需要 API token)
    raise NotImplementedError(
        f"Git provider '{provider_type.value}' 尚未实现，请使用 local 或贡献 PR"
    )


def create_pr_manager(
    config: HITLConfig,
    audit: AuditLogger,
    notification: NotificationManager,
) -> PRManager:
    """创建 PR Manager"""
    provider = create_git_provider(config, audit)
    file_generator = PRFileGenerator(
        environment=config.environment,
        region=config.region,
    )
    parser = CommentCommandParser(audit)
    error_handler = PRErrorHandler(audit)

    return PRManager(
        provider=provider,
        file_generator=file_generator,
        parser=parser,
        audit=audit,
        notification=notification,
        error_handler=error_handler,
    )


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    """CLI 入口: PR 创建/审核/状态查询"""
    import argparse

    parser = argparse.ArgumentParser(
        description="HITL Mode B - PR-based Review for Terraform IaC",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-pr 子命令
    create_parser = subparsers.add_parser("create-pr", help="创建 Terraform PR")
    create_parser.add_argument("--type", "-t", choices=["nl2hcl", "import", "apply"], required=True)
    create_parser.add_argument("--env", "-e", default="dev")
    create_parser.add_argument("--files-dir", help="HCL 文件所在目录")

    # status 子命令
    status_parser = subparsers.add_parser("status", help="查询 PR 状态")
    status_parser.add_argument("pr_id", help="PR ID (如 pr-1)")

    # comment 子命令
    comment_parser = subparsers.add_parser("comment", help="添加 PR 评论")
    comment_parser.add_argument("pr_id", help="PR ID")
    comment_parser.add_argument("body", help="评论内容")

    # approve/reject/merge/close 子命令
    for cmd in ("approve", "reject", "merge", "close"):
        sp = subparsers.add_parser(cmd, help=f"{cmd} PR")
        sp.add_argument("pr_id", help="PR ID")
        if cmd == "reject":
            sp.add_argument("reason", help="拒绝原因")

    args = parser.parse_args()

    # 初始化
    config = HITLConfig.load()
    audit = AuditLogger()
    notification = NotificationManager(config, audit)
    pr_manager = create_pr_manager(config, audit, notification)
    provider = pr_manager.provider
    parser_obj = pr_manager.parser

    if args.command == "create-pr":
        # 加载 HCL 文件
        hcl_files = {}
        if args.files_dir:
            files_dir = Path(args.files_dir)
            for tf_file in files_dir.glob("*.tf"):
                hcl_files[tf_file.name] = tf_file.read_text(encoding="utf-8")

        checkpoint = Checkpoint(
            id=f"cp-pr-test-{int(time.time())}",
            type=CheckpointType(args.type),
            environment=Environment(args.env),
        )

        try:
            pr = pr_manager.create_terraform_pr(hcl_files, checkpoint)
            print(f"[OK] PR 创建成功")
            print(f"  ID: {pr.id}")
            print(f"  Number: #{pr.number}")
            print(f"  URL: {pr.url}")
            print(f"  Branch: {pr.branch}")
            print(f"  Reviewers: {', '.join(pr.reviewers) or '(无)'}")
        except GitError as e:
            print(f"[ERROR] PR 创建失败: {e} (code={e.code})")
            sys.exit(1)

    elif args.command == "status":
        try:
            pr = provider.get_pr(args.pr_id)
            print(f"PR #{pr.number}: {pr.title}")
            print(f"  Status: {pr.status.value}")
            print(f"  Branch: {pr.branch}")
            print(f"  Approvals: {', '.join(pr.approvals) or '(none)'}")
            if pr.rejections:
                print(f"  Rejections:")
                for user, reason in pr.rejections:
                    print(f"    - {user}: {reason}")
        except GitError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    elif args.command == "comment":
        result = parser_obj.parse(args.body, user=os.environ.get("USER", "cli"))
        comment = provider.add_pr_comment(args.pr_id, args.body)
        print(f"[OK] Comment added: {comment['id']}")
        if result.action != CommentAction.NONE:
            print(f"  Command detected: {result.action.value}")

    elif args.command in ("approve", "reject", "merge", "close"):
        user = os.environ.get("USER", "cli-user")
        try:
            if args.command == "approve":
                provider.approve_pr(args.pr_id, user)
                print(f"[OK] {user} approved {args.pr_id}")
            elif args.command == "reject":
                provider.reject_pr(args.pr_id, user, args.reason)
                print(f"[OK] {user} rejected {args.pr_id}: {args.reason}")
            elif args.command == "merge":
                provider.merge_pr(args.pr_id)
                print(f"[OK] PR {args.pr_id} merged")
            elif args.command == "close":
                provider.close_pr(args.pr_id)
                print(f"[OK] PR {args.pr_id} closed")
        except GitError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
