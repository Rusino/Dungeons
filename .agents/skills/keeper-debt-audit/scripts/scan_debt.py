#!/usr/bin/env python3
"""
Project KEEPER - Defensive Debt Scanner
Scans source files for structured TODO(KEEPER-DEBT) markers and flags anonymous TODOs.
"""

import argparse
import os
import re
import sys
from pathlib import Path

VALID_DEBT_PATTERN = re.compile(r"TODO\(KEEPER-DEBT:\s*([^)]+)\):\s*(.+)")
GENERIC_TODO_PATTERN = re.compile(r"^\s*(?://|#|/\*)\s*(?:TODO|FIXME)\b(?!\(KEEPER-DEBT)", re.IGNORECASE)

EXCLUDE_DIRS = {
    ".git",
    ".agents",
    "venv",
    ".venv",
    "__pycache__",
    "out",
    "build",
    ".idea",
    "node_modules",
    ".antigravity",
}

EXTENSIONS = {
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
    ".go", ".py", ".sh", ".rs", ".js", ".ts", ".dart"
}


def scan_file(file_path: Path):
    valid_items = []
    invalid_items = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                match_valid = VALID_DEBT_PATTERN.search(clean_line)
                if match_valid:
                    inv_id = match_valid.group(1).strip()
                    desc = match_valid.group(2).strip()
                    valid_items.append({
                        "file": str(file_path),
                        "line": line_no,
                        "invariant": inv_id,
                        "description": desc,
                    })
                    continue

                match_generic = GENERIC_TODO_PATTERN.search(clean_line)
                if match_generic:
                    invalid_items.append({
                        "file": str(file_path),
                        "line": line_no,
                        "snippet": clean_line,
                    })
    except Exception as e:
        sys.stderr.write(f"Warning: Could not read {file_path}: {e}\n")

    return valid_items, invalid_items


def main():
    parser = argparse.ArgumentParser(description="KEEPER Defensive Debt Scanner")
    parser.add_argument("--root", default=".", help="Root directory to scan")
    parser.add_argument("--fail-on-anonymous", action="store_true", help="Exit 1 if anonymous TODOs are found")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    all_valid = []
    all_invalid = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            ext = Path(f).suffix.lower()
            if ext in EXTENSIONS:
                path = Path(dirpath) / f
                rel_path = path.relative_to(root_dir)
                val, inval = scan_file(rel_path)
                all_valid.extend(val)
                all_invalid.extend(inval)

    print("### Project KEEPER: Defensive Debt Audit Report\n")
    if all_valid:
        print("#### Registered Defensive Debt Markers")
        print("| Invariant ID | File:Line | Deferred Capability |")
        print("| :--- | :--- | :--- |")
        for item in all_valid:
            print(f"| `{item['invariant']}` | `{item['file']}:{item['line']}` | {item['description']} |")
        print()
    else:
        print("No registered `TODO(KEEPER-DEBT)` markers found.\n")

    if all_invalid:
        print("#### ⚠️ Anonymous / Protocol Violations (Unstructured Debt)")
        print("| File:Line | Code Snippet |")
        print("| :--- | :--- |")
        for item in all_invalid:
            print(f"| `{item['file']}:{item['line']}` | `{item['snippet'][:80]}` |")
        print()
        if args.fail_on_anonymous:
            sys.exit(1)
    else:
        print("✅ Zero anonymous TODO/FIXME violations detected.\n")


if __name__ == "__main__":
    main()
