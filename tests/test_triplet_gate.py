import unittest
from unittest.mock import patch, MagicMock
from traps.triplet_gate import check_triplet

class TestTripletGate(unittest.TestCase):

    @patch("subprocess.run")
    def test_no_product_files(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="docs/README.md\ntraps/triplet_gate.py\ntests/some_test.py")
        ok, msg = check_triplet()
        self.assertTrue(ok)
        self.assertEqual(msg, "No product code modified; triplet bypassed.")

    @patch("subprocess.run")
    def test_all_triplet_present(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="src/main.cpp\ntests/test_main.cpp\nINVARIANTS.md")
        ok, msg = check_triplet()
        self.assertTrue(ok)
        self.assertEqual(msg, "Git Triplet Verification passed.")

    @patch("subprocess.run")
    def test_missing_tests_and_invariants(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="src/main.cpp\ndocs/README.md")
        ok, msg = check_triplet()
        self.assertFalse(ok)
        self.assertIn("Missing: tests/, INVARIANTS.md", msg)

    @patch("subprocess.run")
    def test_missing_tests(self, mock_run): # e.g. someone updates src and INVARIANTS but no tests
        mock_run.return_value = MagicMock(returncode=0, stdout="src/main.cpp\nINVARIANTS.md")
        ok, msg = check_triplet()
        self.assertFalse(ok)
        self.assertIn("Missing: tests/", msg)

    def test_triplet_gate_monorepo_subdir_blocks_incomplete_triplet(self):
        """Red-team test: check_triplet must correctly verify triplet in monorepo subdirectories."""
        import os
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(root), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), check=True, capture_output=True)

            subdir = root / "tools" / "editor"
            subdir.mkdir(parents=True, exist_ok=True)
            (subdir / "src").mkdir(parents=True, exist_ok=True)
            (subdir / "tests").mkdir(parents=True, exist_ok=True)

            a_cpp = subdir / "src" / "a.cpp"
            t_cpp = subdir / "tests" / "t.cpp"
            inv_md = subdir / "INVARIANTS.md"

            a_cpp.write_text("int main() { return 0; }\n", encoding="utf-8")
            t_cpp.write_text("int test() { return 0; }\n", encoding="utf-8")
            inv_md.write_text("# Invariants\n", encoding="utf-8")

            subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(root), check=True, capture_output=True)

            # Modify ONLY subdir / "src" / "a.cpp"
            with open(a_cpp, "a", encoding="utf-8") as f:
                f.write("// change\n")

            ok, msg = check_triplet(str(subdir))
            self.assertFalse(ok)
            self.assertIn("Missing: tests/, INVARIANTS.md", msg)

    def test_triplet_gate_recognizes_untracked_files_and_excluded_invariants(self):
        """Red-team test: check_triplet must recognize untracked files and mtime-updated excluded INVARIANTS.md."""
        import os
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(root), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), check=True, capture_output=True)

            subdir = root / "tools" / "editor"
            subdir.mkdir(parents=True, exist_ok=True)
            readme = subdir / "README.md"
            readme.write_text("# Readme\n", encoding="utf-8")

            subprocess.run(["git", "add", "."], cwd=str(root), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(root), check=True, capture_output=True)

            # Add /tools/editor/INVARIANTS.md to .git/info/exclude
            exclude_file = root / ".git" / "info" / "exclude"
            exclude_file.parent.mkdir(parents=True, exist_ok=True)
            with open(exclude_file, "a", encoding="utf-8") as f:
                f.write("/tools/editor/INVARIANTS.md\n")

            commit_ts = int(subprocess.check_output(["git", "log", "-1", "--format=%ct"], cwd=str(root)).strip())

            inv_path = subdir / "INVARIANTS.md"
            inv_path.write_text("# Subsystem Invariants\n", encoding="utf-8")
            os.utime(inv_path, (commit_ts - 100, commit_ts - 100))

            # Create untracked product and test files
            src_dir = subdir / "src"
            tests_dir = subdir / "tests"
            src_dir.mkdir(parents=True, exist_ok=True)
            tests_dir.mkdir(parents=True, exist_ok=True)

            (src_dir / "new_feature.cpp").write_text("int feature() { return 1; }\n", encoding="utf-8")
            (tests_dir / "test_new_feature.cpp").write_text("int test_feature() { return 1; }\n", encoding="utf-8")

            # Check 1: INVARIANTS.md mtime is older than commit -> should fail
            ok, msg = check_triplet(str(subdir))
            self.assertFalse(ok)
            self.assertIn("INVARIANTS.md", msg)

            # Check 2: Update INVARIANTS.md content and set mtime to commit_ts + 10 -> should pass
            inv_path.write_text("# Subsystem Invariants (Updated)\n", encoding="utf-8")
            os.utime(inv_path, (commit_ts + 10, commit_ts + 10))

            ok, msg = check_triplet(str(subdir))
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
