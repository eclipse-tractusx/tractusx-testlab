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

This effort is a **structural-only** refactor of the TestLab codebases. It changes
*where code lives and how modules are organized* — never *what the code does*. No
behavior, output, or contract changes ship as part of this work.

The refactor is split by codebase ownership. Each codebase has its own detailed
plan; this page is the shared contract and status tracker that binds them together.

## Objectives & Guiding Principles

**The goal is a deeply modular codebase — not merely "split files over 300 lines."**
Every concern (hooks, helpers, stores, sync, serialization, transforms, views, and
their sub-concerns) becomes a **module in its own right**: a folder with a single
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
3. **Single responsibility.** Every module, function, hook, and class does one
   thing. One concern per file; one nameable purpose per module.
4. **No over-engineering (guardrail).** Nest **only** where a real, nameable seam
   exists. Do not create single-function "modules" just to add depth, do not split a
   cohesive unit, and do not invent a folder holding one stray file. The boring,
   readable structure a human can navigate wins over artificial depth.
5. **Data-driven, no hardcoding.** Anything that enumerates options, types, or
   configuration comes from data (catalog JSON, config, lookups), never inline
   string literals or hardcoded lists.
6. **Concern-based folders + barrels.** Folders group by *concern*, not by file
   type. Each module exposes a barrel `index.ts`/`__init__.py` as its public
   surface; consumers import the barrel, never deep internals. Cross-module
   references inside the same area use direct relative paths to avoid barrel cycles.
7. **Reuse over duplication.** If the same logic appears twice, it is extracted
   into one importable module. Splitting a file must *produce reusable units*, not
   two coupled halves.
8. **NO behavior or appearance change.** Every phase is verified green against the
   existing test suite and type checker before and after, and (for the IDE) proven
   pixel-identical in the live browser. A phase that changes a test assertion or a
   generated artifact is out of scope and must be rejected.

## Refactor Charter

These are **non-negotiable directives** from the Chief Architect. They govern every
phase in every codebase. Any work that violates them is out of scope and must be
rejected — no exceptions.

1. **This is a REFACTOR, not a redesign.** No new features. We change where code
   lives and how it is organized — never what the product does.
2. **Behavior- AND appearance-preserving.** The IDE must **look** the same and
   **work** the same: identical layout, styling, Blockly theme, panels, and
   interactions. The backend must keep the **same** API contracts, CLI surface,
   runtime behavior, and compiled `.stck` output. Nothing the user or an integrator
   can observe may change.
3. **Stability is paramount.** The product must remain stable throughout. Each phase
   ships green (type check, build, full test suite) and visually unchanged — no
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
   verify the product still builds, still passes tests, and (for the IDE) still
   looks and behaves identically. Never a big-bang rewrite verified only at the end.
2. **Verify before declaring done.** Each phase must prove it changed neither
   appearance nor functionality. For the **backend**, that proof is a passing
   contract/test-suite check. For the **IDE**, a green `tsc`/`vite build` is
   explicitly **not** sufficient: no phase is "done" until the live app has been run
   in a browser, the affected views captured as a BEFORE screenshot set, the real
   interactions exercised, then re-captured AFTER and compared pixel-for-pixel —
   using the `visual-regression-guard` skill. Verify one feature/area at a time: run
   it, confirm it works, refactor it, re-verify it looks and behaves identically,
   THEN move to the next area — never refactor several areas and inspect only at the
   very end. Any visible difference or broken interaction is a regression: fix it,
   never explain it away. A passing build alone never satisfies this gate.
3. **Parallelize safely.** Running multiple specialist agents in parallel is
   encouraged **only** when their work cannot conflict — disjoint files/folders, no
   unmet dependency, no shared frozen contract. Frontend and backend are always safe
   to run together. Agents must share knowledge as they go — record findings and
   decisions in shared notes and update the phase-status table promptly — so they
   build on each other instead of duplicating or contradicting work.
4. **No over-engineering. Be time-effective.** Do the simplest change that satisfies
   the phase. No speculative abstractions, no "while I'm here" extras. The plan
   defines scope — execute exactly that, efficiently.
5. **Exclude `docs/` from the refactor.** Do not modify or take guidance from the
   existing `docs/` content — it describes the OLD structure and would introduce
   bias. The only documentation that defines the target is the refactor plan in
   `docs/developer/refactor-plan/`. The sole `docs/` files a phase may touch are the
   refactor-plan files themselves (e.g. the phase-status table). Syncing the old docs
   to the new structure is a separate, later task.

## Boundary Table — Who Owns What

| Codebase | Owner agent | Root | Detailed plan |
|----------|-------------|------|---------------|
| Frontend IDE | `testlab-ide-master` | `ide/src/` | [ide-refactor-plan.md](ide-refactor-plan.md) |
| Python library | `testlab-master` | `src/tractusx_testlab/` | [backend-refactor-plan.md](backend-refactor-plan.md) |

Neither owner may modify the other codebase. Work that touches both is coordinated
through the shared contracts below.

## Shared Cross-Codebase Contracts

These are the boundaries the two codebases meet at. **Neither side may change them
unilaterally.** A change to any of these is a *contract change*, not a structural
refactor, and is therefore out of scope for this effort — unless it ships in
lockstep across both codebases with coordinated review.

| Contract | Frontend touch point | Backend touch point | Rule |
|----------|----------------------|---------------------|------|
| **YAML v2 syntax** (`@variable`, step shape, phases) | `services/yaml/` (`modelToYaml`, `yamlToModel`) | `authoring/`, `compiler/` parser | Field names, ordering semantics, and variable syntax are frozen. Refactors may relocate the mapping code but must emit byte-identical YAML. |
| **Block catalog schema + `classes.json` taxonomy** | `public/blocks/**`, `blocks/registration/`, `toolbox/` | catalog consumed during compile validation | Block JSON shape, category taxonomy, and param-type names are frozen. Reorganizing loaders/registration must not alter the manifest contract. |
| **TCK env / services manifest model** | `features/environment-editor/`, `store/environment/`, `models/environment.ts` | env/services manifest reader | The manifest field model is frozen. Both sides serialize/deserialize the same shape. |
| **Compiled `.stck` package format** | export feature / compile API client | `compiler/` packager | The package layout and contents are frozen. The frontend only triggers and consumes it. |

**Lockstep rule:** changes to the **serialization ↔ YAML ↔ compiler** boundary
(the chain that turns blocks into YAML into a compiled package) ship together in a
single coordinated change set, reviewed by both `testlab-ide-master` and
`testlab-master`. No partial landing on one side.

## Phase Status

Legend: ⬜ not started · 🟡 in progress · ✅ done

### Frontend — see [ide-refactor-plan.md](ide-refactor-plan.md)

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Remove dead legacy `components/BlockEditor/` tree | ✅ |
| 1 | Split `serialization/serialize/workspaceToModel.ts` (303); outputs organized into nested `serialize/{reader,writer,validation}/` modules (one module per responsibility, no flat dump) | ✅ |
| 2 | Split `hooks/useBlocklyWorkspace.ts` (301→70) into `useBlocklyInit` / `useBlocklyStoreSync` / `useBlocklyResize` + shared `blocklyWorkspaceRefs` (flat hooks per §2 tree); composer returns identical shape — pixel + YAML-hash identical, gates green | ✅ |
| 3 | Dissolve kitchen-sink `serialization/helpers.ts` into `serializationParts/` | ✅ Split into `serializationParts/{workspaceBlockFactory,blockFieldAccessors,valueBlockBuilders,structuralBlockBuilders,assertionChainBuilders}` + barrel; deleted dead `helpers/` folder; YAML + pixel identical |
| 4 | Decompose `populate/populateTest.ts` switch into per-param populators | ✅ Replaced 13-arm `switch (p.type)` with data-driven `paramPopulators/` module (one `<type>ParamPopulator.ts` per param type + `paramPopulatorRegistry.ts` + barrel); `populateTest.ts` 288→209, dispatches via `resolveParamPopulator`; YAML hash-identical (f9ef27da), pixel-identical, console clean |
| 5 | Modularize `serialization/populate/` → nested per-responsibility modules | ✅ Extracted the real 3-file seam into `populate/assertions/` (`assertionPopulators` ← `populateAssertions`, `assertionGrouping`, `assertionNormalization`) + barrel. Per the §2.4 guardrail, `populateFilterExpressions.ts` and `stepOutputTracker.ts` stay as cohesive single-responsibility leaves at `populate/` root — folding each into its own folder would be a banned single-file module. YAML hash-identical (f9ef27da), pixel-identical, console clean |
| 6 | Modularize `block-editor/fields/` → per-field modules (`wrappedText/`, `templateString/`) | ✅ Moved `FieldWrappedText`+`bubblePatch`+`wrappedTextDialog` into `fields/wrappedText/` (git mv, history kept) + barrel; `fields/index.ts` re-exports both module barrels. 5 importers rerouted to the `wrappedText/` module barrel. YAML hash-identical (f25163d4), pixel-identical, console clean |
| 7 | Split `blocks/common/catalog/` → `loader/` + `variables/` | ✅ Moved `variableCollection`+`typedVariableCollection` into `catalog/variables/` module + barrel; `catalogLoader.ts` stays at catalog root (single-file guardrail). Created `catalog/index.ts` barrel re-exporting both. 6 importers rerouted. YAML hash-identical (b3fe9dd4), pixel-identical, console clean. Plan reconciliation: `loader/` folder omitted (would be a banned single-file module) |
| 8 | Remove dead root-level block duplicates (`blocks/catalogBlocks.ts`, `blocks/valueBlocks.ts`) | ✅ Deleted both (246+277 lines, zero importers); superseded by `registration/steps/catalogBlocks.ts` and `registration/values/valueBlocks.ts`. Pixel-identical (SHA1 `9679a85f`), console clean |
| 9 | Modularize `features/environment-editor/` → `services/ variables/ preview/ shared/` | ✅ Moved into `services/` (ServicesSection, ServiceCard, InternalServiceCard, ExternalServiceCard, FieldWithToggle + ServiceCard.css), `variables/` (VariablesSection, VariableRow + VariablesTable.css), `preview/` (YamlPreviewSection, yamlPreview); each module has barrel `index.ts`. Plan reconciliation: `shared/` omitted — FieldWithToggle's only consumers are service cards so it joins `services/` (single-file module guardrail). Screenshot byte-identical (813e04e9), YAML identical, console clean |
| 10 | Modularize `features/tck-dashboard/dataflow/` (18 files) → `graph/ panels/ builder/` | ✅ |
| 11 | Modularize `features/preconditions/` → `modal/ list/ rules/` | ✅ Moved `AddPreconditionModal` into `modal/`, `PreconditionsList`+`PreconditionEditor` into `list/`, `RuleSection`+`ConstraintRow`+`templatePolicies` into `rules/`; each module has barrel `index.ts`. `PreconditionsPanel.tsx` stays at root as composition entry. Import-chain impact internal only. Pixel-identical, console clean |
| 12 | Modularize `features/project-explorer/` → `tree/ contextMenu/ actions/` | ✅ Moved `TreeRow`+`ExplorerHeader`+`useTestDragReorder` into `tree/`, `ExplorerContextMenu`+`ExplorerContextMenuParts`+`explorerContextMenuTypes` into `contextMenu/`, `ExplorerActions` into `actions/`; each module has barrel `index.ts`. `ProjectExplorer.tsx` stays at root as composition entry. Import-chain impact internal only. Pixel-identical, console clean |
| 13 | Modularize `features/yaml-editor/` → `editors/` + `VariablePicker/` + setup | ✅ Moved `MonacoEditor`+`SchemaEditor`+`TestdataEditor`+`TestdataEditorHelpers`(→`testdataEditorTransforms`) into `editors/` module + barrel; `VariablePicker/` kept as own module; `monacoSetup.ts` stays at root. 1 external importer (`EditorPanels`) rerouted to feature barrel. Pixel-identical, console clean |
| 14 | Decompose `models/schema.ts` → `models/schema/` per-concern modules | ✅ Split into `schema/{assertionSchema,phaseSchema,testSchema}` + barrel; 281→73+128+139; all consumers unaffected (barrel surface identical). Pixel-identical, console clean |
| 15 | Modularize `store/selectors/` + tidy slice barrels | ✅ Split `selectors.ts` into per-domain modules (`variableSelectors`, `testSelectors`); renamed `helpers.ts` → `storeBuilders.ts` (descriptive); barrel surface unchanged. All 7 slice folders confirmed with own barrel. Pixel-identical, console clean |
| 16 | Move pure project I/O from `store/project/` to `services/project/` | ✅ Created `services/project/` module (6 files): `projectImportExport`, `projectExportTransforms`, `exampleProjectLoader`, `projectImportTransforms`, `projectFilePersistence`, `projectDocumentParser` + barrel. Moved `SchemaFile`/`TestdataFile`/`ActiveFile` types to `models/project.ts`. Store persistence now delegates to service layer. Deleted dead `documentLoader.ts`. Layer compliance verified: services/ imports only models/, store/ imports services/. YAML hash byte-identical, pixel-identical, console clean |
| 17 | Centralize model↔YAML field mapping (de-dup `modelToYaml`/`yamlToModel`) | ✅ |
| 18 | Descriptive-name sweep (remaining generic file names) | ✅ Renamed 9 files: `store/types`→`store.types`, `bottom-panel/types`→`bottomPanel.types`, `workspaceTypes`→`blocklyWorkspace.types`, `graphHelpers`→`dependencyGraphNodeBuilders`, `assertionHelpers`→`assertionBlockResolvers`, `validationHelpers`→`validationBlockReaders`, `builder/constants`→`dataspaceOptions`, `builder/types`→`pipelineGraph.types`, `templateString/types`→`templateSegment.types`. All importers updated. Pixel-identical, console clean |
| 19 | Consolidate all styling into SCSS under `assets/styles/` | ✅ Full. Pass 1: renamed 67 `.css`→`.scss`, scaffold. Pass 2 (19b): migrated all 67 co-located SCSS into centralized `assets/styles/{base,layout,components,features}/` partials, wired `main.scss` as sole entry (imported in `app/main.tsx`), removed all co-located imports, deleted all co-located `.scss` files. Zero `.scss`/`.css` outside `assets/styles/`. Pixel-identical, build clean |
| 20 | Enforce barrels + naming + style guards (lint) | ✅ Created missing barrels (`shared/index.ts`, `features/index.ts`). Rewrote all 67 deep `@/store/*/…` imports in features/ and layout/ to use `@/store` barrel. Fixed layout→feature deep paths to use feature barrels. Added `ActiveFile` type to `store/project/` barrel. Installed ESLint + `typescript-eslint`, configured `no-restricted-imports` to ban `@/store/*/*` and `@/features/*/*` patterns. Added `VariablePicker`/`TestdataVariableButton` to `yaml-editor` barrel. Zero lint violations, pixel-identical, console clean |

> Phases 0–4 split today's oversized/at-limit files. Phases 5–15 carry the deep
> modularization across the rest of the frontend — flat feature folders and
> sub-300 files that bundle responsibilities. Phases 16–17 cross layer/contract
> boundaries (done late, in lockstep where flagged). Phases 18–20 are renames,
> styling, and the lint guard that locks in the structure.

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
