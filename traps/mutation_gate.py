#!/usr/bin/env python3
# ==============================================================================
# THE MIMIC: Dual-Gate Mutation Testing Auditor
# ==============================================================================
# Gate A (Pre-Flight): Audits The Trapsmith's tests against mutated baseline code.
#                      Rejects ghost tests if the mutant survives.
# Gate B (Post-Flight): Audits The Artificer's implementation against mutated new code.
#                       Rejects refactoring if invariants were bypassed.
# ==============================================================================

import argparse
import glob
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_THRESHOLD_SCORE = 80.0

# Supported mutation patterns: (regex_search, replacement, description)
MUTATION_OPERATORS = [
    (r"(?<![=!<>])==(?![=])", "!=", "Invert equality operator (== -> !=)"),
    (r"(?<![=!<>])!=(?![=])", "==", "Invert inequality operator (!= -> ==)"),
    (r" <= ", " > ", "Invert boundary check (<= -> >)"),
    (r" >= ", " < ", "Invert boundary check (>= -> <)"),
    (r"(?<![-+<>=]) < (?![=])", " >= ", "Invert comparison operator (< -> >=)"),
    (r"(?<![-+<>=]) > (?![=])", " <= ", "Invert comparison operator (> -> <=)"),
    (r" && ", " || ", "Invert logical AND to OR (&& -> ||)"),
    (r" \|\| ", " && ", "Invert logical OR to AND (|| -> &&)"),
    (r" \+ ", " - ", "Invert addition to subtraction (+ -> -)"),
    (r" - ", " + ", "Invert subtraction to addition (- -> +)"),
    (r"\btrue\b", "false", "Invert boolean literal (true -> false)"),
    (r"\bfalse\b", "true", "Invert boolean literal (false -> true)"),
    (r"return\s+0;", "return 1;", "Mutate return zero to return one"),
    (r"return\s+true;", "return false;", "Mutate return true to return false"),
    (r"return\s+false;", "return true;", "Mutate return false to return true"),
]


class Mutant:
    def __init__(self, file_path: Path, line_index: int, original_line: str, mutated_line: str, description: str):
        self.file_path = file_path
        self.line_index = line_index
        self.original_line = original_line
        self.mutated_line = mutated_line
        self.description = description
        self.status = "PENDING"  # KILLED, SURVIVED, STILLBORN (compile fail)
        self.details = ""


def resolve_config_commands(work_dir: Path) -> Tuple[str, str]:
    """Resolves build and test commands from KEEPER_CONFIG.md, keeper.yaml, or defaults."""
    build_cmd = ""
    test_cmd = ""

    # Check KEEPER_CONFIG.md
    cfg_file = work_dir / "KEEPER_CONFIG.md"
    if cfg_file.exists():
        text = cfg_file.read_text(encoding="utf-8")
        b_m = re.search(r"\*\*Build Command\*\*:\s*`([^`]+)`", text)
        if b_m:
            build_cmd = b_m.group(1).strip()
        t_m = re.search(r"\*\*Unit Test Command\*\*:\s*`([^`]+)`", text)
        if t_m:
            test_cmd = t_m.group(1).strip()

    # Check keeper.yaml fallback
    if not build_cmd or not test_cmd:
        candidates = [work_dir / "keeper.yaml", work_dir / "codex" / "keeper.yaml"]
        for c in candidates:
            if c.exists():
                try:
                    import yaml
                    with open(c, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    cfg = data.get("config", {})
                    if not build_cmd:
                        build_cmd = cfg.get("build_cmd", "")
                    if not test_cmd:
                        test_cmd = cfg.get("test_cmd", "")
                except Exception:
                    pass
                break

    return build_cmd, test_cmd


def find_target_files(work_dir: Path, target_dir: Optional[str] = None) -> List[Path]:
    """Discovers source files eligible for mutation testing."""
    if target_dir:
        base = work_dir / target_dir
        if base.is_file():
            return [base]
        patterns = ["**/*.cpp", "**/*.cc", "**/*.c", "**/*.hpp", "**/*.h"]
        files = []
        for pat in patterns:
            files.extend(base.glob(pat))
        return [f for f in files if f.is_file()]

    # First preference: files modified in git diff
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        git_files = [
            work_dir / line.strip()
            for line in res.stdout.splitlines()
            if line.strip() and line.strip().startswith("src/")
        ]
        valid_git = [f for f in git_files if f.is_file() and f.suffix in [".cpp", ".cc", ".c", ".hpp", ".h"]]
        if valid_git:
            return valid_git
    except Exception:
        pass

    # Fallback to all files under src/
    src_dir = work_dir / "src"
    if src_dir.exists():
        patterns = ["**/*.cpp", "**/*.cc", "**/*.c", "**/*.hpp", "**/*.h"]
        found = []
        for pat in patterns:
            found.extend(src_dir.glob(pat))
        return [f for f in found if f.is_file()]

    return []


def generate_mutants(target_files: List[Path], max_mutants: int = 15) -> List[Mutant]:
    """Scans target files and generates candidate mutations."""
    mutants: List[Mutant] = []

    for file_path in target_files:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except Exception:
            continue

        for i, line in enumerate(lines):
            # Skip comments and preprocessor lines
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("#"):
                continue

            for pattern, replacement, desc in MUTATION_OPERATORS:
                if re.search(pattern, line):
                    mutated = re.sub(pattern, replacement, line, count=1)
                    if mutated != line:
                        mutants.append(
                            Mutant(
                                file_path=file_path,
                                line_index=i,
                                original_line=line,
                                mutated_line=mutated,
                                description=f"{desc} in {file_path.name}:{i + 1}",
                            )
                        )
                        if len(mutants) >= max_mutants:
                            return mutants

    return mutants


class FileRestorer:
    """Context manager to guarantee files are restored."""
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.original_content = file_path.read_bytes()

    def restore(self):
        try:
            self.file_path.write_bytes(self.original_content)
        except Exception as e:
            sys.stderr.write(f"CRITICAL: Failed to restore {self.file_path}: {e}\n")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore()


def run_mutation_engine(
    stage: str,
    work_dir: Path,
    build_cmd: str,
    test_cmd: str,
    threshold: float = DEFAULT_THRESHOLD_SCORE,
    target_dir: Optional[str] = None,
    max_mutants: int = 10,
    timeout_sec: int = 30,
    strict: bool = False,
) -> int:
    """Executes the mutation testing gauntlet."""
    print(f"==> [The Mimic: {stage.upper()}] Initializing Mutation Testing Audit...")
    print(f"[*] Target Directory: {target_dir or 'src/'}")
    print(f"[*] Build Command:    {build_cmd or '(none)'}")
    print(f"[*] Test Command:     {test_cmd or '(none)'}")
    print(f"[*] Kill Threshold:   {threshold:.1f}%")

    target_files = find_target_files(work_dir, target_dir)
    if not target_files:
        if strict:
            print(f"[FAIL] The Mimic: No source files found for mutation testing.")
            return 1
        print(f"[*] The Mimic: No source files found to mutate in {work_dir / (target_dir or 'src')}.")
        print("[PASS] The Mimic: Skipped (no source files found).")
        return 0

    mutants = generate_mutants(target_files, max_mutants=max_mutants)
    if not mutants:
        print(f"[*] The Mimic: No mutable operators found in {len(target_files)} target file(s).")
        print("[PASS] The Mimic: Clean audit pass (no mutable tokens detected).")
        return 0

    print(f"[*] Generated {len(mutants)} candidate mutant(s) across {len(target_files)} file(s).\n")

    if not build_cmd or not test_cmd:
        if strict:
            print("[FAIL] The Mimic: Build or test command not configured.")
            return 1
        print("[!] Warning: Build/test commands not configured. Mutation audit cannot run dynamically.")
        print("[PASS] The Mimic: Gate passed with warning.")
        return 0

    killed_count = 0
    survived_count = 0
    stillborn_count = 0

    for idx, mutant in enumerate(mutants, 1):
        print(f"--- Mutant {idx}/{len(mutants)}: {mutant.description} ---")
        lines = mutant.file_path.read_text(encoding="utf-8").splitlines(keepends=True)

        with FileRestorer(mutant.file_path):
            lines[mutant.line_index] = mutant.mutated_line
            mutant.file_path.write_text("".join(lines), encoding="utf-8")

            # 1. Compilation check
            try:
                b_res = subprocess.run(
                    build_cmd,
                    shell=True,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
            except subprocess.TimeoutExpired:
                print(f"  [+] KILLED: Compilation timed out.")
                mutant.status = "KILLED"
                killed_count += 1
                continue
            except Exception as e:
                print(f"  [-] Compilation invocation error: {e}")
                mutant.status = "STILLBORN"
                stillborn_count += 1
                continue

            if b_res.returncode != 0:
                print(f"  [-] STILLBORN by Compiler: Mutant produced build failure (excluded from score).")
                mutant.status = "STILLBORN"
                stillborn_count += 1
                continue

            # 2. Test Execution
            try:
                t_res = subprocess.run(
                    test_cmd,
                    shell=True,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
            except subprocess.TimeoutExpired:
                print(f"  [+] KILLED: Test execution timed out (infinite loop caught).")
                mutant.status = "KILLED"
                killed_count += 1
                continue
            except Exception as e:
                print(f"  [-] Test execution error: {e}")
                mutant.status = "STILLBORN"
                stillborn_count += 1
                continue

            if stage == "gate_b":
                if t_res.returncode != 0:
                    print(f"  [+] KILLED by Test Suite (Test failed as expected on mutated logic).")
                    mutant.status = "KILLED"
                    killed_count += 1
                else:
                    print(f"  [!] SURVIVED: Tests passed with exit code 0 despite mutated logic!")
                    print(f"      Original: {mutant.original_line.strip()}")
                    print(f"      Mutated:  {mutant.mutated_line.strip()}")
                    mutant.status = "SURVIVED"
                    survived_count += 1
            else:
                if t_res.returncode != 0:
                    print(f"  [+] KILLED: Trap remained active.")
                    mutant.status = "KILLED"
                    killed_count += 1
                else:
                    print(f"  [!] SURVIVED: Mutant neutralized defect trap unexpectedly.")
                    mutant.status = "SURVIVED"
                    survived_count += 1

    total_evaluated = killed_count + survived_count
    score = 100.0 if total_evaluated == 0 else (killed_count / total_evaluated) * 100.0

    print("\n" + "=" * 60)
    print(f"🛡️  THE MIMIC MUTATION SCORE: {score:.1f}%")
    print(
        f"    Total Evaluated: {total_evaluated} | Killed: {killed_count} | "
        f"Survived: {survived_count} | Stillborn: {stillborn_count}"
    )
    print("=" * 60)

    if total_evaluated == 0 and stillborn_count > 0:
        if strict:
            print("[FAIL] The Mimic: All generated mutants failed compilation (0 viable mutants evaluated).")
            return 1
        print("[!] Warning: All generated mutants were stillborn (failed compilation).")
        return 0

    if score < threshold:
        print(f"[FAIL] The Mimic rejected the test suite: Mutation score {score:.1f}% < required {threshold:.1f}%.")
        print("Surviving mutants prove test suite blind spots. Add assertions covering the mutated lines above.")
        return 1

    print(f"[PASS] The Mimic approved test suite quality (Score {score:.1f}% >= {threshold:.1f}%).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="The Mimic: Mutation Testing Auditor")
    parser.add_argument("--stage", choices=["gate_a", "gate_b"], default="gate_b", help="Audit stage (gate_a or gate_b)")
    parser.add_argument("--build-cmd", default="", help="Command to compile the project")
    parser.add_argument("--test-cmd", default="", help="Command to run the test suite")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_SCORE, help="Minimum mutation score (percentage)")
    parser.add_argument("--target-dir", default=None, help="Target directory or file to mutate")
    parser.add_argument("--max-mutants", type=int, default=10, help="Maximum number of mutants to test")
    parser.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds")
    parser.add_argument("--strict", action="store_true", help="Fail if no files or commands are available")
    args, unknown = parser.parse_known_args()

    stage = args.stage
    for u in unknown:
        if u in ["gate_a", "gate_b"]:
            stage = u

    work_dir = Path.cwd()
    build_cmd = args.build_cmd
    test_cmd = args.test_cmd
    if not build_cmd or not test_cmd:
        resolved_build, resolved_test = resolve_config_commands(work_dir)
        build_cmd = build_cmd or resolved_build
        test_cmd = test_cmd or resolved_test

    sys.exit(
        run_mutation_engine(
            stage=stage,
            work_dir=work_dir,
            build_cmd=build_cmd,
            test_cmd=test_cmd,
            threshold=args.threshold,
            target_dir=args.target_dir,
            max_mutants=args.max_mutants,
            timeout_sec=args.timeout,
            strict=args.strict,
        )
    )


if __name__ == "__main__":
    main()
