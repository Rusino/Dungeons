import sys
import subprocess

def check_triplet(work_dir: str = ".") -> tuple[bool, str]:
    try:
        res = subprocess.run(["git", "diff", "HEAD", "--name-only"], cwd=work_dir, capture_output=True, text=True, check=True)
        files = res.stdout.splitlines()

        has_src = any(f.startswith("src/") for f in files)
        has_tests = any(f.startswith("tests/") for f in files)
        has_invariants = any(f == "INVARIANTS.md" for f in files)
        
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
