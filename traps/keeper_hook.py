#!/usr/bin/env python3
"""
Project KEEPER Lifecycle Hook & Red-Line Interceptor (traps/keeper_hook.py)
============================================================================
Implements the Jetski Lifecycle Hook protocol (--event pre_tool_use | post_tool_use | stop).
Enforces containment boundaries and red-line safety checks:
1. pre_tool_use:
   - Direct engine code edits when .keeper/state.json status is RUNNING.
   - Ungrounded subagent prompt (canonical role without on-disk prompt file reference).
   - Black-box ingress leak (Trapsmith prompt leaking src/ production paths).
   - Destructive or bypass shell commands (git reset --hard, git push --force, etc.).
   Returns "force_ask" with diagnostic reason on violation; "allow" otherwise.
   Logs all calls to <workspace>/.keeper/diagnostics.jsonl.
2. post_tool_use:
   - Increments read-quantum counter in .keeper/turn_telemetry.json on read tools.
   - Logs to <workspace>/.keeper/diagnostics.jsonl.
   - Returns {}.
3. stop:
   - Inspects git status / diff for unmarked TODOs, disallowed constructs, header loops.
   - Checks unacknowledged protocol_violations in .keeper/state.json.
   - Writes <workspace>/.keeper/last_turn_diagnostics.md.
   - Returns {"decision": "continue", "reason": ...} on first failure per executionNum,
     and {"decision": "stop"} thereafter to prevent loops.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CANONICAL_ROLES = [
    "Architect",
    "Trapsmith",
    "Artificer",
    "Mimic",
    "Inquisitor",
    "Coroner",
    "Censor",
    "Oracle",
    "Beholder",
    "Cartographer",
    "Quartermaster",
    "Acid Pit",
    "Scavenger",
]

ON_DISK_PROMPT_PATTERNS = [
    "codex/prompts/",
    ".antigravity/prompts/",
    ".keeper/prompts/",
    ".keeper/active_task.md",
    "docs/",
]

DISALLOWED_CONSTRUCTS = [
    "#pragma",
    "reinterpret_cast",
    "goto",
    "malloc(",
    "free(",
]


def _get_workspace_path(payload: Dict[str, Any], cwd: Optional[Path] = None) -> Path:
    """Extracts the active workspace path from hook payload or falls back to cwd."""
    paths = payload.get("workspacePaths", [])
    if paths:
        return Path(paths[0]).resolve()
    return (cwd or Path.cwd()).resolve()


def _append_diagnostic_log(ws: Path, event: str, entry: Dict[str, Any]):
    """Logs lifecycle event to <workspace>/.keeper/diagnostics.jsonl."""
    try:
        diag_file = ws / ".keeper" / "diagnostics.jsonl"
        diag_file.parent.mkdir(parents=True, exist_ok=True)
        record = dict(entry)
        record["event"] = event
        with open(diag_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def evaluate_pre_tool_use(payload: Dict[str, Any], cwd: Optional[Path] = None) -> Dict[str, Any]:
    """
    Evaluates pre_tool_use event against KEEPER red lines.
    Returns {"decision": "allow"} or {"decision": "force_ask", "reason": ...}
    """
    ws = _get_workspace_path(payload, cwd)
    tool_call = payload.get("toolCall", {})
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    _append_diagnostic_log(ws, "pre_tool_use", {"toolCall": tool_call})

    # Red Line 1: Direct Engine Code Edit by Lead Agent when state is RUNNING
    if name in ("replace_file_content", "write_to_file", "multi_replace_file_content"):
        target_file_str = args.get("TargetFile", "")
        if target_file_str:
            target_path = Path(target_file_str)
            try:
                rel_path = target_path.resolve().relative_to(ws).as_posix()
            except ValueError:
                rel_path = target_path.as_posix()

            is_engine_code = (
                rel_path.startswith("src/")
                or rel_path.startswith("include/")
                or rel_path.startswith("tests/")
            )

            if is_engine_code:
                state_file = ws / ".keeper" / "state.json"
                if state_file.exists():
                    try:
                        state_data = json.loads(state_file.read_text(encoding="utf-8"))
                        if state_data.get("status") == "RUNNING":
                            return {
                                "decision": "force_ask",
                                "reason": (
                                    f"⚠️ KEEPER DIAGNOSTIC [Direct Code Edit]: "
                                    f"Lead agent attempted direct edit to production/test file `{rel_path}` "
                                    f"while KEEPER engine state is RUNNING. All edits to `src/**`, `include/**`, "
                                    f"or `tests/**` must be delegated to the designated subagent worker (The Artificer or The Trapsmith)."
                                ),
                            }
                    except Exception:
                        pass

    # Red Line 2: Ungrounded Subagent Prompt or Black-Box Ingress Leak
    if name == "invoke_subagent":
        subagents = args.get("Subagents", [])
        for sub in subagents:
            role = sub.get("Role", "")
            prompt = sub.get("Prompt", "")

            # Check if role matches canonical KEEPER roles
            is_canonical = any(c_role.lower() in role.lower() for c_role in CANONICAL_ROLES)
            if is_canonical:
                # Check for on-disk grounding
                is_grounded = any(p in prompt for p in ON_DISK_PROMPT_PATTERNS)
                if not is_grounded:
                    return {
                        "decision": "force_ask",
                        "reason": (
                            f"⚠️ KEEPER DIAGNOSTIC [Ungrounded Subagent Prompt]: "
                            f"Subagent '{role}' was invoked without referencing an on-disk prompt or spec file "
                            f"({', '.join(ON_DISK_PROMPT_PATTERNS)}). Prompt must be grounded in physical disk files."
                        ),
                    }

                # Check Trapsmith black-box ingress leak
                if "trapsmith" in role.lower():
                    # If prompt references production implementation paths/patches (src/)
                    if "src/" in prompt:
                        return {
                            "decision": "force_ask",
                            "reason": (
                                f"⚠️ KEEPER DIAGNOSTIC [Black-Box Ingress Violation]: "
                                f"The Trapsmith must operate black-box and is forbidden from viewing or referencing "
                                f"production implementation paths (`src/`). Remove `src/` references from Trapsmith prompt."
                            ),
                        }

    # Red Line 3: Destructive or Bypass Shell Command
    if name == "run_command":
        cmd = args.get("CommandLine", "")
        destructive_patterns = [
            "git reset --hard",
            "git push --force",
            "git commit --no-verify",
        ]
        if any(pat in cmd for pat in destructive_patterns) or re.search(r"(?:sed\s+-i|>\s*(?:src/|include/|tests/|traps/))", cmd):
            return {
                "decision": "force_ask",
                "reason": (
                    f"⚠️ KEEPER DIAGNOSTIC [Shell Red Line]: "
                    f"Detected destructive or bypass command: `{cmd}`. Direct working tree destruction or "
                    f"shell bypasses of source files are strictly prohibited."
                ),
            }

    return {"decision": "allow"}


def evaluate_post_tool_use(payload: Dict[str, Any], cwd: Optional[Path] = None) -> Dict[str, Any]:
    """
    Evaluates post_tool_use event: tracks telemetry, increments read quantum counter.
    Outputs {}.
    """
    ws = _get_workspace_path(payload, cwd)
    tool_call = payload.get("toolCall", {})
    name = tool_call.get("name", "")

    _append_diagnostic_log(ws, "post_tool_use", {"toolCall": tool_call})

    # Track read tools: view_file, read_url_content, etc.
    if name in ("view_file", "read_url_content", "read_browser_page"):
        telemetry_file = ws / ".keeper" / "turn_telemetry.json"
        telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if telemetry_file.exists():
            try:
                data = json.loads(telemetry_file.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        data["read_count"] = data.get("read_count", 0) + 1
        telemetry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return {}


def evaluate_stop(payload: Dict[str, Any], cwd: Optional[Path] = None) -> Dict[str, Any]:
    """
    Evaluates stop event:
    Checks modified files in src/**, include/**, tests/** for unmarked TODOs, banned constructs.
    Checks unacknowledged protocol_violations in .keeper/state.json.
    Writes .keeper/last_turn_diagnostics.md.
    Returns continue once per executionNum if violations exist; stop otherwise.
    """
    ws = _get_workspace_path(payload, cwd)
    execution_num = payload.get("executionNum", 1)

    _append_diagnostic_log(ws, "stop", {"executionNum": execution_num})

    violations: List[str] = []

    # 1. Run git diff check if in a git repo
    try:
        diff_res = subprocess.run(
            ["git", "diff", "HEAD", "--relative"],
            cwd=str(ws),
            capture_output=True,
            text=True,
        )
        diff_text = diff_res.stdout
        if diff_res.returncode != 0:
            diff_res2 = subprocess.run(
                ["git", "diff", "--relative"],
                cwd=str(ws),
                capture_output=True,
                text=True,
            )
            diff_text = diff_res2.stdout

        untracked_res = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(ws),
            capture_output=True,
            text=True,
        )
        if untracked_res.returncode == 0:
            for rel_f in untracked_res.stdout.splitlines():
                rel_f_clean = rel_f.strip()
                if rel_f_clean and (ws / rel_f_clean).is_file():
                    diff_text += f"\n+++ b/{rel_f_clean}\n"
                    diff_text += "\n".join(f"+{ln}" for ln in (ws / rel_f_clean).read_text(encoding="utf-8", errors="ignore").splitlines())

        current_file = ""
        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                continue
            if not line.startswith("+") or line.startswith("+++"):
                continue

            added = line[1:].strip()

            if current_file.startswith("src/"):
                if ("// TODO" in added or "/* TODO" in added) and "TODO(KEEPER-DEBT:" not in added:
                    violations.append(f"Unmarked TODO in {current_file}: '{added}'")
                for construct in DISALLOWED_CONSTRUCTS:
                    if construct in added:
                        violations.append(f"Disallowed construct '{construct}' in {current_file}: '{added}'")

            elif current_file.startswith("include/"):
                if "for (" in added or "while (" in added:
                    violations.append(f"Algorithmic loop in header {current_file}: '{added}'")
                if ("// TODO" in added or "/* TODO" in added) and "TODO(KEEPER-DEBT:" not in added:
                    violations.append(f"Unmarked TODO in {current_file}: '{added}'")

            elif current_file.startswith("tests/") and current_file.endswith((".cpp", ".cc", ".cxx", ".h", ".hpp")):
                if "SKIP_IF" in added or "GTEST_SKIP" in added:
                    violations.append(f"Test skip bypass in {current_file}: '{added}'")
                if "#define private public" in added:
                    violations.append(f"Encapsulation breach in {current_file}: '{added}'")

    except Exception as e:
        pass

    # 2. Check protocol violations in state.json
    state_file = ws / ".keeper" / "state.json"
    if state_file.exists():
        try:
            s_data = json.loads(state_file.read_text(encoding="utf-8"))
            p_violations = s_data.get("protocol_violations", [])
            for pv in p_violations:
                if not pv.get("acknowledged", False):
                    violations.append(f"Protocol Violation in Phase {pv.get('phase_id')}: {pv.get('detail')}")
        except Exception:
            pass

    # 3. Write .keeper/last_turn_diagnostics.md
    diag_file = ws / ".keeper" / "last_turn_diagnostics.md"
    diag_file.parent.mkdir(parents=True, exist_ok=True)
    diag_content = [
        "# KEEPER Turn Diagnostic Report",
        f"- **Execution Number**: {execution_num}",
        f"- **Violation Count**: {len(violations)}",
        "",
    ]
    if violations:
        diag_content.append("## Detected Violations")
        for v in violations:
            diag_content.append(f"- ⚠️ {v}")
    else:
        diag_content.append("✅ No physical violations or protocol breaches detected.")

    diag_file.write_text("\n".join(diag_content) + "\n", encoding="utf-8")

    # 4. Check telemetry for alerting loop prevention
    telemetry_file = ws / ".keeper" / "turn_telemetry.json"
    t_data = {}
    if telemetry_file.exists():
        try:
            t_data = json.loads(telemetry_file.read_text(encoding="utf-8"))
        except Exception:
            t_data = {}

    last_alerted_exec = t_data.get("last_alerted_execution")

    if violations and last_alerted_exec != execution_num:
        t_data["last_alerted_execution"] = execution_num
        telemetry_file.write_text(json.dumps(t_data, indent=2), encoding="utf-8")
        reason_msg = "🚨 KEEPER DIAGNOSTIC ALERT: Disclose the following physical rule deviations to The Overgod before ending your turn:\n" + "\n".join(f"- {v}" for v in violations)
        return {
            "decision": "continue",
            "reason": reason_msg,
        }

    # Reset read counter for next turn and stop
    t_data["read_count"] = 0
    telemetry_file.write_text(json.dumps(t_data, indent=2), encoding="utf-8")
    return {"decision": "stop"}


def main():
    parser = argparse.ArgumentParser(description="KEEPER Lifecycle Hook")
    parser.add_argument(
        "--event",
        choices=["pre_tool_use", "post_tool_use", "stop"],
        required=True,
        help="Hook lifecycle event",
    )
    args = parser.parse_args()

    # Read stdin
    try:
        input_data = sys.stdin.read().strip()
        payload = json.loads(input_data) if input_data else {}
    except Exception as e:
        sys.stderr.write(f"Failed to parse hook JSON input: {e}\n")
        payload = {}

    if args.event == "pre_tool_use":
        res = evaluate_pre_tool_use(payload)
    elif args.event == "post_tool_use":
        res = evaluate_post_tool_use(payload)
    elif args.event == "stop":
        res = evaluate_stop(payload)
    else:
        res = {}

    if res:
        sys.stdout.write(json.dumps(res))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
