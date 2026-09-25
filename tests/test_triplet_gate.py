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

if __name__ == "__main__":
    unittest.main()
