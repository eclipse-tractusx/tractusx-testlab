<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8). -->
<!-- It was reviewed and tested by a human committer. -->

# Refactor Plan — Index

This effort is a **structural-only** refactor of the TestLab engine. It changes
*where code lives and how modules are organized* — never *what the code does*. No
behavior, output, or contract changes ship as part of this work.

The detailed plan is [backend-refactor-plan.md](backend-refactor-plan.md); this
page holds the principles, the charter, and the phase-status tracker.

## Objectives & Guiding Principles

**The goal is a deeply modular codebase — not merely "split files over 300 lines."**
Every concern (helpers, serialization, transforms, validation, and their
sub-concerns) becomes a **module in its own right**: a package with a single
nameable responsibility and its own barrel as public surface, nested into
sub-modules within sub-modules wherever a real responsibility seam exists.
Modularity is the objective; file size is only one of several triggers.

1. **Deep modularity by design.** Code is organized into small, single-responsibility
   modules with clear, typed boundaries, nested as deep as real seams require. We
   design for modularity up front — we do not bolt it on after the fact. A cohesive
   file that bundles two responsibilities is two modules, even if it is small.
2. **The 300-line limit is one trigger, not the goal.** Triggers that reveal a
   missing module are: (a) a file bundling more than one responsibility — even well
   under 300 lines; (b) a flat folder whose siblings obviously cluster by concern;
   (c) a file exceeding 300 lines (the loudest, last-resort trigger); (d) the same
   logic appearing twice. We split along responsibility seams — never by arbitrarily
   cutting a file in half.
3. **Single responsibility.** Every module, function, and class does one
   thing. One concern per file; one nameable purpose per module.
4. **No over-engineering (guardrail).** Nest **only** where a real, nameable seam
   exists. Do not create single-function "modules" just to add depth, do not split a
   cohesive unit, and do not invent a folder holding one stray file. The boring,
   readable structure a human can navigate wins over artificial depth.
5. **Data-driven, no hardcoding.** Anything that enumerates options, types, or
   configuration comes from data (registries, config, lookups), never inline
   string literals or hardcoded lists.
6. **Concern-based folders + barrels.** Folders group by *concern*, not by file
   type. Each module exposes a barrel `__init__.py` as its public
   surface; consumers import the barrel, never deep internals. Cross-module
   references inside the same area use direct relative paths to avoid barrel cycles.
7. **Reuse over duplication.** If the same logic appears twice, it is extracted
   into one importable module. Splitting a file must *produce reusable units*, not
   two coupled halves.
8. **NO behavior change.** Every phase is verified green against the
   existing test suite and type checker before and after. A phase that changes a
   test assertion or a generated artifact is out of scope and must be rejected.

## Refactor Charter

These are **non-negotiable directives** from the Chief Architect. They govern every
phase. Any work that violates them is out of scope and must be
rejected — no exceptions.

1. **This is a REFACTOR, not a redesign.** No new features. We change where code
   lives and how it is organized — never what the product does.
2. **Behavior-preserving.** The engine must keep the **same** API contracts, CLI
   surface, runtime behavior, YAML syntax, and compiled package output. Nothing a
   user or an integrator can observe may change.
3. **Stability is paramount.** The product must remain stable throughout. Each phase
   ships green (type check, full test suite) — no
   phase may leave the product in a broken or half-migrated state.
4. **Legacy removal IS allowed and encouraged.** Dead code, unused functions,
   orphaned files, and superseded implementations with **zero importers/callers**
   may be deleted. Deleting unreachable code is behavior-preserving and is part of
   reaching production-ready quality.
5. **Write code like a human programmer, for a human maintainer.** Use descriptive
   names for variables, methods, classes, and types. Keep logic simple, linear, and
   easy to read and understand. The end goal is code a **human** will maintain — if
   an AI writes it so complex, clever, or over-abstracted that a human cannot easily
   understand it, it is wrong. Favor the boring, obvious, readable solution over the
   clever one. Readability and maintainability outrank cleverness, brevity, and
   premature optimization.
6. **End goal: PRODUCTION-READY code** — clean, concise, modular. Same product,
   better internal structure.

### Execution Discipline

How the charter directives above are carried out, phase by phase. These are equally
non-negotiable.

1. **Step by step, but safe.** Move in small, reversible steps. After each step,
   verify the product still passes its type check and tests. Never a big-bang
   rewrite verified only at the end.
2. **Verify before declaring done.** Each phase must prove it changed no
   functionality: a passing contract/test-suite check, with no new failures against
   the baseline.
3. **Parallelize safely.** Running multiple specialist agents in parallel is
   encouraged **only** when their work cannot conflict — disjoint files/folders, no
   unmet dependency, no shared frozen contract. Agents must share knowledge as they
   go — record findings and decisions in shared notes and update the phase-status
   table promptly — so they build on each other instead of duplicating or
   contradicting work.
4. **No over-engineering. Be time-effective.** Do the simplest change that satisfies
   the phase. No speculative abstractions, no "while I'm here" extras. The plan
   defines scope — execute exactly that, efficiently.
5. **Exclude `docs/` from the refactor.** Do not modify or take guidance from the
   existing `docs/` content — it describes the OLD structure and would introduce
   bias. The only documentation that defines the target is the refactor plan in
   `docs/developer/refactor-plan/`. The sole `docs/` files a phase may touch are the
   refactor-plan files themselves (e.g. the phase-status table). Syncing the old docs
   to the new structure is a separate, later task.

## Phase Status

Legend: ⬜ not started · 🟡 in progress · ✅ done

### Backend — see [backend-refactor-plan.md](backend-refactor-plan.md)

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Split `steps/connector/consume.py` → `_dsp_consumer` + `catalog_query` + `dsp/negotiate` + `dsp/transfer`; `consume.py` → barrel | ✅ |
| 2 | Dedup `player/execution/_phase_runners.py` → `execution/phases/` (one `_run_phase` driver + setup/main/teardown wrappers) | ✅ |
| 3 | Isolate `steps/conditions.py` grammar → `_condition_parsing.py`; `conditions.py` orchestration only | ✅ |
| 4 | Dedupe `steps/precondition/policy_config.py` → `_policy_builders.py` (Jupiter/Saturn ODRL) | ✅ |
| 5 | Nest `steps/_checks.py` → `steps/_checks/` (status · equality · json_path · extraction) | ✅ |
| 6 | Nest `compiler/` → `compiler/ir/` + `compiler/validation/` | ✅ |
| 7 | Split `services/manager.py` → `_factory.py` (creation) + `manager.py` (lifecycle) | ✅ |
| 8 | Nest `server/` → `server/routes/` + `server/streaming/` | ✅ |
| 9 | Extract `player/execution/player.py` trace formatting → `_trace_formatter.py` | ✅ |
| 10 | Watch-list guard — record near-limit files in repo memory (no moves) | ✅ |
| 11 | Conditional `models/` nesting (`enums/`, `results/`) — guardrail: cohesive, no split needed | ✅ |

> Phase 1 splits today's at-limit file. Phases 2–9 carry the deep modularization
> across the backend — mixed-concern files and flat packages (steps · compiler ·
> services · server · player) that bundle responsibilities. Phases 10–11 are the
> watch-list guard and a guardrail-gated model nesting. The 300-line rule is one
> trigger; deep modularity is the objective. **Baseline:** the suite carries 20
> known CCM fixture-path failures unrelated to this refactor — a phase is green
> when it adds **no new** failures.
