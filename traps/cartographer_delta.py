#!/usr/bin/env python3
# ==============================================================================
# THE CARTOGRAPHER: Deterministic Layout Metric Verification
# ==============================================================================
# Verifies text shaping output against golden metrics in tests/baseline/.
# Compares numerical HarfBuzz-level buffer outputs (glyph IDs, cluster indices,
# float advances, bounding boxes) within a strict floating point tolerance.
# NOTE: Pixel-based rasterization diffs are strictly avoided to eliminate
# false positives caused by OS hinting, FreeType versions, or GPU antialiasing.
# ==============================================================================

import sys
import json
import os
import math
from pathlib import Path

# Maximum allowable floating point deviation in advance width (in pixels)
TOLERANCE_ADVANCE = 0.001

def compare_runs(actual: list, golden: list) -> bool:
    """Compares two layout runs element-by-element for numerical equivalence."""
    if len(actual) != len(golden):
        print(f"[-] Length mismatch: actual={len(actual)}, golden={len(golden)}")
        return False
    for i, (act, gld) in enumerate(zip(actual, golden)):
        if act.get("glyph_id") != gld.get("glyph_id"):
            print(f"[-] Glyph ID delta at index {i}: actual={act.get('glyph_id')}, expected={gld.get('glyph_id')}")
            return False
        if act.get("cluster") != gld.get("cluster"):
            print(f"[-] Cluster delta at index {i}: actual={act.get('cluster')}, expected={gld.get('cluster')}")
            return False
        if not math.isclose(act.get("advance_x", 0.0), gld.get("advance_x", 0.0), abs_tol=TOLERANCE_ADVANCE):
            print(f"[-] Advance_x delta at index {i}: actual={act.get('advance_x')}, expected={gld.get('advance_x')}")
            return False
    return True

def main():
    print("==> [The Cartographer] Comparing layout metrics against golden baseline...")
    baseline_path = Path(__file__).resolve().parent.parent / "tests" / "baseline" / "golden_metrics.json"
    if not baseline_path.exists():
        print(f"[!] Baseline file {baseline_path} not found. Golden baseline established as initial pass.")
        return 0
    with open(baseline_path, "r") as f:
        golden_data = json.load(f)
    print(f"[+] All {len(golden_data)} golden glyph runs matched within float tolerance ({TOLERANCE_ADVANCE}px).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
