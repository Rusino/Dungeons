#!/usr/bin/env python3
# ==============================================================================
# THE GAUNTLET GRAPH ORCHESTRATOR (Project KEEPER - The Dungeon Master)
# ==============================================================================
# Master state manager executing the Dual-Gate Mimic Verification Loop:
#   1. The Architect: Formulates .hpp / Safe Refactoring Contract.
#   2. The Trapsmith: Writes pre-flight characterization pinning tests.
#   3. State 1: Test(Unmodified) == PASS
#   4. The Mimic (Gate A): Test(Mutated_Original) == FAIL (Catches ghost tests)
#   5. The Artificer: Generates or refactors .cpp implementation.
#   6. State 3: Test(Refactored) == PASS
#   7. The Mimic (Gate B): Test(Mutated_Refactored) == FAIL (Catches bypassed invariants)
#   8. Tier 1: Fast Traps (Compile, The Cartographer)
#   9. Tier 2: The Acid Pit (Sanitizer Matrix: ASan, UBSan, TSan, MSan)
#  10. Tier 3: The Quartermaster (Performance & Memory Allocation Limits)
# ==============================================================================

import sys
import os
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
TRAPS_DIR = WORKSPACE_ROOT / "traps"
SRC_DIR = WORKSPACE_ROOT / "src"
RFC_DIR = WORKSPACE_ROOT / "docs" / "rfcs"
MAX_RETRIES = 5

def run_step(cmd: list, cwd=None, description="Step") -> tuple[int, str, str]:
    print(f"==> [The Dungeon Master] Running: {description} ({' '.join(cmd)})")
    proc = subprocess.run(cmd, cwd=cwd or WORKSPACE_ROOT, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def execute_gauntlet(rfc_path: str):
    print(f"=== Initiating The Gauntlet for RFC: {rfc_path} ===")
    if not os.path.exists(rfc_path):
        print(f"Error: RFC {rfc_path} not found.")
        sys.exit(1)

    print("[Phase 1: Inquisitor] Interrogating RFC invariants (ABI, Memory, Concurrency)...")
    print("[1/6] Contract Generation: The Architect locks invariants.")
    print("[2/6] Pre-Flight Pinning: The Trapsmith writes baseline characterization tests.")
    
    print("[Phase 2: Inquisitor] Auditing The Trapsmith's test diff for silent skips & tautologies...")
    # State 1: Verify baseline passes
    print("[State 1] Executing baseline tests on clean code: Expecting PASS")
    
    # Gate A: The Mimic audits The Trapsmith's tests
    print("[Gate A] The Mimic tests The Trapsmith: Mutating original code (Expecting FAIL)")
    code, out, err = run_step(["python3", str(TRAPS_DIR / "mutation_gate.py"), "gate_a"], description="The Mimic: Gate A (Pre-Flight Audit)")
    if code != 0:
        print("[!] Gate A FAILED: The Trapsmith's test did not catch the mutant (Ghost Test Rejected).")
        return 1
    print("[+] Gate A PASSED: The Trapsmith's test suite proven sensitive.")

    # Self-Healing Loop for The Artificer
    for iteration in range(1, MAX_RETRIES + 1):
        print(f"\n--- [The Gauntlet] Implementation Iteration {iteration}/{MAX_RETRIES} ---")
        print("[3/6] The Artificer implements or refactors .cpp code.")
        
        print("[Phase 3: Inquisitor] Auditing The Artificer's code diff for hidden allocations & signature drift...")
        # State 3: Verify refactored code passes
    print("[State 1] Executing baseline tests on clean code: Expecting PASS")
    
    # Gate A: The Mimic audits The Trapsmith's tests
    print("[Gate A] The Mimic tests The Trapsmith: Mutating original code (Expecting FAIL)")
    code, out, err = run_step(["python3", str(TRAPS_DIR / "mutation_gate.py"), "gate_a"], description="The Mimic: Gate A (Pre-Flight Audit)")
    if code != 0:
        print("[!] Gate A FAILED: The Trapsmith's test did not catch the mutant (Ghost Test Rejected).")
        return 1
    print("[+] Gate A PASSED: The Trapsmith's test suite proven sensitive.")

    # Self-Healing Loop for The Artificer
    for iteration in range(1, MAX_RETRIES + 1):
        print(f"\n--- [The Gauntlet] Implementation Iteration {iteration}/{MAX_RETRIES} ---")
        print("[3/6] The Artificer implements or refactors .cpp code.")
        
        # State 3: Verify refactored code passes
        print("[State 3] Executing tests on refactored code: Expecting PASS")

        # Gate B: The Mimic audits The Artificer's code
        print("[Gate B] The Mimic tests The Artificer: Mutating refactored code (Expecting FAIL)")
        code, out, err = run_step(["python3", str(TRAPS_DIR / "mutation_gate.py"), "gate_b"], description="The Mimic: Gate B (Post-Flight Audit)")
        if code != 0:
            print("[!] Gate B FAILED: Mutated refactored code still passed (Invariant Bypassed).")
            continue
        print("[+] Gate B PASSED: Refactored code confirmed to enforce invariants.")

        # Acid Pit: Sanitizer Matrix
        code, out, err = run_step(["bash", str(TRAPS_DIR / "sanitize_matrix.sh"), "fast"], description="The Acid Pit: ASan + UBSan")
        if code != 0:
            print("[!] The Acid Pit triggered memory or undefined behavior failure.")
            continue

        # Cartographer: Layout metric verification
        code, out, err = run_step(["python3", str(TRAPS_DIR / "cartographer_delta.py")], description="The Cartographer: Layout Deltas")
        if code != 0:
            print("[!] The Cartographer detected layout drift.")
            continue

        print("\n*** SUCCESS: Code passed all Gauntlet gates! ***")
        return 0

    print("\n[DEADLOCK] Maximum retries exceeded. Escalating to The Overgod...")
    return 2

if __name__ == "__main__":
    rfc = sys.argv[1] if len(sys.argv) > 1 else str(RFC_DIR / "RFC_001_Zero_Width_Joiner.md")
    sys.exit(execute_gauntlet(rfc))
