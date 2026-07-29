"""Tests for wizard_cli integration with chat context (P9)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


# Lazy imports so tests don't fail if wizard_cli is mid-edit.
def _wizard():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "alicloud-gcl-runner-ops" / "scripts"))
    import wizard_cli  # type: ignore  # noqa: F401
    return wizard_cli


class TestBindFromEnv:
    def test_bind_from_env_sets_context_var(self, monkeypatch):
        from alicloud_shared.chat_context import _ctx_var
        from alicloud_shared.chat_context import bind_from_env
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        monkeypatch.setenv("CHAT_USER_ID", "alice")
        monkeypatch.setenv("CHAT_SESSION_ID", "sess-1")
        monkeypatch.setenv("CHAT_TYPE", "group")
        try:
            ctx = bind_from_env()
            assert ctx is not None
            assert ctx.user_id == "alice"
            assert ctx.session_id == "sess-1"
            assert ctx.platform == "wecom"
            assert ctx.chat_type == "group"
        finally:
            _ctx_var.set(None)


class TestPersistDryRunTraceChatFields:
    def test_persist_dry_run_trace_accepts_user_id_platform(self):
        from execution_trace import CommandRecord, persist_dry_run_trace
        with tempfile.TemporaryDirectory() as tmp:
            trace_dir = Path(tmp) / "audit-results"
            records = [
                CommandRecord(
                    phase="INIT",
                    command="terraform init -backend=false",
                    working_directory="/tmp/tf",
                    exit_code=0,
                    stdout_excerpt="ok",
                    stderr_excerpt="",
                    duration_ms=100,
                ),
            ]
            path = persist_dry_run_trace(
                operation="nl2hcl",
                environment="int",
                region="cn-hangzhou",
                request="创建一台1核2G的ECS",
                work_dir=Path("/tmp/tf"),
                command_records=records,
                success=True,
                plan_stdout="Plan: 5 to add, 0 to change, 0 to destroy",
                intent={"resources": ["vpc"]},
                session_id="session-test-001",
                user_id="alice",
                platform="wecom",
                chat_type="group",
                trace_dir=trace_dir,
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["user_id"] == "alice"
            assert data["platform"] == "wecom"
            assert data["chat_type"] == "group"
            assert data["session_id"] == "session-test-001"


class TestWizardSessionDerivation:
    def test_run_nl2hcl_session_uses_chat_context_for_user_and_session(self, monkeypatch, tmp_path):
        """When chat context is bound via env, WizardSession should carry its user_id + session_id.

        We don't run the full wizard (it would prompt); we exercise the same derivation
        logic that `run_nl2hcl` uses, by binding context + calling the module helper.
        """
        from alicloud_shared.chat_context import _ctx_var
        from alicloud_shared.chat_context import bind_from_env

        # Bind first.
        monkeypatch.setenv("CHAT_PLATFORM", "feishu")
        monkeypatch.setenv("CHAT_USER_ID", "bob")
        monkeypatch.setenv("CHAT_SESSION_ID", "chat-xyz")
        monkeypatch.setenv("CHAT_TYPE", "dm")
        _ctx_var.set(None)
        ctx = bind_from_env()
        assert ctx is not None

        try:
            wc = _wizard()
            from alicloud_shared.chat_context import current as _chat_current

            chat_ctx = _chat_current()
            derived_session_id = chat_ctx.session_id if chat_ctx else wc.new_session_id()
            derived_user_id = chat_ctx.user_id if chat_ctx else os.environ.get("USER", "unknown")
            derived_platform = chat_ctx.platform if chat_ctx else "cli"
            derived_chat_type = chat_ctx.chat_type if chat_ctx else "n/a"

            session = wc.WizardSession(
                session_id=derived_session_id,
                user_id=derived_user_id,
                workflow_type="nl2hcl",
            )
            assert session.session_id == "chat-xyz"
            assert session.user_id == "bob"
            assert derived_platform == "feishu"
            assert derived_chat_type == "dm"
        finally:
            _ctx_var.set(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
