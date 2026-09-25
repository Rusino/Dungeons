#!/usr/bin/env python3
"""
Unit Tests for Project KEEPER Runner (test_keeper_runner.py)
============================================================
Proves that the state machine runner deterministically:
1. Enforces Gate A and rejects Ghost Tests.
2. Enforces Gate B (build + pass).
3. Enforces Circuit Breakers (Forbidden Paths, Blast Radius, Strike 3).
4. Auto-advances silently when gates pass.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# Add parent directory to import keeper_runner
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from keeper_runner import KeeperRunner, CircuitBreakerException


class TestKeeperRunner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="keeper_test_")
        self.work_dir = Path(self.test_dir)

        # Minimal test keeper.yaml
        self.test_spec = {
            "version": "1.0",
            "project": "TEST_KEEPER",
            "circuit_breakers": {
                "max_attempts": 3,
                "step_timeout_seconds": 60,
                "max_diff_lines": 50,
            },
            "config": {
                "build_cmd": "echo 'build ok'",
                "test_cmd": "echo 'test ok'",
            },
            "phases": [
                {
                    "id": 1,
                    "name": "Phase 1: Inception",
                    "actor": "The Overgod",
                    "interactive": True,
                    "produces": ["docs/*.md"],
                    "gate": {"type": "file_exists", "target": "docs/*.md"},
                },
                {
                    "id": 2,
                    "name": "Phase 2: Gate A Verification",
                    "actor": "The Trapsmith",
                    "interactive": False,
                    "circuit_breakers": {
                        "forbidden_paths": ["src/**", "include/**"]
                    },
                    "gate": {
                        "type": "gate_a",
                        "build_command": "true",
                        "run_command": "false",  # Exits 1 (defect reproduced)
                        "expected_exit_code": 1,
                    },
                },
                {
                    "id": 3,
                    "name": "Phase 3: Implementation",
                    "actor": "The Artificer",
                    "interactive": False,
                    "circuit_breakers": {
                        "forbidden_paths": ["include/**", "tests/**"]
                    },
                    "gate": {
                        "type": "gate_b",
                        "build_command": "true",
                        "run_command": "true",  # Exits 0 (defect resolved)
                        "expected_exit_code": 0,
                    },
                },
            ],
        }

        with open(self.work_dir / "keeper.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.test_spec, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_file_exists_gate(self):
        """Proves file_exists gate passes only when matching file exists on disk."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        phase_1 = runner.phases[0]

        # Missing file -> False
        passed, msg = runner.evaluate_gate(phase_1)
        self.assertFalse(passed)

        # Create file -> True
        docs_dir = self.work_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "RFC.md").write_text("# RFC Title", encoding="utf-8")

        passed, msg = runner.evaluate_gate(phase_1)
        self.assertTrue(passed)
        self.assertIn("RFC.md", msg)

    def test_gate_a_rejection_of_ghost_tests(self):
        """Proves Gate A rejects ghost tests that erroneously pass (exit 0) on broken code."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        
        # Scenario 1: Trap test exits 0 on broken code -> REJECT (Ghost test!)
        ghost_gate = {
            "type": "gate_a",
            "build_command": "true",
            "run_command": "true",  # returns 0
            "expected_exit_code": 1,
        }
        passed, msg = runner.evaluate_gate({"id": 2, "name": "Gate A", "gate": ghost_gate})
        self.assertFalse(passed)
        self.assertIn("Ghost Test Detected", msg)

        # Scenario 2: Trap test exits 1 (SIGABRT/failure) -> PASS (Legitimate defect reproduction)
        real_trap_gate = {
            "type": "gate_a",
            "build_command": "true",
            "run_command": "exit 1",
            "expected_exit_code": 1,
        }
        passed, msg = runner.evaluate_gate({"id": 2, "name": "Gate A", "gate": real_trap_gate})
        self.assertTrue(passed)
        self.assertIn("Defect caught", msg)

    def test_gate_b_verification(self):
        """Proves Gate B requires both build=0 and test=0."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))

        # Scenario 1: Implementation fails build -> FAIL
        broken_build = {
            "type": "gate_b",
            "build_command": "false",
            "run_command": "true",
        }
        passed, msg = runner.evaluate_gate({"id": 3, "name": "Gate B", "gate": broken_build})
        self.assertFalse(passed)
        self.assertIn("Compilation failed", msg)

        # Scenario 2: Implementation builds and tests pass -> PASS
        working_gate = {
            "type": "gate_b",
            "build_command": "true",
            "run_command": "true",
        }
        passed, msg = runner.evaluate_gate({"id": 3, "name": "Gate B", "gate": working_gate})
        self.assertTrue(passed)
        self.assertIn("Gate B Certified", msg)

    def test_circuit_breaker_forbidden_paths(self):
        """Proves that touching forbidden paths raises CircuitBreakerException."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))

        # Mock git status --porcelain returning a modified forbidden file
        with patch("keeper_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=" M src/forbidden_hack.cpp\n",
            )
            with self.assertRaises(CircuitBreakerException) as ctx:
                runner.check_forbidden_paths("Phase 2", ["src/**", "include/**"])

            self.assertIn("Scope Guard Violation", str(ctx.exception))
            self.assertIn("src/forbidden_hack.cpp", str(ctx.exception))

    def test_circuit_breaker_strike_three(self):
        """Proves that 3 consecutive failed gate checks halt the state machine."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 1  # Phase 2 (automated)

        # Make gate consistently fail
        with patch.object(runner, "evaluate_gate", return_value=(False, "Synthetic failure")):
            # Attempt 1
            adv1 = runner.run_step(auto_advance=False)
            self.assertFalse(adv1)
            self.assertEqual(runner.state["attempt_counts"]["2"], 1)
            self.assertEqual(runner.state["status"], "RUNNING")

            # Attempt 2
            adv2 = runner.run_step(auto_advance=False)
            self.assertFalse(adv2)
            self.assertEqual(runner.state["attempt_counts"]["2"], 2)
            self.assertEqual(runner.state["status"], "RUNNING")

            # Attempt 3 -> Circuit breaker trips!
            adv3 = runner.run_step(auto_advance=False)
            self.assertFalse(adv3)
            self.assertEqual(runner.state["attempt_counts"]["2"], 3)
            self.assertEqual(runner.state["status"], "HALTED")
            self.assertIn("Strike 3", runner.state["last_halt_reason"])

    def test_auto_advance_on_green(self):
        """Proves that when a non-interactive gate passes, it silently auto-advances."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 1  # Start at Phase 2 (automated)

        # Mock gate passing for Phase 2 and Phase 3
        with patch.object(runner, "evaluate_gate", return_value=(True, "All good")):
            runner.run_step(auto_advance=True)

            # Proves it auto-advanced through Phase 2 and Phase 3 to completion!
            self.assertEqual(runner.state["status"], "COMPLETED")
            self.assertIn(2, runner.state["completed_phases"])
            self.assertIn(3, runner.state["completed_phases"])

    def test_fuzz_config_override(self):
        """Proves that KEEPER_CONFIG.md overrides fuzz_cmd."""
        cfg_path = self.work_dir / "KEEPER_CONFIG.md"
        cfg_path.write_text(
            "# Config\n- **Fuzz Command**: `out/Fuzz/custom_fuzzer`\n",
            encoding="utf-8",
        )
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        self.assertEqual(runner.config_vars.get("fuzz_cmd"), "out/Fuzz/custom_fuzzer")

    def test_beholder_fuzz_gate_evaluation(self):
        """Proves that The Beholder fuzz gate resolves command and evaluates successfully."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.config_vars["fuzz_cmd"] = "echo 'fuzz passed'"
        phase = {
            "id": 8.5,
            "name": "The Beholder",
            "gate": {"type": "shell", "command": "{fuzz_cmd}", "expected_exit_code": 0},
        }
        success, evidence = runner.evaluate_gate(phase)
        self.assertTrue(success)
        self.assertIn("expected code 0", evidence)

    def test_run_drive_stops_at_interactive_phase(self):
        """Proves that run_drive pauses cleanly at interactive phases for Overgod review."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 0  # Phase 1 is interactive
        with patch.object(runner, "dispatch_phase_worker") as mock_dispatch:
            res = runner.run_drive()
            self.assertTrue(res)
            # Worker must NOT be dispatched for interactive human phases
            mock_dispatch.assert_not_called()
            self.assertEqual(runner.state["current_phase_idx"], 0)

    def test_run_drive_dispatches_worker_and_advances(self):
        """Proves that run_drive dispatches worker for automated phases and auto-advances on gate pass."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 1  # Start at Phase 2 (automated)

        with patch.object(runner, "dispatch_phase_worker", return_value=True) as mock_dispatch, \
             patch.object(runner, "evaluate_gate", return_value=(True, "Receipt verified")):
            res = runner.run_drive()
            self.assertTrue(res)
            self.assertEqual(mock_dispatch.call_count, 2)  # Dispatched for Phase 2 and Phase 3
            self.assertEqual(runner.state["status"], "COMPLETED")
            self.assertIn(2, runner.state["completed_phases"])
            self.assertIn(3, runner.state["completed_phases"])

    def test_run_drive_retries_with_feedback(self):
        """Proves that run_drive feeds failure stderr back into retry attempts."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 1  # Phase 2 (automated)

        gate_evaluations = [
            (False, "Compilation error on line 42"),
            (True, "All tests passed cleanly"),
        ]

        with patch.object(runner, "dispatch_phase_worker", return_value=True) as mock_dispatch, \
             patch.object(runner, "evaluate_gate", side_effect=gate_evaluations):
            res = runner.run_drive(target_phase_id=2)
            self.assertTrue(res)
            self.assertEqual(mock_dispatch.call_count, 2)
            # Verify attempt 1 had no feedback, but attempt 2 had the error feedback
            mock_dispatch.assert_any_call(runner.phases[1], error_feedback=None)
            mock_dispatch.assert_any_call(runner.phases[1], error_feedback="Compilation error on line 42")
            self.assertIn(2, runner.state["completed_phases"])

    def test_audit_workflow_initialization(self):
        """Proves that workflow='audit' initializes audit phases and separate state file."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir), workflow="audit")
        self.assertEqual(runner.workflow, "audit")
        self.assertEqual(runner.state_file, ".keeper/audit_state.json")
        self.assertTrue(len(runner.phases) > 0)
        # Verify first phase is build check
        self.assertEqual(runner.phases[0]["id"], "audit.build")

    def test_audit_workflow_auto_advance(self):
        """Proves that audit workflow executes automated gates and pauses at report ratification."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir), workflow="audit")
        # Mock evaluate_gate to pass for all automated checks
        with patch.object(runner, "evaluate_gate", return_value=(True, "Check passed")):
            runner.run_step(auto_advance=True)
            # Should advance past all automated phases and pause at the interactive audit.report phase
            cur_idx = runner.state["current_phase_idx"]
            self.assertTrue(runner.phases[cur_idx].get("interactive"))
            self.assertEqual(runner.phases[cur_idx]["id"], "audit.report")


    def test_conditional_phase_skipping(self):
        """Proves that conditional phases are skipped unless their specific condition is satisfied."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))

        # Test milestone conditional
        milestone_phase = {"id": "8.6", "name": "The Censor", "conditional": "on_milestone"}
        should_run, reason = runner.should_execute_phase(milestone_phase)
        self.assertFalse(should_run)
        self.assertIn("milestone", reason.lower())

        # Test with is_milestone=True
        m_runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir), is_milestone=True)
        should_run, reason = m_runner.should_execute_phase(milestone_phase)
        self.assertTrue(should_run)

        # Test defect escape conditional
        escape_phase = {"id": "11", "name": "The Coroner", "conditional": "on_defect_escape"}
        should_run, reason = runner.should_execute_phase(escape_phase)
        self.assertFalse(should_run)
        self.assertIn("defect escape", reason.lower())

        esc_runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir), is_defect_escape=True)
        should_run, reason = esc_runner.should_execute_phase(escape_phase)
        self.assertTrue(should_run)

        # Test compilation breakage conditional
        align_phase = {"id": "3.7", "name": "Syntactic Alignment", "conditional": "on_compilation_breakage"}
        runner.state["last_build_failed"] = False
        should_run, _ = runner.should_execute_phase(align_phase)
        self.assertFalse(should_run)

        runner.state["last_build_failed"] = True
        should_run, _ = runner.should_execute_phase(align_phase)
        self.assertTrue(should_run)

    def test_approve_rejects_missing_receipts(self):
        """Proves that approve_current_phase rejects approval when required physical artifacts are missing."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 0  # Phase 1 mandates produces: ["docs/*.md"]

        # Attempt to approve without creating docs/*.md
        ok, msg = runner.approve_current_phase()
        self.assertFalse(ok)
        self.assertIn("Mandatory produced artifact missing", msg)
        self.assertEqual(runner.state["current_phase_idx"], 0)
        self.assertEqual(runner.state["status"], "HALTED")

        # Now create the required artifact
        docs_dir = self.work_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "RFC_test.md").write_text("# Test Inception Intent\n", encoding="utf-8")

        # Approve again -> Must succeed!
        ok, msg = runner.approve_current_phase()
        self.assertTrue(ok)
        self.assertEqual(runner.state["current_phase_idx"], 1)
        self.assertEqual(runner.state["status"], "RUNNING")
        self.assertIn(1, runner.state["completed_phases"])

    def test_approve_validates_requires_prerequisites(self):
        """Proves that approve validates requires patterns before permitting sign-off."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        phase_with_req = {
            "id": 2.5,
            "name": "Contract Sign-off",
            "interactive": True,
            "requires": ["include/*.h"],
        }
        valid, msg = runner.validate_approval_prerequisites(phase_with_req)
        self.assertFalse(valid)
        self.assertIn("Prerequisite artifact missing", msg)

        # Create header
        inc_dir = self.work_dir / "include"
        inc_dir.mkdir(parents=True, exist_ok=True)
        (inc_dir / "contract.h").write_text("#pragma once\n", encoding="utf-8")

        valid, msg = runner.validate_approval_prerequisites(phase_with_req)
        self.assertTrue(valid)

    def test_mutation_engine_mutant_generation(self):
        """Proves that the real mutation engine identifies C++ operators and generates mutations."""
        from traps.mutation_gate import generate_mutants

        test_cpp = self.work_dir / "sample.cpp"
        test_cpp.write_text("bool check(int a, int b) {\n    return a == b;\n}\n", encoding="utf-8")

        mutants = generate_mutants([test_cpp])
        self.assertGreater(len(mutants), 0)
        # Should detect '==' and propose '!='
        self.assertTrue(any("!=" in m.mutated_line for m in mutants))

    def test_performance_auditor_budget_enforcement(self):
        """Proves that performance auditor rejects benchmarks that violate memory/latency budgets."""
        from traps.performance_auditor import run_benchmark_audit

        # Mock a benchmark run that exceeds memory allocation budget
        mock_output = json.dumps({
            "benchmarks": [
                {
                    "name": "BM_LeakyOperation",
                    "cpu_time_ns": 50.0,
                    "heap_allocations": 5  # Budget is 0!
                }
            ]
        })

        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
            exit_code = run_benchmark_audit(
                work_dir=self.work_dir,
                cmd_str="./dummy_bench",
                max_allocs=0,
                max_ns=100.0,
            )
            self.assertEqual(exit_code, 1)

    def test_gate_a_rejects_command_not_found(self):
        """Proves Gate A rejects shell invocation errors (exit 126/127) instead of certifying them as caught defects."""
        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        broken_cmd_gate = {
            "type": "gate_a",
            "build_command": "true",
            "run_command": "nonexistent_binary_xyz_12345",
            "expected_exit_code": 1,
        }
        passed, msg = runner.evaluate_gate({"id": 4, "name": "Gate A", "gate": broken_cmd_gate})
        self.assertFalse(passed, f"Gate A must reject exit code 127, but got passed=True ({msg})")
        self.assertIn("127", msg)

    def test_circuit_breaker_cleans_untracked_files(self):
        """Proves that when a worker creates an untracked file in a forbidden path, rollback removes it."""
        # Initialize a real git repo in self.work_dir
        import subprocess
        subprocess.run(["git", "init"], cwd=self.work_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@keeper.local"], cwd=self.work_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Keeper Test"], cwd=self.work_dir, capture_output=True, check=True)
        subprocess.run(["git", "add", "keeper.yaml"], cwd=self.work_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.work_dir, capture_output=True, check=True)

        runner = KeeperRunner(config_path="keeper.yaml", work_dir=str(self.work_dir))
        runner.state["current_phase_idx"] = 1  # Phase 2 forbids src/**

        rogue_file = self.work_dir / "src" / "rogue_untracked.cpp"

        call_count = 0
        async def fake_worker(phase, error_feedback=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Attempt 1: create an untracked file in forbidden src/
                rogue_file.parent.mkdir(parents=True, exist_ok=True)
                rogue_file.write_text("// rogue file\n", encoding="utf-8")
            return True

        with patch.object(runner, "dispatch_phase_worker", side_effect=fake_worker), \
             patch.object(runner, "evaluate_gate", return_value=(True, "Gate A passed")):
            res = runner.run_drive(target_phase_id=2)
            self.assertTrue(res, "Attempt 2 should succeed after untracked rogue file is cleaned up")
            self.assertFalse(rogue_file.exists(), "Untracked rogue file in forbidden path must be deleted on rollback")

    def test_mutation_engine_stillborn_on_compile_failure(self):
        """Proves that uncompilable mutants are marked STILLBORN and excluded from killed_count."""
        from traps.mutation_gate import run_mutation_engine

        test_cpp = self.work_dir / "src" / "sample.cpp"
        test_cpp.parent.mkdir(parents=True, exist_ok=True)
        test_cpp.write_text("bool check(int a, int b) {\n    return a == b;\n}\n", encoding="utf-8")

        # Build fails (exit 1), meaning all mutants fail to compile -> STILLBORN, not KILLED.
        # Under strict=True, if 0 mutants are actually evaluated by tests, it should fail (return 1).
        rc = run_mutation_engine(
            stage="gate_b",
            work_dir=self.work_dir,
            build_cmd="false",
            test_cmd="true",
            strict=True,
        )
        self.assertEqual(rc, 1, "Uncompilable mutants must be STILLBORN, not counted as KILLED")


if __name__ == "__main__":
    unittest.main()
