#!/usr/bin/env python3
"""
Project KEEPER Operational State Machine Runner (keeper_runner.py)
==================================================================
Deterministic, neuro-symbolic workflow runner for Project KEEPER.
Enforces physical receipt gates and ironclad circuit breakers.
Zero-bother execution: auto-advances on green; halts hard on red.
"""

import argparse
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

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
    print(f"  ------------------------------------------------------------------")
    print(f"  👁️  Overgod Action:  {action_required}")
    print(f"{color}{sep}{Colors.RESET}\n")


class CircuitBreakerException(Exception):
    """Raised when an ironclad safety circuit breaker trips."""
    pass


class KeeperRunner:
    def __init__(self, config_path: str = "keeper.yaml", work_dir: str = "."):
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

        self.global_breakers = self.spec.get("circuit_breakers", {})
        self.config_vars = self.spec.get("config", {})
        self._load_keeper_config_overrides()

        self.phases = self.spec.get("phases", [])
        self.state = self._load_state()

    def _load_keeper_config_overrides(self):
        """Loads project-specific commands from KEEPER_CONFIG.md if present."""
        cfg_file = self.work_dir / "KEEPER_CONFIG.md"
        if not cfg_file.exists():
            return

        text = cfg_file.read_text(encoding="utf-8")
        build_match = re.search(r"\*\*Build Command\*\*:\s*`([^`]+)`", text)
        if build_match:
            self.config_vars["build_cmd"] = build_match.group(1).strip()

        test_match = re.search(r"\*\*Unit Test Command\*\*:\s*`([^`]+)`", text)
        if test_match:
            self.config_vars["test_cmd"] = test_match.group(1).strip()

        asan_match = re.search(r"ASan\+UBSan Command:\s*`([^`]+)`", text)
        if asan_match:
            self.config_vars["sanitizer_cmd"] = asan_match.group(1).strip()

    def _load_state(self) -> Dict[str, Any]:
        """Loads state from .keeper/state.json or initializes default state."""
        state_path = self.work_dir / STATE_FILE
        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "current_phase_idx": 0,
            "completed_phases": [],
            "attempt_counts": {},
            "status": "RUNNING",
            "last_halt_reason": None,
        }

    def save_state(self):
        """Persists state to .keeper/state.json."""
        state_dir = self.work_dir / ".keeper"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / "state.json", "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def reset_state(self):
        """Resets the state machine back to Phase 1."""
        self.state = {
            "current_phase_idx": 0,
            "completed_phases": [],
            "attempt_counts": {},
            "status": "RUNNING",
            "last_halt_reason": None,
        }
        self.save_state()
        log_progress("", "🔄", "State machine reset to Phase 1.", Colors.GREEN)

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
        """Asserts that no modified or staged files match forbidden path patterns."""
        if not forbidden_patterns:
            return

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
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
                    if fnmatch.fnmatch(file_path, clean_pat) or fnmatch.fnmatch(
                        file_path, f"*/{clean_pat}"
                    ):
                        raise CircuitBreakerException(
                            f"Scope Guard Violation! Subagent touched forbidden path: {file_path} (Matches pattern: {pat})"
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
                return False, f"Compilation failed for Gate A test.\nStderr:\n{b_res.stderr[:300]}"

            log_progress(phase_name, "🎯", f"Running Gate A defect reproduction trap: {run_cmd}")
            r_res = subprocess.run(run_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)

            if r_res.returncode == 0:
                return False, "Ghost Test Detected! Gate A requires the test to FAIL on current code, but it passed."
            if r_res.returncode != expected_exit and expected_exit != -1:
                return True, f"Defect caught! Test failed with returncode {r_res.returncode} (Gate A certified)."
            return True, f"Defect caught! Test returned expected code {r_res.returncode}."

        elif gate_type == "gate_b":
            # Gate B: MUST build (0) AND test MUST PASS (0) on refactored code
            build_cmd = self._resolve_command(gate.get("build_command", ""))
            run_cmd = self._resolve_command(gate.get("run_command", ""))

            log_progress(phase_name, "🔨", f"Building implementation: {build_cmd}")
            b_res = subprocess.run(build_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if b_res.returncode != 0:
                return False, f"Compilation failed for Gate B implementation.\nStderr:\n{b_res.stderr[:300]}"

            log_progress(phase_name, "🎯", f"Running Gate B regression suite: {run_cmd}")
            r_res = subprocess.run(run_cmd, shell=True, cwd=self.work_dir, capture_output=True, text=True)
            if r_res.returncode == 0:
                return True, "Gate B Certified: Code builds and all tests pass with exit code 0."
            return False, f"Gate B Failed: Tests failed with exit code {r_res.returncode}.\nOutput:\n{r_res.stdout[-300:]}"

        elif gate_type == "human_approval":
            return True, "Awaiting Overgod interactive input."

        return False, f"Unknown gate type: {gate_type}"

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

        # 1. Safety Checks (Circuit Breakers)
        try:
            self.check_forbidden_paths(phase_name, breakers.get("forbidden_paths", []))
            self.check_blast_radius(phase_name, breakers.get("max_diff_lines", 250))
        except CircuitBreakerException as e:
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

    def print_status(self):
        """Prints the current state and execution graph."""
        idx = self.state["current_phase_idx"]
        status = self.state["status"]
        print(f"\n{Colors.BOLD}Project KEEPER Operational Status:{Colors.RESET}")
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

            print(f"  {mark} Phase {p_id:4}: {name:<32} ({actor:<22} | {inter})")

        if self.state.get("last_halt_reason"):
            print(f"\n{Colors.RED}Last Halt Reason: {self.state['last_halt_reason']}{Colors.RESET}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Project KEEPER Deterministic State Machine Runner")
    parser.add_argument("--config", default="keeper.yaml", help="Path to keeper.yaml")
    parser.add_argument("--status", action="store_true", help="Print current status and exit")
    parser.add_argument("--reset", action="store_true", help="Reset state machine to Phase 1")
    parser.add_argument("--dry-run", action="store_true", help="Validate workflow graph and exit")
    parser.add_argument("--approve", action="store_true", help="Approve current interactive checkpoint and advance")
    args = parser.parse_args()

    try:
        runner = KeeperRunner(config_path=args.config)
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
            log_progress(f"Phase {cur['id']}", "✍️", "Overgod approval granted.", Colors.GREEN)
            runner.state["completed_phases"].append(cur["id"])
            runner.state["current_phase_idx"] = idx + 1
            runner.state["status"] = "RUNNING"
            runner.state["last_halt_reason"] = None
            runner.save_state()
            runner.run_step(auto_advance=True)
        return

    runner.run_step(auto_advance=True)


if __name__ == "__main__":
    main()
