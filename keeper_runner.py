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
    def __init__(self, config_path: str = "keeper.yaml", work_dir: str = ".", workflow: str = "feature"):
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
        build_match = re.search(r"\*\*Build Command\*\*:\s*`([^`]+)`", text)
        if build_match:
            self.config_vars["build_cmd"] = build_match.group(1).strip()

        test_match = re.search(r"\*\*Unit Test Command\*\*:\s*`([^`]+)`", text)
        if test_match:
            self.config_vars["test_cmd"] = test_match.group(1).strip()

        asan_match = re.search(r"ASan\+UBSan Command:\s*`([^`]+)`", text)
        if asan_match:
            self.config_vars["sanitizer_cmd"] = asan_match.group(1).strip()

        fuzz_match = re.search(r"\*\*Fuzz(?:ing)? Command\*\*:\s*`([^`]+)`", text)
        if fuzz_match:
            self.config_vars["fuzz_cmd"] = fuzz_match.group(1).strip()

    def _load_state(self) -> Dict[str, Any]:
        """Loads state from configured state file or initializes default state."""
        state_path = self.work_dir / self.state_file
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
        """Persists state to configured state file."""
        state_path = self.work_dir / self.state_file
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def reset_state(self):
        """Resets the state machine back to initial phase."""
        self.state = {
            "current_phase_idx": 0,
            "completed_phases": [],
            "attempt_counts": {},
            "status": "RUNNING",
            "last_halt_reason": None,
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
        phase_name = phase["name"]
        actor = phase.get("actor", "Subagent")

        # 1. Resolve system prompt
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

        # 2. Construct constrained task prompt
        prompt_parts = [
            f"# Project KEEPER: Phase {phase_id} ({phase_name})",
            f"**Assigned Actor**: {actor}",
            f"**Workspace**: `{self.work_dir}`",
        ]

        if phase.get("prompt"):
            prompt_parts.append(f"**Directive**: {phase['prompt']}")

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

        log_progress(f"Phase {phase_id}", "🤖", f"Spawning {actor} via Antigravity SDK...")

        config = LocalAgentConfig(
            system_instructions=system_instructions,
            capabilities=CapabilitiesConfig(),
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

                # Dispatch worker
                try:
                    asyncio.run(self.dispatch_phase_worker(phase, error_feedback=error_feedback))
                except Exception as e:
                    log_progress(phase_name, "❌", f"Worker execution error: {e}", Colors.RED)
                    error_feedback = f"Worker runtime exception: {e}"

                # Check Circuit Breakers
                circuit_tripped = False
                try:
                    self.check_forbidden_paths(phase_name, breakers.get("forbidden_paths", []))
                    self.check_blast_radius(phase_name, breakers.get("max_diff_lines", 250))
                except CircuitBreakerException as cb_err:
                    circuit_tripped = True
                    log_progress(phase_name, "🛑", f"Circuit Breaker Tripped! {cb_err}", Colors.RED)
                    # Revert modifications to prevent bad state from compounding
                    subprocess.run(["git", "restore", "."], cwd=self.work_dir)
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
    args = parser.parse_args()

    workflow = "audit" if args.audit else "feature"
    try:
        runner = KeeperRunner(config_path=args.config, workflow=workflow)
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
