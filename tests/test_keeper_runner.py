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


if __name__ == "__main__":
    unittest.main()
