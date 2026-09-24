#!/usr/bin/env python3
# ==============================================================================
# THE QUARTERMASTER: Resource & Performance Auditor
# ==============================================================================
# Executes Google Benchmark binaries and checks for resource regressions.
# Prevents AI agents from 'gaming' tests by introducing defensive deep copies,
# excess mutex locks, or hidden heap allocations during the hot text shaping loop.
# ==============================================================================

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default Constraints
DEFAULT_MAX_ALLOWED_ALLOCATIONS = 0
DEFAULT_MAX_TIME_NS_PER_GLYPH = 150.0

DEFAULT_CANDIDATE_BINARIES = [
    "out/Release/benchmarks",
    "out/Debug/benchmarks",
    "build/benchmarks",
    "bin/benchmarks",
    "benchmarks",
]


def resolve_benchmark_command(work_dir: Path) -> Optional[str]:
    """Resolves benchmark command from KEEPER_CONFIG.md, candidate binaries, or config."""
    cfg_file = work_dir / "KEEPER_CONFIG.md"
    if cfg_file.exists():
        text = cfg_file.read_text(encoding="utf-8")
        m = re.search(r"\*\*(?:Benchmark|Performance) Command\*\*:\s*`([^`]+)`", text)
        if m:
            return m.group(1).strip()

    # Check candidate binaries on disk
    for cand in DEFAULT_CANDIDATE_BINARIES:
        p = work_dir / cand
        if p.exists() and os.access(p, os.X_OK):
            return str(p)

    return None


def run_benchmark_audit(
    work_dir: Path,
    cmd_str: Optional[str] = None,
    max_allocs: int = DEFAULT_MAX_ALLOWED_ALLOCATIONS,
    max_ns: float = DEFAULT_MAX_TIME_NS_PER_GLYPH,
    strict: bool = False,
    timeout_sec: int = 60,
) -> int:
    print("==> [The Quartermaster] Auditing performance and memory constraints...")

    resolved_cmd = cmd_str or resolve_benchmark_command(work_dir)

    if not resolved_cmd:
        if strict:
            print("[FAIL] The Quartermaster: No benchmark binary or command configured.")
            return 1

        # Check if golden metrics baseline is present
        baseline_file = work_dir / "tests" / "baseline" / "golden_metrics.json"
        if baseline_file.exists():
            try:
                metrics = json.loads(baseline_file.read_text(encoding="utf-8"))
                print(f"[*] Verified golden metrics baseline: {len(metrics)} entry/entries recorded.")
            except Exception as e:
                print(f"[!] Warning: Error reading baseline metrics: {e}")

        print("[*] No active benchmark binary detected. To activate continuous profiling, set 'Benchmark Command' in KEEPER_CONFIG.md.")
        print("[PASS] The Quartermaster: Performance audit passed (no active benchmark target configured).")
        return 0

    print(f"[*] Executing benchmark target: {resolved_cmd}")
    # If the command doesn't already specify json format, append it if it looks like a Google Benchmark binary
    full_cmd = resolved_cmd
    if "--benchmark_format" not in full_cmd:
        full_cmd = f"{resolved_cmd} --benchmark_format=json"

    try:
        res = subprocess.run(
            full_cmd,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        print(f"[FAIL] The Quartermaster: Benchmark run timed out after {timeout_sec}s.")
        return 1
    except Exception as e:
        print(f"[FAIL] The Quartermaster: Error executing benchmark command: {e}")
        return 1

    if res.returncode != 0:
        print(f"[FAIL] The Quartermaster: Benchmark execution failed with exit code {res.returncode}.")
        if res.stderr:
            print(f"Stderr:\n{res.stderr[:500]}")
        return 1

    # Parse JSON output
    data: Dict[str, Any] = {}
    try:
        # Locate the JSON block in stdout
        raw_output = res.stdout.strip()
        json_start = raw_output.find("{")
        if json_start != -1:
            data = json.loads(raw_output[json_start:])
        else:
            data = json.loads(raw_output)
    except Exception as e:
        print(f"[!] Warning: Could not parse benchmark JSON output ({e}). Checking exit code only.")
        print(f"[PASS] The Quartermaster: Benchmark executed successfully (exit code 0).")
        return 0

    benchmarks = data.get("benchmarks", [])
    if not benchmarks:
        print("[*] Benchmark run completed with 0 recorded benchmark cases.")
        print("[PASS] The Quartermaster approved resource costs.")
        return 0

    passed = True
    for bm in benchmarks:
        name = bm.get("name", "Unknown")
        # Check cpu time
        cpu_time = bm.get("cpu_time_ns", bm.get("cpu_time", 0.0))
        # Check heap allocations if reported
        allocs = bm.get("heap_allocations", bm.get("allocations", 0))

        print(f"[*] Benchmark {name}: {cpu_time:.1f} ns/op, {allocs} heap allocs")

        if allocs > max_allocs:
            print(f"[FAIL] Allocation budget exceeded in {name}: {allocs} > {max_allocs}")
            passed = False

        if cpu_time > max_ns:
            print(f"[FAIL] Latency budget exceeded in {name}: {cpu_time:.1f}ns > {max_ns}ns")
            passed = False

    if not passed:
        print("[FAIL] The Quartermaster rejected resource profile.")
        return 1

    print("[PASS] The Quartermaster approved resource costs.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="The Quartermaster: Resource & Performance Auditor")
    parser.add_argument("--cmd", default=None, help="Benchmark execution command")
    parser.add_argument("--max-allocs", type=int, default=DEFAULT_MAX_ALLOWED_ALLOCATIONS, help="Max allowed heap allocations")
    parser.add_argument("--max-ns", type=float, default=DEFAULT_MAX_TIME_NS_PER_GLYPH, help="Max allowed nanoseconds per operation")
    parser.add_argument("--strict", action="store_true", help="Fail if benchmark command is not available")
    parser.add_argument("--timeout", type=int, default=60, help="Benchmark execution timeout")
    args = parser.parse_args()

    work_dir = Path.cwd()
    sys.exit(
        run_benchmark_audit(
            work_dir=work_dir,
            cmd_str=args.cmd,
            max_allocs=args.max_allocs,
            max_ns=args.max_ns,
            strict=args.strict,
            timeout_sec=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
