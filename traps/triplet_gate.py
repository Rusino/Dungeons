import sys
import subprocess
from pathlib import Path

def check_triplet(work_dir: str = ".") -> tuple[bool, str]:
    try:
        res = subprocess.run(["git", "diff", "HEAD", "--relative", "--name-only"], cwd=work_dir, capture_output=True, text=True, check=True)
        files = res.stdout.splitlines()

        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=work_dir, capture_output=True, text=True)
        if untracked.returncode == 0 and isinstance(untracked.stdout, str):
            files.extend(untracked.stdout.splitlines())

        has_src = any(f.startswith("src/") for f in files)
        has_tests = any(f.startswith("tests/") for f in files)
        has_invariants = any(f == "INVARIANTS.md" for f in files)

        if not has_invariants:
            inv_path = Path(work_dir) / "INVARIANTS.md"
            if inv_path.is_file():
                tracked = subprocess.run(["git", "ls-files", "INVARIANTS.md"], cwd=work_dir, capture_output=True, text=True)
                if tracked.returncode == 0 and not tracked.stdout.strip():
                    head_ts_res = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=work_dir, capture_output=True, text=True)
                    if head_ts_res.returncode == 0 and head_ts_res.stdout.strip().isdigit():
                        if inv_path.stat().st_mtime > int(head_ts_res.stdout.strip()):
                            has_invariants = True
        
        has_product_code = has_src or any(f.startswith("include/") for f in files)
        if not has_product_code:
            return True, "No product code modified; triplet bypassed."

        missing = []
        if not has_src: missing.append("src/")
        if not has_tests: missing.append("tests/")
        if not has_invariants: missing.append("INVARIANTS.md")

        if missing:
            return False, f"Git Triplet Violation: Feature/Defect commits must modify src/, tests/, and INVARIANTS.md. Missing: {', '.join(missing)}"
        
        return True, "Git Triplet Verification passed."

    except subprocess.CalledProcessError as e:
        return False, f"Git diff failed: {e}"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".")
    args = parser.parse_args()
    
    ok, msg = check_triplet(args.dir)
    if not ok:
        print(f"🚨 {msg}")
        sys.exit(1)
    print(f"✅ {msg}")
    sys.exit(0)
