---
name: keeper-milestone-sync
description: >-
  Synchronizes local operational codex rules and invariants with the canonical upstream Dungeons codex. Use when closing an inquest, finalizing a milestone, or preparing for branch merges.
---

# KEEPER Upstream Milestone Synchronization Runbook

This skill enforces Axiom 13 (**The Upstream Milestone Synchronization Protocol**) of Project KEEPER.

---

## Objectives
1. **Eliminate Invariant Drift**: Ensure that local subsystem enhancements, newly discovered invariants, and protocol hardenings propagate to the canonical upstream codex (`codex/AGENTS.md` and `codex/TEXT_DOMAIN.md`).
2. **Milestone Integrity Gate**: Validate that all unit tests, debt checks, and sanitizer gates pass cleanly before synchronizing.
3. **Preserve Lineage**: Maintain Git provenance and prevent fragmentation across repository clones.

---

## Operational Steps

### 1. Pre-Synchronization Health Gate
Before executing any sync operations, verify the physical health of the active branch:
```bash
# 1. Run unit test suite
python3 -m unittest discover tests

# 2. Run defensive debt audit
python3 .agents/skills/keeper-debt-audit/scripts/scan_debt.py --fail-on-anonymous
```
*Criteria*: Exit code `0` on both commands. Zero active dormant debt.

### 2. Upstream Invariant Alignment
Check for local changes that belong in the Master Constitution:
- If new universal laws were discovered during an inquest, append them to `codex/AGENTS.md`.
- If new text layout or rendering invariants were locked, update `codex/TEXT_DOMAIN.md`.
- Ensure all skills in `.agents/skills/` are up to date and tracked.

### 3. Verify Codex Integrity
Run the built-in codex integrity test:
```bash
python3 tests/test_codex_integrity.py
```
Confirm that formatting, headers, and constitutional structure pass without errors.

### 4. Emit Milestone Synchronization Receipt
Conclude the turn with the formal synchronization receipt:

```markdown
### Upstream Milestone Synchronization Receipt

- **Branch / Revision**: `[git rev-parse --short HEAD]`
- **Pre-Sync Tests**: PASSED (22/22 tests OK)
- **Defensive Debt**: ZERO (0 markers, 0 anonymous)
- **Synchronized Artifacts**:
  - `codex/AGENTS.md` (Tier 1 Master Constitution)
  - `codex/TEXT_DOMAIN.md` (Tier 2 Text Codex)
  - `.agents/skills/*` (Modular Skills Catalog)
- **Status**: SYNCHRONIZED & MILESTONE-READY
```
