<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This work is made available under the terms of the
 Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
 which is available at
 https://creativecommons.org/licenses/by/4.0/legalcode.

 SPDX-License-Identifier: CC-BY-4.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0022: TCK Static Inspection

## Status

Accepted — **amended 2026-08-18.** `.stck` no longer exists; `<package>` is a
`.tck`, plain or encrypted. `testlab inspect` also absorbed `testlab info` and
`testlab decompile`, which are now its `--manifest` and `--extract` sections.

## Date

2026-07-20

## Context

TestLab users and engine backends need to read
metadata from `.tck` and `.stck` packages — Test Name, total step count, total
validation count, and per-step details (name, `uses` identifier, phase) — **without
executing the test**. Use cases include:

- Displaying test metadata in a dashboard or UI before scheduling a run
- Validating that a package contains the expected tests before deploying it
- Generating pre-run reports or conformance summaries

Previously, the only way to extract this information was to execute `testlab run` and
parse the execution trace, which requires a live dataspace environment and leaks no
static summary.

A parallel capability, `Tck.all_variables()` (implemented in
[ADR-0018](../shared/ADR-0018-unified-variables-model.md)), already demonstrates the
correct pattern for extracting static metadata from a loaded `Tck`: a frozen Pydantic
model describes the result, a pure helper function in `scripting/_*.py` performs the
extraction, and the `Tck` class exposes a single method that delegates to it.

## Decision

### 1. Method on `Tck`: `inspect()`

We add `Tck.inspect() -> TckInspectionResult` to `scripting/script.py`, mirroring
the `Tck.all_variables() -> list[VariableDefinition]` pattern exactly:

```
Tck.inspect()
    └── calls build_inspection_result(self)          # scripting/_inspection.py
            └── returns TckInspectionResult          # models/runtime/inspection.py
```

The method works on any loaded `Tck`, whether loaded from a plain `.tck` or a
decrypted `.stck`. Decryption is the caller's responsibility (handled by `Loader`
before `inspect()` is ever called).

### 2. Result models in `models/runtime/inspection.py`

Three frozen Pydantic v2 models capture the static metadata:

```python
class StepMeta(BaseModel):
    model_config = ConfigDict(frozen=True)
    step_name: str          # step.name if set, otherwise falls back to step.uses
    uses: str               # block identifier (e.g. "connector/consumer/get_catalog")
    phase: StepPhase        # SETUP | EXECUTION | TEARDOWN
    validation_count: int   # number of validate: entries on this step

class ScriptInspection(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    steps: tuple[StepMeta, ...]

class TckInspectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    total_steps: int
    total_validations: int
    scripts: tuple[ScriptInspection, ...]
```

All three are exported through `models/runtime/__init__.py` and `models/__init__.py`
so consumers can import them as:

```python
from tractusx_testlab.models import TckInspectionResult, ScriptInspection, StepMeta
```

### 3. Pure helper in `scripting/_inspection.py`

`build_inspection_result(tck)` iterates all scripts and, for each, maps the three
phase lists (`setup`, `steps`, `teardown`) into `StepMeta` tuples using `_map_steps`.
It computes `total_steps` and `total_validations` by aggregating across all scripts.
The function has no side effects and does not touch the network or filesystem.

### 4. CLI command: `testlab inspect`

A new Typer command in `cli/inspect.py` exposes the feature at the command line:

```
testlab inspect <package> [--player-keys <path>] [--compiler-pub <path>] [--variables] [--infrastructure] [--json]
```

- `<package>` accepts both `.tck` (plain) and `.stck` (encrypted) files.
- `--player-keys` and `--compiler-pub` are required for `.stck` packages; the command
  rejects `.stck` without keys with a clear error message.
- `--variables` flag: additionally prints the variable list returned by `Tck.all_variables()`
  (ID, source, scope, type — as a human-readable table or embedded in the JSON envelope).
- `--infrastructure` flag: additionally prints the infrastructure requirements returned by
  `Tck.infrastructure_requirements()` (capability, side, required flag, standard — as a
  human-readable table or embedded in the JSON envelope).
- Default output: human-readable table printed to stdout.
- `--json` flag: outputs a JSON envelope
  `{"inspection": ..., "variables": [...], "infrastructure": {...}}` — only the sections
  requested via `--variables` / `--infrastructure` are populated in the envelope.

The three sections (`inspection`, `variables`, `infrastructure`) are independently optional.
At least one of the three must be requested or the command prints the inspection table by
default.

### 5. Amendment (2026-07): `Tck.infrastructure_requirements()`

Following the same pattern as `Tck.inspect()` and `Tck.all_variables()`, a method
`Tck.infrastructure_requirements() -> InfrastructureConfig` is added to `scripting/script.py`.

```
Tck.infrastructure_requirements()
    └── calls collect_infrastructure_requirements(self)   # scripting/_infrastructure.py
            └── returns InfrastructureConfig              # models/authoring/infrastructure.py
```

`collect_infrastructure_requirements(tck)` applies a two-pass merge:

1. If the TCK manifest declares a top-level `infrastructure:` block, that block wins as-is.
2. Otherwise, the function iterates all `TestScript` objects and merges their per-script
   `infrastructure:` blocks: `required: true` wins over `required: false`, and the first
   non-`None` `standard` wins.

`InfrastructureConfig`, `CapabilityRequirement`, `Standard`, and `DataspaceContext` are
all exported from `tractusx_testlab.models`:

```python
from tractusx_testlab.models import InfrastructureConfig, CapabilityRequirement, Standard
```

This amendment does **not** change the decision recorded in the original sections. It extends
the pattern documented in § 2 and § 3 with a third static-metadata accessor.

### 6. `StepPhase` enum value rename

The `StepPhase` enum values in `models/primitives/enums.py` are renamed to align
with user-facing and JSON-serialized terminology:

| Old value | New value  |
|-----------|------------|
| `MAIN`    | `EXECUTION` |
| `CLEANUP` | `TEARDOWN`  |
| `SETUP`   | `SETUP` (unchanged) |

This rename is applied to all callers in `player/execution/phases/`.

## Consequences

### Positive

- Backends and UIs can query TCK metadata without provisioning a live dataspace
  environment — significantly reduces onboarding friction.
- The `--json` output of `testlab inspect` provides a stable, machine-readable
  contract for engine integrations.
- Pattern is consistent with `Tck.all_variables()` and `Tck.infrastructure_requirements()` — the
  codebase has one way to extract each kind of static metadata from a loaded `Tck`.
- `--variables` and `--infrastructure` flags give engine backends a complete pre-run picture
  (what the TCK does, what variables it needs, what infrastructure it requires) from a single
  `testlab inspect` call.
- `StepPhase` values now match the domain language (`EXECUTION`, `TEARDOWN`) and
  serialize correctly to JSON without needing a display mapping.

### Negative

- `StepPhase.MAIN` and `StepPhase.CLEANUP` are removed — any downstream code
  (outside this repository) that imported these enum members must be updated to
  `StepPhase.EXECUTION` and `StepPhase.TEARDOWN`.

### Neutral

- No REST API endpoints are added. The feature is library-level (`tck.inspect()`)
  and CLI-level (`testlab inspect`). Engine backends consume the library directly.
- `testlab inspect` on an `.stck` file performs full decryption in memory to load
  the `Tck` object; no intermediate cleartext is written to disk.
