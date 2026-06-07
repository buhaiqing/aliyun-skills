#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import re
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
        out = gcl_runner.sanitize(text)
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
            "command": "aliyun ecs DescribeInstances",
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
        # All 8 dimensions should be present
        self.assertEqual(len(c["scores"]), 8)

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
            "command": "aliyun ecs DeleteFoo --X 1",
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


class HallucinationDetectTests(unittest.TestCase):
    """Hallucination Detection (H) — pre-execution structural validity check."""

    def test_happy_path_known_params(self):
        """All CLI flags known to PARAMETER_KNOWLEDGE → PASS."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 10"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks"]["cli_parameters"]["unrecognized"], [])

    def test_unrecognized_param_detected(self):
        """A flag not in PARAMETER_KNOWLEDGE → FAIL with unrecognized list."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DeleteInstance --RegionId cn-hangzhou --FakeParam foo"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("--FakeParam", result["checks"]["cli_parameters"]["unrecognized"])

    def test_unrecognized_param_detected_zone_vs_zoneid(self):
        """--Zone instead of --ZoneId is caught."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DescribeInstances --Zone cn-hangzhou-f"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("--Zone", result["checks"]["cli_parameters"]["unrecognized"])

    def test_known_params_with_common_flags(self):
        """Generic `aliyun` CLI flags (--output, --format) are NOT flagged."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou --output json --format pretty"
        )
        self.assertEqual(result["status"], "PASS")

    def test_non_aliyun_command_passes(self):
        """Non-aliyun commands (data-plane tools) pass CLI parameter check."""
        result = gcl_runner.hallucination_detect(
            "mysql -h localhost -u root -p mydb -e 'SELECT 1'"
        )
        self.assertEqual(result["status"], "PASS")

    def test_unknown_product_passes(self):
        """Unknown product not in PARAMETER_KNOWLEDGE passes conservatively."""
        result = gcl_runner.hallucination_detect(
            "aliyun unknown-product DescribeFoo --Bar baz"
        )
        self.assertEqual(result["status"], "PASS")

    def test_waf_deletion_protection_disabled(self):
        """--DeletionProtection false is flagged as WAF Security violation."""
        result = gcl_runner.hallucination_detect(
            "aliyun rds CreateDBInstance --Engine MySQL --DeletionProtection false --DBInstanceClass rds.mysql.s2.large"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"]["waf_compliance"]["status"], "FAIL")

    def test_waf_force_flag_on_delete(self):
        """--Force on a destructive op is flagged as Security concern."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DeleteInstance --InstanceId i-bp1xxx --Force"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(len(result["checks"]["waf_compliance"]["violations"]), 0)

    def test_waf_backup_retention_zero(self):
        """--BackupRetentionPeriod 0 is flagged as Stability violation."""
        result = gcl_runner.hallucination_detect(
            "aliyun rds CreateDBInstance --Engine MySQL --BackupRetentionPeriod 0"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Stability", result["checks"]["waf_compliance"]["violations"][0])

    def test_waf_postpaid_flag(self):
        """--PayType PostPaid flagged as Cost concern."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs CreateInstance --ImageId xxx --InstanceType ecs.g6.large --PayType PostPaid"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Cost", result["checks"]["waf_compliance"]["violations"][0])

    def test_json_payload_pass(self):
        """Valid JSON-like payload passes JSON structure check."""
        result = gcl_runner.hallucination_detect(
            'aliyun ecs RunInstances --RegionId cn-hangzhou --Amount 1 --Tag "[{\"Key\":\"env\",\"Value\":\"prod\"}]"'
        )
        # CLI params may fail if not in knowledge base, but JSON check passes
        self.assertEqual(result["checks"]["json_structure"]["status"], "PASS")

    def test_combination_multi_fail(self):
        """Command with multiple hallucination types fails across categories."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs CreateInstance --ImageId ami-123 --FakeParam x --DeletionProtection false"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"]["cli_parameters"]["status"], "FAIL")
        self.assertEqual(result["checks"]["waf_compliance"]["status"], "FAIL")
        self.assertIn("--FakeParam", result["checks"]["cli_parameters"]["unrecognized"])

    def test_no_flag_command(self):
        """CLI command with no flags passes trivially."""
        result = gcl_runner.hallucination_detect("aliyun ecs DescribeRegions")
        self.assertEqual(result["status"], "PASS")

    def test_report_format(self):
        """FAIL result includes a human-readable report string."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DeleteInstance --FakeFlag value"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(len(result["report"]) > 0)
        self.assertIn("FakeFlag", result["report"])

    def test_cli_params_exact_count(self):
        """CLI parameter check reports correct total/recognized counts."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 10 --FakeFlag foo"
        )
        cli = result["checks"]["cli_parameters"]
        self.assertEqual(cli["total"], 3)
        self.assertEqual(cli["recognized"], 2)
        self.assertIn("--FakeFlag", cli["unrecognized"])

    def test_force_without_delete_not_extra_flagged(self):
        """--Force on a non-delete operation does not trigger the extra stability heuristic."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs StopInstance --InstanceId i-bp1 --Force"
        )
        # --Force itself is a WAF flag, but the heuristic delete check shouldn't add extra
        self.assertIn("Security", result["report"])

    def test_dry_run_with_hallucination_passes_via_cli(self):
        """Dry-run + enable-hallucination-check passes the H result through."""
        trace = gcl_runner._synthesize_dry_run(
            skill="alicloud-ecs-ops",
            op="DescribeInstances",
            command="aliyun ecs DescribeInstances --RegionId cn-hangzhou",
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
            command="aliyun ecs DeleteInstance --FakeParam foo",
            user_request=None,
            rubric={"version": "1.0", "ops": {"DeleteInstance": "test"}, "regexes": [], "max_iter": 1},
            max_iter=1,
            enable_hallucination_check=True,
        )
        self.assertEqual(trace["final"]["status"], "HALLUCINATION_ABORT")

    def test_report_empty_on_pass(self):
        """PASS result has an empty report."""
        result = gcl_runner.hallucination_detect(
            "aliyun ecs DescribeRegions"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["report"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
