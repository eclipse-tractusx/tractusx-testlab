<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Catena-X Automotive Network e.V.
 Copyright (c) 2026 Contributors to the Eclipse Foundation

 Licensed under the Creative Commons Attribution 4.0 International License
 (the "License"); you may not use this file except in compliance with the
 License. You may obtain a copy of the License at

    https://creativecommons.org/licenses/by/4.0/

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 SPDX-License-Identifier: CC-BY-4.0
-->

# Backend Refactor Plan — `src/tractusx_testlab/`

> All phases obey the Refactor Charter in [README.md](./README.md) — structural-only, no new features, same API contracts / CLI / runtime behavior / `.stck` output, stable throughout, legacy/dead code removal allowed, end goal production-ready (clean, concise, modular).

> **Scope:** structural-only. No behavior, no contract, no `.stck`/CLI/API change.
> Every phase ends green on the test suite and type/lint checks. See
> [README.md](./README.md) for the charter and the phase-status tracker.

The backend already has a clean **layered** package layout (`models/ · services/ ·
steps/ · compiler/ · player/ · server/ · …`) and zero files over 300 lines. This
plan now drives that architecture all the way down: **every concern becomes a
module in its own right, nested as deep as real responsibility seams require.**

---

## 0. Objective — a deeply modular backend

**The goal is a deeply modular backend, not merely "split files over 300 lines."**

Every concern — step domains, compile passes, IR assembly, validation rules,
expression grammar, server routes, streaming, model groups, and service wiring —
becomes a **module in its own right**: a package with a single nameable
responsibility, its own barrel (`__init__.py`) as public surface, and freedom to
nest into **sub-packages within sub-packages** wherever a real seam exists.
Modularity is the objective; file size is only one of several triggers that reveal
where modularity is missing.

**Triggers that signal a module is needed** (any one is sufficient):

1. **A file bundles more than one nameable responsibility** — even well under 300
   lines. A 180-line module that holds an orchestrator *plus* its grammar regexes
   *plus* parse helpers is three modules wearing one filename.
2. **A package is a flat dump of siblings** that obviously cluster by concern (e.g.
   one `compiler/` folder mixing IR assembly, lowering passes, and validation
   rules that are really *ir/* + *validation/* sub-packages).
3. **A file exceeds 300 lines** — the loudest trigger, but the *last* one to rely
   on. By the time a module is oversized, the missing seams are already obvious.
4. **The same logic appears twice** (e.g. three phase loops re-implementing one
   per-step iteration) — extract it into one importable module.

**This plan therefore covers the whole backend**, not only today's near-limit
files. Sub-300 modules and flat packages that bundle responsibilities are
modularized too.

### Guardrail — no over-engineering (non-negotiable)

Nest **only** where a real, nameable responsibility seam exists. Each module must
have a single nameable purpose and a minimal public surface. **Do not** create a
single-function "module" just to add depth, do not split a cohesive unit, and do
not invent a package that holds one stray file with no sibling concern (unless the
§2 tree defines that seam). A private helper used by exactly one module stays a
`_helper.py` next to its caller — it does not become a package. The boring,
readable structure a human can navigate always wins over artificial depth.

### Doctrine — behavior + contract unchanged

Modularization is **purely structural**. No phase changes runtime behavior, the
compiled `.stck` output, the CLI surface, the HTTP API, or any observable contract.
Every phase is a **pure move + barrel re-export** — public import paths
(`from tractusx_testlab... import ...`) are preserved, tests are unchanged, and the
`@step(...)` registry resolves every moved step type as before. The 300-line
acceptance check in §6 remains, but it is a **floor**, not the target — passing it
does not mean a package is modular.

> **Baseline note (test suite):** there is a known set of **20 pre-existing CCM
> fixture-path failures** (`test_ccm_compile_all.py`, `test_ccm_integration_parsing.py`)
> caused by concurrent `docs/examples` renames and an empty `tests/fixtures/` — they
> are **unrelated to this refactor** and out of scope here. A phase is "green" when
> it introduces **no new** failures beyond this baseline.

---

## 1. Current-State Assessment

The backend is **already layered and healthy** — but layering is not the same as
deep modularity. Several packages are still **flat dumps** of single-concern files
that should cluster into sub-packages, and a few modules **bundle two
responsibilities** under one filename. Those are the seams this plan targets.
Baseline metrics (verified 2026-05-29):

| Metric | Result |
|--------|--------|
| Files exceeding 300 lines | **0** |
| `except Exception` / bare `except:` | **0** |
| `print(` (excluding `_fingerprint`) | **0** |
| Layered package layout | Intact (12 top-level layers) |

This is **not** a rescue refactor — the layers are sound. But "no file over 300
lines" is a **floor, not the goal**. The work below makes the backend *deeply*
modular: flat single-concern packages gain sub-packages along real seams, and the
handful of files that bundle two responsibilities split into focused modules. The
near-limit files are simply the loudest of these triggers.

### 1a. Near-limit watch list (actual line counts)

These files are within ~40 lines of the 300 limit. They are the **loudest**
trigger, but not the only one — several already double as multi-responsibility
modules (§1b/§1c).

| File | Lines | Status |
|------|------:|--------|
| [compiler/_ir_helpers.py](../../../src/tractusx_testlab/compiler/_ir_helpers.py) | 299 | Split into `compiler/ir/` (Phase 6) |
| [server/streaming.py](../../../src/tractusx_testlab/server/streaming.py) | 298 | Split into `server/streaming/` (Phase 8) |
| [player/execution/player.py](../../../src/tractusx_testlab/player/execution/player.py) | 298 | Extract trace/result formatting (Phase 9) |
| [compiler/ir_builder.py](../../../src/tractusx_testlab/compiler/ir_builder.py) | 278 | Split into `compiler/ir/` (Phase 6) |
| [server/routes.py](../../../src/tractusx_testlab/server/routes.py) | 271 | Split into `server/routes/` (Phase 8) |
| [steps/conditions.py](../../../src/tractusx_testlab/steps/conditions.py) | 267 | Grammar isolation (Phase 3) |
| [player/loading/_parser.py](../../../src/tractusx_testlab/player/loading/_parser.py) | 267 | Watch (Phase 10 watch-list) |
| [services/manager.py](../../../src/tractusx_testlab/services/manager.py) | 262 | Split factory vs lifecycle (Phase 7) |
| [cli/compile.py](../../../src/tractusx_testlab/cli/compile.py) | 260 | Watch (Phase 10 watch-list) |
| [steps/_checks.py](../../../src/tractusx_testlab/steps/_checks.py) | 213 | Split into `steps/_checks/` (Phase 5) |

### 1b. Multi-responsibility files (below the limit, but bundling concerns)

These are not near the limit, but mix two concerns under one roof. Extracting the
secondary concern improves reuse and testability without changing behavior.

- **[steps/connector/consume.py](../../../src/tractusx_testlab/steps/connector/consume.py)** — *(✅ Phase 1, done)* split into `_dsp_consumer.py` + `catalog_query.py` + `negotiate.py` + `transfer.py`; `consume.py` is now a barrel.
- **[player/execution/_phase_runners.py](../../../src/tractusx_testlab/player/execution/_phase_runners.py)** (180 lines) — `execute_setup_steps`, `execute_main_steps`, `execute_teardown_steps` each re-implement the same per-step loop (monitor → condition gate → resolve step class → run → collect). *(Phase 2)*
- **[steps/conditions.py](../../../src/tractusx_testlab/steps/conditions.py)** — `ConditionEvaluator` plus **eight** module-level compiled regexes and parsing free-functions for the `${{ ... }}` / legacy `${ }` expression grammar. *(Phase 3)*
- **[steps/precondition/policy_config.py](../../../src/tractusx_testlab/steps/precondition/policy_config.py)** — `_build_jupiter_policy` and `_build_saturn_policy` are two version-specific ODRL body builders embedded next to the step class. *(Phase 4)*
- **[steps/_checks.py](../../../src/tractusx_testlab/steps/_checks.py)** (213) — bundles distinct check families (status/equality/JSONPath/schema) that the assertion + condition steps share; cluster into a `steps/_checks/` package. *(Phase 5)*
- **[services/manager.py](../../../src/tractusx_testlab/services/manager.py)** (262) — service **factory/creation** wiring mixed with **lifecycle** (start/stop/own) management. *(Phase 7)*
- **[player/execution/player.py](../../../src/tractusx_testlab/player/execution/player.py)** (298) — orchestration mixed with result/execution-trace **formatting**; extract the formatter. *(Phase 9)*

### 1c. Flat packages that should nest (deep-modularity targets)

These packages are **single-layer dumps** whose files obviously cluster by
sub-concern. Each becomes a small set of nested sub-packages along the seam — the
core of the deep-modularity goal beyond the oversized-file triggers.

| Package | Today (flat) | Real sub-concerns → sub-packages | Phase |
|---------|--------------|----------------------------------|:-----:|
| `compiler/` | 10 sibling files (orchestrator + IR assembly + lowering + validation + assets + expressions + fingerprint) | `ir/` (builder, helpers, assets, lowering) · `validation/` (validator, rules, expressions) · top-level orchestrator/packager/fingerprint | 6 |
| `server/` | 9 sibling files (app + routes + compile + callbacks + streaming + buffer + registry + storage) | `routes/` (route groups: compile/run/callback) · `streaming/` (SSE formatter + lifecycle + buffer) · top-level app/storage/registry | 8 |
| `models/` | 8 flat domain files | keep flat **unless** a file bundles groups: `enums.py` (service/phase/state enum families) and `results.py` (step + assertion + trace results) are the only nest candidates → `enums/`, `results/` | 11 |
| `authoring/` | test + parser + registry + `_builders` | builders cluster (`_builders.py`) → `_builders/` only if it grows; otherwise leave — **guardrail check** | 10 (watch) |

> **Guardrail reminder:** `config/`, `logging/`, `syntax/`, `security/crypto`,
> `security/trust`, `services/participants.py`, and the already-nested `player/`,
> `steps/connector|industry|precondition|utility|server|pull_data` packages are
> **already correctly modular** — they are explicitly **out of scope**. Do not nest
> them further; there is no real seam to add.

---

## 2. Target Architecture

The layered structure is **confirmed**. This section defines the **complete nested
end-state** the migration phases (§4) converge to — not just the top-level layers,
but every meaningful sub-package down to the responsibility seam. Items marked
**(new)** are introduced by a phase; everything else exists today. Each directory
owns one concern and exposes its public surface via a barrel `__init__.py`.

### 2.1 Layering & import rules (apply at every depth)

The runtime imports between the top-level packages are:

```
syntax, models, contracts   leaves: no imports from other testlab packages
infrastructure ─▶ models, syntax
config         ─▶ infrastructure, models
security       ─▶ models
logging        ─▶ models
services       ─▶ models, syntax                          (SDK service wiring)
authoring      ─▶ models, syntax, steps                   (registry, parser, step docs)
steps          ─▶ authoring, logging, models, syntax, server.mock_registry
compiler       ─▶ authoring, infrastructure, models, steps, syntax
player         ─▶ authoring, compiler, config, contracts, infrastructure,
                  logging, models, security, server, services, steps, syntax
server         ─▶ authoring, compiler, config, models, player, syntax
cli            ─▶ authoring, compiler, config, infrastructure, logging,
                  models, player, security, syntax        (`serve` loads server by import string)
```

The graph has two cycles, both resolved with deferred imports: `authoring` ↔ `steps`
(steps register through `authoring.registry.step`; the step reference renderer reads
`BaseStep` contracts) and `player` ↔ `server` (the server app owns a `TestlabPlayer`;
the player uses the callback manager and mock registry and starts the app in-process
for CLI runs).

Rules that hold across the graph:

- **`steps/` is the keystone** — it is imported by `compiler` (to check `uses:`,
  `with:`, `returns:` and `validate:` against the declared contracts) and by `player`
  (for execution). A step refers to `StepContext` from `player` only under
  `TYPE_CHECKING`, and reaches the server only through `server.mock_registry`
  (mock and wait steps); it never imports `cli/`.
- **`models/` holds no behavior** — only Pydantic data, enums, exceptions. Anything
  with logic belongs in `services`, `steps`, `compiler`, or `player`.
- **`__init__.py` is a barrel only** at every level — it re-exports the package's
  public surface and contains **no logic**. Sub-packages re-export their leaves so
  callers import `from ...steps.connector import QueryCatalogStep`, never the file.
- **Private helpers** (`_*.py`) are package-internal — never re-exported through the
  barrel, never imported across package boundaries.

### 2.2 Complete nested tree

```
tractusx_testlab/
  __init__.py                      # top barrel — public package surface only
  __main__.py                      # `python -m tractusx_testlab` → cli entrypoint

  cli/                             # Typer command groups — thin; delegate, never compute
    __init__.py                    #   barrel: assembles `app` via add_typer(...)
    compile.py                     #   `testlab compile` — calls compiler/, no IR logic here
    run.py                         #   `testlab run` — calls player/, no execution logic here
    validate.py                    #   `testlab validate` — calls compiler validator only
    serve.py                       #   `testlab serve` — boots server/app
    keys.py                        #   `testlab keys` — calls security/crypto

  compiler/                        # COMPILE-TIME: YAML → IR → validation → package
    __init__.py                    #   barrel: Compiler, Validator, Packager
    compiler.py                    #   orchestrator: drives build → validate → package
    packager.py                    #   IR → `.stck` package on disk
    _fingerprint.py                #   (priv) deterministic package fingerprint
    ir/                            #   (new, Phase 6) IR assembly + lowering
      __init__.py                  #     barrel: build_ir entrypoint
      builder.py                   #     YAML doc → IR  (was ir_builder.py, 278L)
      _helpers.py                  #     (priv) IR node assembly helpers (was _ir_helpers.py, 299L)
      _assets.py                   #     (priv) asset-node IR construction (was _assets.py)
      _compilation.py              #     (priv) IR lowering passes (was _ir_compilation.py)
    validation/                    #   (new, Phase 6) IR → diagnostics
      __init__.py                  #     barrel: Validator (public validation entrypoint)
      validator.py                 #     orchestrates rules → diagnostics (was validator.py)
      _rules.py                    #     (priv) individual validation rules (was _validation.py)
      _expressions.py              #     (priv) compile-time expression checks (see §3 grammar)

  contracts/                       # LEAF: Protocols stating what the engine requires of SDK services

  infrastructure/                  # typed infrastructure bindings (sut / engine sides), config/env/${{ }} forms

  config/                          # configuration loading & settings (data + I/O only)
    __init__.py                    #   barrel: ConfigLoader, settings types
    loader.py                      #   read/merge config sources → TestlabConfig
    settings.py                    #   Pydantic settings models (no behavior)

  logging/                         # structured logging — cross-cutting, depends only on models
    __init__.py                    #   barrel: StructuredLogger / get_logger
    structured.py                  #   JSON/structured log formatter + adapter

  models/                          # Pydantic DATA ONLY — no behavior, no I/O
    __init__.py                    #   barrel: all public models/enums/exceptions
    exceptions.py                  #   TestLabError hierarchy (Compilation/Execution/...)
    definitions.py                 #   step/TCK definition models
    jobs.py                        #   JobStatus and job lifecycle models
    preconditions.py               #   precondition declaration models
    security.py                    #   key/identity/trust data models
    server.py                      #   mock-server request/response models
    enums/                         #   (new, Phase 11 — only if seam holds) enum families
      __init__.py                  #     barrel: all enums
      service.py                   #     ServiceState, ServiceType
      phases.py                    #     phase/lifecycle enums
    results/                       #   (new, Phase 11 — only if seam holds) result models
      __init__.py                  #     barrel: all result models
      step.py                      #     step + assertion result models
      trace.py                     #     execution-trace models

  player/                          # RUN-TIME: load → execute → track jobs
    __init__.py                    #   barrel: TestlabPlayer, job API
    jobs.py                        #   in-flight job registry + status tracking

    loading/                       #   run-time YAML/package → executable test
      __init__.py                  #     barrel: loader public surface
      loader.py                    #     package/YAML → Test object
      _parser.py                   #     (priv) YAML → raw structures   [watch: 267L]
      _constants.py                #     (priv) loader keys/defaults
      ordering.py                  #     phase/step ordering (setup→main→teardown)
      resolver.py                  #     variable/@ref + dependency resolution

    execution/                     #   the step-execution engine
      __init__.py                  #     barrel: player, context, monitor
      player.py                    #     orchestration: runs phases via phases/  [Phase 9]
      _trace_formatter.py          #     (new, Phase 9) result/execution-trace formatting
      context.py                   #     StepContext — per-run state container (data)
      monitor.py                   #     ExecutionMonitor — progress/event emission
      step_runner.py               #     single-step driver: resolve → run → collect outputs
      preconditions.py             #     precondition evaluation gate before main phase
      mock_server.py               #     run-time mock-server lifecycle hook
      _helpers.py                  #     (priv) shared execution utilities
      _phase_runners.py            #     (priv) phase loops → refactored to one _run_phase
      phases/                      #     (new, Phase 2) one driver, thin phase wrappers
        __init__.py                #       barrel: run_setup/run_main/run_teardown
        _run_phase.py              #       (new) shared async per-step loop (single source)
        setup.py                   #       (new) setup wrapper: stop-on-fail + gate
        main.py                    #       (new) main wrapper: stop-on-fail + gate
        teardown.py                #       (new) teardown wrapper: runs unconditionally

  authoring/                       # test object model + builder DSL (author-facing)
    __init__.py                    #   barrel: Test, registry, builders
    test.py                      #   Test aggregate (phases, steps, metadata)
    parser.py                      #   author YAML → Test
    registry.py                    #   step-type registry lookup
    _builders.py                   #   (priv) fluent builder helpers

  security/                        # crypto + trust (logic over models/security.py)
    __init__.py                    #   barrel: keygen, signing, trust public API
    crypto/                        #   cryptographic primitives
      __init__.py                  #     barrel: keygen/sign/encrypt entrypoints
      keygen.py                    #     key generation + fingerprint
      signing.py                   #     sign/verify operations
      encryption.py                #     encrypt/decrypt operations
    trust/                         #   identity & trust-store management
      __init__.py                  #     barrel: identity, trust store, vault
      identity.py                  #     participant identity handling
      trust_store.py               #     trusted-key/cert store
      vault.py                     #     secret/key vault access

  server/                          # FastAPI mock server + compile/run HTTP surface
    __init__.py                    #   barrel: app factory, CallbackManager, storage
    app.py                         #   FastAPI app factory + wiring
    mock_registry.py               #   registered mock-route table
    storage.py                     #   PackageStorage — package persistence
    routes/                        #   (new, Phase 8) route handlers grouped by surface
      __init__.py                  #     barrel: register_routes(app)
      compile.py                   #     compile endpoint handler (was server/compile.py)
      callbacks.py                 #     inbound callback/input endpoints (was callbacks.py)
      mock.py                      #     mock/run route handlers (was routes.py, 271L)
    streaming/                     #   (new, Phase 8) SSE streaming
      __init__.py                  #     barrel: SSE stream public surface
      lifecycle.py                 #     connection open/close/keepalive (was streaming.py, 298L)
      formatter.py                 #     (new) event → SSE wire formatting
      _event_buffer.py             #     (priv) SSE event ring buffer (was _event_buffer.py)

  services/                        # SDK SERVICE WIRING + lifecycle (no protocol reimpl)
    __init__.py                    #   barrel: ServiceManager, participant API
    manager.py                     #   ServiceManager facade: owns lifecycle  [Phase 7]
    _factory.py                    #   (new, Phase 7) SDK connector/discovery/AAS creation
    participants.py                #   participant ↔ service mapping & config

  steps/                           # STEP EXECUTORS — one domain per sub-package
    __init__.py                    #   barrel: BaseStep, @step registry, all step types
    base.py                        #   BaseStep ABC + @step decorator/registry
    assertions.py                  #   assertion evaluation steps
    conditions.py                  #   ConditionEvaluator orchestration only  [Phase 3]
    _condition_parsing.py          #   (new, Phase 3) regex grammar + _evaluate_* helpers
    _checks/                       #   (new, Phase 5) shared check primitives by family
      __init__.py                  #     barrel: all check primitives (was _checks.py, 213L)
      status.py                    #     status/outcome checks
      equality.py                  #     equality/comparison checks
      json_path.py                 #     JSONPath validation (was _json_path_validation.py)
      extraction.py                #     JSONPath/value extraction (was _path_extraction.py)

    connector/                     #   EDC connector / DSP domain steps
      __init__.py                  #     barrel: all connector step classes
      consume.py                   #     → barrel re-export after split  [Phase 1]
      _dsp_consumer.py             #     (new, Phase 1) _DspConsumer helper
      catalog_query.py             #     (new, Phase 1) the 3 QueryCatalog* steps
      catalog_filter.py            #     catalog filter-expression step
      provision.py                 #     provider-side asset provisioning step
      extract.py                   #     dataplane/EDR extraction step
      dataplane.py                 #     dataplane GET step
      cleanup.py                   #     connector teardown/cleanup step
      utils.py                     #     connector-step shared utilities
      dsp.py                       #     → barrel re-export for dsp/ subpackage
      dsp/                         #     low-level DSP protocol steps (one verb/file)
        __init__.py                #       barrel: dsp step classes
        version.py                 #       DSP version-negotiation step
        catalog.py                 #       DSP catalog request step
        negotiate.py               #       DSP contract-negotiation step
        transfer.py                #       DSP transfer step
        resolve.py                 #       DSP endpoint/EDR resolve step
        generic.py                 #       generic DSP request step
        _constants.py              #       (priv) DSP context/property keys

    industry/                      #   Industry / AAS / DTR domain steps
      __init__.py                  #     barrel: industry step classes
      dtr.py                       #     Digital Twin Registry steps
      submodels.py                 #     submodel CRUD steps
      semantic.py                  #     semantic-model steps
      notification.py              #     notification (EDC/industry) steps

    precondition/                  #   precondition setup steps (idempotent config)
      __init__.py                  #     barrel: precondition step classes
      asset_config.py              #     asset precondition step
      contract_config.py           #     contract precondition step
      policy_config.py             #     policy step class only  [Phase 4]
      _policy_builders.py          #     (new, Phase 4) Jupiter/Saturn ODRL builders

    pull_data/                     #   data-pull domain steps
      __init__.py                  #     barrel: pull-data step(s)
      _executor.py                 #     (priv) pull execution helper
      _constants.py                #     (priv) pull keys/defaults

    server/                        #   mock-server-facing steps
      __init__.py                  #     barrel: mock/wait steps
      mock.py                      #     register-mock step
      wait.py                      #     wait-for-callback step

    utility/                       #   pure helper/value steps (no external I/O)
      __init__.py                  #     barrel: utility step classes
      uuid_gen.py                  #     auto-generate UUID step
      variables.py                 #     set/transform variable step
      json_extract.py              #     extract value from JSON step
      load_schema.py               #     load JSON schema step

  syntax/                          # LEAF: default syntax constants — no testlab imports
    __init__.py                    #   barrel: defaults, keys, patterns, context vars
    defaults.py                    #   default syntax values
    keys.py                        #   canonical key names
    patterns.py                    #   regex/token patterns (grammar tokens)
    context_vars.py                #   built-in context variable names

  schemas/                         # packaged JSON schemas (data assets, no code)
    __init__.py                    #   barrel / package marker
```

> **Note on `schemas/`:** holds shipped JSON-schema assets (resources), not Python
> logic. It stays a flat data package — no nesting needed.

### 2.3 Where the structure changes (seam, not arbitrary cut)

Every change below extracts a **reusable** unit along a responsibility seam (detail
in §3/§4) — never an arbitrary line-count cut:

**Mixed-concern file splits:**
- `steps/connector/consume.py` (5 steps + helper) → `_dsp_consumer.py` + `catalog_query.py`
  + `dsp/negotiate.py` + `dsp/transfer.py`; `consume.py` becomes a barrel. *(✅ Phase 1)*
- `player/execution/_phase_runners.py` (3 near-identical loops) → `execution/phases/`
  with one `_run_phase.py` driver and thin `setup/main/teardown` wrappers. *(Phase 2)*
- `steps/conditions.py` (orchestration + grammar) → `_condition_parsing.py` (grammar)
  + `conditions.py` (orchestration only). *(Phase 3)*
- `steps/precondition/policy_config.py` (step + 2 builders) → `_policy_builders.py`. *(Phase 4)*
- `services/manager.py` (factory + lifecycle) → `_factory.py` + `manager.py` facade. *(Phase 7)*
- `player/execution/player.py` (orchestration + trace formatting) → `_trace_formatter.py`. *(Phase 9)*

**Flat-package → nested sub-packages:**
- `steps/_checks.py` (+ `_json_path_validation.py`, `_path_extraction.py`) → `steps/_checks/`
  (status / equality / json_path / extraction). *(Phase 5)*
- `compiler/` flat → `compiler/ir/` (builder + helpers + assets + lowering) and
  `compiler/validation/` (validator + rules + expressions). *(Phase 6)*
- `server/` flat → `server/routes/` (compile / callbacks / mock groups) and
  `server/streaming/` (lifecycle + formatter + buffer). *(Phase 8)*
- `models/enums.py` → `models/enums/`; `models/results.py` → `models/results/` —
  **only if** the families are genuinely separable (guardrail check at execution). *(Phase 11)*

### Layer-boundary notes (blur to watch, not fix-now)

- **`steps/execution` import direction:** `_phase_runners.py` imports `run_step` /
  `store_step_outputs` from `step_runner` via **function-local imports** to dodge a
  circular import. This is a smell, but resolving it means re-ordering module
  dependencies — out of scope for a structural-only pass. Document it; do not
  rewire it now.
- **`compiler` ↔ `player/loading`:** both parse YAML-ish input (`ir_builder` /
  `_ir_helpers` vs `loading/_parser`). The boundary is correct (compile-time vs
  run-time), but the **expression/condition grammar** is the one rule set that
  must stay single-sourced (see Phase 3) to avoid drift between compile validation
  and runtime evaluation.

No layer needs to be created, merged, or moved.

---

## 3. Module / Responsibility Map

| Module | Current responsibility | Proposed split (seam) |
|--------|------------------------|-----------------------|
| `steps/connector/consume.py` *(✅ done)* | DSP consumer helper + 5 step classes | `_dsp_consumer.py` + `catalog_query.py` + `dsp/negotiate.py` + `dsp/transfer.py`; barrel re-export |
| `player/execution/_phase_runners.py` | 3 near-identical phase loops | Extract shared `async _run_phase(...)`; setup/main/teardown become thin wrappers in `execution/phases/` |
| `steps/conditions.py` | `ConditionEvaluator` + regex grammar + parse helpers | `_condition_parsing.py` (regexes + `_evaluate_*`); `conditions.py` keeps orchestration only |
| `steps/precondition/policy_config.py` | step class + Jupiter/Saturn policy builders | `_policy_builders.py` (both builders + shared ODRL scaffolding); step class stays |
| `steps/_checks.py` (+ `_json_path_validation`, `_path_extraction`) | 4 check families in flat files | `steps/_checks/` package: `status.py` · `equality.py` · `json_path.py` · `extraction.py` |
| `compiler/` (10 flat files) | orchestrator + IR + validation mixed at one level | `compiler/ir/` (builder/helpers/assets/compilation) + `compiler/validation/` (validator/rules/expressions); orchestrator + packager + fingerprint stay top-level |
| `services/manager.py` (262) | SDK service **creation** + **lifecycle** | `_factory.py` (create connector/discovery/AAS) + `manager.py` facade (own/start/stop) |
| `server/` (9 flat files) | app + route groups + SSE + storage mixed | `server/routes/` (compile/callbacks/mock) + `server/streaming/` (lifecycle/formatter/buffer); app/storage/registry stay top-level |
| `player/execution/player.py` (298) | orchestration + trace/result formatting | extract `_trace_formatter.py`; `player.py` keeps orchestration |
| `models/enums.py`, `models/results.py` | bundled enum/result families | `models/enums/`, `models/results/` **only if** families separate cleanly (guardrail check) |
| `player/loading/_parser.py` (267), `cli/compile.py` (260), `authoring/_builders.py` | near-limit / cohesive | **Watch only** (Phase 10) — split-first rule on next feature touch; no move now |

---

## 4. Migration Phases (leaf-first, deep modularity)

Ordered so each step is independent and leaf-first (no module is split before its
dependents are stable). Every phase is a **pure move + barrel re-export** — public
import paths preserved, tests unchanged, `@step(...)` registry unaffected. Phases
1–4 split the mixed-concern files; phases 5–9 carry deep modularity across the rest
of the backend (flat packages and bundled responsibilities); phases 10–11 are the
watch-list guard and the conditional model nesting.

#### Phase ordering & status

| # | Phase | Target (seam) | Priority | Status |
|---|-------|---------------|:--------:|:------:|
| 1 | `consume.py` split | `_dsp_consumer.py` + `catalog_query.py` + `dsp/negotiate.py` + `dsp/transfer.py`; `consume.py` → barrel | P1 | **Done** ✅ |
| 2 | `_phase_runners.py` dedup | `execution/phases/` — one `_run_phase` driver + thin setup/main/teardown wrappers | P1 | **Done** ✅ |
| 3 | `conditions.py` grammar isolation | `_condition_parsing.py` (regexes + `_evaluate_*`); `conditions.py` orchestration only | P2 | **Done** ✅ |
| 4 | `policy_config.py` dedupe | `_policy_builders.py` (Jupiter/Saturn ODRL builders) | P2 | **Done** ✅ |
| 5 | `steps/_checks/` package | nest check families: `status` · `equality` · `json_path` · `extraction` | P2 | **Done** ✅ |
| 6 | `compiler/` nesting | `compiler/ir/` (builder/helpers/assets/compilation) + `compiler/validation/` (validator/rules/expressions) | P2 | **Done** ✅ |
| 7 | `services/manager.py` split | `_factory.py` (SDK service creation) + `manager.py` lifecycle facade | P2 | **Done** ✅ |
| 8 | `server/` nesting | `server/routes/` (compile/callbacks/mock) + `server/streaming/` (lifecycle/formatter/buffer) | P2 | **Done** ✅ |
| 9 | `player/execution/player.py` split | extract `_trace_formatter.py`; `player.py` keeps orchestration | P3 | **Done** ✅ |
| 10 | Watch-list guard | no moves — record watch list (`_parser.py`, `cli/compile.py`, `_builders.py`) in repo memory | P3 | **Done** ✅ |
| 11 | `models/` conditional nesting | `models/enums/`, `models/results/` — guardrail: cohesive, no split needed | P3 | **Done** ✅ |

### Phase 1 — `steps/connector/consume.py` (P1, at limit) ✅
1. Create `steps/connector/_dsp_consumer.py`; move `_DspConsumer`.
2. Create `steps/connector/catalog_query.py`; move the three `QueryCatalog*` steps.
3. Move `NegotiateContractStep` → `negotiate.py`, `TransferDataStep` → `transfer.py`.
4. Turn `consume.py` (or `connector/__init__.py`) into a barrel re-export so the
   `@step(...)` registry and existing imports resolve unchanged.
5. `pytest -x -q` — connector + integration suites green. **(done; no new failures)**

### Phase 2 — `player/execution/_phase_runners.py` (P1, dedup)
1. Create `player/execution/phases/` with `_run_phase.py` holding one private
   `async _run_phase(*, test, phase, stop_on_failure, gate_conditions, ...)`.
2. Add thin `setup.py` / `main.py` / `teardown.py` wrappers configuring policy
   (setup & main stop on failure + gate on `if_condition`; teardown unconditional);
   `phases/__init__.py` re-exports `run_setup` / `run_main` / `run_teardown`.
3. Keep the existing function-local `step_runner` imports (do not rewire circular
   dependency in this pass).
4. `pytest -x -q` — runner / execution / precondition-execution suites green.

### Phase 3 — `steps/conditions.py` (P2, grammar isolation)
1. Create `steps/_condition_parsing.py`; move the 8 compiled regexes and
   `_evaluate_status_fn` / `_evaluate_step_outcome` / comparison helpers.
2. `conditions.py` imports from it; `ConditionEvaluator` keeps orchestration only.
3. This single-sources the expression grammar referenced by compile-time
   validation and runtime evaluation — guard against drift.
4. `pytest -x -q` — condition / sse / pause-resume suites green.

### Phase 4 — `steps/precondition/policy_config.py` (P2, dedupe)
1. Create `steps/precondition/_policy_builders.py`; move both version builders +
   shared ODRL scaffolding (constraint/permission assembly).
2. `policy_config.py` keeps the `@step` class only.
3. `pytest -x -q` — precondition policy/contract suites green.

### Phase 5 — `steps/_checks/` package (P2, flat → nested)
1. Create `steps/_checks/` package; move check families into `status.py`,
   `equality.py`, plus the existing `_json_path_validation.py` → `json_path.py` and
   `_path_extraction.py` → `extraction.py`.
2. `steps/_checks/__init__.py` re-exports the same names the old flat module
   exposed, so `assertions.py` / `conditions.py` imports resolve unchanged.
3. **Guardrail check:** if a family is a single cohesive function, leave it as one
   file — do not create a one-function module.
4. `pytest -x -q` — assertion / condition / step-executor suites green.

### Phase 6 — `compiler/` nesting (P2, flat → nested)
1. Create `compiler/ir/` and move `ir_builder.py` → `ir/builder.py`,
   `_ir_helpers.py` → `ir/_helpers.py`, `_assets.py` → `ir/_assets.py`,
   `_ir_compilation.py` → `ir/_compilation.py`; `ir/__init__.py` exposes `build_ir`.
2. Create `compiler/validation/` and move `validator.py` → `validation/validator.py`,
   `_validation.py` → `validation/_rules.py`, `_expressions.py` →
   `validation/_expressions.py`; `validation/__init__.py` exposes `Validator`.
3. `compiler/__init__.py` re-exports `Compiler`, `Validator`, `Packager` unchanged;
   `compiler.py`, `packager.py`, `_fingerprint.py` stay top-level.
4. `pytest -x -q` — compiler / compile-endpoint / CCM-compile suites green (no new
   failures beyond the baseline CCM fixture-path set).

### Phase 7 — `services/manager.py` split (P2, factory vs lifecycle)
1. Create `services/_factory.py`; move SDK connector/discovery/AAS **creation**
   wiring (`ServiceFactory` calls) out of `manager.py`.
2. `manager.py` keeps the `ServiceManager` **lifecycle** facade (own/start/stop)
   and delegates creation to `_factory.py`.
3. `pytest -x -q` — participant / service-manager / mock-server suites green.

### Phase 8 — `server/` nesting (P2, flat → nested)
1. Create `server/routes/`; move `compile.py` → `routes/compile.py`,
   `callbacks.py` → `routes/callbacks.py`, and the `routes.py` handlers →
   `routes/mock.py`; `routes/__init__.py` exposes `register_routes(app)`.
2. Create `server/streaming/`; split `streaming.py` into `streaming/lifecycle.py`
   (connection open/close/keepalive) + `streaming/formatter.py` (event → SSE wire)
   and move `_event_buffer.py` → `streaming/_event_buffer.py`.
3. `server/__init__.py` and `app.py` wiring re-export/import the same public names;
   `app.py`, `storage.py`, `mock_registry.py` stay top-level.
4. `pytest -x -q` — health / compile-endpoint / sse-streaming / pause-resume-event
   suites green.

### Phase 9 — `player/execution/player.py` split (P3, extract formatter)
1. Create `player/execution/_trace_formatter.py`; move result/execution-trace
   formatting out of `player.py`.
2. `player.py` keeps orchestration and calls the formatter.
3. `pytest -x -q` — runner / sse-streaming / test-runner suites green.

### Phase 10 — Watch-list guard (P3, no-op unless touched)
No moves now. Record the watch list (`player/loading/_parser.py` 267,
`cli/compile.py` 260, `authoring/_builders.py` 208 + §1a) in repo memory so the
**next** feature touching any near-limit file triggers a split-first rule rather
than an overflow.

### Phase 11 — `models/` conditional nesting (P3, guardrail-gated)
1. Inspect `models/enums.py` and `models/results.py` at execution time. **Only if**
   each holds genuinely separable families (e.g. service enums vs phase enums; step
   results vs trace models) create `models/enums/` and `models/results/` with the
   families as leaf modules and a barrel re-exporting every name.
2. **Guardrail:** if a file is one cohesive set of related models, leave it flat —
   nesting cohesive data into one-file packages is over-engineering and is rejected.
3. `pytest -x -q` — model / compiler / runner suites green.

---

## 5. Risks

**Overall risk: LOW.** Every phase is a mechanical move-and-re-export with no logic
change, validated by the existing suite.

| Risk | Severity | Mitigation |
|------|----------|------------|
| Step `@step(...)` registry breaks if a moved module isn't imported | Medium | Keep barrel re-exports in `consume.py` / `connector/__init__.py` / `_checks/__init__.py`; assert registry membership in tests after each phase |
| Circular-import regression in `player/execution` | Medium | Preserve existing function-local imports in `_phase_runners`; do **not** rewire in this pass |
| Condition-grammar drift between compile & runtime | Medium | Phase 3 single-sources the grammar in one module; both callers import it |
| Hidden behavior change during dedupe/extraction (Phases 2, 4, 7, 9) | Low | Pure extraction; identical inputs/outputs; suite is the gate |
| Package nesting breaks a public import path (Phases 5, 6, 8, 11) | Medium | Barrel `__init__.py` re-exports every previously public name; run the full suite after each move |
| Over-nesting cohesive code into one-file packages | Low | Guardrail check per phase (§0); leave flat with a one-line reason when no seam exists |

### Contract touch points

These YAML ↔ compiler ↔ package boundaries are **external contracts**. This plan
does **not** change them, and a structural pass must leave them untouched:

- **YAML v2 syntax** (`@variable_name` refs, `${{ }}` expressions) — touched
  indirectly by Phase 3 (grammar isolation). Verify no token/precedence change.
- **Step ids** — the `@step(...)` id strings tests name in `uses:`; renames are
  forbidden in a structural pass.
- **TCK manifest model** — compiler input contract; untouched.
- **`.stck` package format** — compiler output contract; untouched.

---

## 6. Acceptance Criteria

All must hold after **every** phase (run from repo root). The line-count check is a
**floor, not the goal** — passing it does not mean a package is deeply modular; the
structural checks below are what prove the objective.

```bash
# 1. No source file exceeds 300 lines (floor, not the objective)
find src -name '*.py' | xargs wc -l | awk '$1>300 && !/total/'   # → empty

# 2. No broad exception handling
grep -rn "except Exception:\|except:" src/ --include="*.py"      # → empty

# 3. No print statements
grep -rn "print(" src/ --include="*.py" | grep -v "_fingerprint" # → empty

# 4. Test suite introduces NO NEW failures beyond the baseline
python -m pytest tests/ -q   # → only the 20 pre-existing CCM fixture-path failures
```

> **Baseline:** the suite carries **20 known CCM fixture-path failures** unrelated
> to this refactor (see §0). A phase passes when the failing-test set is **identical
> before and after** — never larger. Do not attempt to fix the baseline here.

Plus structural checks (the real proof of the objective):

- [ ] **Deep modularity:** every flat package called out in §1c is nested along its
      real seam (or explicitly left flat by the guardrail with a one-line reason).
- [ ] Layered package layout intact; barrels (`__init__.py`) expose public surface only.
- [ ] Each new sub-package has a single nameable responsibility and a minimal public surface.
- [ ] **No over-engineering:** no single-function "module", no one-file package added
      purely for depth (guardrail held).
- [ ] Step `@step(...)` registry resolves all moved step types unchanged.
- [ ] No public import path broken (existing `from tractusx_testlab...` imports still resolve).
- [ ] Condition grammar single-sourced in one module.
- [ ] Each split is a responsibility seam (one concern per new file/package), not an arbitrary cut.
