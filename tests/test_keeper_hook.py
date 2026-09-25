#!/usr/bin/env python3
"""
Unit Tests for Project KEEPER Lifecycle Hook & Red-Line Interceptor
(tests/test_keeper_hook.py)
===================================================================
Gate A defect-pinning unit tests enforcing:
1. pre_tool_use:
   - Direct edit (replace_file_content on src/foo.cpp) when .keeper/state.json
     has "status": "RUNNING" returns decision == "force_ask" and "Direct Code Edit" in reason.
   - invoke_subagent with Role "The Artificer" and ungrounded Prompt returns
     decision == "force_ask" and "Ungrounded Subagent Prompt" in reason.
   - invoke_subagent with Role "The Trapsmith" and Prompt containing trapsmith_system.md
     AND "src/engine.cpp" returns decision == "force_ask" and "Black-Box Ingress Violation" in reason.
   - invoke_subagent with Role "The Trapsmith" and Prompt referencing trapsmith_system.md
     and .keeper/active_task.md (no src/) returns decision == "allow".
   - run_command with "git reset --hard" returns decision == "force_ask".
2. post_tool_use:
   - view_file increments read count in .keeper/turn_telemetry.json.
3. stop:
   - In temp git repo with unmarked // TODO: fix in modified src/foo.cpp, stop event
     with executionNum=1 returns decision == "continue", "KEEPER DIAGNOSTIC ALERT" in reason,
     and writes .keeper/last_turn_diagnostics.md.
   - Second call with executionNum=1 returns decision == "stop" (no infinite loop).
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HOOK_SCRIPT = Path(__file__).resolve().parent.parent / "traps" / "keeper_hook.py"


def _run_hook_cli(event: str, payload: dict, cwd: Path) -> dict:
    """Invokes traps/keeper_hook.py via subprocess CLI."""
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), "--event", event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"keeper_hook.py exited with {proc.returncode}.\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
    stdout_trimmed = proc.stdout.strip()
    if not stdout_trimmed:
        return {}
    return json.loads(stdout_trimmed)


class TestKeeperHook(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.keeper_dir = self.work_dir / ".keeper"
        self.keeper_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- pre_tool_use tests ---

    def test_pre_tool_use_direct_code_edit_when_running(self):
        """Direct edit to src/foo.cpp while .keeper/state.json status is RUNNING triggers force_ask."""
        state_file = self.keeper_dir / "state.json"
        state_file.write_text(json.dumps({"status": "RUNNING"}))

        payload = {
            "toolCall": {
                "name": "replace_file_content",
                "args": {
                    "TargetFile": str(self.work_dir / "src" / "foo.cpp"),
                    "TargetContent": "a",
                    "ReplacementContent": "b",
                },
            },
            "workspacePaths": [str(self.work_dir)],
        }

        resp = _run_hook_cli("pre_tool_use", payload, self.work_dir)
        self.assertEqual(resp.get("decision"), "force_ask")
        self.assertIn("Direct Code Edit", resp.get("reason", ""))

    def test_pre_tool_use_ungrounded_subagent_prompt(self):
        """invoke_subagent for a canonical role without an on-disk prompt triggers force_ask."""
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [
                        {
                            "Role": "The Artificer",
                            "Prompt": "Just fix the bug",
                        }
                    ]
                },
            },
            "workspacePaths": [str(self.work_dir)],
        }

        resp = _run_hook_cli("pre_tool_use", payload, self.work_dir)
        self.assertEqual(resp.get("decision"), "force_ask")
        self.assertIn("Ungrounded Subagent Prompt", resp.get("reason", ""))

    def test_pre_tool_use_trapsmith_black_box_ingress_violation(self):
        """invoke_subagent for Trapsmith referencing src/ production code triggers force_ask."""
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [
                        {
                            "Role": "The Trapsmith",
                            "Prompt": "Read codex/prompts/trapsmith_system.md and inspect src/engine.cpp to write tests.",
                        }
                    ]
                },
            },
            "workspacePaths": [str(self.work_dir)],
        }

        resp = _run_hook_cli("pre_tool_use", payload, self.work_dir)
        self.assertEqual(resp.get("decision"), "force_ask")
        self.assertIn("Black-Box Ingress Violation", resp.get("reason", ""))

    def test_pre_tool_use_trapsmith_compliant_invocation(self):
        """invoke_subagent for Trapsmith referencing prompt and active_task without src/ is allowed."""
        payload = {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [
                        {
                            "Role": "The Trapsmith",
                            "Prompt": "Read codex/prompts/trapsmith_system.md and .keeper/active_task.md to write tests in tests/.",
                        }
                    ]
                },
            },
            "workspacePaths": [str(self.work_dir)],
        }

        resp = _run_hook_cli("pre_tool_use", payload, self.work_dir)
        self.assertEqual(resp.get("decision"), "allow")

    def test_pre_tool_use_destructive_shell_command(self):
        """run_command with 'git reset --hard' triggers force_ask."""
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "git reset --hard HEAD~1",
                },
            },
            "workspacePaths": [str(self.work_dir)],
        }

        resp = _run_hook_cli("pre_tool_use", payload, self.work_dir)
        self.assertEqual(resp.get("decision"), "force_ask")

    # --- post_tool_use tests ---

    def test_post_tool_use_increments_read_count(self):
        """Calling view_file increments read count in .keeper/turn_telemetry.json."""
        payload = {
            "toolCall": {
                "name": "view_file",
                "args": {"AbsolutePath": str(self.work_dir / "README.md")},
            },
            "workspacePaths": [str(self.work_dir)],
        }

        _run_hook_cli("post_tool_use", payload, self.work_dir)

        telemetry_file = self.keeper_dir / "turn_telemetry.json"
        self.assertTrue(telemetry_file.exists(), ".keeper/turn_telemetry.json was not created")

        data = json.loads(telemetry_file.read_text())
        read_count = data.get("read_count", 0)
        self.assertGreaterEqual(read_count, 1)

        # Call again to ensure increment
        _run_hook_cli("post_tool_use", payload, self.work_dir)
        data2 = json.loads(telemetry_file.read_text())
        self.assertEqual(data2.get("read_count", 0), read_count + 1)

    # --- stop tests ---

    def test_stop_alerts_on_unmarked_todo_and_prevents_loop(self):
        """Unmarked TODO triggers continue on first attempt and stop on second with same executionNum."""
        # Initialize a git repository in work_dir
        subprocess.run(["git", "init"], cwd=str(self.work_dir), check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "trapsmith@keeper.test"],
            cwd=str(self.work_dir),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "The Trapsmith"],
            cwd=str(self.work_dir),
            check=True,
            capture_output=True,
        )

        src_dir = self.work_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        foo_cpp = src_dir / "foo.cpp"
        foo_cpp.write_text("int clean_code() { return 0; }\n")

        subprocess.run(["git", "add", "."], cwd=str(self.work_dir), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(self.work_dir), check=True, capture_output=True)

        # Modify foo.cpp with an unmarked TODO
        foo_cpp.write_text("int clean_code() {\n    // TODO: fix later\n    return 0;\n}\n")

        payload = {
            "executionNum": 1,
            "workspacePaths": [str(self.work_dir)],
        }

        # First call: should alert with continue decision and write diagnostics
        resp1 = _run_hook_cli("stop", payload, self.work_dir)
        self.assertEqual(resp1.get("decision"), "continue")
        self.assertIn("KEEPER DIAGNOSTIC ALERT", resp1.get("reason", ""))

        diag_file = self.keeper_dir / "last_turn_diagnostics.md"
        self.assertTrue(diag_file.exists(), ".keeper/last_turn_diagnostics.md was not written")
        diag_content = diag_file.read_text()
        self.assertIn("TODO", diag_content)

        # Second call with same executionNum=1: must return stop to prevent infinite loops
        resp2 = _run_hook_cli("stop", payload, self.work_dir)
        self.assertEqual(resp2.get("decision"), "stop")


if __name__ == "__main__":
    unittest.main()
