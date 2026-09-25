# Project KEEPER: Self-Host Harness Configuration (Dungeons Codex)

Deterministic verification harness for self-auditing the Project KEEPER meta-repository (`./keeper --audit`):

- **Build Command**: `python3 -m py_compile keeper_runner.py traps/*.py tests/*.py .agents/skills/keeper-debt-audit/scripts/scan_debt.py`
- **Unit Test Command**: `python3 -m unittest discover -s tests`
- **Fuzz Command**: `python3 keeper_runner.py --audit-prompts`
- **Incremental Build Timeout**: `30s`
- **Fast Unit Test Timeout**: `30s`
- **Sanitizer Matrix**:
  - ASan+UBSan Command: `python3 .agents/skills/keeper-debt-audit/scripts/scan_debt.py --root . --fail-on-anonymous && python3 traps/triplet_gate.py`
