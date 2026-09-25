#!/usr/bin/env python3
"""
Project KEEPER Operational State Machine Runner (keeper_runner.py)
==================================================================
Deterministic, neuro-symbolic workflow runner for Project KEEPER.
Enforces physical receipt gates and ironclad circuit breakers.
Zero-bother execution: auto-advances on green; halts hard on red.
"""

import argparse
import asyncio
import fnmatch
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
    from google.antigravity.hooks import policy
    ANTIGRAVITY_AVAILABLE = True
except ImportError:
    ANTIGRAVITY_AVAILABLE = False

STATE_FILE = ".keeper/state.json"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log_progress(phase_name: str, emoji: str, message: str, color: str = ""):
    """Prints a single-line real-time status update to stdout."""
    prefix = f"[{phase_name}]" if phase_name else "[KEEPER]"
    formatted = f"{color}{prefix} {emoji} {message}{Colors.RESET}"
    sys.stdout.write(f"\r\033[K{formatted}\n")
    sys.stdout.flush()


def print_dossier(
    phase_id: Any,
    phase_name: str,
    actor: str,
    gate_status: str,
    evidence: str,
    action_required: str,
    is_halt: bool = False,
    violations: Optional[List[Dict[str, Any]]] = None,
):
    """Prints a standardized, human-readable KEEPER Gate Dossier."""
    color = Colors.RED if is_halt else Colors.YELLOW
    header = f"🛡️  KEEPER GATE DOSSIER: Phase {phase_id} ({phase_name})"
    sep = "=" * 68
    print(f"\n{color}{sep}")
    print(f"{header}")
    print(f"{sep}{Colors.RESET}")
    print(f"  👤 Actor:           {actor}")
    print(f"  🧪 Gate Status:     {gate_status}")
    print(f"  📦 Evidence:        {evidence}")
    if violations:
        print(f"  ------------------------------------------------------------------")
        print(f"  🚨 PROTOCOL VIOLATION LEDGER ({len(violations)} breached containment):")
        for v in violations:
            p_id = v.get("phase_id", "?")
            act = v.get("actor", "Unknown")
            det = v.get("detail", "")
            att = v.get("attempt", 1)
            print(f"    - [Phase {p_id} | {act} | Att {att}]: {det}")
    print(f"  ------------------------------------------------------------------")
    print(f"  👁️  Overgod Action:  {action_required}")
    print(f"{color}{sep}{Colors.RESET}\n")


class CircuitBreakerException(Exception):
    """Raised when an ironclad safety circuit breaker trips."""
    pass


class KeeperRunner:
    def __init__(
        self,
        config_path: str = "keeper.yaml",
        work_dir: str = ".",
        workflow: str = "feature",
        is_milestone: bool = False,
        is_defect_escape: bool = False,
        strict: bool = False,
    ):
        self.work_dir = Path(work_dir).resolve()
        self.config_path = self.work_dir / config_path
        if not self.config_path.exists():
            # Check codex fallback
            codex_path = self.work_dir / "codex" / "keeper.yaml"
            if codex_path.exists():
                self.config_path = codex_path
            else:
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

        self.workflow = workflow
        self.is_milestone = is_milestone
        self.is_defect_escape = is_defect_escape
        self.strict = strict
        self.global_breakers = self.spec.get("circuit_breakers", {})
        self.config_vars = self.spec.get("config", {})
        self._load_keeper_config_overrides()

        if self.workflow == "audit":
            self.phases = self.spec.get("audit_phases") or self._get_default_audit_phases()
            self.state_file = ".keeper/audit_state.json"
        else:
            self.phases = self.spec.get("phases", [])
            self.state_file = STATE_FILE

        self.state = self._load_state()

    def _get_default_audit_phases(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "audit.build",
                "name": "Compilation & Link Integrity",
                "actor": "The Artificer",
                "interactive": False,
                "gate": {
                    "type": "shell",
                    "command": "{build_cmd}",
                    "expected_exit_code": 0,
                },
            },
            {
                "id": "audit.test",
                "name": "Unit Test Suite",
                "actor": "The Trapsmith",
                "interactive": False,
                "gate": {
                    "type": "shell",
                    "command": "{test_cmd}",
                    "expected_exit_code": 0,
                },
            },
            {
                "id": "audit.fuzz",
                "name": "The Beholder (Bounded Fuzz Gate)",
                "actor": "The Beholder",
                "interactive": False,
                "gate": {
                    "type": "shell",
                    "command": "{fuzz_cmd}",
                    "expected_exit_code": 0,
                },
            },
            {
                "id": "audit.sanitizers",
                "name": "The Acid Pit (Sanitizers)",
                "actor": "The Acid Pit",
                "interactive": False,
                "gate": {
                    "type": "shell",
                    "command": "{sanitizer_cmd}",
                    "expected_exit_code": 0,
                },
            },
            {
                "id": "audit.report",
                "name": "Health Dossier Ratification",
                "actor": "The Overgod",
                "interactive": True,
                "prompt": "All physical health checks verified. Ratify clean engine health status?",
                "gate": {
                    "type": "human_approval",
                    "prompt": "Confirm clean engine health.",
                },
            },
        ]

    def _load_keeper_config_overrides(self):
        """Loads project-specific commands from KEEPER_CONFIG.md if present."""
        cfg_file = self.work_dir / "KEEPER_CONFIG.md"
        if not cfg_file.exists():
            return

        text = cfg_file.read_text(encoding="utf-8")

        def _extract_cmd(inline_pattern: str, section_pattern: str) -> Optional[str]:
            m = re.search(inline_pattern, text)
            if m:
                return m.group(1).strip()
            sec = re.search(
                rf"###\s+(?:{section_pattern})\s*\n+```(?:bash|sh)?\n([^`]+)```",
                text,
                re.IGNORECASE,
            )
            if sec:
                lines = [
                    ln.strip()
                    for ln in sec.group(1).splitlines()
                    if ln.strip() and not ln.strip().startswith("#")
                ]
                if lines:
                    return " && ".join(lines)
            return None

        build_cmd = _extract_cmd(r"\*\*Build Command\*\*:\s*`([^`]+)`", r"Build Command")
        if build_cmd:
            self.config_vars["build_cmd"] = build_cmd

        test_cmd = _extract_cmd(
            r"\*\*(?:Unit )?Test Command\*\*:\s*`([^`]+)`", r"(?:Unit )?Test Command"
        )
        if test_cmd:
            self.config_vars["test_cmd"] = test_cmd

        asan_cmd = _extract_cmd(r"ASan\+UBSan Command:\s*`([^`]+)`", r"Sanitizer(?:s| Matrix)?")
        if asan_cmd:
            self.config_vars["sanitizer_cmd"] = asan_cmd

        fuzz_cmd = _extract_cmd(r"\*\*Fuzz(?:ing)? Command\*\*:\s*`([^`]+)`", r"Fuzz(?:ing)? Command")
        if fuzz_cmd:
            self.config_vars["fuzz_cmd"] = fuzz_cmd

    def _load_state(self) -> Dict[str, Any]:
        """Loads state from configured state file or initializes default state."""
        state_path = self.work_dir / self.state_file
        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    if "last_build_failed" not in s:
                        s["last_build_failed"] = False
                    if "protocol_violations" not in s:
                        s["protocol_violations"] = []
                    return s
            except Exception:
                pass

        return {
            "current_phase_idx": 0,
            "completed_phases": [],
            "attempt_counts": {},
            "status": "RUNNING",
            "last_halt_reason": None,
            "last_build_failed": False,
            "protocol_violations": [],
        }

    def record_violation(
        self,
        phase_id: Any,
        actor: str,
        violation_type: str,
        detail: str,
        attempt: int = 1,
    ) -> None:
        """Records a containment or protocol violation to the persistent ledger."""
        if "protocol_violations" not in self.state:
            self.state["protocol_violations"] = []
        entry = {
            "phase_id": phase_id,
            "actor": actor,
            "type": violation_type,
            "detail": detail,
            "attempt": attempt,
        }
        self.state["protocol_violations"].append(entry)
        self.save_state()

    def save_state(self):
        """Persists state to configured state file."""
        state_path = self.work_dir / self.state_file
        state_path.parent.mkdir(parents=True, exist_ok=True)
        gitignore_path = state_path.parent / ".gitignore"
        if state_path.parent.name == ".keeper" and not gitignore_path.exists():
            gitignore_path.write_text("*\n", encoding="utf-8")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def _get_git_head(self) -> Optional[str]:
        """Returns the current git HEAD commit hash, or None if not in a valid repo."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def _rollback_working_tree(self, pre_head: Optional[str] = None):
        """Reverts tracked, staged, and untracked modifications back to pre_head."""
        if pre_head:
            cur_head = self._get_git_head()
            if cur_head and cur_head != pre_head:
                subprocess.run(
                    ["git", "reset", "--soft", pre_head],
                    cwd=self.work_dir,
                    capture_output=True,
                )
        subprocess.run(
            ["git", "restore", "--staged", "."],
            cwd=self.work_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "restore", "."],
            cwd=self.work_dir,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "clean",
                "-fd",
                "-e",
                ".keeper/",
                "-e",
                "AGENTS.md",
                "-e",
                "INVARIANTS.md",
                "-e",
                "KEEPER_CONFIG.md",
                "-e",
                "keeper",
                "-e",
                "keeper.yaml",
                "-e",
                "traps",
                "-e",
                "fuzz/",
                "-e",
                ".agents/",
                "-e",
                ".antigravity/",
            ],
            cwd=self.work_dir,
            capture_output=True,
        )

    def reset_state(self):
        """Resets the state machine back to initial phase."""
        self.state = {
            "current_phase_idx": 0,
            "completed_phases": [],
            "attempt_counts": {},
            "status": "RUNNING",
            "last_halt_reason": None,
            "last_build_failed": False,
            "protocol_violations": [],
        }
        self.save_state()
        mode_label = "Audit workflow" if self.workflow == "audit" else "State machine"
        log_progress("", "🔄", f"{mode_label} reset to initial phase.", Colors.GREEN)

    def get_phase_breakers(self, phase: Dict[str, Any]) -> Dict[str, Any]:
        """Merges global circuit breaker defaults with phase-specific overrides."""
        merged = dict(self.global_breakers)
        merged.update(phase.get("circuit_breakers", {}))
        return merged

    def _resolve_command(self, cmd_str: str) -> str:
        """Substitutes configured variables into command strings."""
        if not cmd_str:
            return ""
        for k, v in self.config_vars.items():
            cmd_str = cmd_str.replace(f"{{{k}}}", v)
        return cmd_str

    def check_blast_radius(self, phase_name: str, max_lines: int) -> int:
        """Asserts that total lines changed in git does not exceed max_lines."""
        try:
            res = subprocess.run(
                ["git", "diff", "--numstat"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            total_lines = 0
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    total_lines += int(parts[0]) + int(parts[1])

            if total_lines > max_lines:
                raise CircuitBreakerException(
                    f"Blast Radius Exceeded! Diff is {total_lines} lines (maximum allowed: {max_lines})."
                )
            return total_lines
        except subprocess.CalledProcessError:
            return 0

    def check_forbidden_paths(self, phase_name: str, forbidden_patterns: List[str]):
        """Asserts that no modified, staged, or untracked files match forbidden path patterns."""
        if not forbidden_patterns:
            return

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-uall"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            for line in res.stdout.splitlines():
                if not line.strip() or len(line) < 4:
                    continue
                file_path = line[3:].strip()
                # If renamed, take the destination path
                if " -> " in file_path:
                    file_path = file_path.split(" -> ")[1].strip()

                for pat in forbidden_patterns:
                    # Strip leading wildcards for matching
                    clean_pat = pat.lstrip("/")
                    prefix_dir = clean_pat[:-2] if clean_pat.endswith("/**") else None
                    if (
                        fnmatch.fnmatch(file_path, clean_pat)
                        or fnmatch.fnmatch(file_path, f"*/{clean_pat}")
                        or (prefix_dir and file_path.startswith(prefix_dir))
                    ):
                        raise CircuitBreakerException(
                            f"Scope Guard Violation! Subagent touched forbidden path: {file_path} (Matches pattern: {pat})"
                        )
        except subprocess.CalledProcessError:
            pass

    def check_code_traces(self, phase_name: str) -> None:
        """
        Inspects added lines from git diff for disallowed constructs, unmarked TODOs,
        header loops, and forbidden test skips.
        """
        try:
            diff_res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
            diff_text = diff_res.stdout
            if diff_res.returncode != 0:
                diff_res2 = subprocess.run(
                    ["git", "diff"],
                    cwd=self.work_dir,
                    capture_output=True,
                    text=True,
                )
                diff_text = diff_res2.stdout

            current_file = ""
            disallowed_constructs = [
                "#pragma",
                "reinterpret_cast",
                "goto",
                "malloc(",
                "free(",
            ]

            for line in diff_text.splitlines():
                if line.startswith("+++ b/"):
                    current_file = line[6:].strip()
                    continue
                if not line.startswith("+") or line.startswith("+++"):
                    continue

                added = line[1:].strip()

                if current_file.startswith("src/"):
                    for construct in disallowed_constructs:
                        if construct in added:
                            raise CircuitBreakerException(
                                f"Executable Trace Violation: Disallowed construct '{construct}' in {current_file}: '{added}'"
                            )
                    if ("// TODO" in added or "/* TODO" in added) and "TODO(KEEPER-DEBT:" not in added:
                        raise CircuitBreakerException(
                            f"Executable Trace Violation: Unmarked TODO in {current_file}: '{added}'"
                        )

                elif current_file.startswith("include/"):
                    if "for (" in added or "while (" in added:
                        raise CircuitBreakerException(
                            f"Executable Trace Violation: Algorithmic loop in header {current_file}: '{added}'"
                        )
                    if ("// TODO" in added or "/* TODO" in added) and "TODO(KEEPER-DEBT:" not in added:
                        raise CircuitBreakerException(
                            f"Executable Trace Violation: Unmarked TODO in {current_file}: '{added}'"
                        )

                elif current_file.startswith("tests/") and current_file.endswith((".cpp", ".cc", ".cxx", ".h", ".hpp")):
                    if "SKIP_IF" in added or "GTEST_SKIP" in added:
                        raise CircuitBreakerException(
                            f"Executable Trace Violation: Forbidden test bypass '{added}' in {current_file}"
                        )
                    if "#define private public" in added:
                        raise CircuitBreakerException(
                            f"Executable Trace Violation: Forbidden test bypass '#define private public' in {current_file}"
                        )

        except subprocess.CalledProcessError:
            pass

    def evaluate_gate(self, phase: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Deterministically evaluates physical receipts for a phase gate.
        Returns (success: bool, evidence_description: str).
        """
        gate = phase.get("gate")
        if not gate:
            return True, "No gate defined."

        gate_type = gate.get("type", "shell")
        phase_name = f"Phase {phase['id']}: {phase['name']}"

        if gate_type == "file_exists":
            target = gate.get("target")
            pattern = str(self.work_dir / target)
            matches = glob.glob(pattern, recursive=True)
            non_empty = [m for m in matches if os.path.isfile(m) and os.path.getsize(m) > 0]
            if non_empty:
                rel_files = [os.path.relpath(f, self.work_dir) for f in non_empty[:3]]
                return True, f"Verified files exist: {', '.join(rel_files)}"
            return False, f"Missing physical artifact matching: {target}"

        elif gate_type == "shell":
            raw_cmd = gate.get("command", "")
            cmd = self._resolve_command(raw_cmd)
            expected = gate.get("expected_exit_code", 0)

            log_progress(phase_name, "🔨", f"Executing gate check: {cmd}")
            res = subprocess.run(cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if res.returncode == expected:
                return True, f"Command exited with expected code {expected}"
            return False, f"Command '{cmd}' exited with code {res.returncode} (expected {expected}).\nStderr:\n{res.stderr[:300]}"

        elif gate_type == "gate_a":
            # Gate A: MUST build (0), but test MUST FAIL (expected non-zero) on unmodified code
            build_cmd = self._resolve_command(gate.get("build_command", ""))
            run_cmd = self._resolve_command(gate.get("run_command", ""))
            expected_exit = gate.get("expected_exit_code", 1)

            log_progress(phase_name, "🔨", f"Building test binary: {build_cmd}")
            b_res = subprocess.run(build_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if b_res.returncode != 0:
                self.state["last_build_failed"] = True
                self.save_state()
                return False, f"Compilation failed for Gate A test.\nStderr:\n{b_res.stderr[:300]}"
            self.state["last_build_failed"] = False

            log_progress(phase_name, "🎯", f"Running Gate A defect reproduction trap: {run_cmd}")
            r_res = subprocess.run(run_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)

            if r_res.returncode == 0:
                return False, "Ghost Test Detected! Gate A requires the test to FAIL on current code, but it passed."
            if r_res.returncode in (126, 127):
                return (
                    False,
                    f"Gate A test command invocation failed with shell exit code {r_res.returncode} "
                    f"(command not found or not executable: '{run_cmd}').\nStderr:\n{r_res.stderr[:300]}",
                )
            if expected_exit not in (-1, 1) and r_res.returncode != expected_exit:
                return (
                    False,
                    f"Gate A test exited with unexpected code {r_res.returncode} (expected {expected_exit}).\n"
                    f"Stderr:\n{r_res.stderr[:300]}",
                )
            return True, f"Defect caught! Test failed with returncode {r_res.returncode} (Gate A certified)."

        elif gate_type == "gate_b":
            # Gate B: MUST build (0) AND test MUST PASS (0) on refactored code
            build_cmd = self._resolve_command(gate.get("build_command", ""))
            run_cmd = self._resolve_command(gate.get("run_command", ""))

            log_progress(phase_name, "🔨", f"Building implementation: {build_cmd}")
            b_res = subprocess.run(build_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if b_res.returncode != 0:
                self.state["last_build_failed"] = True
                self.save_state()
                return False, f"Compilation failed for Gate B implementation.\nStderr:\n{b_res.stderr[:300]}"
            self.state["last_build_failed"] = False

            log_progress(phase_name, "🎯", f"Running Gate B regression suite: {run_cmd}")
            r_res = subprocess.run(run_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if r_res.returncode == 0:
                return True, "Gate B Certified: Code builds and all tests pass with exit code 0."
            return False, f"Gate B Failed: Tests failed with exit code {r_res.returncode}.\nOutput:\n{r_res.stdout[-300:]}"

        elif gate_type == "human_approval":
            return True, "Awaiting Overgod interactive input."

        return False, f"Unknown gate type: {gate_type}"

    def should_execute_phase(self, phase: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates whether a conditional phase should execute or be skipped.
        Returns (should_execute: bool, reason: str).
        """
        cond = phase.get("conditional")
        if not cond:
            return True, ""

        if cond == "on_compilation_breakage":
            if self.state.get("last_build_failed", False):
                return True, "Triggered by compilation breakage in prior phase"
            return False, "Skipped: Clean build; no syntactic compilation breakage"

        elif cond == "on_milestone":
            if self.is_milestone:
                return True, "Triggered by --milestone flag"
            return False, "Skipped: Routine feature run; milestone hygiene not requested (use --milestone to activate)"

        elif cond == "on_defect_escape":
            if self.is_defect_escape:
                return True, "Triggered by --defect-escape flag"
            return False, "Skipped: Clean feature run; no defect escape reported (use --defect-escape to activate)"

        return True, ""

    def validate_approval_prerequisites(self, phase: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Physically validates that all required receipts and artifacts exist on disk
        BEFORE allowing the Overgod to approve and advance past an interactive phase.
        Prevents accidental approval bypass.
        """
        phase_id = phase["id"]
        phase_name = f"Phase {phase_id}: {phase['name']}"

        # 1. Check circuit breakers first
        breakers = self.get_phase_breakers(phase)
        try:
            self.check_forbidden_paths(phase_name, breakers.get("forbidden_paths", []))
            self.check_blast_radius(phase_name, breakers.get("max_diff_lines", 250))
            self.check_code_traces(phase_name)
        except CircuitBreakerException as e:
            return False, f"Circuit breaker tripped: {e}"

        if str(phase_id) == "10":
            try:
                sys.path.insert(0, str(self.work_dir))
                from traps.triplet_gate import check_triplet
                ok, msg = check_triplet(str(self.work_dir))
                if not ok:
                    return False, msg
            except Exception as e:
                return False, f"Triplet gate execution failed: {e}"

        # 2. Check requires dependencies
        requires_patterns = phase.get("requires", [])
        for pat in requires_patterns:
            pattern = str(self.work_dir / pat)
            matches = glob.glob(pattern, recursive=True)
            non_empty = [m for m in matches if os.path.isfile(m) and os.path.getsize(m) > 0]
            if not non_empty:
                return False, f"Prerequisite artifact missing: No non-empty file matching '{pat}' found."

        # 3. Check produces artifacts if specified
        produces_patterns = phase.get("produces", [])
        for pat in produces_patterns:
            pattern = str(self.work_dir / pat)
            matches = glob.glob(pattern, recursive=True)
            non_empty = [m for m in matches if os.path.isfile(m) and os.path.getsize(m) > 0]
            if not non_empty:
                return False, f"Mandatory produced artifact missing: No non-empty file matching '{pat}' found."

        # 4. Check gate condition if not purely human_approval
        gate = phase.get("gate", {})
        gate_type = gate.get("type", "")
        if gate_type == "file_exists":
            target = gate.get("target")
            pattern = str(self.work_dir / target)
            matches = glob.glob(pattern, recursive=True)
            non_empty = [m for m in matches if os.path.isfile(m) and os.path.getsize(m) > 0]
            if not non_empty:
                return False, f"Physical gate unsatisfied: Missing file '{target}'."
        elif gate_type == "shell":
            cmd = self._resolve_command(gate.get("command", ""))
            expected = gate.get("expected_exit_code", 0)
            res = subprocess.run(cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if res.returncode != expected:
                return False, f"Gate command '{cmd}' failed (exit code {res.returncode}, expected {expected})."

        return True, "All physical receipts and prerequisites verified."

    def approve_current_phase(self) -> Tuple[bool, str]:
        """
        Approves the current interactive phase after validating physical receipts.
        Returns (success: bool, message: str).
        """
        idx = self.state["current_phase_idx"]
        if idx >= len(self.phases):
            return False, "All phases already completed."

        cur = self.phases[idx]
        valid, reason = self.validate_approval_prerequisites(cur)
        if not valid:
            self.state["status"] = "HALTED"
            self.state["last_halt_reason"] = f"Approval rejected on Phase {cur['id']}: {reason}"
            self.save_state()
            return False, reason

        log_progress(f"Phase {cur['id']}", "✍️", "Overgod approval granted and physical receipts verified.", Colors.GREEN)
        self.state["completed_phases"].append(cur["id"])
        self.state["current_phase_idx"] = idx + 1
        self.state["status"] = "RUNNING"
        self.state["last_halt_reason"] = None
        self.save_state()
        return True, "Approval granted and physical receipts verified."

    def run_step(self, auto_advance: bool = True) -> bool:
        """
        Executes or validates the current phase.
        Auto-advances if gate passes and interactive=False.
        Halts and alerts the Overgod if interactive=True or a circuit breaker trips.
        """
        idx = self.state["current_phase_idx"]
        if idx >= len(self.phases):
            log_progress("", "🏆", "All KEEPER phases completed successfully!", Colors.GREEN)
            self.state["status"] = "COMPLETED"
            self.save_state()
            return True

        phase = self.phases[idx]
        phase_id = phase["id"]
        phase_name = f"Phase {phase_id}: {phase['name']}"
        actor = phase.get("actor", "Subagent")
        interactive = phase.get("interactive", False)
        breakers = self.get_phase_breakers(phase)

        # 0. Conditional Phase Check
        should_run, skip_reason = self.should_execute_phase(phase)
        if not should_run:
            log_progress(phase_name, "⏭️", f"Conditional phase skipped: {skip_reason}", Colors.BLUE)
            self.state["completed_phases"].append(f"{phase_id} (skipped)")
            self.state["current_phase_idx"] = idx + 1
            self.save_state()
            if auto_advance:
                return self.run_step(auto_advance=True)
            return True

        # 1. Safety Checks (Circuit Breakers)
        try:
            self.check_forbidden_paths(phase_name, breakers.get("forbidden_paths", []))
            self.check_blast_radius(phase_name, breakers.get("max_diff_lines", 250))
            self.check_code_traces(phase_name)
        except CircuitBreakerException as e:
            self.record_violation(
                phase_id=phase_id,
                actor=actor,
                violation_type="CircuitBreakerException",
                detail=str(e),
                attempt=1,
            )
            self.state["status"] = "HALTED"
            self.state["last_halt_reason"] = str(e)
            self.save_state()
            print_dossier(
                phase_id=phase_id,
                phase_name=phase["name"],
                actor=actor,
                gate_status="CIRCUIT BREAKER TRIPPED",
                evidence=str(e),
                action_required="HALT: Architectural violation. Inspect tree and resolve before proceeding.",
                is_halt=True,
                violations=self.state.get("protocol_violations"),
            )
            return False

        # 2. Interactive Human Gate Handling
        if interactive:
            prompt_text = phase.get("gate", {}).get("prompt", phase.get("prompt", "Approval required."))
            print_dossier(
                phase_id=phase_id,
                phase_name=phase["name"],
                actor=actor,
                gate_status="READY FOR OVERGOD REVIEW",
                evidence="Preconditions verified. Awaiting explicit Overgod sign-off.",
                action_required=f"ACTION REQUIRED: {prompt_text}",
                is_halt=False,
            )
            return True

        # 3. Automated Physical Receipt Evaluation
        log_progress(phase_name, "🔍", f"Evaluating physical receipt gates...")
        passed, evidence = self.evaluate_gate(phase)

        phase_key = str(phase_id)
        attempts = self.state["attempt_counts"].get(phase_key, 0)

        if not passed:
            attempts += 1
            self.state["attempt_counts"][phase_key] = attempts
            max_attempts = breakers.get("max_attempts", 3)

            if attempts >= max_attempts:
                self.state["status"] = "HALTED"
                self.state["last_halt_reason"] = f"Strike {attempts} reached on {phase_name}"
                self.save_state()
                print_dossier(
                    phase_id=phase_id,
                    phase_name=phase["name"],
                    actor=actor,
                    gate_status=f"STRIKE {attempts} (RETRY LIMIT EXCEEDED)",
                    evidence=evidence,
                    action_required=f"HALT: Subagent failed {attempts} consecutive attempts. Overgod intervention required.",
                    is_halt=True,
                )
                return False
            else:
                log_progress(
                    phase_name,
                    "⚠️",
                    f"Gate check failed (Attempt {attempts}/{max_attempts}). Reason: {evidence.splitlines()[0]}",
                    Colors.YELLOW,
                )
                self.save_state()
                return False

        # 4. Gate Passed -> Silent Auto-Advance
        log_progress(phase_name, "✅", f"Gate verified! {evidence}", Colors.GREEN)
        self.state["completed_phases"].append(phase_id)
        self.state["attempt_counts"][phase_key] = 0

        if auto_advance:
            next_idx = idx + 1
            self.state["current_phase_idx"] = next_idx
            self.save_state()
            if next_idx < len(self.phases):
                next_p = self.phases[next_idx]
                log_progress(phase_name, "⏩", f"Auto-advancing to Phase {next_p['id']} ({next_p['name']})...")
                # If next is non-interactive, advance recursively or prompt next
                if not next_p.get("interactive", False):
                    return self.run_step(auto_advance=auto_advance)
                else:
                    return self.run_step(auto_advance=False)
            else:
                return self.run_step(auto_advance=False)

        return True

    def materialize_phase_prompt(
        self, phase: Dict[str, Any], error_feedback: Optional[str] = None
    ) -> Tuple[Path, str]:
        """
        Materializes a disk-grounded prompt packet for the subagent phase.
        Writes to .keeper/prompts/phase_<id>_<actor_slug>.md and .keeper/active_phase_prompt.md.
        Records SHA-256 hash in state.
        """
        phase_id = phase["id"]
        phase_name = phase["name"]
        actor = phase.get("actor", "Subagent")
        actor_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", actor.lower()).strip("_")

        # 1. Resolve system prompt
        sys_prompt_file = phase.get("system_prompt")
        system_prompt_path_str = ""
        system_instructions = ""
        if sys_prompt_file:
            candidates = [
                self.work_dir / sys_prompt_file,
                self.work_dir / "codex" / "prompts" / Path(sys_prompt_file).name,
                self.work_dir / ".antigravity" / "prompts" / Path(sys_prompt_file).name,
            ]
            for c in candidates:
                if c.exists():
                    system_instructions = c.read_text(encoding="utf-8")
                    system_prompt_path_str = str(c.relative_to(self.work_dir) if c.is_relative_to(self.work_dir) else c)
                    break

        if not system_prompt_path_str and sys_prompt_file:
            system_prompt_path_str = str(sys_prompt_file)

        # 2. Build task prompt packet
        prompt_parts = [
            f"# Project KEEPER: Phase {phase_id} ({phase_name})",
            f"**Assigned Actor**: {actor}",
            f"**Workspace**: `{self.work_dir}`",
        ]

        if system_prompt_path_str:
            prompt_parts.append(f"**Role Constitution File**: `{system_prompt_path_str}`")

        active_task_path = self.work_dir / ".keeper" / "active_task.md"
        if active_task_path.exists():
            prompt_parts.append(f"**Task Specification**: `.keeper/active_task.md`")

        if phase.get("prompt"):
            prompt_parts.append(f"**Directive**: {phase['prompt']}")

        if phase.get("requires"):
            prompt_parts.append(f"**Input Dependencies**: {', '.join(phase['requires'])}")

        if phase.get("produces"):
            prompt_parts.append(f"**Target Outputs**: {', '.join(phase['produces'])}")

        breakers = self.get_phase_breakers(phase)
        forbidden = breakers.get("forbidden_paths")
        if forbidden:
            prompt_parts.append(
                f"⛔ **FORBIDDEN PATHS**: You are STRICTLY PROHIBITED from modifying or creating files matching:\n"
                + "\n".join(f"  - `{p}`" for p in forbidden)
            )

        gate = phase.get("gate", {})
        gate_type = gate.get("type", "shell")
        if gate_type == "gate_a":
            prompt_parts.append(
                "🎯 **Gate A Trap Mandate**: Write a hostile test that COMPORTS with the codebase (builds with exit code 0) "
                "AND MUST FAIL on the current unmodified code (exit non-zero) to prove defect sensitivity. "
                "Do NOT fix or touch production code."
            )
        elif gate_type == "gate_b":
            prompt_parts.append(
                "🎯 **Gate B Verification Mandate**: Implement the logic so that the build succeeds AND all tests pass (exit code 0)."
            )
        elif gate_type == "file_exists":
            prompt_parts.append(f"🎯 **Receipt Mandate**: Create the required physical artifact: `{gate.get('target')}`")
        elif gate_type == "shell":
            prompt_parts.append(f"🎯 **Receipt Mandate**: Fulfill condition checked by command: `{gate.get('command')}`")

        if error_feedback:
            prompt_parts.append(
                f"\n⚠️ **PREVIOUS ATTEMPT FAILED WITH PHYSICAL RECEIPT REJECTION**:\n"
                f"```\n{error_feedback}\n```\n"
                f"Inspect the exact compiler/test failure above, locate the flaw, and fix it."
            )

        task_prompt = "\n\n".join(prompt_parts)

        # 3. Write disk artifacts
        prompts_dir = self.work_dir / ".keeper" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        phase_prompt_path = prompts_dir / f"phase_{phase_id}_{actor_slug}.md"
        phase_prompt_path.write_text(task_prompt, encoding="utf-8")

        active_phase_prompt_path = self.work_dir / ".keeper" / "active_phase_prompt.md"
        active_phase_prompt_path.parent.mkdir(parents=True, exist_ok=True)
        active_phase_prompt_path.write_text(task_prompt, encoding="utf-8")

        # 4. Compute SHA-256 and save in state
        sha256_hash = hashlib.sha256(task_prompt.encode("utf-8")).hexdigest()
        try:
            rel_path_str = str(phase_prompt_path.relative_to(self.work_dir))
        except ValueError:
            rel_path_str = str(phase_prompt_path)

        self.state["last_dispatched_prompt"] = {
            "phase_id": phase_id,
            "actor": actor,
            "prompt_path": rel_path_str,
            "sha256": sha256_hash,
        }
        self.save_state()

        return phase_prompt_path, task_prompt

    async def dispatch_phase_worker(
        self, phase: Dict[str, Any], error_feedback: Optional[str] = None
    ) -> bool:
        """
        Dispatches an autonomous Antigravity subagent strictly scoped to this phase.
        Loads the specific role system prompt (e.g. trapsmith_system.md) and task prompt.
        """
        if not ANTIGRAVITY_AVAILABLE:
            raise RuntimeError(
                "Antigravity SDK (google-antigravity) is not installed in the environment."
            )

        phase_id = phase["id"]
        actor = phase.get("actor", "Subagent")

        # Materialize prompt on disk
        prompt_path, task_prompt = self.materialize_phase_prompt(phase, error_feedback=error_feedback)

        # Resolve system instructions
        sys_prompt_file = phase.get("system_prompt")
        system_instructions = ""
        if sys_prompt_file:
            candidates = [
                self.work_dir / sys_prompt_file,
                self.work_dir / "codex" / "prompts" / Path(sys_prompt_file).name,
                self.work_dir / ".antigravity" / "prompts" / Path(sys_prompt_file).name,
            ]
            for c in candidates:
                if c.exists():
                    system_instructions = c.read_text(encoding="utf-8")
                    break

        if not system_instructions:
            system_instructions = (
                f"You are {actor} in Project KEEPER. You must strictly execute your designated phase mandate."
            )

        log_progress(f"Phase {phase_id}", "🤖", f"Spawning {actor} via Antigravity SDK...")

        policies = []
        if ANTIGRAVITY_AVAILABLE and "policy" in globals() and hasattr(policy, "allow_all"):
            policies = [policy.allow_all()]

        config = LocalAgentConfig(
            system_instructions=system_instructions,
            capabilities=CapabilitiesConfig(),
            policies=policies,
        )

        async with Agent(config) as agent:
            response = await agent.chat(task_prompt)
            async for token in response:
                sys.stdout.write(token)
                sys.stdout.flush()
            print()

        return True

    def run_drive(self, target_phase_id: Optional[Any] = None) -> bool:
        """
        Autonomously drives the KEEPER workflow using Antigravity workers.
        - Stops at interactive gates for Overgod review.
        - Spawns worker agents with isolated prompts for automated phases.
        - Evaluates circuit breakers (blast radius, forbidden paths) and gates.
        - Automatically feeds compiler/test failures back into retry attempts.
        - Commits verified milestones and auto-advances.
        """
        while True:
            idx = self.state["current_phase_idx"]
            if idx >= len(self.phases):
                log_progress("", "🏆", "All KEEPER phases completed successfully!", Colors.GREEN)
                self.state["status"] = "COMPLETED"
                self.save_state()
                return True

            phase = self.phases[idx]
            phase_id = str(phase["id"])
            phase_name = f"Phase {phase['id']}: {phase['name']}"
            actor = phase.get("actor", "Subagent")
            interactive = phase.get("interactive", False)
            breakers = self.get_phase_breakers(phase)

            # If user targeted a specific phase
            if target_phase_id is not None and str(target_phase_id) != phase_id:
                found_idx = None
                for i, p in enumerate(self.phases):
                    if str(p["id"]) == str(target_phase_id):
                        found_idx = i
                        break
                if found_idx is None:
                    print(f"{Colors.RED}Target phase {target_phase_id} not found.{Colors.RESET}")
                    return False
                self.state["current_phase_idx"] = found_idx
                self.save_state()
                continue

            # 0. Conditional Phase Check
            should_run, skip_reason = self.should_execute_phase(phase)
            if not should_run:
                log_progress(phase_name, "⏭️", f"Conditional phase skipped: {skip_reason}", Colors.BLUE)
                self.state["completed_phases"].append(f"{phase['id']} (skipped)")
                self.state["current_phase_idx"] = idx + 1
                self.save_state()
                if target_phase_id is not None and str(target_phase_id) == phase_id:
                    return True
                continue

            # 1. Interactive Overgod Gate
            if interactive:
                prompt_text = phase.get("gate", {}).get("prompt", phase.get("prompt", "Approval required."))
                print_dossier(
                    phase_id=phase["id"],
                    phase_name=phase["name"],
                    actor=actor,
                    gate_status="AWAITING OVERGOD APPROVAL",
                    evidence="Phase requires explicit human architectural review.",
                    action_required=f"ACTION REQUIRED: {prompt_text}\n(Run `./keeper --approve` to ratify and advance)",
                    is_halt=False,
                )
                return True

            # 2. Automated Phase Worker Loop
            max_attempts = breakers.get("max_attempts", 3)
            phase_key = str(phase["id"])
            attempts = self.state["attempt_counts"].get(phase_key, 0)
            error_feedback = None

            while attempts < max_attempts:
                attempts += 1
                self.state["attempt_counts"][phase_key] = attempts
                self.save_state()

                log_progress(
                    phase_name,
                    "🚀",
                    f"Dispatching worker {actor} (Attempt {attempts}/{max_attempts})...",
                    Colors.YELLOW,
                )

                pre_head = self._get_git_head()

                # Dispatch worker
                try:
                    asyncio.run(self.dispatch_phase_worker(phase, error_feedback=error_feedback))
                except Exception as e:
                    log_progress(phase_name, "❌", f"Worker execution error: {e}", Colors.RED)
                    error_feedback = f"Worker runtime exception: {e}"

                # Unpack any unauthorized git commits made by the worker so Scope Guard can inspect them
                post_head = self._get_git_head()
                if pre_head and post_head and pre_head != post_head:
                    subprocess.run(
                        ["git", "reset", "--soft", pre_head],
                        cwd=self.work_dir,
                        capture_output=True,
                    )

                # Check Circuit Breakers
                circuit_tripped = False
                try:
                    self.check_forbidden_paths(phase_name, breakers.get("forbidden_paths", []))
                    self.check_blast_radius(phase_name, breakers.get("max_diff_lines", 250))
                    self.check_code_traces(phase_name)
                except CircuitBreakerException as cb_err:
                    circuit_tripped = True
                    self.record_violation(
                        phase_id=phase["id"],
                        actor=actor,
                        violation_type="CircuitBreakerException",
                        detail=str(cb_err),
                        attempt=attempts,
                    )
                    log_progress(phase_name, "🛑", f"Circuit Breaker Tripped! {cb_err}", Colors.RED)
                    # Revert tracked, staged, and untracked modifications to prevent bad state from compounding
                    self._rollback_working_tree(pre_head)
                    error_feedback = (
                        f"CIRCUIT BREAKER VIOLATION: {cb_err}\n"
                        f"You touched forbidden paths or exceeded diff lines. Reverted changes."
                    )

                if circuit_tripped:
                    if attempts >= max_attempts:
                        break
                    continue

                # Evaluate Gate
                log_progress(phase_name, "🔍", "Evaluating physical receipt gates...")
                passed, evidence = self.evaluate_gate(phase)

                if passed:
                    log_progress(phase_name, "✅", f"Gate verified! {evidence}", Colors.GREEN)
                    self.state["completed_phases"].append(phase["id"])
                    self.state["attempt_counts"][phase_key] = 0
                    self.state["current_phase_idx"] = idx + 1
                    self.save_state()

                    # Commit milestone if git repo is dirty
                    status_res = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=self.work_dir,
                        capture_output=True,
                        text=True,
                    )
                    if status_res.stdout.strip():
                        subprocess.run(["git", "add", "-A"], cwd=self.work_dir)
                        subprocess.run(
                            [
                                "git",
                                "commit",
                                "-m",
                                f"KEEPER: Phase {phase['id']} ({phase['name']}) verified",
                            ],
                            cwd=self.work_dir,
                        )
                        log_progress(phase_name, "📦", f"Committed verified milestone for Phase {phase['id']}.")

                    if target_phase_id is not None:
                        return True
                    break
                else:
                    log_progress(
                        phase_name,
                        "⚠️",
                        f"Gate check failed (Attempt {attempts}/{max_attempts}): {evidence.splitlines()[0]}",
                        Colors.YELLOW,
                    )
                    error_feedback = evidence

            # If loop finished without passing
            if self.state["attempt_counts"].get(phase_key, 0) >= max_attempts:
                self.state["status"] = "HALTED"
                self.state["last_halt_reason"] = f"Strike {max_attempts} reached on {phase_name}"
                self.save_state()
                print_dossier(
                    phase_id=phase["id"],
                    phase_name=phase["name"],
                    actor=actor,
                    gate_status=f"STRIKE {max_attempts} (RETRY LIMIT EXCEEDED)",
                    evidence=error_feedback or "Unknown error",
                    action_required=f"HALT: Subagent failed {max_attempts} consecutive attempts. Overgod intervention required.",
                    is_halt=True,
                )
                return False

    def print_status(self):
        """Prints the current state and execution graph."""
        idx = self.state["current_phase_idx"]
        status = self.state["status"]
        mode_label = "The Inspection (Audit & Health Check)" if self.workflow == "audit" else "The Forge (Feature & Defect)"
        print(f"\n{Colors.BOLD}Project KEEPER Operational Status [{mode_label}]:{Colors.RESET}")
        print(f"Status: {status} | Progress: {idx}/{len(self.phases)} phases completed\n")

        for i, p in enumerate(self.phases):
            p_id = p["id"]
            name = p["name"]
            actor = p.get("actor", "Agent")
            inter = "👤 Interactive" if p.get("interactive") else "🤖 Automated"

            if i < idx:
                mark = f"{Colors.GREEN}✔ [COMPLETED]{Colors.RESET}"
            elif i == idx:
                mark = f"{Colors.YELLOW}▶ [ACTIVE]   {Colors.RESET}"
            else:
                mark = "  [PENDING]  "

            print(f"  {mark} Phase {p_id:>12}: {name:<36} ({actor:<22} | {inter})")

        if self.state.get("last_halt_reason"):
            print(f"\n{Colors.RED}Last Halt Reason: {self.state['last_halt_reason']}{Colors.RESET}")

        violations = self.state.get("protocol_violations", [])
        if violations:
            print(f"\n{Colors.RED}🚨 PROTOCOL VIOLATION LEDGER ({len(violations)} breached containment):{Colors.RESET}")
            for v in violations:
                p_id = v.get("phase_id", "?")
                act = v.get("actor", "Unknown")
                det = v.get("detail", "")
                att = v.get("attempt", 1)
                print(f"  - [Phase {p_id} | {act} | Att {att}]: {det}")
        print()


def main():
    # If running directly from CLI and not in venv, auto-reexec inside venv if present
    script_dir = Path(__file__).resolve().parent
    venv_python = script_dir / "venv" / "bin" / "python3"
    if not ANTIGRAVITY_AVAILABLE and venv_python.exists() and sys.executable != str(venv_python):
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

    parser = argparse.ArgumentParser(description="Project KEEPER Deterministic State Machine Runner")
    parser.add_argument("--config", default="keeper.yaml", help="Path to keeper.yaml")
    parser.add_argument("--status", action="store_true", help="Print current status and exit")
    parser.add_argument("--reset", action="store_true", help="Reset state machine to initial phase")
    parser.add_argument("--dry-run", action="store_true", help="Validate workflow graph and exit")
    parser.add_argument("--approve", action="store_true", help="Approve current interactive checkpoint and advance")
    parser.add_argument("--drive", action="store_true", help="Autonomously drive phases using Antigravity SDK")
    parser.add_argument("--phase", type=str, default=None, help="Execute autonomous driver specifically for a given phase ID")
    parser.add_argument("--audit", action="store_true", help="Run the automated Inspection / General Health Audit gauntlet")
    parser.add_argument("--milestone", action="store_true", help="Activate milestone-only conditional phases (e.g. Phase 8.6 The Censor)")
    parser.add_argument("--defect-escape", action="store_true", help="Activate post-mortem defect inquest phases (e.g. Phase 11 The Coroner)")
    parser.add_argument("--strict", action="store_true", help="Enforce strict verification gates without fallback")
    parser.add_argument("--audit-prompts", action="store_true", help="Audit subagent prompts and codex for executable trace compliance")
    args = parser.parse_args()

    if args.audit_prompts:
        from traps.prompt_trace_auditor import audit_repository_prompts, format_markdown_report
        work_dir = Path(".").resolve()
        report = audit_repository_prompts(work_dir)
        md_text = format_markdown_report(report)
        print(md_text)
        out_json = work_dir / ".keeper" / "prompt_trace_report.json"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        sys.exit(0)

    workflow = "audit" if args.audit else "feature"
    try:
        runner = KeeperRunner(
            config_path=args.config,
            workflow=workflow,
            is_milestone=args.milestone,
            is_defect_escape=args.defect_escape,
            strict=args.strict,
        )
    except FileNotFoundError as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)

    if args.reset:
        runner.reset_state()
        return

    if args.status:
        runner.print_status()
        return

    if args.dry_run:
        print(f"{Colors.GREEN}✅ Validated {len(runner.phases)} phases in {runner.config_path}{Colors.RESET}")
        runner.print_status()
        return

    if args.approve:
        idx = runner.state["current_phase_idx"]
        if idx < len(runner.phases):
            cur = runner.phases[idx]
            ok, msg = runner.approve_current_phase()
            if not ok:
                print_dossier(
                    phase_id=cur["id"],
                    phase_name=cur["name"],
                    actor=cur.get("actor", "The Overgod"),
                    gate_status="APPROVAL REJECTED: PHYSICAL RECEIPT MISSING",
                    evidence=msg,
                    action_required=f"Cannot approve Phase {cur['id']}. Satisfy required physical receipts before approving.",
                    is_halt=True,
                )
                sys.exit(1)

            if args.drive:
                runner.run_drive()
            else:
                runner.run_step(auto_advance=True)
        return

    if args.drive or args.phase is not None:
        runner.run_drive(target_phase_id=args.phase)
        return

    runner.run_step(auto_advance=True)


if __name__ == "__main__":
    main()
