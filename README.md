# Project KEEPER: Keeping End-to-End Paranoia in Engine Reliability

Project KEEPER is an autonomous, zero-trust engineering framework designed for mission-critical software engines. It shifts the human engineer to the role of **Architectural Arbitrator ("The Overgod")**, while adversarial AI subagents and deterministic verification gauntlets autonomously write specifications, implement logic, attack boundary conditions, and enforce system invariants.

---

## The Two-Tier Invariant Architecture

Project KEEPER operates under a strict two-tier governance model:

1. **Tier 1: Master Constitution ([`codex/AGENTS.md`](codex/AGENTS.md))**:
   - Universal, domain-agnostic operational laws governing agent containment, zero-trust separation of concerns, the Tripartite Governance Model (Executive, Judicial, Legislative branches), verification gates (Gate A / Gate B), dynamic investigation budgets, and execution watchdogs.
2. **Tier 2: Local Domain Codices (`INVARIANTS.md` in Subsystems)**:
   - Specific domain invariants for specialized engineering areas (e.g. typography, GPU pipelines, audio synchronization, database engines).
   - A standardized template for text and typography engines is provided at [`codex/TEXT_DOMAIN.md`](codex/TEXT_DOMAIN.md).

---

## The Distribution Hub (`codex/`)

The [`codex/`](codex/) directory contains the canonical operational codices ready to be deployed to target repositories:

| File / Folder | Tier | Description |
| :--- | :---: | :--- |
| **[`codex/AGENTS.md`](codex/AGENTS.md)** | **Tier 1** | **The Master Constitution**. Copy this file to any project root as `AGENTS.md` to instantly equip it with Project KEEPER rules. |
| **[`codex/TEXT_DOMAIN.md`](codex/TEXT_DOMAIN.md)** | **Tier 2** | **Universal Text Domain Codex**. Standardized invariants for interactive text, complex typography, BiDi selection, and layout. Copy to a text subsystem root as `INVARIANTS.md`. |
| **[`codex/prompts/`](codex/prompts/)** | **Roles** | **Canonical Subagent System Prompts**. The 13 frozen system prompts for all Legislative, Judicial, and Executive roles. |

---

## How to Adopt KEEPER in a New or Existing Project

### Option A: Automated 1-Command Bootstrap (Recommended)
Use the included [`init_keeper.sh`](init_keeper.sh) script to deploy the constitution, subagent prompts, and domain invariants in one step:

```bash
# 1. Standard bootstrap for a standalone project (uses defaults: --link and --domain text):
cd /path/to/my-project
~/Sources/Dungeons/init_keeper.sh

# 2. Subsystem / Monorepo Isolation (Client Zero Pattern):
# When working on a tool/subsystem within a larger monorepo (e.g. Skia, Chromium),
# scope KEEPER strictly to the subsystem directory to keep the monorepo root pristine:
~/Sources/Dungeons/init_keeper.sh /path/to/monorepo/tools/my_subsystem

# 3. Bootstrap a non-text engine (e.g. compiler, database) without text domain invariants:
~/Sources/Dungeons/init_keeper.sh /path/to/my-project --no-domain

# 4. Bootstrap a standalone project with full copies (no symlinks):
~/Sources/Dungeons/init_keeper.sh /path/to/my-project --copy
```

### Option B: Manual Adoption
1. **Deploy Master Constitution**:
   Symlink (or copy) `codex/AGENTS.md` into your project or subsystem root:
   ```bash
   ln -sf ~/Sources/Dungeons/codex/AGENTS.md <your_subsystem>/AGENTS.md
   ```
2. **Deploy Subagent Prompts**:
   Symlink (or copy) the 13 canonical subagent prompts:
   ```bash
   mkdir -p <your_subsystem>/.antigravity/prompts
   for p in ~/Sources/Dungeons/codex/prompts/*.md; do
       ln -sf "$p" "<your_subsystem>/.antigravity/prompts/$(basename "$p")"
   done
   ```
3. **Deploy Local Domain Invariants (Tier 2)**:
   For text, typography, or editor projects, copy the domain template:
   ```bash
   cp ~/Sources/Dungeons/codex/TEXT_DOMAIN.md <your_subsystem>/INVARIANTS.md
   ```
4. **Configure Local Build Toolchain**:
   See [`docs/BUILD_ADAPTERS.md`](docs/BUILD_ADAPTERS.md) for instructions on wiring GN/Ninja, CMake, Cargo, or Bazel into KEEPER's test gauntlet.

---

## Client Zero: The Text Editor Case Study

The foundational proving ground for Project KEEPER was **Client Zero** (`skia/tools/text_editor` in the Skia repository). 

By strictly applying the **Subsystem Isolation Pattern**, `tools/text_editor` operates under KEEPER governance (`AGENTS.md`, `INVARIANTS.md`, and `.antigravity/prompts/` live strictly inside `tools/text_editor/`) without altering, dirtying, or polluting the root of the Google Skia monorepo.

---

## Repository Structure

```
~/Sources/Dungeons/
├── README.md                                     # Project overview, adoption guide, directory map
├── KEEPER_INSTRUCTIONS_FOR_AGENTS.md             # Master Constitution (Root Copy)
├── init_keeper.sh                                # 1-command automated project bootstrapper
│
├── codex/                                        # Canonical Distribution Hub
│   ├── AGENTS.md                                 # Tier 1 Master Constitution
│   ├── TEXT_DOMAIN.md                            # Tier 2 Universal Text Domain Codex
│   └── prompts/                                  # Canonical Subagent System Prompts (13 roles)
│
├── docs/                                         # Architectural Documentation & RFCs
│   ├── BUILD_ADAPTERS.md                         # Wiring GN, CMake, Cargo, Bazel into Gauntlet
│   ├── architecture/
│   │   └── zero_trust_cpp_gauntlet_architecture.md # Foundational Gauntlet Whitepaper
│   └── rfcs/                                     # Architectural Proposals (RFCs)
│
├── .antigravity/                                 # Orchestration & Agent Tooling
│   ├── gauntlet_graph.py                         # Master execution graph
│   └── prompts/                                  # Canonical subagent role prompts
│
├── traps/                                        # Reference Verification Traps (CMake sample)
│   ├── sanitize_matrix.sh                        # Multi-pass sanitizer runner (ASan, TSan, MSan)
│   ├── mutation_gate.py                          # Mutation testing auditor
│   └── cartographer_delta.py                     # Metric delta comparator
│
├── src/                                          # Reference C++ HarfBuzz Engine (CMake sample)
└── tests/                                        # Reference Test Suites
```
