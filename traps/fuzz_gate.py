#!/usr/bin/env python3
# ==============================================================================
# THE BEHOLDER: Continuous & Bounded Fuzz Testing Gate
# ==============================================================================
# Executes coverage-guided fuzz targets and regression corpora.
# Traps crashes, ASan/UBSan violations, hangs, and invariant breaches.
# ==============================================================================

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_CANDIDATES = [
    "out/Debug/fuzzer_beholder",
    "out/Fuzz/fuzzer_beholder",
    "build/fuzzer_beholder",
    "src/fuzz/fuzzer_beholder",
    "fuzzer_beholder",
]

DEFAULT_CORPUS_DIRS = [
    "fuzz/corpus",
    "src/fuzz/corpus",
]


def resolve_binary(target_arg: str = None) -> Path:
    if target_arg:
        p = Path(target_arg)
        if p.exists() and os.access(p, os.X_OK):
            return p.resolve()
        # Might be in PATH or relative
        which = shutil.which(target_arg)
        if which:
            return Path(which).resolve()
        return p

    for c in DEFAULT_CANDIDATES:
        p = Path(c)
        if p.exists() and os.access(p, os.X_OK):
            return p.resolve()

    return None


def resolve_corpus(corpus_arg: str = None) -> Path:
    if corpus_arg:
        p = Path(corpus_arg)
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    for d in DEFAULT_CORPUS_DIRS:
        p = Path(d)
        if p.exists():
            return p.resolve()

    # Default to fuzz/corpus
    p = Path("fuzz/corpus")
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def run_fuzz_cmd(cmd_str: str, timeout_sec: int) -> int:
    print(f"==> [The Beholder: FUZZ GATE] Executing fuzz test command: {cmd_str}")
    try:
        res = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if res.returncode == 0:
            print(f"[PASS] The Beholder: Fuzz test suite passed cleanly.")
            return 0
        else:
            print(f"[FAIL] The Beholder: Fuzz test suite failed with exit code {res.returncode}!")
            _emit_crash_dossier(cmd_str, res.stdout + res.stderr)
            return 1
    except subprocess.TimeoutExpired:
        print(f"[FAIL] The Beholder: Fuzz test command timed out after {timeout_sec}s!")
        return 1
    except Exception as e:
        print(f"[FAIL] The Beholder: Unexpected error executing fuzz command: {e}")
        return 1


def run_fuzz_gate(
    target_bin: Path,
    corpus_dir: Path,
    timeout_sec: int,
    max_runs: int,
    regression_only: bool,
    strict: bool,
) -> int:
    print("==> [The Beholder: FUZZ GATE] Initializing fuzz testing verification...")

    if not target_bin or not target_bin.exists():
        if strict:
            print(f"[FAIL] The Beholder: Specified fuzz target binary not found: {target_bin}")
            return 1
        print(f"[*] The Beholder: No compiled fuzz target binary detected.")
        print(f"[*] To activate fuzz verification, build with fuzzing enabled (-fsanitize=fuzzer) or set 'Fuzz Command' in KEEPER_CONFIG.md.")
        print("[PASS] The Beholder: Fuzz gate skipped (no active target configured).")
        return 0

    print(f"[*] Fuzz Target:  {target_bin}")
    print(f"[*] Seed Corpus:  {corpus_dir}")

    # Pass 1: Regression Corpus Verification (runs=0 checks existing seeds without mutation)
    print(f"[*] Pass 1: Testing existing regression corpus seeds (runs=0)...")
    try:
        reg_res = subprocess.run(
            [str(target_bin), str(corpus_dir), "-runs=0"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if reg_res.returncode != 0:
            print(f"[FAIL] The Beholder: Regression corpus triggered crash or invariant failure!")
            _emit_crash_dossier(str(target_bin), reg_res.stdout + reg_res.stderr)
            return 1
        print(f"[PASS] The Beholder: Regression corpus verified cleanly.")
    except subprocess.TimeoutExpired:
        print(f"[FAIL] The Beholder: Regression corpus timed out during execution!")
        return 1
    except Exception as e:
        print(f"[FAIL] The Beholder: Execution error on regression corpus: {e}")
        return 1

    if regression_only:
        print("[PASS] The Beholder: Regression-only fuzz verification passed.")
        return 0

    # Pass 2: Bounded Coverage-Guided Fuzzing Exploration
    print(f"[*] Pass 2: Bounded exploration fuzzing (timeout: {timeout_sec}s, max_runs: {max_runs})...")
    fuzz_cmd = [
        str(target_bin),
        str(corpus_dir),
        f"-max_total_time={timeout_sec}",
        f"-runs={max_runs}",
    ]

    try:
        fuzz_res = subprocess.run(
            fuzz_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 10,
        )

        output = fuzz_res.stdout + fuzz_res.stderr

        if fuzz_res.returncode != 0:
            print(f"[FAIL] The Beholder: Fuzz target crashed or tripped an invariant!")
            _emit_crash_dossier(str(target_bin), output)
            return 1

        # Extract exec summary if libFuzzer format
        exec_match = re.search(r"stat::number_of_executed_units:\s*(\d+)", output)
        rate_match = re.search(r"stat::average_exec_per_sec:\s*(\d+)", output)
        exec_count = exec_match.group(1) if exec_match else "completed"
        exec_rate = f" ({rate_match.group(1)} exec/s)" if rate_match else ""

        print(f"[PASS] The Beholder: Bounded fuzzing passed cleanly. Executions: {exec_count}{exec_rate}.")
        return 0

    except subprocess.TimeoutExpired:
        print(f"[FAIL] The Beholder: Fuzz execution hung and exceeded hard process timeout ({timeout_sec + 10}s)!")
        return 1
    except Exception as e:
        print(f"[FAIL] The Beholder: Unexpected fuzzing execution failure: {e}")
        return 1


def _emit_crash_dossier(target: str, log_output: str):
    print("\n" + "=" * 68)
    print("🛡️  THE BEHOLDER: CRASH / INVARIANT VIOLATION DOSSIER")
    print("=" * 68)
    print(f"  🎯 Target Harness: {target}")
    
    # Check for crash artifact files (e.g. crash-*, leak-*, timeout-*)
    crashes = glob.glob("crash-*") + glob.glob("leak-*") + glob.glob("timeout-*")
    if crashes:
        print(f"  💣 Reproducer File: {crashes[0]}")
        print(f"  💡 Repro Command:   {target} {crashes[0]}")
    else:
        print(f"  💣 Reproducer:      Captured in execution trace")

    print("  ------------------------------------------------------------------")
    print("  📋 Tail of Failure Trace:")
    lines = [l for l in log_output.strip().splitlines() if l.strip()]
    tail = lines[-20:] if len(lines) > 20 else lines
    for line in tail:
        print(f"    {line}")
    print("=" * 68 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="The Beholder: Continuous & Bounded Fuzz Testing Gate for Project KEEPER"
    )
    parser.add_argument("--cmd", default=None, help="Direct test command to execute for fuzz verification")
    parser.add_argument("--target", default=None, help="Path to fuzz target binary")
    parser.add_argument("--corpus", default=None, help="Directory containing regression seeds")
    parser.add_argument("--timeout", type=int, default=15, help="Fuzzing exploration duration in seconds")
    parser.add_argument("--max-runs", type=int, default=100000, help="Max iterations")
    parser.add_argument("--regression-only", action="store_true", help="Only verify existing seeds without mutation")
    parser.add_argument("--strict", action="store_true", help="Fail if no fuzzer binary is detected")

    args = parser.parse_args()

    if args.cmd:
        return run_fuzz_cmd(args.cmd, args.timeout)

    bin_path = resolve_binary(args.target)
    corpus_path = resolve_corpus(args.corpus)

    return run_fuzz_gate(
        target_bin=bin_path,
        corpus_dir=corpus_path,
        timeout_sec=args.timeout,
        max_runs=args.max_runs,
        regression_only=args.regression_only,
        strict=args.strict,
    )



if __name__ == "__main__":
    sys.exit(main())
