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

# ADR-0023: Variable Scope Annotation

## Status

Accepted

## Date

2026-07-20

## Context

[ADR-0018](../shared/ADR-0018-unified-variables-model.md) established the unified variable
model: every value a test needs is declared as a `VariableDefinition` with a `source`
(`value` | `input` | `generated`). Runtime input variables (`source: input`) are provided
by a human operator before the run starts.

[ADR-0019](ADR-0019-service-requirements-and-engine-bindings.md) introduced the two-sided
topology: `engine` (the host running TestLab) and `sut` (the System Under Test). Together
these two sides own *all* the external state a TCK run needs. Infrastructure capabilities
are already scoped to a side. Variables, however, are not.

A TCK may declare a dozen `source: input` variables — some are TestLab endpoint URLs (the
engine operator knows them), some are SUT business partner numbers (the SUT operator knows
them). Without a scope annotation, the consumer of the variable list cannot determine **who
is responsible for providing each value**. This matters for:

- Engine backends that must split the pre-run input form into "engine fields" and "SUT
  fields" and route them to the correct operator.
- Compile-time validation that catches missing or misattributed variables early.
- Documentation generation that groups inputs by responsible party.

The problem is compounded by the fact that the engine and SUT are often operated by different
organisations. Surfacing an engine URL in the SUT onboarding form (or a SUT BPN in the engine
config panel) creates confusion and operational errors.

## Decision

### 1. New optional field: `scope` on `VariableDefinition`

A `scope: engine | sut` field is added to the verb-form `with:` block of every
`source: input` variable declaration. The scope identifies which participant is
responsible for providing the value at runtime.

```yaml
env:
  variables:
    - id: testlab_management_url
      description: TestLab engine connector management API endpoint.
      uses: variable/type/string
      with:
        source: input
        scope: engine        # ← the engine operator provides this
      returns:
        value:
          type: string

    - id: provider_bpn
      description: BPN-L of the SUT certificate provider.
      uses: variable/type/string
      with:
        source: input
        scope: sut           # ← the SUT operator provides this
      returns:
        value:
          type: string

    - id: certificate_type
      description: Certificate type (default: iso9001).
      uses: variable/type/string
      with:
        value: iso9001       # source: value — scope not required
```

`scope` is **only required** for `source: input` variables. Variables with `source: value`
or `source: generated` carry their own value and have no external owner — `scope` is omitted
and defaults to `None`.

### 2. `VariableScope` enum in `models/primitives/enums.py`

```python
class VariableScope(str, enum.Enum):
    """Identifies which participant is responsible for providing a runtime input variable."""
    ENGINE = "engine"
    SUT = "sut"
```

`VariableDefinition.scope: Optional[VariableScope] = None`.

### 3. Parser wires scope from `with.scope`

`authoring/_variable_form.py` — `_build_verb_variable()` reads `with_block.get("scope")`
and coerces it via `VariableScope(raw_scope)`. Invalid values raise `ValueError`; the
compiler pre-validates before this point is reached (§ 4).

### 4. Compiler enforces scope on all `source: input` variables

`compiler/validation/_rules.py` — `_validate_variable_scopes(env: dict) -> list[str]`
iterates `env.variables`, finds every entry with `with.source == "input"`, and raises a
compilation error when `scope` is absent or not in `{engine, sut}`:

```
Variable 'provider_bpn' has source: input but no scope declared.
Add scope: engine or scope: sut to identify who is responsible for
providing this value at runtime.
```

This is a **hard compilation error** — a package with unscoped input variables cannot be
compiled. This policy is intentionally strict: an unscoped input variable is an authoring
mistake, not an acceptable default.

`_validate_variable_scopes` is called from `validate_tck_manifest()` after JSON-schema
validation and file-reference checks, so all errors are collected and reported together.

### 5. Public model export

`VariableScope` is exported from `tractusx_testlab.models` alongside `VariableSource`:

```python
from tractusx_testlab.models import VariableScope
```

## Consequences

### Positive

- Engine backends can split the pre-run input form into engine fields and SUT fields with a
  simple `var.scope == VariableScope.ENGINE` filter — no heuristics or naming conventions
  needed.
- Compilation fails explicitly when an author forgets to annotate an input variable. The error
  message names the variable and explains what to add — no silent miscategorisation at
  runtime.
- The authoring contract stays additive: `scope` is a new optional field that existing
  `source: value` and `source: generated` variables do not need.

### Negative

- All existing TCK manifests with `source: input` variables must be updated to add `scope`.
  The compiler error makes this a migration, not a silent break. The CCM reference TCK
  (`docs/examples/certificate-management-v2/raw/index.yaml`) is updated in this commit.
- Authors must now understand the engine/SUT topology before annotating input variables. In
  practice the distinction is straightforward: engine variables are TestLab endpoints and
  credentials; SUT variables are business identifiers and SUT endpoints.

### Neutral

- `VariableScope` mirrors the `SideKey` concept from ADR-0019 (`engine` | `sut`). The two
  enumerations are intentionally consistent but kept separate — `SideKey` is an infrastructure
  concept, `VariableScope` is a variable authoring concept.
- Variables with `source: value` (have defaults) and `source: generated` (auto-produced)
  remain unchanged. `scope: None` is the correct representation for them.

## Related

- [ADR-0018](../shared/ADR-0018-unified-variables-model.md) — unified variable model that
  introduced `VariableSource`
- [ADR-0019](ADR-0019-service-requirements-and-engine-bindings.md) — two-sided topology
  (`engine` / `sut`) that this scope annotation aligns with
- [ADR-0022](ADR-0022-tck-static-inspection.md) — `Tck.all_variables()` returns the
  variable list enriched with scope; `testlab inspect --variables` displays it
