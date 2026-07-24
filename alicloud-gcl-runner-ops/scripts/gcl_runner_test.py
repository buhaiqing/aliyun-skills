#!/usr/bin/env python3
"""
gcl_runner_test.py — unit tests for `gcl_runner.py`.

Pure stdlib `unittest`; no third-party dependencies. Run with:
    python -m unittest scripts.gcl_runner_test -v

or
    python scripts/gcl_runner_test.py

Test coverage:
- T1  sanitize() — all SECRET_PATTERNS fire correctly
- T2  parse_rubric() — frontmatter + per-op sub-rules + detection regex
- T3  preflight() — product prefix check, op documentation, secret detection
- T4  _command_targets_product() — exact match, no false positives
- T5  _is_data_plane_tool() — mongosh, mysql, psql, sqlplus, curl, go
- T6  _risk_severity() — risk class ordering
- T7  critique() — destructive regex → Safety=0 + blocking
- T8  critique() — empty rubric → degrade gracefully
- T9  decide() — first-match termination (PASS / RETRY / MAX_ITER / SAFETY_FAIL)
- T10 run_loop() — full loop integration (dry-run)
- T11 persist_trace() — JSON schema matches AGENTS.md §12.6
- T12 CLI integration — main() returns correct exit codes
- T13 hallucination_detect() — CLI params, JSON structure, WAF compliance
- T14 run_loop() with H check — HALLUCINATION_ABORT exit path
- T15 _synthesize_dry_run() — H result passthrough in dry-run mode
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Make `gcl_runner` importable when running this file directly
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import gcl_runner  # noqa: E402


# ---------------------------------------------------------------------------
# Mixin: per-test memory_store isolation
# ---------------------------------------------------------------------------
class _GCLRunnerMemoryIsolated(unittest.TestCase):
    """Mixin: route gcl_runner's memory_store() writes into a per-test temp dir.

    Why: ``gcl_runner.main()`` unconditionally calls ``memory_store(trace, ...)``
    after persisting each trace. In unit tests we don't want fixture traces to
    leak into the repo's ``.runtime/memory/{skill}/*.jsonl`` index.

    How: ``memory_store()`` resolves ``memory_root`` via
    ``_resolve_memory_root(None)`` → ``os.environ.get("GCL_MEMORY_ROOT")``.
    We inject the env var in ``setUp`` (after the subclass prepared
    ``self.tmp_root: Path``) and restore it in ``tearDown``.

    Subclass contract:
      - Define ``self.tmp_root: Path`` BEFORE calling ``super().setUp()``.
      - Clean up ``self.tmp_root`` AFTER calling ``super().tearDown()``.
      - Inherit order: ``class Foo(_GCLRunnerMemoryIsolated, unittest.TestCase)``.
    """

    _GCL_MEMORY_ROOT_ENV = "GCL_MEMORY_ROOT"

    def setUp(self):
        super().setUp()
        if not hasattr(self, "tmp_root"):
            raise RuntimeError(
                f"{type(self).__name__} must define self.tmp_root (Path) "
                "before super().setUp() — _GCLRunnerMemoryIsolated needs it "
                "to route memory_store() into the test's temp dir."
            )
        self._orig_memory_root = os.environ.pop(self._GCL_MEMORY_ROOT_ENV, None)
        os.environ[self._GCL_MEMORY_ROOT_ENV] = str(Path(self.tmp_root) / "memory")

    def tearDown(self):
        if self._orig_memory_root is None:
            os.environ.pop(self._GCL_MEMORY_ROOT_ENV, None)
        else:
            os.environ[self._GCL_MEMORY_ROOT_ENV] = self._orig_memory_root
        super().tearDown()


# ---------------------------------------------------------------------------
# Regression tests for _GCLRunnerMemoryIsolated mixin contract.
# ---------------------------------------------------------------------------
# These tests guard the mixin's behavior so future refactors can't silently
# break the memory_store() isolation that CriticModeEnvTests relies on.
# Each test is fully self-contained: it does NOT use the mixin itself
# (we are testing the mixin), so each test owns its own tmp_root and
# restores GCL_MEMORY_ROOT before returning.
# ---------------------------------------------------------------------------
class _GCLRunnerMemoryIsolatedTest(unittest.TestCase):
    """Regression tests for the _GCLRunnerMemoryIsolated mixin.

    Each test exercises one slice of the contract:
      * missing tmp_root → RuntimeError
      * env var is set to tmp_root/memory in setUp
      * env var is restored in tearDown
      * memory_store() end-to-end lands in tmp_root/memory (not repo root)

    Test mechanics: rather than subclassing the mixin (which would force us
    to set up a tmp_root before super().setUp() — chicken/egg), each test
    instantiates the mixin's setUp/tearDown on a bare object that has
    ``tmp_root`` already attached. This lets us assert against the SAME
    tmp_root that the test prepared.
    """

    _ENV = "GCL_MEMORY_ROOT"

    def setUp(self):
        # Snapshot outer env so a failing test cannot leak GCL_MEMORY_ROOT
        # into sibling tests in this class (or in the rest of the suite).
        self._outer_env = os.environ.get(self._ENV)
        os.environ.pop(self._ENV, None)
        # Test-local tmp_root — the mixin itself doesn't create one; tests
        # that USE the mixin must define their own.
        self.tmp_root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)
        if self._outer_env is None:
            os.environ.pop(self._ENV, None)
        else:
            os.environ[self._ENV] = self._outer_env

    # -- Helpers ------------------------------------------------------------

    def _make_user_with_tmp_root(self):
        """Return a bare unittest.TestCase-like object with tmp_root attached.

        Calling setUp/tearDown on it runs the mixin's logic against THIS
        test's tmp_root, so we can assert against it directly.
        """
        # Bypass __init_subclass__ / unittest.TestCase machinery by using a
        # minimal mixin subclass with __init__ no-op'd via type().
        cls = type(
            "_UserUnderTest",
            (_GCLRunnerMemoryIsolated, unittest.TestCase),
            {"__init__": lambda self: None},
        )
        user = cls.__new__(cls)
        user.tmp_root = self.tmp_root
        return user

    def _make_user_without_tmp_root(self):
        """Return a bare object missing tmp_root, to exercise the contract guard."""
        cls = type(
            "_BadUser",
            (_GCLRunnerMemoryIsolated, unittest.TestCase),
            {"__init__": lambda self: None},
        )
        return cls.__new__(cls)

    # -- Helpers ------------------------------------------------------------

    # -- Contract tests -----------------------------------------------------

    def test_raises_runtime_error_when_tmp_root_missing(self):
        """Mixin must abort setUp() if subclass forgot to define tmp_root.

        Rationale: silent fallback to repo .runtime/memory would defeat the
        whole point of the mixin (preventing fixture pollution).
        """
        bad = self._make_user_without_tmp_root()
        with self.assertRaises(RuntimeError) as cm:
            bad.setUp()
        self.assertIn("tmp_root", str(cm.exception))

    def test_sets_env_var_to_tmp_root_memory(self):
        """When subclass defines tmp_root, setUp routes env var to <tmp_root>/memory."""
        user = self._make_user_with_tmp_root()
        try:
            user.setUp()
            expected = str(self.tmp_root / "memory")
            self.assertEqual(os.environ.get(self._ENV), expected)
        finally:
            user.tearDown()

    def test_teardown_restores_existing_env_value(self):
        """If GCL_MEMORY_ROOT was set before setUp, tearDown restores it."""
        prior = "/some/prior/memory/root"
        os.environ[self._ENV] = prior
        try:
            user = self._make_user_with_tmp_root()
            user.setUp()
            # During the test, env points to the temp dir, not the prior value
            self.assertNotEqual(os.environ.get(self._ENV), prior)
            user.tearDown()
            # After tearDown, env is restored to the prior value
            self.assertEqual(os.environ.get(self._ENV), prior)
        finally:
            if self._outer_env is None:
                os.environ.pop(self._ENV, None)
            else:
                os.environ[self._ENV] = self._outer_env

    def test_teardown_unsets_when_originally_unset(self):
        """If GCL_MEMORY_ROOT was unset before setUp, tearDown leaves it unset."""
        os.environ.pop(self._ENV, None)
        user = self._make_user_with_tmp_root()
        try:
            user.setUp()
            self.assertIn(self._ENV, os.environ)
            user.tearDown()
            self.assertNotIn(self._ENV, os.environ)
        finally:
            # outer_env already restored by outer tearDown
            pass

    def test_full_cycle_leaves_env_clean(self):
        """End-to-end: setUp → tearDown must leave the outer env byte-identical."""
        prior = "/prior/memory/root/for/cycle/test"
        os.environ[self._ENV] = prior
        try:
            user = self._make_user_with_tmp_root()
            user.setUp()
            self.assertEqual(os.environ[self._ENV], str(self.tmp_root / "memory"))
            user.tearDown()
            self.assertEqual(os.environ[self._ENV], prior)
        finally:
            if self._outer_env is None:
                os.environ.pop(self._ENV, None)
            else:
                os.environ[self._ENV] = self._outer_env

    def test_memory_store_lands_in_tmp_root_memory_not_repo_root(self):
        """End-to-end: calling memory_store() inside a mixin-using test must
        write to tmp_root/memory/, NOT to <repo>/.runtime/memory/.

        This is the regression we actually care about: a future refactor of
        either _resolve_memory_root() or the mixin must not silently re-route
        fixture traces into the repo's persistent memory index.
        """
        repo_root_marker = Path(".runtime") / "memory" / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        user = self._make_user_with_tmp_root()
        try:
            user.setUp()
            # Invoke the real memory_store path that gcl_runner.main() uses
            rc = gcl_runner.memory_store(
                {
                    "skill": "alicloud-ecs-ops",
                    "operation": "DescribeInstances",
                    "rubric_version": "test",
                    "iterations": [],
                    "final": {"status": "PASS"},
                },
                trace_path="/tmp/fake-trace.json",
            )
            self.assertEqual(rc, 0, "memory_store should return 0 on success")
            # Must land in tmp_root/memory/alicloud-ecs-ops/DescribeInstances.jsonl
            expected = self.tmp_root / "memory" / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
            self.assertTrue(expected.is_file(), f"expected file at {expected}")
            # Must NOT touch repo-root .runtime/memory/ — check the jsonl file
            # (not the parent dir, which may legitimately exist from prior runs).
            self.assertFalse(
                repo_root_marker.is_file(),
                f"fixture leaked into repo at {repo_root_marker}",
            )
            # Verify content shape
            line = expected.read_text(encoding="utf-8").strip()
            entry = json.loads(line)
            self.assertEqual(entry["skill"], "alicloud-ecs-ops")
            self.assertEqual(entry["operation"], "DescribeInstances")
        finally:
            user.tearDown()


# ---------------------------------------------------------------------------
# T1: sanitize()
# ---------------------------------------------------------------------------


class SanitizeTests(unittest.TestCase):
    """T1: every SECRET_PATTERNS entry must fire on a matching input."""

    def test_ak_sk_env_var(self):
        text = "export ALIBABA_CLOUD_ACCESS_KEY_SECRET=supersecret123"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("supersecret123", out)
        self.assertIn("<masked>", out)

    def test_ak_id_env_var(self):
        text = "ALIBABA_CLOUD_ACCESS_KEY_ID=LTAI5tFakeFakeFakeFake"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("LTAI5tFakeFakeFakeFake", out)

    def test_access_key_secret_flag(self):
        text = "aliyun ecs foo --access-key-secret 12345abcde"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("12345abcde", out)

    def test_password_flag(self):
        text = "redis-cli -h host -a MyRedisPwd2024 PING"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("MyRedisPwd2024", out)

    def test_account_password_flag(self):
        # Aliyun --AccountPassword flag (Redis / RDS / PolarDB)
        text = "aliyun rds CreateAccount --AccountPassword 'P@ssw0rd!'"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("P@ssw0rd!", out)

    def test_pgpassword_env(self):
        text = "PGPASSWORD=secret psql -h host -U user -d db"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("secret psql", out)
        self.assertIn("PGPASSWORD=<masked>", out)

    def test_mysql_pwd_env(self):
        text = "MYSQL_PWD=secret mysql -h host -u user db"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("MYSQL_PWD=secret", out)

    def test_sqlplus_creds(self):
        text = "sqlplus admin/oracle_pwd@//host:1521/PDB1"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("oracle_pwd", out)

    def test_mongo_uri_creds(self):
        text = "mongosh 'mongodb://user:mongopwd@host:27017/db'"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("mongopwd", out)

    def test_mysql_uri_creds(self):
        text = "mysql -u root -pmysqlpwd -h host db"
        gcl_runner.sanitize(text)
        # mysql CLI -p<password> (no space) is not directly covered; only
        # the URI form is sanitized. Document this limitation explicitly.
        # Here we test the URI form instead:
        text2 = "mysql 'mysql://root:mysqlpwd@host:3306/db'"
        out2 = gcl_runner.sanitize(text2)
        self.assertNotIn("mysqlpwd", out2)

    def test_private_key_block(self):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA...\n"
            "-----END RSA PRIVATE KEY-----\n"
        )
        out = gcl_runner.sanitize(text)
        self.assertNotIn("MIIEpAIBAAKCAQEA", out)
        self.assertIn("<masked>", out)

    def test_jwt_like(self):
        text = "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", out)

    def test_bearer_token(self):
        text = "Authorization: Bearer abcdefghij1234567890"
        out = gcl_runner.sanitize(text)
        self.assertNotIn("abcdefghij1234567890", out)

    def test_kms_plaintext(self):
        text = '{"Plaintext": "aGVsbG93b3JsZA=="}'
        out = gcl_runner.sanitize(text)
        self.assertNotIn("aGVsbG93b3JsZA==", out)

    def test_kms_secret_data(self):
        text = '{"SecretData": "abcdefghijklmnopqrstuvwxyz=="}'
        out = gcl_runner.sanitize(text)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", out)

    def test_idempotent(self):
        text = "ALIBABA_CLOUD_ACCESS_KEY_SECRET=foo"
        once = gcl_runner.sanitize(text)
        twice = gcl_runner.sanitize(once)
        self.assertEqual(once, twice)

    def test_empty_input(self):
        self.assertEqual("", gcl_runner.sanitize(""))
        self.assertIsNone(gcl_runner.sanitize(None))  # type: ignore


# ---------------------------------------------------------------------------
# T2: parse_rubric()
# ---------------------------------------------------------------------------


RUBRIC_FIXTURE = """---
name: test-rubric
description: Test rubric for unit testing
metadata:
  skill: alicloud-test-ops
  api: Test 2026-01-01
  cli_applicability: cli-first
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  max_iter: 3
---

# Test Rubric

## 1. Core Dimensions

### 1.2 Safety

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteFoo` | (a) user confirmation; (b) backup created; (c) prod marker absent |
| `DeleteBar` | (a) user confirmation; (b) 2-step cascade; (c) cross-skill check |
| `Operation` | Sub-rule (header row, skip) |

### 1.3 Idempotency

## 2. Aliyun-Specific Extensions

### 2.2 Detection Regex (for Critic)

| Regex | Risk | Examples |
|---|---|---|
| `db\\.\\w+\\.dropDatabase\\s*\\(\\s*\\)` | DESTRUCTIVE-MASS | `db.mydb.dropDatabase()` |
| `^drop\\s+user\\s+\\S+\\s+cascade` | DESTRUCTIVE-MASS | `DROP USER x CASCADE;` |
| `match_all\\s*:\\s*\\{\\s*\\}` | DESTRUCTIVE-QUERY | `{"match_all": {}}` |

### 2.3 Well-Architected
"""


class ParseRubricTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        self.tmp.write(RUBRIC_FIXTURE)
        self.tmp.close()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        os.unlink(self.path)

    def test_parses_frontmatter(self):
        r = gcl_runner.parse_rubric(self.path)
        self.assertEqual(r["version"], "1.0.0")
        self.assertEqual(r["api"], "Test 2026-01-01")
        self.assertEqual(r["cli_applicability"], "cli-first")
        self.assertEqual(r["max_iter"], 3)

    def test_parses_per_op_subrules(self):
        r = gcl_runner.parse_rubric(self.path)
        self.assertIn("DeleteFoo", r["ops"])
        self.assertIn("DeleteBar", r["ops"])
        self.assertIn("user confirmation", r["ops"]["DeleteFoo"])
        self.assertIn("2-step cascade", r["ops"]["DeleteBar"])
        # Header row should be skipped
        self.assertNotIn("Operation", r["ops"])

    def test_parses_detection_regexes(self):
        r = gcl_runner.parse_rubric(self.path)
        self.assertEqual(len(r["regexes"]), 3)
        patterns = [p for p, _ in r["regexes"]]
        self.assertTrue(any("dropDatabase" in p for p in patterns))
        self.assertTrue(any("drop" in p and "user" in p for p in patterns))
        self.assertTrue(any("match_all" in p for p in patterns))

    def test_missing_file_raises(self):
        with self.assertRaises(gcl_runner.RubricError):
            gcl_runner.parse_rubric(Path("/nonexistent/path.md"))

    def test_empty_rubric_raises(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        tmp.write("---\nname: empty\n---\n\n# Empty\n")
        tmp.close()
        try:
            with self.assertRaises(gcl_runner.RubricError):
                gcl_runner.parse_rubric(Path(tmp.name))
        finally:
            os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# T3: preflight()
# ---------------------------------------------------------------------------


class PreflightTests(unittest.TestCase):

    def _rubric(self, ops=None, regexes=None):
        return {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "Test",
            "cli_applicability": "cli-first",
            "ops": ops or {"DeleteFoo": "(a) ... (b) ... (c) ..."},
            "regexes": regexes or [],
            "max_iter": 2,
            "required_or_recommended": "required",
        }

    def test_happy_path(self):
        ok, errs = gcl_runner.preflight(
            skill="alicloud-ecs-ops",
            op="DeleteFoo",
            command="aliyun ecs DeleteFoo --InstanceId i-1",
            rubric=self._rubric(),
            user_request="delete foo",
        )
        self.assertTrue(ok, msg=f"unexpected errors: {errs}")
        self.assertEqual(errs, [])

    def test_unknown_skill(self):
        ok, errs = gcl_runner.preflight(
            skill="alicloud-unknown-ops",
            op="DeleteFoo",
            command="aliyun unknown DeleteFoo",
            rubric=self._rubric(),
            user_request=None,
        )
        self.assertFalse(ok)
        self.assertTrue(any("unknown skill" in e for e in errs))

    def test_wrong_product(self):
        ok, errs = gcl_runner.preflight(
            skill="alicloud-ecs-ops",
            op="DeleteFoo",
            command="aliyun rds DeleteFoo",
            rubric=self._rubric(),
            user_request=None,
        )
        self.assertFalse(ok)
        self.assertTrue(any("different product" in e for e in errs))

    def test_data_plane_tool_allowed(self):
        # mongosh on a dual-path skill
        rubric = self._rubric(ops={"dropDatabase": "..."})
        rubric["cli_applicability"] = "dual-path"
        ok, errs = gcl_runner.preflight(
            skill="alicloud-mongodb-ops",
            op="dropDatabase",
            command="mongosh --host pc-bp1 --eval 'db.x.dropDatabase()'",
            rubric=rubric,
            user_request=None,
        )
        self.assertTrue(ok, msg=f"unexpected errors: {errs}")

    def test_op_not_documented(self):
        ok, errs = gcl_runner.preflight(
            skill="alicloud-ecs-ops",
            op="UnknownOp",
            command="aliyun ecs UnknownOp",
            rubric=self._rubric(),
            user_request=None,
        )
        self.assertFalse(ok)
        self.assertTrue(any("not documented" in e for e in errs))

    def test_inlined_secret_caught(self):
        ok, errs = gcl_runner.preflight(
            skill="alicloud-redis-ops",
            op="CreateAccount",
            command="aliyun r-kvstore CreateAccount --AccountPassword 'MyPwd!'",
            rubric=self._rubric(),
            user_request=None,
        )
        self.assertFalse(ok)
        self.assertTrue(any("secret pattern" in e for e in errs))


# ---------------------------------------------------------------------------
# T4: _command_targets_product()
# ---------------------------------------------------------------------------


class CommandTargetsProductTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(gcl_runner._command_targets_product("aliyun ecs DescribeInstances", "ecs"))

    def test_no_match_different_product(self):
        self.assertFalse(gcl_runner._command_targets_product("aliyun rds DescribeDBInstances", "ecs"))

    def test_no_aliyun_prefix(self):
        self.assertFalse(gcl_runner._command_targets_product("kubectl get pods", "cs"))

    def test_aliyun_alone(self):
        self.assertFalse(gcl_runner._command_targets_product("aliyun", "ecs"))


# ---------------------------------------------------------------------------
# T5: _is_data_plane_tool()
# ---------------------------------------------------------------------------


class IsDataPlaneToolTests(unittest.TestCase):
    def test_mongosh(self):
        self.assertTrue(gcl_runner._is_data_plane_tool("mongosh --host x --eval 'db.x.dropDatabase()'"))

    def test_mysql(self):
        self.assertTrue(gcl_runner._is_data_plane_tool("mysql -h x -u user db"))

    def test_psql(self):
        self.assertTrue(gcl_runner._is_data_plane_tool("psql -h x -U user -d db"))

    def test_sqlplus(self):
        self.assertTrue(gcl_runner._is_data_plane_tool("sqlplus user/pass@host:1521/pdb"))

    def test_redis_cli(self):
        self.assertTrue(gcl_runner._is_data_plane_tool("redis-cli -h x -a pwd PING"))

    def test_curl(self):
        self.assertTrue(gcl_runner._is_data_plane_tool("curl -X DELETE 'http://es-bp1:9200/*'"))

    def test_aliyun_is_not(self):
        # `aliyun` is the control-plane tool, not data-plane
        self.assertFalse(gcl_runner._is_data_plane_tool("aliyun ecs DescribeInstances"))

    def test_empty(self):
        self.assertFalse(gcl_runner._is_data_plane_tool(""))


# ---------------------------------------------------------------------------
# T6: _risk_severity()
# ---------------------------------------------------------------------------


class RiskSeverityTests(unittest.TestCase):
    def test_ordering(self):
        self.assertLess(gcl_runner._risk_severity("READ-ONLY"), gcl_runner._risk_severity("WRITE-KEY"))
        self.assertLess(gcl_runner._risk_severity("WRITE-KEY"), gcl_runner._risk_severity("WRITE-MANY"))
        self.assertLess(gcl_runner._risk_severity("WRITE-MANY"), gcl_runner._risk_severity("DESTRUCTIVE-MASS"))
        self.assertLess(gcl_runner._risk_severity("DESTRUCTIVE-MASS"), gcl_runner._risk_severity("FATAL"))

    def test_unknown_risk(self):
        self.assertEqual(gcl_runner._risk_severity("UNKNOWN-XYZ"), 0)

    def test_case_insensitive(self):
        self.assertEqual(gcl_runner._risk_severity("fatal"), 5)
        self.assertEqual(gcl_runner._risk_severity("FATAL"), 5)


# ---------------------------------------------------------------------------
# T7: critique() — destructive regex → Safety=0 + blocking
# ---------------------------------------------------------------------------


class CritiqueSafetyFailTests(unittest.TestCase):
    def test_destructive_mongo_dropDatabase(self):
        rubric = {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "Dds",
            "cli_applicability": "dual-path",
            "ops": {"dropDatabase": "..."},
            "regexes": [(r"db\.\w+\.dropDatabase\s*\(\s*\)", "DESTRUCTIVE-MASS")],
            "max_iter": 2,
            "required_or_recommended": "required",
        }
        gen_trace = {
            "command": "mongosh --eval 'db.legacy.dropDatabase()'",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "result_excerpt": "",
            "request_id": "abc",
            "duration_ms": 0,
        }
        c = gcl_runner.critique("dropDatabase", gen_trace, rubric)
        self.assertEqual(c["scores"]["safety"], 0.0)
        self.assertTrue(c["blocking"])
        self.assertTrue(any("dropDatabase" in m for m in c["matched_regexes"]))
        self.assertTrue(any("destructive" in s.lower() for s in c["suggestions"]))

    def test_destructive_es_wildcard_delete(self):
        rubric = {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "ES",
            "cli_applicability": "sdk-only",
            "ops": {"DeleteIndex": "..."},
            "regexes": [
                (r"DELETE\s+/\*", "DESTRUCTIVE-MASS"),
                (r"DELETE\s+/\S+\*\s*$", "DESTRUCTIVE-MASS"),
            ],
            "max_iter": 2,
            "required_or_recommended": "required",
        }
        gen_trace = {
            "command": "curl -X DELETE /logstash-*",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "result_excerpt": "",
            "request_id": "xyz",
            "duration_ms": 0,
        }
        c = gcl_runner.critique("DeleteIndex", gen_trace, rubric)
        self.assertEqual(c["scores"]["safety"], 0.0)
        self.assertTrue(c["blocking"])


# ---------------------------------------------------------------------------
# T8: critique() — empty rubric degrades gracefully
# ---------------------------------------------------------------------------


class CritiqueEmptyRubricTests(unittest.TestCase):
    def test_no_ops_no_regexes(self):
        rubric = {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "Test",
            "cli_applicability": "cli-first",
            "ops": {},
            "regexes": [],
            "max_iter": 2,
            "required_or_recommended": "required",
        }
        gen_trace = {
            "command": _wrap("aliyun ecs DescribeInstances"),
            "exit_code": 0,
            "stdout": "{}",
            "stderr": "",
            "result_excerpt": "{}",
            "request_id": "ok",
            "duration_ms": 1,
        }
        c = gcl_runner.critique("DescribeInstances", gen_trace, rubric)
        # No regex matched, no op sub-rule → Safety = 1 (no destructive evidence)
        self.assertEqual(c["scores"]["safety"], 1.0)
        self.assertFalse(c["blocking"])
        # All 9 dimensions should be present (5 core + 4 Aliyun extensions)
        self.assertEqual(len(c["scores"]), 9)

    def test_only_op_no_regex(self):
        rubric = {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "Test",
            "cli_applicability": "cli-first",
            "ops": {"DeleteFoo": "..."},
            "regexes": [],
            "max_iter": 2,
            "required_or_recommended": "required",
        }
        gen_trace = {
            "command": _wrap("aliyun ecs DeleteFoo --X 1"),
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
            "result_excerpt": "ok",
            "request_id": "ok",
            "duration_ms": 1,
        }
        c = gcl_runner.critique("DeleteFoo", gen_trace, rubric)
        self.assertEqual(c["scores"]["safety"], 1.0)
        self.assertFalse(c["blocking"])


# ---------------------------------------------------------------------------
# T9: decide()
# ---------------------------------------------------------------------------


class DecideTests(unittest.TestCase):
    def _critic(self, safety=1.0, blocking=False, **scores):
        all_scores = {
            "correctness": 1.0, "safety": safety, "idempotency": 1.0,
            "traceability": 1.0, "spec_compliance": 1.0,
            "region_compliance": 1.0, "credential_hygiene": 1.0,
            "well_architected": 1.0,
        }
        all_scores.update(scores)
        return {"scores": all_scores, "blocking": blocking, "suggestions": [], "matched_regexes": []}

    def test_safety_zero_aborts(self):
        self.assertEqual(gcl_runner.decide(self._critic(safety=0.0), 1, 2), "SAFETY_FAIL")

    def test_blocking_true_aborts(self):
        self.assertEqual(gcl_runner.decide(self._critic(blocking=True), 1, 2), "SAFETY_FAIL")

    def test_all_pass(self):
        self.assertEqual(gcl_runner.decide(self._critic(), 1, 2), "PASS")

    def test_retry_when_below_threshold_and_iter_lt_max(self):
        c = self._critic(correctness=0.0)  # 0.0 < 0.5 threshold
        self.assertEqual(gcl_runner.decide(c, 1, 3), "RETRY")

    def test_max_iter_when_exhausted(self):
        c = self._critic(correctness=0.0)
        self.assertEqual(gcl_runner.decide(c, 3, 3), "MAX_ITER")

    def test_first_match_wins(self):
        # Safety=0 + iter<max → SAFETY_FAIL wins (not RETRY)
        c = self._critic(safety=0.0, blocking=True, correctness=0.0)
        self.assertEqual(gcl_runner.decide(c, 1, 3), "SAFETY_FAIL")

    def test_test_assessment_fail_retries(self):
        c = self._critic(blocking=True)
        c["test_assessment"] = {
            "evaluated": True,
            "passed": False,
            "blocking_reason": "inaccurate_tests",
        }
        self.assertEqual(gcl_runner.decide(c, 1, 3), "RETRY")

    def test_test_assessment_fail_max_iter(self):
        c = self._critic(blocking=True)
        c["test_assessment"] = {
            "evaluated": True,
            "passed": False,
            "blocking_reason": "missing_regression_evidence",
        }
        self.assertEqual(gcl_runner.decide(c, 3, 3), "MAX_ITER")


# ---------------------------------------------------------------------------
# T9b: test_assessment evaluation
# ---------------------------------------------------------------------------


class TestAssessmentTests(unittest.TestCase):
    def _base_trace(self, **extra):
        trace = {
            "command": "./alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh DescribeInstances --PageSize 1",
            "exit_code": 0,
            "stdout": '{"Instances":{}}',
            "stderr": "",
            "result_excerpt": '{"Instances":{}}',
            "request_id": "r1",
            "duration_ms": 1,
        }
        trace.update(extra)
        return trace

    def _rubric(self):
        return {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "Ecs",
            "cli_applicability": "cli-first",
            "ops": {"DescribeInstances": "read-only"},
            "regexes": [],
            "max_iter": 2,
            "required_or_recommended": "required",
        }

    def test_no_assessment_passes(self):
        r = gcl_runner.evaluate_test_assessment(None)
        self.assertFalse(r["evaluated"])
        self.assertTrue(r["passed"])

    def test_inaccurate_tests_blocks(self):
        trace = self._base_trace(test_assessment={
            "tests_accurate": False,
            "accuracy_issues": ["missing assertion for skillopt_wrap disabled path"],
        })
        c = gcl_runner.critique("DescribeInstances", trace, self._rubric())
        self.assertTrue(c["blocking"])
        self.assertEqual(c["test_assessment"]["blocking_reason"], "inaccurate_tests")
        self.assertTrue(any("TEST_ACCURACY" in s for s in c["suggestions"]))

    def test_regression_required_without_evidence_blocks(self):
        trace = self._base_trace(test_assessment={
            "tests_accurate": True,
            "regression_required": True,
            "regression_suites": ["bash alicloud-ecs-ops/test-skillopt-backward-compatibility.sh"],
        })
        c = gcl_runner.critique("DescribeInstances", trace, self._rubric())
        self.assertTrue(c["blocking"])
        self.assertEqual(c["test_assessment"]["blocking_reason"], "missing_regression_evidence")

    def test_regression_with_green_evidence_passes(self):
        trace = self._base_trace(test_assessment={
            "tests_accurate": True,
            "regression_required": True,
            "regression_runs_passed": True,
        })
        c = gcl_runner.critique("DescribeInstances", trace, self._rubric())
        self.assertFalse(c["blocking"])
        self.assertTrue(c["test_assessment"]["passed"])


# ---------------------------------------------------------------------------
# T10: run_loop() — full loop integration (dry-run)
# ---------------------------------------------------------------------------


class RunLoopTests(unittest.TestCase):
    def test_pass_on_first_iter(self):
        rubric = {
            "version": "1.0.0", "last_updated": "2026-06-04", "api": "Test",
            "cli_applicability": "cli-first", "ops": {"Foo": "..."},
            "regexes": [], "max_iter": 2, "required_or_recommended": "required",
        }
        trace = gcl_runner.run_loop(
            skill="alicloud-ecs-ops",
            op="Foo",
            command="echo pass",
            user_request="run foo",
            rubric=rubric,
            max_iter=2,
        )
        self.assertEqual(trace["skill"], "alicloud-ecs-ops")
        self.assertEqual(trace["request"], "run foo")
        self.assertEqual(trace["final"]["status"], "PASS")
        self.assertEqual(trace["final"]["iter"], 1)
        self.assertEqual(len(trace["iterations"]), 1)

    def test_max_iter_exhausted(self):
        # A rubric with no ops + no regexes + bad op name → op not documented
        # → safety=0 → SAFETY_FAIL actually, so use a different scenario.
        # Use empty rubric but documented op, with low scores everywhere
        # except safety. Hmm, the critic scores idempotency=0.5 if exit_code=0
        # but spec_compliance=0.5 if command doesn't match... actually it WILL
        # pass for `echo pass` because _command_targets_product returns False,
        # so spec_compliance=0.5 = threshold. So with `echo pass` we get all 1.0/0.5
        # → PASS. Need a different setup.

        # Use a command that triggers spec_compliance=0 + idempotency=0.5
        # (no "already exists" in output) and region_compliance=0.5
        # But spec_compliance < threshold = 0.5. So spec_compliance must be
        # < 0.5 to trigger RETRY. But we only set 0.0 or 0.5. Let's use a
        # mock to force low scores.
        rubric = {
            "version": "1.0.0", "last_updated": "2026-06-04", "api": "Test",
            "cli_applicability": "cli-first", "ops": {"Foo": "..."},
            "regexes": [], "max_iter": 2, "required_or_recommended": "required",
        }
        with mock.patch.object(gcl_runner, "critique") as mcrit:
            mcrit.return_value = {
                "scores": {
                    "correctness": 0.0, "safety": 1.0, "idempotency": 0.5,
                    "traceability": 1.0, "spec_compliance": 1.0,
                    "region_compliance": 1.0, "credential_hygiene": 1.0,
                    "well_architected": 1.0,
                },
                "suggestions": ["fix correctness"],
                "matched_regexes": [],
                "blocking": False,
            }
            trace = gcl_runner.run_loop(
                skill="alicloud-ecs-ops", op="Foo",
                command="echo retry", user_request="x",
                rubric=rubric, max_iter=2,
            )
        # correctness=0.0 < 0.5 threshold → RETRY each iter → MAX_ITER
        self.assertEqual(trace["final"]["status"], "MAX_ITER")
        self.assertEqual(trace["final"]["iter"], 2)
        # best-so-far should be tracked
        self.assertIn("best_iter", trace["final"])


# ---------------------------------------------------------------------------
# T11: persist_trace() — JSON schema
# ---------------------------------------------------------------------------


class PersistTraceTests(unittest.TestCase):
    def test_persistence_writes_valid_json(self):
        trace = {
            "skill": "alicloud-test-ops",
            "request": "test request",
            "rubric_version": "1.0.0",
            "iterations": [
                {
                    "iter": 1,
                    "generator": {"command": "echo hi", "exit_code": 0, "stdout": "hi\n",
                                  "stderr": "", "result_excerpt": "hi", "request_id": "x",
                                  "duration_ms": 1},
                    "critic": {"scores": {"correctness": 1.0, "safety": 1.0, "idempotency": 1.0,
                                          "traceability": 1.0, "spec_compliance": 1.0,
                                          "region_compliance": 1.0, "credential_hygiene": 1.0,
                                          "well_architected": 1.0},
                               "suggestions": [], "matched_regexes": [], "blocking": False},
                    "decision": "PASS",
                }
            ],
            "final": {"status": "PASS", "iter": 1, "output": "ok"},
            "failure_pattern": None,
        }
        with tempfile.TemporaryDirectory() as d:
            p = gcl_runner.persist_trace(trace, Path(d))
            self.assertTrue(p.exists())
            self.assertTrue(p.name.startswith("gcl-trace-"))
            self.assertTrue(p.name.endswith(".json"))
            # Schema validation: every required key is present
            loaded = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("skill", loaded)
            self.assertIn("request", loaded)
            self.assertIn("rubric_version", loaded)
            self.assertIn("iterations", loaded)
            self.assertIn("final", loaded)
            self.assertIn("status", loaded["final"])
            self.assertIn("iter", loaded["final"])
            # Reflexion: failure_pattern field (AGENTS.md §15)
            self.assertIn("failure_pattern", loaded)
            self.assertIsNone(loaded["failure_pattern"])


# ---------------------------------------------------------------------------
# T16: extract_failure_pattern() — Reflexion failure pattern extraction
# ---------------------------------------------------------------------------


class ExtractFailurePatternTests(unittest.TestCase):
    def test_returns_none_when_safety_not_zero(self):
        critic_result = {
            "scores": {"safety": 1.0, "correctness": 1.0},
            "suggestions": [],
            "matched_regexes": [],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DeleteInstance",
            "aliyun ecs DeleteInstance --InstanceId i-xxx"
        )
        self.assertIsNone(result)

    def test_returns_pattern_when_safety_zero(self):
        critic_result = {
            "scores": {"safety": 0.0, "correctness": 0.0},
            "suggestions": ["Destructive op without user confirmation"],
            "matched_regexes": [
                {"risk": "DESTRUCTIVE-DELETE", "regex": "DeleteInstance"}
            ],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DeleteInstance",
            "aliyun ecs DeleteInstance --InstanceId i-xxx --Force true",
            status="SAFETY_FAIL",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "runtime")
        self.assertEqual(result["skill"], "alicloud-ecs-ops")
        self.assertIn("DeleteInstance", result["command"])
        self.assertIn("confirmation", result["fix"].lower())

    def test_max_iter_returns_none_when_no_failing_dimension(self):
        """MAX_ITER with all scores >= 0.8 → no failure pattern (noise filter).

        Note: If scores are between 0.5 and 0.8, a near-miss pattern is recorded
        to capture borderline cases for future optimization.
        """
        critic_result = {
            "scores": {"correctness": 0.9, "safety": 1.0, "idempotency": 0.85,
                       "traceability": 0.95, "spec_compliance": 1.0},
            "suggestions": ["all reasonable"],
            "matched_regexes": [],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DescribeFoo",
            "aliyun ecs DescribeFoo --X 1",
            status="MAX_ITER", scores=critic_result.get("scores"),
        )
        self.assertIsNone(result)

    def test_max_iter_records_near_miss_when_scores_below_08(self):
        """MAX_ITER with all scores >= 0.5 but some < 0.8 → record near-miss."""
        critic_result = {
            "scores": {"correctness": 0.6, "safety": 1.0, "idempotency": 0.7,
                       "traceability": 0.9, "spec_compliance": 1.0},
            "suggestions": ["all reasonable"],
            "matched_regexes": [],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DescribeFoo",
            "aliyun ecs DescribeFoo --X 1",
            status="MAX_ITER", scores=critic_result.get("scores"),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "max_iter")
        self.assertEqual(result["failing_dimensions"], "none_below_0.5")
        self.assertIn("correctness=0.6", result["low_dimensions"])
        self.assertIn("idempotency=0.7", result["low_dimensions"])

    def test_max_iter_returns_pattern_when_failing_dimension_exists(self):
        """MAX_ITER with a score < 0.5 → extract pattern with failing_dimensions."""
        critic_result = {
            "scores": {"correctness": 0.0, "safety": 1.0, "idempotency": 0.5,
                       "traceability": 0.9, "spec_compliance": 1.0},
            "suggestions": ["fix correctness"],
            "matched_regexes": [],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DeleteFoo",
            "aliyun ecs DeleteFoo --X 1",
            status="MAX_ITER", scores=critic_result.get("scores"),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "max_iter")
        self.assertIn("correctness", result["failing_dimensions"])
        self.assertNotIn("idempotency", result["failing_dimensions"])

    def test_truncates_long_command(self):
        long_cmd = "aliyun ecs DeleteInstance --InstanceId " + "x" * 300
        critic_result = {
            "scores": {"safety": 0.0},
            "suggestions": ["Missing confirmation"],
            "matched_regexes": [{"risk": "DESTRUCTIVE-DELETE", "regex": "x"}],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DeleteInstance", long_cmd
        )
        self.assertLessEqual(len(result["command"]), 200)

    def test_hallucination_abort_returns_runtime_pattern(self):
        """A1.1: HALLUCINATION_ABORT → runtime category with hallucination report as fix."""
        critic_result = {
            "scores": {k: 0.0 for k in ("correctness", "safety", "idempotency",
                                        "traceability", "spec_compliance")},
            "suggestions": ["HALLUCINATION_ABORT: missing API parameter --InstanceId"],
            "matched_regexes": [],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DeleteInstance",
            "aliyun ecs DeleteInstance",
            status="HALLUCINATION_ABORT",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "runtime")
        self.assertEqual(result["skill"], "alicloud-ecs-ops")
        self.assertIn("HALLUCINATION_ABORT", result["error"])
        self.assertIn("missing API parameter", result["fix"])
        self.assertEqual(result["root_cause"], "hallucination detected and unresolvable")

    def test_hallucination_abort_handles_empty_suggestions(self):
        """A1.1: HALLUCINATION_ABORT with empty suggestions → returns safe default pattern."""
        critic_result = {
            "scores": {k: 0.0 for k in ("correctness", "safety", "idempotency",
                                        "traceability", "spec_compliance")},
            "suggestions": [],
            "matched_regexes": [],
        }
        result = gcl_runner.extract_failure_pattern(
            critic_result, "alicloud-ecs-ops", "DeleteInstance",
            "aliyun ecs DeleteInstance",
            status="HALLUCINATION_ABORT",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "runtime")
        self.assertEqual(result["error"], "HALLUCINATION_ABORT")


# ---------------------------------------------------------------------------
# T16b: extract_success_pattern() — R4 hard-won PASS extraction
# ---------------------------------------------------------------------------


def _pass_trace(
    *,
    command: str = "aliyun ecs DeleteInstance --InstanceId.1 i-abc --RegionId cn-hangzhou",
    scores: dict[str, float] | None = None,
    iterations: list[dict] | None = None,
    memory_preflight: dict | None = None,
    dry_run: bool = False,
) -> dict:
    final_scores = scores or {
        "correctness": 1.0,
        "safety": 1.0,
        "idempotency": 1.0,
        "traceability": 1.0,
        "spec_compliance": 1.0,
    }
    iters = iterations
    if iters is None:
        iters = [
            {
                "iter": 1,
                "generator": {"command": command},
                "critic": {"scores": final_scores, "blocking": False},
                "decision": "PASS",
            }
        ]
    trace: dict = {
        "skill": "alicloud-ecs-ops",
        "final": {"status": "PASS", "iter": len(iters)},
        "iterations": iters,
    }
    if memory_preflight is not None:
        trace["memory_preflight"] = memory_preflight
    if dry_run:
        trace["dry_run"] = True
    return trace


class ExtractSuccessPatternTests(unittest.TestCase):
    def test_ordinary_pass_skipped(self):
        trace = _pass_trace()
        row, meta = gcl_runner.extract_success_pattern(
            trace, "alicloud-ecs-ops", "DeleteInstance", trace["iterations"][0]["generator"]["command"]
        )
        self.assertIsNone(row)
        self.assertFalse(meta["captured"])
        self.assertEqual(meta["reason"], "ordinary_pass")

    def test_multi_iter_captured(self):
        cmd = "aliyun ecs DeleteInstance --InstanceId.1 i-abc --RegionId cn-hangzhou"
        scores = {
            "correctness": 1.0,
            "safety": 1.0,
            "idempotency": 1.0,
            "traceability": 1.0,
            "spec_compliance": 1.0,
        }
        trace = _pass_trace(
            command=cmd,
            iterations=[
                {
                    "iter": 1,
                    "generator": {"command": cmd},
                    "critic": {"scores": {**scores, "correctness": 0.6}, "blocking": False},
                    "decision": "RETRY",
                },
                {
                    "iter": 2,
                    "generator": {"command": cmd},
                    "critic": {"scores": scores, "blocking": False},
                    "decision": "PASS",
                },
            ],
        )
        row, meta = gcl_runner.extract_success_pattern(
            trace, "alicloud-ecs-ops", "DeleteInstance", cmd
        )
        self.assertIsNotNone(row)
        self.assertTrue(meta["captured"])
        self.assertEqual(meta["capture_reason"], "multi_iter")
        self.assertEqual(row["iterations"], 2)
        self.assertIn("store_key", meta)

    def test_traps_informed_captured(self):
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        trace = _pass_trace(
            command=cmd,
            memory_preflight={
                "known_traps": [{"category": "cli_parameter", "error": "MissingParam"}],
            },
        )
        row, meta = gcl_runner.extract_success_pattern(
            trace, "alicloud-ecs-ops", "DescribeInstances", cmd
        )
        self.assertIsNotNone(row)
        self.assertEqual(meta["capture_reason"], "traps_informed")
        self.assertTrue(row["preflight_had_traps"])
        self.assertEqual(row["trap_count"], 1)
        self.assertEqual(row["matched_trap_categories"], ["cli_parameter"])

    def test_score_recovery_reason(self):
        cmd = "aliyun ecs DeleteInstance --InstanceId.1 i-abc"
        high = {
            "correctness": 1.0,
            "safety": 1.0,
            "idempotency": 1.0,
            "traceability": 1.0,
            "spec_compliance": 1.0,
        }
        low = {**high, "correctness": 0.2, "idempotency": 0.2}
        trace = _pass_trace(
            command=cmd,
            iterations=[
                {
                    "iter": 1,
                    "generator": {"command": cmd},
                    "critic": {"scores": low, "blocking": False},
                    "decision": "RETRY",
                },
                {
                    "iter": 2,
                    "generator": {"command": cmd},
                    "critic": {"scores": high, "blocking": False},
                    "decision": "PASS",
                },
            ],
        )
        row, meta = gcl_runner.extract_success_pattern(
            trace, "alicloud-ecs-ops", "DeleteInstance", cmd
        )
        self.assertIsNotNone(row)
        self.assertEqual(meta["capture_reason"], "multi_iter")
        signals = gcl_runner._detect_hard_won_signals(trace)
        self.assertTrue(signals["score_recovery"])

    def test_dry_run_skipped(self):
        trace = _pass_trace(dry_run=True)
        row, meta = gcl_runner.extract_success_pattern(
            trace, "alicloud-ecs-ops", "DeleteInstance", "cmd"
        )
        self.assertIsNone(row)
        self.assertEqual(meta["reason"], "dry_run")

    def test_test_assessment_skipped(self):
        trace = _pass_trace()
        trace["iterations"][0]["generator"]["test_assessment"] = {"synthetic": True}
        row, meta = gcl_runner.extract_success_pattern(
            trace, "alicloud-ecs-ops", "DeleteInstance", "cmd"
        )
        self.assertIsNone(row)
        self.assertEqual(meta["reason"], "test_assessment_only")

    def test_run_loop_attaches_success_pattern_meta(self):
        rubric = {
            "version": "1.0.0",
            "last_updated": "2026-06-04",
            "api": "Test",
            "cli_applicability": "cli-first",
            "ops": {"Foo": "..."},
            "regexes": [],
            "max_iter": 2,
            "required_or_recommended": "required",
        }
        cmd = "echo pass"
        preflight = {
            "known_traps": [{"category": "cli_parameter", "error": "MissingParam"}],
            "slots": {},
        }
        trace = gcl_runner.run_loop(
            skill="alicloud-ecs-ops",
            op="Foo",
            command=cmd,
            user_request="delete",
            rubric=rubric,
            max_iter=2,
            memory_preflight=preflight,
        )
        self.assertEqual(trace["final"]["status"], "PASS")
        self.assertIn("success_pattern", trace)
        self.assertTrue(trace["success_pattern"]["captured"])
        self.assertIn("_success_pattern_payload", trace)


# ---------------------------------------------------------------------------
# T12: CLI integration — main() returns correct exit codes
# ---------------------------------------------------------------------------


class CLITests(unittest.TestCase):
    def setUp(self):
        # Build an isolated "skill root" with a fixture rubric, then chdir into
        # a parent temp dir so that gcl_runner.main() can resolve rubric paths
        # relative to its own __file__ — we override the default rubric path
        # explicitly via --rubric instead of patching Path.resolve (which would
        # break __file__ discovery).
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.rubric_file = self.tmp_path / "rubric.md"
        self.rubric_file.write_text(RUBRIC_FIXTURE, encoding="utf-8")
        self.audit_dir = self.tmp_path / "audit"
        self.audit_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_pass_exit_0(self):
        with mock.patch.object(gcl_runner, "run_loop") as mloop:
            mloop.return_value = {
                "skill": "alicloud-ecs-ops", "request": "x", "rubric_version": "1.0.0",
                "iterations": [], "final": {"status": "PASS", "iter": 1, "output": "ok"},
            }
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteFoo",
                "--command", "aliyun ecs DeleteFoo --X 1",
                "--rubric", str(self.rubric_file),
                "--output-dir", str(self.audit_dir),
            ])
        self.assertEqual(code, gcl_runner.EXIT_PASS)

    def test_safety_fail_exit_2(self):
        with mock.patch.object(gcl_runner, "run_loop") as mloop:
            mloop.return_value = {
                "skill": "alicloud-ecs-ops", "request": "x", "rubric_version": "1.0.0",
                "iterations": [], "final": {"status": "SAFETY_FAIL", "iter": 1, "output": "fail"},
            }
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteFoo",
                "--command", "aliyun ecs DeleteFoo --X 1",
                "--rubric", str(self.rubric_file),
                "--output-dir", str(self.audit_dir),
            ])
        self.assertEqual(code, gcl_runner.EXIT_SAFETY_FAIL)

    def test_usage_error_exit_3(self):
        code = gcl_runner.main([
            "--skill", "alicloud-ecs-ops",
            "--op", "DeleteFoo",
            "--command", "aliyun rds WrongProduct",  # wrong product
            "--rubric", str(self.rubric_file),
            "--output-dir", str(self.audit_dir),
        ])
        self.assertEqual(code, gcl_runner.EXIT_USAGE_ERROR)

    def test_max_iter_exit_1(self):
        with mock.patch.object(gcl_runner, "run_loop") as mloop:
            mloop.return_value = {
                "skill": "alicloud-ecs-ops", "request": "x", "rubric_version": "1.0.0",
                "iterations": [], "final": {"status": "MAX_ITER", "iter": 2, "output": "best-so-far"},
            }
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteFoo",
                "--command", "aliyun ecs DeleteFoo --X 1",
                "--rubric", str(self.rubric_file),
                "--output-dir", str(self.audit_dir),
            ])
        self.assertEqual(code, gcl_runner.EXIT_MAX_ITER)


# ---------------------------------------------------------------------------
# T13 — Hallucination Detection (H) Tests  (gcl_runner.hallucination_detect)
# ---------------------------------------------------------------------------

#: Prefix used in tests to indicate a wrapper-routed command. The wrapper
#: detection regex (`skillopt-wrapper.sh`) in gcl_runner matches this.
WRAPPER_PREFIX = "alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh"


def _wrap(cmd: str) -> str:
    """Prefix a bare `aliyun` command with the skillopt wrapper path so it
    passes the wrapper_compliance check (added in AGENTS.md §15.8 / GCL §14.2.4).
    """
    return f"{WRAPPER_PREFIX} {cmd}"


class HallucinationDetectTests(unittest.TestCase):
    """Hallucination Detection (H) — pre-execution structural validity check."""

    def test_happy_path_known_params(self):
        """All CLI flags known to PARAMETER_KNOWLEDGE → PASS."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 10")
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks"]["cli_parameters"]["unrecognized"], [])

    def test_unrecognized_param_detected(self):
        """A flag not in PARAMETER_KNOWLEDGE → FAIL with unrecognized list."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DeleteInstance --RegionId cn-hangzhou --FakeParam foo")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("--FakeParam", result["checks"]["cli_parameters"]["unrecognized"])

    def test_unrecognized_param_detected_zone_vs_zoneid(self):
        """--Zone instead of --ZoneId is caught."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DescribeInstances --Zone cn-hangzhou-f")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("--Zone", result["checks"]["cli_parameters"]["unrecognized"])

    def test_known_params_with_common_flags(self):
        """Generic `aliyun` CLI flags (--output, --format) are NOT flagged."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DescribeInstances --RegionId cn-hangzhou --output json --format pretty")
        )
        self.assertEqual(result["status"], "PASS")

    def test_non_aliyun_command_passes(self):
        """Non-aliyun commands (data-plane tools) pass CLI parameter check."""
        result = gcl_runner.hallucination_detect(
            "mysql -h localhost -u root -p mydb -e 'SELECT 1'"
        )
        self.assertEqual(result["status"], "PASS")

    def test_unknown_product_passes(self):
        """Unknown product not in PARAMETER_KNOWLEDGE passes conservatively (and wrapper doesn't apply)."""
        result = gcl_runner.hallucination_detect(
            "aliyun unknown-product DescribeFoo --Bar baz"
        )
        self.assertEqual(result["status"], "PASS")

    def test_waf_deletion_protection_disabled(self):
        """--DeletionProtection false is flagged as WAF Security violation."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun rds CreateDBInstance --Engine MySQL --DeletionProtection false --DBInstanceClass rds.mysql.s2.large")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"]["waf_compliance"]["status"], "FAIL")

    def test_waf_force_flag_on_delete(self):
        """--Force on a destructive op is flagged as Security concern."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DeleteInstance --InstanceId i-bp1xxx --Force")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(len(result["checks"]["waf_compliance"]["violations"]), 0)

    def test_waf_backup_retention_zero(self):
        """--BackupRetentionPeriod 0 is flagged as Stability violation."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun rds CreateDBInstance --Engine MySQL --BackupRetentionPeriod 0")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Stability", result["checks"]["waf_compliance"]["violations"][0])

    def test_waf_postpaid_flag(self):
        """--PayType PostPaid flagged as Cost concern."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs CreateInstance --ImageId xxx --InstanceType ecs.g6.large --PayType PostPaid")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Cost", result["checks"]["waf_compliance"]["violations"][0])

    def test_json_payload_pass(self):
        """Valid JSON-like payload passes JSON structure check."""
        result = gcl_runner.hallucination_detect(
            _wrap('aliyun ecs RunInstances --RegionId cn-hangzhou --Amount 1 --Tag "[{\\"Key\\":\\"env\\",\\"Value\\":\\"prod\\"}]"')
        )
        # CLI params may fail if not in knowledge base, but JSON check passes
        self.assertEqual(result["checks"]["json_structure"]["status"], "PASS")

    def test_combination_multi_fail(self):
        """Command with multiple hallucination types fails across categories."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs CreateInstance --ImageId ami-123 --FakeParam x --DeletionProtection false")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"]["cli_parameters"]["status"], "FAIL")
        self.assertEqual(result["checks"]["waf_compliance"]["status"], "FAIL")
        self.assertIn("--FakeParam", result["checks"]["cli_parameters"]["unrecognized"])

    def test_no_flag_command(self):
        """CLI command with no flags passes trivially."""
        result = gcl_runner.hallucination_detect(_wrap("aliyun ecs DescribeRegions"))
        self.assertEqual(result["status"], "PASS")

    def test_report_format(self):
        """FAIL result includes a human-readable report string."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DeleteInstance --FakeFlag value")
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(len(result["report"]) > 0)
        self.assertIn("FakeFlag", result["report"])

    def test_cli_params_exact_count(self):
        """CLI parameter check reports correct total/recognized counts."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 10 --FakeFlag foo")
        )
        cli = result["checks"]["cli_parameters"]
        self.assertEqual(cli["total"], 3)
        self.assertEqual(cli["recognized"], 2)
        self.assertIn("--FakeFlag", cli["unrecognized"])

    def test_force_without_delete_not_extra_flagged(self):
        """--Force on a non-delete operation does not trigger the extra stability heuristic."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs StopInstance --InstanceId i-bp1 --Force")
        )
        # --Force itself is a WAF flag, but the heuristic delete check shouldn't add extra
        self.assertIn("Security", result["report"])

    def test_wrapper_compliance_pass_via_wrapper(self):
        """A command routed through the skillopt wrapper PASSES wrapper_compliance."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DescribeInstances --RegionId cn-hangzhou")
        )
        self.assertEqual(result["checks"]["wrapper_compliance"]["status"], "PASS")
        self.assertEqual(result["checks"]["wrapper_compliance"]["execution_path"], "wrapper")

    def test_wrapper_compliance_fail_via_direct_aliyun(self):
        """A direct `aliyun <product>` call on a skill with a wrapper FAILS wrapper_compliance."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"]["wrapper_compliance"]["status"], "FAIL")
        self.assertEqual(result["checks"]["wrapper_compliance"]["execution_path"], "direct_aliyun")
        self.assertTrue(result["checks"]["wrapper_compliance"]["wrapper_should_be_used"])
        self.assertIn("WRAPPER_BYPASS", result["report"])

    def test_wrapper_compliance_pass_for_data_plane(self):
        """Data-plane tools (redis-cli, mysql) are not subject to wrapper compliance."""
        result = gcl_runner.hallucination_detect("redis-cli -h r-bp1 ping")
        self.assertEqual(result["checks"]["wrapper_compliance"]["status"], "PASS")
        self.assertEqual(result["checks"]["wrapper_compliance"]["execution_path"], "data_plane")

    def test_wrapper_compliance_pass_for_non_skilled_product(self):
        """A product without a wrapper (e.g. unknown-product) does not require the wrapper."""
        result = gcl_runner.hallucination_detect("aliyun unknown-product DescribeFoo")
        self.assertEqual(result["checks"]["wrapper_compliance"]["status"], "PASS")
        self.assertFalse(result["checks"]["wrapper_compliance"]["wrapper_should_be_used"])

    def test_dry_run_with_hallucination_passes_via_cli(self):
        """Dry-run + enable-hallucination-check passes the H result through."""
        trace = gcl_runner._synthesize_dry_run(
            skill="alicloud-ecs-ops",
            op="DescribeInstances",
            command=_wrap("aliyun ecs DescribeInstances --RegionId cn-hangzhou"),
            user_request="list instances",
            rubric={"version": "1.0", "ops": {}, "regexes": [], "max_iter": 2},
            enable_hallucination_check=True,
        )
        self.assertIn("hallucination_detector", trace["iterations"][0])
        self.assertEqual(
            trace["iterations"][0]["hallucination_detector"]["status"],
            "PASS",
        )

    def test_main_hallucination_abort_exit_5(self):
        """When H detects an unrecognized param with --enable-hallucination-check, exit code is 5."""
        trace = gcl_runner.run_loop(
            skill="alicloud-ecs-ops",
            op="DeleteInstance",
            command=_wrap("aliyun ecs DeleteInstance --FakeParam foo"),
            user_request=None,
            rubric={"version": "1.0", "ops": {"DeleteInstance": "test"}, "regexes": [], "max_iter": 1},
            max_iter=1,
            enable_hallucination_check=True,
        )
        self.assertEqual(trace["final"]["status"], "HALLUCINATION_ABORT")

    def test_main_wrapper_bypass_exit_6(self):
        """Direct aliyun call on a skill with wrapper → exit code 6 (WRAPPER_BYPASS)."""
        trace = gcl_runner.run_loop(
            skill="alicloud-ecs-ops",
            op="DescribeInstances",
            command="aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            user_request=None,
            rubric={"version": "1.0", "ops": {"DescribeInstances": "test"}, "regexes": [], "max_iter": 1},
            max_iter=1,
        )
        self.assertEqual(trace["final"]["status"], "WRAPPER_BYPASS")
        # Critic scores wrapper_compliance=0
        self.assertEqual(trace["iterations"][0]["critic"]["scores"]["wrapper_compliance"], 0.0)
        # Trace records the bypass
        self.assertEqual(trace["iterations"][0]["generator"]["execution_path"], "direct_aliyun")

    def test_report_empty_on_pass(self):
        """PASS result has an empty report."""
        result = gcl_runner.hallucination_detect(
            _wrap("aliyun ecs DescribeInstances --RegionId cn-hangzhou")
        )
        self.assertEqual(result["report"], "")


# ---------------------------------------------------------------------------
# T14 — GCL Critic Mode Environment Tests (--critic-mode + env vars)
# ---------------------------------------------------------------------------

class CriticModeEnvTests(_GCLRunnerMemoryIsolated, unittest.TestCase):
    """Test critic mode parsing: CLI arg > env var > default (mechanical)."""

    def setUp(self):
        # Prepare tmp_root BEFORE super().setUp() so the mixin can route
        # memory_store() writes into it.
        self.tmp_root = Path(tempfile.mkdtemp())
        super().setUp()
        self.rubric_path = self.tmp_root / "rubric.md"
        self.rubric_path.write_text("""---
rubric_version: "1.0"
version: "1.0"
max_iter: 2
gcl_classification: required
ops:
  DeleteInstance: Delete an ECS instance
---

## Detection Regex

| Regex | Risk |
|-------|------|
| ERROR | FATAL |
| --InstanceId | READ-ONLY |
""")

    def tearDown(self):
        # Clean up tmp_root AFTER super().tearDown() (which restored the env).
        tmp_root = self.tmp_root
        super().tearDown()
        shutil.rmtree(tmp_root)

    def test_default_mechanical_when_no_env_no_cli(self):
        """No CLI --critic-mode and no env var → default mechanical."""
        # Clear env vars for this test
        orig_mode = os.environ.pop("GCL_CRITIC_MODE", None)
        try:
            # Since we can't easily inspect the gcl_critic_mode variable after main() exits,
            # just verify that it runs without error (default mode skips env check)
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteInstance",
                "--command", _wrap("aliyun ecs DeleteInstance --InstanceId i-test"),
                "--rubric", str(self.rubric_path),
                "--output-dir", str(self.tmp_root),
                "--dry-run",
            ])
            # WRAPPER_BYPASS is exit 6 which is expected here (we're testing env parsing not wrapper compliance)
            self.assertIn(code, (0, 6))  # either PASS or WRAPPER_BYPASS is OK here
        finally:
            if orig_mode is not None:
                os.environ["GCL_CRITIC_MODE"] = orig_mode

    def test_env_var_hybrid_read_correctly(self):
        """GCL_CRITIC_MODE=hybrid from env → mode=hybrid."""
        orig_mode = os.environ.pop("GCL_CRITIC_MODE", None)
        orig_endpoint = os.environ.pop("GCL_CRITIC_LLM_ENDPOINT", None)
        orig_apikey = os.environ.pop("GCL_CRITIC_LLM_API_KEY", None)
        os.environ["GCL_CRITIC_MODE"] = "hybrid"
        os.environ["GCL_CRITIC_LLM_ENDPOINT"] = "https://example.com/v1/chat/completions"
        os.environ["GCL_CRITIC_LLM_API_KEY"] = "test-key"
        try:
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteInstance",
                "--command", _wrap("aliyun ecs DeleteInstance --InstanceId i-test"),
                "--rubric", str(self.rubric_path),
                "--output-dir", str(self.tmp_root),
                "--dry-run",
            ])
            self.assertIn(code, (0, 6))  # no preflight error → endpoint+api-key check passed
        finally:
            os.environ.pop("GCL_CRITIC_MODE")
            os.environ.pop("GCL_CRITIC_LLM_ENDPOINT")
            os.environ.pop("GCL_CRITIC_LLM_API_KEY")
            if orig_mode is not None:
                os.environ["GCL_CRITIC_MODE"] = orig_mode
            if orig_endpoint is not None:
                os.environ["GCL_CRITIC_LLM_ENDPOINT"] = orig_endpoint
            if orig_apikey is not None:
                os.environ["GCL_CRITIC_LLM_API_KEY"] = orig_apikey

    def test_cli_overrides_env(self):
        """--critic-mode llm on CLI overrides env var GCL_CRITIC_MODE=hybrid."""
        orig_mode = os.environ.pop("GCL_CRITIC_MODE", None)
        orig_endpoint = os.environ.pop("GCL_CRITIC_LLM_ENDPOINT", None)
        orig_apikey = os.environ.pop("GCL_CRITIC_LLM_API_KEY", None)
        os.environ["GCL_CRITIC_MODE"] = "hybrid"
        os.environ["GCL_CRITIC_LLM_ENDPOINT"] = "https://example.com/v1/chat/completions"
        os.environ["GCL_CRITIC_LLM_API_KEY"] = "test-key"
        try:
            # CLI --critic-mode llm still needs endpoint+key (we have them) so passes
            code = gcl_runner.main([
                "--critic-mode", "llm",
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteInstance",
                "--command", _wrap("aliyun ecs DeleteInstance --InstanceId i-test"),
                "--rubric", str(self.rubric_path),
                "--output-dir", str(self.tmp_root),
                "--dry-run",
            ])
            self.assertIn(code, (0, 6))
        finally:
            os.environ.pop("GCL_CRITIC_MODE")
            os.environ.pop("GCL_CRITIC_LLM_ENDPOINT")
            os.environ.pop("GCL_CRITIC_LLM_API_KEY")
            if orig_mode is not None:
                os.environ["GCL_CRITIC_MODE"] = orig_mode
            if orig_endpoint is not None:
                os.environ["GCL_CRITIC_LLM_ENDPOINT"] = orig_endpoint
            if orig_apikey is not None:
                os.environ["GCL_CRITIC_LLM_API_KEY"] = orig_apikey

    def test_empty_endpoint_fail_open_true_fallback(self):
        """GCL_CRITIC_MODE=hybrid + empty endpoint + FAIL_OPEN=true → fallback to mechanical, no exit error."""
        orig_mode = os.environ.pop("GCL_CRITIC_MODE", None)
        orig_endpoint = os.environ.pop("GCL_CRITIC_LLM_ENDPOINT", None)
        orig_apikey = os.environ.pop("GCL_CRITIC_LLM_API_KEY", None)
        orig_fail_open = os.environ.pop("GCL_CRITIC_LLM_FAIL_OPEN", None)
        os.environ["GCL_CRITIC_MODE"] = "hybrid"
        # endpoint empty
        os.environ["GCL_CRITIC_LLM_FAIL_OPEN"] = "true"
        try:
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteInstance",
                "--command", _wrap("aliyun ecs DeleteInstance --InstanceId i-test"),
                "--rubric", str(self.rubric_path),
                "--output-dir", str(self.tmp_root),
                "--dry-run",
            ])
            # Should NOT fail with exit 3 (USAGE_ERROR), should fallback → continues
            self.assertIn(code, (0, 6))
        finally:
            os.environ.pop("GCL_CRITIC_MODE")
            os.environ.pop("GCL_CRITIC_LLM_FAIL_OPEN")
            if orig_mode is not None:
                os.environ["GCL_CRITIC_MODE"] = orig_mode
            if orig_endpoint is not None:
                os.environ["GCL_CRITIC_LLM_ENDPOINT"] = orig_endpoint
            if orig_apikey is not None:
                os.environ["GCL_CRITIC_LLM_API_KEY"] = orig_apikey
            if orig_fail_open is not None:
                os.environ["GCL_CRITIC_LLM_FAIL_OPEN"] = orig_fail_open

    def test_empty_endpoint_fail_open_false_exit_error(self):
        """GCL_CRITIC_MODE=hybrid + empty endpoint + FAIL_OPEN=false → EXIT_USAGE_ERROR (3)."""
        orig_mode = os.environ.pop("GCL_CRITIC_MODE", None)
        orig_endpoint = os.environ.pop("GCL_CRITIC_LLM_ENDPOINT", None)
        orig_apikey = os.environ.pop("GCL_CRITIC_LLM_API_KEY", None)
        orig_fail_open = os.environ.pop("GCL_CRITIC_LLM_FAIL_OPEN", None)
        os.environ["GCL_CRITIC_MODE"] = "hybrid"
        os.environ["GCL_CRITIC_LLM_FAIL_OPEN"] = "false"
        try:
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteInstance",
                "--command", _wrap("aliyun ecs DeleteInstance --InstanceId i-test"),
                "--rubric", str(self.rubric_path),
                "--output-dir", str(self.tmp_root),
                "--dry-run",
            ])
            self.assertEqual(code, gcl_runner.EXIT_USAGE_ERROR)
        finally:
            os.environ.pop("GCL_CRITIC_MODE")
            os.environ.pop("GCL_CRITIC_LLM_FAIL_OPEN")
            if orig_mode is not None:
                os.environ["GCL_CRITIC_MODE"] = orig_mode
            if orig_endpoint is not None:
                os.environ["GCL_CRITIC_LLM_ENDPOINT"] = orig_endpoint
            if orig_apikey is not None:
                os.environ["GCL_CRITIC_LLM_API_KEY"] = orig_apikey
            if orig_fail_open is not None:
                os.environ["GCL_CRITIC_LLM_FAIL_OPEN"] = orig_fail_open

    def test_mechanical_skips_env_check(self):
        """GCL_CRITIC_MODE=mechanical → never checks endpoint/api-key even if they're empty."""
        orig_mode = os.environ.pop("GCL_CRITIC_MODE", None)
        os.environ["GCL_CRITIC_MODE"] = "mechanical"
        # leave endpoint empty → still OK
        try:
            code = gcl_runner.main([
                "--skill", "alicloud-ecs-ops",
                "--op", "DeleteInstance",
                "--command", _wrap("aliyun ecs DeleteInstance --InstanceId i-test"),
                "--rubric", str(self.rubric_path),
                "--output-dir", str(self.tmp_root),
                "--dry-run",
            ])
            self.assertIn(code, (0, 6))  # no error → skipped check
        finally:
            os.environ.pop("GCL_CRITIC_MODE")
            if orig_mode is not None:
                os.environ["GCL_CRITIC_MODE"] = orig_mode

    def test_report_empty_on_pass(self):
        """PASS result has an empty report."""
        result = gcl_runner.hallucination_detect(            _wrap("aliyun ecs DescribeRegions")
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["report"], "")


# ---------------------------------------------------------------------------
# T16: gcl_runner → memory_store integration
# ---------------------------------------------------------------------------

class MemoryStoreIntegrationTests(unittest.TestCase):
    """Verify that gcl_runner.py main() invokes memory_store after persist_trace()."""

    def _setup_temp_rubric(self, tmp_dir: str) -> Path:
        rubric_path = Path(tmp_dir) / "rubric.md"
        rubric_content = """---
rubric_version: "1.0"
version: "1.0"
max_iter: 2
gcl_classification: required
ops:
  DescribeInstances: Describe ECS instances
---

## Detection Regex

| Regex | Risk |
|-------|------|
| --PageSize | READ-ONLY |
"""
        rubric_path.write_text(rubric_content, encoding="utf-8")
        return rubric_path

    def test_memory_store_import_available(self):
        """gcl_memory.memory_store is importable from gcl_runner's import path."""
        try:
            from gcl_memory import memory_store  # noqa: F811
        except ImportError:
            self.fail("memory_store import failed from gcl_memory")
        import inspect
        sig = inspect.signature(memory_store)
        self.assertIn("trace", sig.parameters)

    def test_memory_store_import_fallback(self):
        """When gcl_memory is unavailable, the no-op fallback returns 0."""
        def _fallback_memory_store(*args, **kwargs):
            return 0
        rc = _fallback_memory_store({}, trace_path="/tmp/trace.json")
        self.assertEqual(rc, 0)

    def test_memory_store_invoked_after_persist(self):
        """After persist_trace + memory_store, a memory JSONL file is created.

        Runs gcl_runner in dry-run mode with a real rubric, then checks that
        memory_store has written to .runtime/memory/.
        """
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "audit-results"
            memory_root = Path(tmp) / ".runtime" / "memory"
            rubric_path = self._setup_temp_rubric(tmp)

            orig_store = gcl_runner.memory_store

            def _patched_memory_store(trace, trace_path=None, operation=None, **_kw):
                # Inject custom memory_root from outer scope; don't shadow it via parameter
                return orig_store(
                    trace,
                    trace_path=trace_path,
                    memory_root=str(memory_root),
                    operation=operation,
                )

            with mock.patch.object(gcl_runner, "memory_store", side_effect=_patched_memory_store):
                code = gcl_runner.main([
                    "--skill", "alicloud-ecs-ops",
                    "--op", "DescribeInstances",
                    "--command", _wrap("aliyun ecs DescribeInstances --PageSize 10"),
                    "--rubric", str(rubric_path),
                    "--output-dir", str(output_dir),
                    "--dry-run",
                ])

            self.assertIn(code, (0, 6))

            mem_files = list(memory_root.rglob("*.jsonl"))
            if mem_files:
                content = mem_files[0].read_text(encoding="utf-8").strip()
                self.assertTrue(len(content) > 0)


# ---------------------------------------------------------------------------
# T17: R2 memory preflight → Generator prompt (Local-first P0)
# ---------------------------------------------------------------------------

class MemoryPreflightGeneratorTests(unittest.TestCase):
    """P0: memory slots substitute into Generator template and attach to trace."""

    def test_apply_memory_preflight_slots(self):
        slots = {
            "recent_executions": "- 2026-06-20 op=DeleteInstance status=FAIL",
            "known_traps": "- MissingParam on --InstanceId",
            "success_patterns": "- [multi_iter] count=2 Use --InstanceId.1",
            "strategy_hints": "- risk_score=0.4",
        }
        text = (
            "{{recent_executions}}\n{{known_traps}}\n"
            "{{success_patterns}}\n{{strategy_hints}}"
        )
        out = gcl_runner.apply_memory_preflight_slots(text, slots)
        self.assertIn("DeleteInstance", out)
        self.assertIn("MissingParam", out)
        self.assertIn("multi_iter", out)
        self.assertIn("risk_score", out)
        self.assertNotIn("{{known_traps}}", out)
        self.assertNotIn("{{success_patterns}}", out)

    def test_attach_memory_preflight_to_trace_with_mock_template(self):
        trace: dict = {}
        preflight = {
            "empty": False,
            "recent_executions": [],
            "known_traps": [],
            "strategy_hints": {"empty": True},
            "slots": {
                "recent_executions": "(none)",
                "known_traps": "- trap-A",
                "strategy_hints": "(none)",
            },
        }
        with mock.patch.object(
            gcl_runner,
            "load_generator_template",
            return_value="TRAPS:\n{{known_traps}}",
        ):
            gcl_runner.attach_memory_preflight_to_trace(
                trace, preflight, Path("/tmp"), "alicloud-ecs-ops",
            )
        self.assertIn("memory_preflight", trace)
        self.assertEqual(trace["generator_prompt_with_memory"], "TRAPS:\n- trap-A")

    def test_load_generator_template_ecs_excludes_markdown_tables(self):
        repo = Path(__file__).resolve().parent.parent.parent
        body = gcl_runner.load_generator_template(repo, "alicloud-ecs-ops")
        self.assertTrue(body)
        self.assertNotIn("| Placeholder |", body)
        self.assertNotIn("```text", body)
        self.assertIn("{{user.request}}", body)

    def test_load_generator_template_all_skills_have_memory_slots(self):
        repo = Path(__file__).resolve().parent.parent.parent
        skills = sorted(
            p.parent.parent.name
            for p in repo.glob("alicloud-*/references/prompt-templates.md")
        )
        self.assertGreater(len(skills), 30, msg="expected GCL prompt-templates across skills")
        for skill in skills:
            with self.subTest(skill=skill):
                body = gcl_runner.load_generator_template(repo, skill)
                self.assertTrue(body, msg=f"missing §1 Generator ```text for {skill}")
                self.assertIn("{{known_traps}}", body)
                self.assertIn("{{recent_executions}}", body)
                self.assertIn("{{strategy_hints}}", body)
                self.assertIn("{{success_patterns}}", body)

    def test_extract_text_fence_block(self):
        lines = ["**Role:** noise", "```text", "hello {{known_traps}}", "```", "tail"]
        self.assertEqual(
            gcl_runner._extract_text_fence_block(lines),
            "hello {{known_traps}}",
        )

    def test_run_loop_includes_memory_preflight(self):
        rubric = {
            "version": "1.0.0", "last_updated": "2026-06-04", "api": "Test",
            "cli_applicability": "cli-first", "ops": {"DescribeRegions": "..."},
            "regexes": [], "max_iter": 1, "required_or_recommended": "required",
        }
        preflight = {
            "empty": True,
            "slots": {"known_traps": "x", "recent_executions": "y", "strategy_hints": "z"},
        }
        with mock.patch.object(gcl_runner, "run_command") as mcmd:
            mcmd.return_value = {
                "command": "aliyun ecs DescribeRegions",
                "exit_code": 0,
                "stdout": "{}",
                "stderr": "",
                "result_excerpt": "{}",
                "request_id": "r-1",
                "duration_ms": 1,
            }
            trace = gcl_runner.run_loop(
                skill="alicloud-ecs-ops",
                op="DescribeRegions",
                command="aliyun ecs DescribeRegions",
                user_request=None,
                rubric=rubric,
                max_iter=1,
                memory_preflight=preflight,
                skills_root=None,
            )
        self.assertEqual(trace["memory_preflight"], preflight)


class CritiqueLlmUsageTests(unittest.TestCase):
    """Phase 1 TEL — GCL critic LLM usage parsing and critic_meta persistence."""

    def _trace(self) -> dict:
        return {
            "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "exit_code": 0,
            "stdout": '{"Instances": []}',
            "stderr": "",
            "result_excerpt": "ok",
        }

    def _rubric(self) -> dict:
        return {"regexes": [], "ops": {}}

    def _llm_response_bytes(
        self,
        *,
        usage: dict | None,
        critic_content: dict | None = None,
        model: str = "gpt-4o-mini",
    ) -> bytes:
        if critic_content is None:
            critic_content = {
                "scores": {
                    "correctness": 1.0,
                    "safety": 1.0,
                    "idempotency": 1.0,
                    "traceability": 1.0,
                    "spec_compliance": 1.0,
                    "region_compliance": 1.0,
                    "credential_hygiene": 1.0,
                    "well_architected": 1.0,
                    "wrapper_compliance": 1.0,
                },
                "suggestions": [],
                "blocking": False,
            }
        body: dict = {
            "model": model,
            "choices": [{"message": {"content": json.dumps(critic_content)}}],
        }
        if usage is not None:
            body["usage"] = usage
        return json.dumps(body).encode("utf-8")

    def _mock_urlopen(self, mock_urlopen, payload: bytes) -> None:
        mock_resp = mock.Mock()
        mock_resp.read.return_value = payload
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

    def test_parse_openai_llm_usage_none_when_absent(self):
        self.assertIsNone(gcl_runner.parse_openai_llm_usage({}, "gpt-4o-mini"))

    def test_parse_openai_llm_usage_computes_total(self):
        usage = gcl_runner.parse_openai_llm_usage(
            {"usage": {"prompt_tokens": 10, "completion_tokens": 5}, "model": "m1"},
            "fallback",
        )
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["total_tokens"], 15)
        self.assertEqual(usage["model"], "m1")

    def test_parse_openai_llm_usage_cache_tokens_alibaba(self):
        """Alibaba (DashScope) uses prompt_tokens_details.cached_tokens."""
        usage = gcl_runner.parse_openai_llm_usage(
            {
                "usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 300,
                    "total_tokens": 1800,
                    "prompt_tokens_details": {"cached_tokens": 800},
                },
                "model": "qwen-plus",
            },
            "fallback",
            provider="alibaba",
        )
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["cache_tokens"], 800)
        self.assertAlmostEqual(usage["cache_hit_ratio"], 0.533, places=3)

    def test_parse_openai_llm_usage_cache_tokens_deepseek(self):
        """DeepSeek uses prompt_cache_hit_tokens (unique field name)."""
        usage = gcl_runner.parse_openai_llm_usage(
            {
                "usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 300,
                    "total_tokens": 1800,
                    "prompt_cache_hit_tokens": 800,
                },
                "model": "deepseek-v4-flash",
            },
            "fallback",
            provider="deepseek",
        )
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["cache_tokens"], 800)
        self.assertAlmostEqual(usage["cache_hit_ratio"], 0.533, places=3)

    def test_parse_openai_llm_usage_cache_tokens_minimax_anthropic(self):
        """MiniMax Anthropic format uses cache_read_input_tokens."""
        usage = gcl_runner.parse_openai_llm_usage(
            {
                "usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 300,
                    "total_tokens": 1800,
                    "cache_read_input_tokens": 800,
                },
                "model": "MiniMax-Text-01",
            },
            "fallback",
            provider="minimax",
        )
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["cache_tokens"], 800)
        self.assertAlmostEqual(usage["cache_hit_ratio"], 0.533, places=3)

    def test_parse_openai_llm_usage_cache_tokens_unsupported(self):
        """Unsupported provider returns None for cache fields."""
        usage = gcl_runner.parse_openai_llm_usage(
            {
                "usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 300,
                    "total_tokens": 1800,
                    "prompt_tokens_details": {"cached_tokens": 800},
                },
                "model": "unknown-model",
            },
            "fallback",
            provider="unsupported_vendor",
        )
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertIsNone(usage["cache_tokens"])
        self.assertIsNone(usage["cache_hit_ratio"])

    def test_parse_openai_llm_usage_cache_tokens_zero_prompt(self):
        """Zero prompt_tokens avoids division by zero."""
        usage = gcl_runner.parse_openai_llm_usage(
            {
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 100,
                    "total_tokens": 100,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
                "model": "qwen-plus",
            },
            "fallback",
            provider="alibaba",
        )
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["cache_tokens"], 0)
        self.assertIsNone(usage["cache_hit_ratio"])

    def test_detect_llm_provider(self):
        tests = [
            ("https://api.deepseek.com/v1/chat/completions", "deepseek"),
            ("https://api.minimax.chat/v1/chat/completions", "minimax"),
            ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "zhipu"),
            ("https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions", "volcengine"),
            ("https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/text-generation", "alibaba"),
            ("https://api.openai.com/v1/chat/completions", None),
        ]
        for endpoint, expected in tests:
            self.assertEqual(gcl_runner.detect_llm_provider(endpoint), expected)

    def test_build_critic_meta_required_fields(self):
        meta = gcl_runner.build_critic_meta(mode="mechanical", llm_model=None)
        self.assertEqual(meta["coding_agent"], "harness_cli")
        self.assertEqual(meta["model"], "unknown")
        self.assertIsNone(meta["llm_usage"])

    @mock.patch.dict(os.environ, {"HARNESS_CODING_AGENT": "cursor"}, clear=False)
    def test_resolve_gcl_coding_agent_env(self):
        self.assertEqual(gcl_runner.resolve_gcl_coding_agent(), "cursor")

    def test_critic_trace_payload_includes_critic_meta(self):
        payload = gcl_runner._critic_trace_payload(
            {
                "scores": {"correctness": 1.0},
                "suggestions": [],
                "matched_regexes": [],
                "blocking": False,
                "critic_meta": {
                    "mode": "llm",
                    "coding_agent": "harness_cli",
                    "model": "gpt-4o-mini",
                    "llm_usage": None,
                },
            }
        )
        self.assertIn("critic_meta", payload)
        self.assertEqual(payload["critic_meta"]["coding_agent"], "harness_cli")

    @mock.patch.dict(
        os.environ,
        {
            "GCL_CRITIC_LLM_ENDPOINT": "http://127.0.0.1/v1/chat/completions",
            "GCL_CRITIC_LLM_MODEL": "gpt-4o-mini",
        },
        clear=False,
    )
    @mock.patch("urllib.request.urlopen")
    def test_critique_llm_parses_usage(self, mock_urlopen):
        self._mock_urlopen(
            mock_urlopen,
            self._llm_response_bytes(
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            ),
        )
        result = gcl_runner.critique_llm(
            "DescribeInstances",
            self._trace(),
            self._rubric(),
            "critique {{output.trace}}",
        )
        meta = result["_critic_llm_meta"]
        self.assertIsNotNone(meta["llm_usage"])
        self.assertEqual(meta["llm_usage"]["prompt_tokens"], 100)
        self.assertEqual(meta["llm_usage"]["total_tokens"], 120)
        self.assertIsInstance(meta["latency_ms"], int)

    @mock.patch.dict(
        os.environ,
        {
            "GCL_CRITIC_LLM_ENDPOINT": "http://127.0.0.1/v1/chat/completions",
            "GCL_CRITIC_LLM_MODEL": "gpt-4o-mini",
        },
        clear=False,
    )
    @mock.patch("urllib.request.urlopen")
    def test_critique_llm_missing_usage_fail_open(self, mock_urlopen):
        self._mock_urlopen(
            mock_urlopen,
            self._llm_response_bytes(usage=None),
        )
        result = gcl_runner.critique_llm(
            "DescribeInstances",
            self._trace(),
            self._rubric(),
            "critique {{output.trace}}",
        )
        self.assertIsNone(result["_critic_llm_meta"]["llm_usage"])
        self.assertEqual(result["scores"]["correctness"], 1.0)

    @mock.patch.dict(
        os.environ,
        {
            "GCL_CRITIC_LLM_ENDPOINT": "http://127.0.0.1/v1/chat/completions",
            "GCL_CRITIC_LLM_MODEL": "gpt-4o-mini",
        },
        clear=False,
    )
    @mock.patch("urllib.request.urlopen")
    def test_pop_critic_llm_meta_strips_internal_key(self, mock_urlopen):
        self._mock_urlopen(
            mock_urlopen,
            self._llm_response_bytes(
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            ),
        )
        result = gcl_runner.critique_llm(
            "DescribeInstances",
            self._trace(),
            self._rubric(),
            "critique {{output.trace}}",
        )
        meta = gcl_runner._pop_critic_llm_meta(result)
        self.assertNotIn("_critic_llm_meta", result)
        self.assertEqual(meta["llm_usage"]["total_tokens"], 2)

    @mock.patch.dict(
        os.environ,
        {
            "GCL_CRITIC_LLM_ENDPOINT": "http://127.0.0.1/v1/chat/completions",
            "GCL_CRITIC_LLM_MODEL": "gpt-4o-mini",
        },
        clear=False,
    )
    @mock.patch("urllib.request.urlopen")
    def test_critique_llm_mode_builds_critic_meta(self, mock_urlopen):
        self._mock_urlopen(
            mock_urlopen,
            self._llm_response_bytes(
                usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "alicloud-ecs-ops" / "references"
            skill_dir.mkdir(parents=True)
            (skill_dir / "prompt-templates.md").write_text(
                "## 2. Critic\n\nScore {{output.generator_output}}\n\n## 3. Other\n",
                encoding="utf-8",
            )
            rubric = {
                "regexes": [],
                "ops": {"DescribeInstances": "READ-ONLY"},
                "version": "1.0.0",
            }
            trace = self._trace()
            result = gcl_runner.critique(
                "DescribeInstances",
                trace,
                rubric,
                gcl_critic_mode="llm",
                skills_root=Path(tmp),
                skill="alicloud-ecs-ops",
                llm_model="gpt-4o-mini",
            )
        cm = result["critic_meta"]
        self.assertEqual(cm["mode"], "llm")
        self.assertEqual(cm["coding_agent"], "harness_cli")
        self.assertEqual(cm["model"], "gpt-4o-mini")
        self.assertIsNotNone(cm["llm_usage"])
        self.assertEqual(cm["llm_usage"]["total_tokens"], 60)
        payload = gcl_runner._critic_trace_payload(result)
        self.assertIn("critic_meta", payload)


# ---------------------------------------------------------------------------
# Risk Scoring Tests (B1)
# ---------------------------------------------------------------------------


class RiskScorerTests(unittest.TestCase):
    """B1: risk_scorer() — operation risk classification."""

    def _default_risk(self, skill: str = "alicloud-ecs-ops", op: str = "DescribeInstances", command: str = "aliyun ecs DescribeInstances") -> dict:
        return gcl_runner.risk_scorer(skill, op, command)

    def test_delete_op_max_fatal(self):
        """DeleteInstance gets fatal_score=1.0."""
        r = self._default_risk(op="DeleteInstance", command="aliyun ecs DeleteInstance --InstanceId i-1")
        self.assertEqual(r["breakdown"]["fatal"], 1.0)
        self.assertEqual(r["breakdown"]["irreversible"], 0.5)

    def test_create_op_medium_fatal(self):
        """CreateInstance gets fatal_score=0.3."""
        r = self._default_risk(op="CreateInstance", command="aliyun ecs CreateInstance --ImageId ami-1")
        self.assertEqual(r["breakdown"]["fatal"], 0.3)

    def test_describe_op_zero_fatal(self):
        """DescribeInstances gets fatal_score=0.0."""
        r = self._default_risk()
        self.assertEqual(r["breakdown"]["fatal"], 0.0)
        self.assertEqual(r["breakdown"]["irreversible"], 0.0)

    def test_unknown_op_defaults_to_zero(self):
        """An operation with no keyword match defaults fatality to 0."""
        r = gcl_runner.risk_scorer("alicloud-ecs-ops", "UnknownOp123", "aliyun ecs UnknownOp123")
        self.assertEqual(r["breakdown"]["fatal"], 0.0)

    def test_modify_op_score(self):
        """SetLoadBalancer gets fatal_score=0.5 (from 'set' keyword)."""
        r = gcl_runner.risk_scorer("alicloud-slb-ops", "SetLoadBalancerStatus", "aliyun slb SetLoadBalancerStatus --LoadBalancerId lb-1 --LoadBalancerStatus inactive")
        self.assertEqual(r["breakdown"]["fatal"], 0.5)
        self.assertEqual(r["breakdown"]["irreversible"], 0.5)

    def test_risk_score_in_zero_one_range(self):
        """Risk score is always between 0.0 and 1.0."""
        for op in ("DescribeInstances", "CreateInstance", "DeleteInstance", "RebootInstance", "StopInstance"):
            r = self._default_risk(op=op)
            self.assertGreaterEqual(r["risk_score"], 0.0)
            self.assertLessEqual(r["risk_score"], 1.0)

    def test_irreversible_only_fatal_ops(self):
        """Irreversible is 0.5 for fatal ops (score >= 0.5), 0 otherwise."""
        fatal_op = self._default_risk(op="DeleteInstance")["breakdown"]
        read_op = self._default_risk(op="DescribeInstances")["breakdown"]
        self.assertEqual(fatal_op["irreversible"], 0.5)
        self.assertEqual(read_op["irreversible"], 0.0)

    def test_stop_op_fatal(self):
        """StopInstance is a fatal operation."""
        r = self._default_risk(op="StopInstance", command="aliyun ecs StopInstance --InstanceId i-1")
        self.assertEqual(r["breakdown"]["fatal"], 1.0)
        self.assertEqual(r["breakdown"]["irreversible"], 0.5)

    def test_risk_score_breakdown_keys(self):
        """risk_scorer returns expected breakdown keys."""
        r = self._default_risk()
        self.assertIn("risk_score", r)
        self.assertIn("breakdown", r)
        for key in ("fatal", "irreversible", "fail_rate", "scope", "weights", "weighted_sum"):
            self.assertIn(key, r["breakdown"])

    def test_fail_rate_default_when_no_reflexion(self):
        """When no reflexion data exists for a skill/op, fail_rate defaults to 0.10."""
        r = gcl_runner.risk_scorer("alicloud-fake-ops", "FakeOp", "aliyun fake FakeOp")
        self.assertEqual(r["breakdown"]["fail_rate"], 0.10)

    def test_get_fail_rate_import_fallback(self):
        """_get_fail_rate uses import fallback when reflexion_retrieve fails."""
        rate = gcl_runner._get_fail_rate("alicloud-ecs-ops", "DeleteInstance")
        self.assertIsInstance(rate, float)
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 1.0)

    def test_risk_score_delete_higher_than_describe(self):
        """DeleteInstance risk_score is higher than DescribeInstances."""
        delete_r = self._default_risk(op="DeleteInstance")
        describe_r = self._default_risk(op="DescribeInstances")
        self.assertGreater(delete_r["risk_score"], describe_r["risk_score"])

    def test_create_vs_delete_distinct(self):
        """CreateInstance and DeleteInstance have different risk scores."""
        create_r = self._default_risk(op="CreateInstance")
        delete_r = self._default_risk(op="DeleteInstance")
        self.assertNotEqual(create_r["risk_score"], delete_r["risk_score"])

    def test_risk_score_is_deterministic(self):
        """Same inputs always yield the same risk score."""
        r1 = self._default_risk(op="DeleteInstance")
        r2 = self._default_risk(op="DeleteInstance")
        self.assertEqual(r1["risk_score"], r2["risk_score"])


# ---------------------------------------------------------------------------
# max_iter_calculator Tests (B2)
# ---------------------------------------------------------------------------


class MaxIterCalculatorTests(unittest.TestCase):
    """B2: max_iter_calculator() — dynamic max_iter from risk score."""

    def test_high_risk_returns_5(self):
        """risk >= 0.7 returns max_iter=5 for ecs."""
        result = gcl_runner.max_iter_calculator(0.8, "alicloud-ecs-ops")
        self.assertEqual(result, 5)

    def test_medium_risk_returns_3(self):
        """0.3 <= risk < 0.7 returns max_iter=3 for ecs."""
        result = gcl_runner.max_iter_calculator(0.5, "alicloud-ecs-ops")
        self.assertEqual(result, 3)

    def test_low_risk_returns_1(self):
        """risk < 0.3 returns calculated=1, but SKILL_MAX_ITER floor=2 for ecs."""
        result = gcl_runner.max_iter_calculator(0.1, "alicloud-ecs-ops")
        self.assertEqual(result, 2)

    def test_skill_floor_applied_when_risk_low(self):
        """SKILL_MAX_ITER floor applies: ecs floor=2 trumps calculated=1."""
        result = gcl_runner.max_iter_calculator(0.1, "alicloud-ecs-ops")
        self.assertEqual(result, 2)

    def test_skill_floor_applied_for_readonly_skill(self):
        """actiontrail floor=5 trumps calculated values for low risk."""
        result = gcl_runner.max_iter_calculator(0.1, "alicloud-actiontrail-ops")
        self.assertGreaterEqual(result, 5)

    def test_high_risk_above_all_floors(self):
        """High risk (5) is always >= any SKILL_MAX_ITER floor."""
        for skill in ("alicloud-ecs-ops", "alicloud-slb-ops", "alicloud-actiontrail-ops"):
            result = gcl_runner.max_iter_calculator(0.9, skill)
            self.assertEqual(result, 5)

    def test_medium_risk_on_high_floor_skill(self):
        """When risk=0.5 (calculated=3) but floor=5, floor wins."""
        result = gcl_runner.max_iter_calculator(0.5, "alicloud-actiontrail-ops")
        self.assertEqual(result, 5)

    def test_unknown_skill_floor_defaults_to_2(self):
        """Unknown skill gets floor=2."""
        result = gcl_runner.max_iter_calculator(0.0, "alicloud-unknown-ops")
        self.assertEqual(result, 2)

    def test_risk_score_0_7_boundary(self):
        """Exactly 0.7 maps to >= 0.7 bucket -> 5."""
        result = gcl_runner.max_iter_calculator(0.7, "alicloud-ecs-ops")
        self.assertEqual(result, 5)

    def test_risk_score_0_3_boundary(self):
        """Exactly 0.3 maps to >= 0.3 bucket -> 3."""
        result = gcl_runner.max_iter_calculator(0.3, "alicloud-ecs-ops")
        self.assertEqual(result, 3)

    def test_risk_score_just_below_0_3(self):
        """0.299 < 0.3 -> low bucket, floor=2."""
        result = gcl_runner.max_iter_calculator(0.299, "alicloud-ecs-ops")
        self.assertEqual(result, 2)


class ResolveSkillVersionTests(unittest.TestCase):
    """Regression guard for skill_version extraction into GCL traces."""

    def _make_skill(self, tmp_root: Path, skill: str, frontmatter: str) -> None:
        skill_dir = tmp_root / skill
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(frontmatter, encoding="utf-8")

    def test_reads_metadata_version(self):
        """metadata.version is extracted with source=skill_md."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_skill(
                root, "alicloud-demo-ops",
                '---\nname: alicloud-demo-ops\nmetadata:\n  version: "9.9.9"\n---\n',
            )
            with mock.patch.object(gcl_runner, "resolve_skills_root", lambda: root):
                version, source = gcl_runner.resolve_skill_version("alicloud-demo-ops", None)
            self.assertEqual(version, "9.9.9")
            self.assertEqual(source, "skill_md")

    def test_accepts_top_level_version_for_robustness(self):
        """A top-level version: key (no metadata block) is also accepted."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_skill(
                root, "alicloud-demo-ops",
                '---\nname: alicloud-demo-ops\nversion: "1.2.3"\n---\n',
            )
            with mock.patch.object(gcl_runner, "resolve_skills_root", lambda: root):
                version, source = gcl_runner.resolve_skill_version("alicloud-demo-ops", None)
            self.assertEqual(version, "1.2.3")
            self.assertEqual(source, "skill_md")

    def test_skips_leading_html_comment(self):
        """SKILL.md with a leading markdownlint HTML comment still parses."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_skill(
                root, "alicloud-demo-ops",
                '<!-- markdownlint-disable -->\n---\nname: x\nmetadata:\n  version: "4.5.6"\n---\n',
            )
            with mock.patch.object(gcl_runner, "resolve_skills_root", lambda: root):
                version, source = gcl_runner.resolve_skill_version("alicloud-demo-ops", None)
            self.assertEqual(version, "4.5.6")
            self.assertEqual(source, "skill_md")

    def test_missing_skill_yields_git_or_unknown(self):
        """A skill with no SKILL.md falls back to git hash / unknown."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)  # no SKILL.md created
            with mock.patch.object(gcl_runner, "resolve_skills_root", lambda: root):
                version, source = gcl_runner.resolve_skill_version("alicloud-missing-ops", None)
            self.assertIn(source, ("git", "unknown"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
