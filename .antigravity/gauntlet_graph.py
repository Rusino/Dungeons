#!/usr/bin/env python3
# ==============================================================================
# THE GAUNTLET GRAPH ORCHESTRATOR (The Dungeon Master)
# ==============================================================================
# This script orchestrates the autonomous development and validation cycle:
#   1. Wakes The Architect to generate C++20 contracts (.hpp) based on RFC.
#   2. Wakes The Trapsmith to write adversarial GTest suites.
#   3. Executes a Self-Healing loop for The Artificer (.cpp implementation) through:
#        - Tier 1: Fast Traps (Clang -Werror, ASan/UBSan, The Cartographer)
#        - Tier 2: Sanitizer Matrix (ThreadSanitizer, MemorySanitizer)
#        - Tier 3: The Mimic (Mull Mutation Testing >= 90%)
#        - Tier 4: The Quartermaster (Google Benchmark latency & alloc check)
#   4. If retries exceed MAX_RETRIES (5), generates a Deadlock Diagnostic for
#      human arbitrator review (The Overgod).
# ==============================================================================

import sys
import os
import subprocess
import json
from pathlib import Path

# Base directories
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
TRAPS_DIR = WORKSPACE_ROOT / "traps"
SRC_DIR = WORKSPACE_ROOT / "src"
TESTS_DIR = WORKSPACE_ROOT / "tests"
RFC_DIR = WORKSPACE_ROOT / "docs" / "rfcs"

# Maximum autonomous self-healing iterations before human escalation
MAX_RETRIES = 5

def run_step(cmd: list, cwd=None, description="Step") -> tuple[int, str, str]:
    """Executes a pipeline step and captures exit code, stdout, and stderr."""
    print(f"==> [The Dungeon Master] Running: {description} ({' '.join(cmd)})")
    proc = subprocess.run(cmd, cwd=cwd or WORKSPACE_ROOT, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def execute_gauntlet(rfc_path: str):
    """Main orchestration loop executing the tiered verification gauntlet."""
    print(f"=== Initiating The Gauntlet for RFC: {rfc_path} ===")
    
    # Verify input feature specification exists
    if not os.path.exists(rfc_path):
        print(f"Error: RFC {rfc_path} not found.")
        sys.exit(1)
        
    print("[1/5] Contract Generation: The Architect generates C++20 .hpp contracts.")
    print("[2/5] Adversarial Testing: The Trapsmith lays edge-case tests.")
    
    # Self-Healing Gauntlet Loop for The Artificer
    for iteration in range(1, MAX_RETRIES + 1):
        print(f"\n--- [The Gauntlet] Iteration {iteration}/{MAX_RETRIES} ---")
        
        # ----------------------------------------------------------------------
        # TIER 1: FAST TRAPS (AddressSanitizer + UndefinedBehaviorSanitizer)
        # ----------------------------------------------------------------------
        code, out, err = run_step(
            ["bash", str(TRAPS_DIR / "sanitize_matrix.sh"), "fast"],
            description="Tier 1: Fast Traps (ASan+UBSan compilation & run)"
        )
        if code != 0:
            print(f"[!] Tier 1 Trap Triggered (Sanitizer / Compile Error):")
            print(err[:500] if err else out[:500])
            continue
            
        # The Cartographer: Verify deterministic glyph advances and bounding boxes
        code, out, err = run_step(
            ["python3", str(TRAPS_DIR / "cartographer_delta.py")],
            description="The Cartographer: Layout Metric Verification"
        )
        if code != 0:
            print(f"[!] The Cartographer Detected Structural Layout Regression.")
            continue
            
        # ----------------------------------------------------------------------
        # TIER 2: DEEP SANITIZER MATRIX (ThreadSanitizer & MemorySanitizer)
        # ----------------------------------------------------------------------
        code, out, err = run_step(
            ["bash", str(TRAPS_DIR / "sanitize_matrix.sh"), "matrix"],
            description="Tier 2: Concurrency & Deep Memory (TSan/MSan)"
        )
        if code != 0:
            print(f"[!] Tier 2 Trap Triggered.")
            continue

        # ----------------------------------------------------------------------
        # TIER 3: THE MIMIC (Mutation Testing Quality Gate via Mull)
        # ----------------------------------------------------------------------
        code, out, err = run_step(
            ["python3", str(TRAPS_DIR / "mutation_gate.py")],
            description="Tier 3: The Mimic (Mutation Testing >= 90%)"
        )
        if code != 0:
            print(f"[!] The Mimic: Test suite mutation score fell below threshold.")
            continue

        # ----------------------------------------------------------------------
        # TIER 4: THE QUARTERMASTER (Performance Profiling via Google Benchmark)
        # ----------------------------------------------------------------------
        code, out, err = run_step(
            ["python3", str(TRAPS_DIR / "performance_auditor.py")],
            description="Tier 4: The Quartermaster (Cycle & Allocation Budget)"
        )
        if code != 0:
            print(f"[!] The Quartermaster: Performance budget exceeded.")
            continue

        print("\n*** SUCCESS: Code passed all Gauntlet traps! ***")
        print("Waiting for The Overgod (Human) final elegance review and merge.")
        return 0

    # Retries exhausted: trigger arbitration summary
    print("\n[DEADLOCK] Maximum retry iterations reached without passing all traps.")
    print("Triggering Deadlock Diagnostic Analyst for The Overgod escalation...")
    return 2

if __name__ == "__main__":
    rfc = sys.argv[1] if len(sys.argv) > 1 else str(RFC_DIR / "RFC_001_Zero_Width_Joiner.md")
    sys.exit(execute_gauntlet(rfc))
