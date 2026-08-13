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

# Step Contracts — the Single Source of Truth

Every step in TestLab has exactly **one canonical contract**: one step id, one set of
parameter names, one output shape. The IDE blocks,
the YAML scripts, the Python executors, the generated reference documentation and the
assertion system all read that same contract — none of them keeps its own copy of it.

This page explains where the contract lives, how it is enforced, and the patterns that
keep the different layers from drifting apart. It is the conceptual layer above
[Block Lifecycle](block-lifecycle.md), which traces a single step through the pipeline.
The IDE/Blockly side of the contract lives in the separate cx-test-suite repository.

## The rule: one name, one shape

The rule, established in the [IDE↔Engine contract parity analysis](ide-engine-contract-parity.md),
is deliberately blunt:

> A step accepts each parameter under exactly one name, produces its output in exactly one
> shape, and is addressed by exactly one id. **No aliases, no backward-compat shims** —
> when a name changes, every script, block and document is migrated to the new one.

Why so strict? Aliases are how the drift started. Back when a parameter answered to
`provider_url` *and* `counter_party_address`, the IDE picked one spelling, the engine
documented another, the JSON Schema rendered a third, and the parity checker could no
longer tell a typo from a valid alternative — which is exactly why the rule exists.
The historical record of every conflict this caused
and how each was resolved lives in the
[contract conflict decision sheet](contract-conflict-decisions.md) (C01–C47), executed via
the [migration plan](contract-migration-plan.md).

Three practical consequences of the rule:

1. Unknown parameters are an error, not something to silently ignore — a misspelled
   `with:` key must fail the step, not no-op.
2. The JSON Schema produced from a step is faithful: what `describe()` says is exactly
   what the executor accepts.
3. The IDE's block catalog is *generable* from the engine registry, because there is
   nothing block-specific left to hand-maintain about names and shapes.

## Where the contract lives

The contract is declared in Python, next to the executor, using three Pydantic base
classes from `src/tractusx_testlab/steps/base.py`:

| Base class | Declares | Notes |
|------------|----------|-------|
| `StepParams` | the step's **inputs** — one field per accepted `with:` key | validated before `execute` runs |
| `StepPayload` | the **output** as an object shape | `extra="forbid"`; `StepPayload.of(doc)` binds a document received from a counterpart |
| `StepValue[T]` | the output as a **bare value** (e.g. `util/base64` → `str`) | the docstring becomes the field description |

There is no separate export channel: **every step publishes all of its return
outputs, always**. Each top-level field of the output becomes a context variable of
the same name after the step runs (`None` values leave the variable unset), so the
constants in `syntax.context_vars` are simply the output field names downstream
steps read back as parameter fallbacks.

A complete declaration looks like this:

```python
class ExtractDatasetParams(StepParams):
    datasets: list[dict]
    dct_type: str

class ExtractDatasetOutput(StepPayload):
    dataset: Optional[dict] = None
    offer_id: Optional[str] = None
    asset_id: Optional[str] = None

@step("connector/consumer/extract_dataset")
class ExtractDatasetStep(BaseStep[ExtractDatasetParams, ExtractDatasetOutput]):
    params_model = ExtractDatasetParams
    output_model = ExtractDatasetOutput
```

`BaseStep.describe()` projects these models into a machine-readable `StepContract`
(`step_type`, `description`, `params_schema`, `output_schema` — all
JSON Schema). Everything downstream — the generated step reference, the IDE catalog, the
parity checker, assertion resolution — is derived from `describe()` or from the models
behind it.

### Enforcement is at import time

`BaseStep.__init_subclass__` calls `_require_declared_contract`, which raises `TypeError`
the moment a step class is defined without a proper `params_model`/`output_model`. The
check lives in `__init_subclass__` rather than in the `@step` decorator on purpose: the
decorator and a direct `StepRegistry.register` call can never diverge. There is therefore
no such thing as a registered step whose interface is undocumented.

### The execution path honours the contract

`BaseStep.invoke()` is the only way a step runs, and it is a straight line through the
declared models:

```text
bind_params        raw `with:` dict → params_model (unknown/invalid keys fail here)
execute            the step's own logic, typed params in, typed output out
bind_output        TypeError if execute returned anything but the declared output_model,
                   then serialised with mode="json", by_alias=True, exclude_unset=True
publish_output     every top-level field of the serialised output written into the
                   run context under its own name (None values leave the variable unset)
```

There is no code path where a step reads an undeclared parameter or emits an undeclared
field.

## Shared contract modules

When two steps talk about the same thing, they share one model instead of re-declaring
it. Exactly two shared modules exist:

- `steps/_contracts.py` — cross-step
  models: parameter mixins (`CounterPartyParams`, `FilterExpressionParams`,
  `HttpTransportParams`, `HttpCallParams`), the `FilterExpression` shape (snake_case in,
  camelCase only on serialisation), the unified `CatalogOutput` (`catalog` + `datasets`,
  shared by every `query_catalog*` step), `DataAddressPayload` (an EDR data address
  document) and `NoOutput` for steps that deliberately return nothing.
- `steps/server/_contracts.py` —
  mock-server models, most importantly `MockInstance` (see below).

Per-step models live beside their executor (`steps/connector/provision.py`,
`steps/industry/dtr.py`, …). A model earns a place in `_contracts.py` only once a second
step needs it.

### `MockInstance`: a contract that crosses the script

`mock/api` returns a `MockInstance` object (`endpoint_id`, `path`, `method`,
`base_mock_url`, `full_mock_url`); `mock/wait/http_request` takes that same object as its
only way to identify the endpoint. One typed value flows *step → script variable → step*,
replacing the old guessing between a bare URL, an id or a path. Note the separation of
layers: `server/mock_registry.py` (plain dataclasses, HTTP routing) describes what the
mock server *serves*; `MockInstance` describes what a *script* holds. They meet only in
the `mock/*` steps.

## Step ids

Ids follow `<category>/<module>/<function>`:

- **category** — the domain under test (`connector`, `digital-twin`, `notification`) or
  an engine facility (`util`, `flow`, `validate`, `http`, `mock`);
- **module** — the component or access path within the category (`consumer`, `provider`,
  `dataplane`, `submodel`);
- **function** — the operation.

The module segment is omitted only when the category has no sub-division (`util/log`,
`flow/delay`, `validate/assert`) — and once a category grows one, every id in it carries
one. A fourth segment is allowed when the access path is itself what distinguishes the
step: `digital-twin-registry/consumer/dataplane/lookup_shell` is a different step from
`digital-twin/provider/get_shell_descriptor` precisely because of *how* the registry is
reached.

Note that steps never name the service they run against — connector services are seeded
into the run context at runtime, and data-plane steps take exactly `dataplane_url` +
`edr_token`.

## Guided siblings (`wizard/` steps)

Some resources can sensibly be created two ways: by handing over the whole document
(scripts driven by `env.variables`), or field by field (scripts built in the IDE form).
One step accepting both shapes would violate the one-shape rule, so each of the four
creation steps has a **guided sibling** under a `wizard/` module:

```text
connector/provider/create_asset                 ⇄  connector/provider/wizard/create_asset
connector/provider/create_policy                ⇄  connector/provider/wizard/create_policy
digital-twin/provider/create_shell_descriptor   ⇄  digital-twin/provider/wizard/create_shell_descriptor
digital-twin/provider/create_submodel_descriptor⇄  digital-twin/provider/wizard/create_submodel_descriptor
```

The anti-drift mechanism is structural, not disciplinary: each pair funnels into a single
module-level helper (e.g. `_register_asset` in `steps/connector/provision.py`) — the raw
step hands over the document it was given, the wizard hands over the document it
assembled, and both get the same call and the same error handling. Both siblings also
share the **same output model**, so `returns:` is identical whichever one a script uses.

## Keeping it from drifting

Three mechanisms guard the contract, in decreasing order of strength:

1. **Import-time enforcement** — a step without declared models cannot exist (see above).
2. **Contract tests** — tests that assert on the declared models themselves, not just on
   behaviour: `tests/test_step_contracts.py` (drives `describe()`),
   `tests/test_mock_and_http_contract.py` (including tests that assert the *absence* of
   retired parameter spellings), `tests/test_catalog_query_contract.py`.
3. **Generated artefacts with `--check`**:
    - `poetry run testlab docs --check` regenerates the step reference
      (`docs/specification/reference/steps.md`) from the registry and fails if the
      committed page differs (renderer: `scripting/step_docs.py`).
    - `poetry run python tools/compare_ide_parity.py --ide <path-to-ide-repo> --check`
      diffs the engine registry against the IDE repository's (cx-test-suite) block
      catalog field by field (it reads `model_fields`, not JSON Schema, so an alias cannot hide) and exits
      non-zero on any breaking divergence class.

The checkers are the weaker guard: they catch drift after the fact. The point of the
architecture is that most drift is impossible to *express* — there is only one place to
write a name down.

## Related reading

| Document | What it covers |
|----------|----------------|
| [IDE↔Engine Contract Parity](ide-engine-contract-parity.md) | The full analysis that motivated the rule, divergence classes A–G, the parity tool |
| [Contract Conflict Decisions](contract-conflict-decisions.md) | The decision sheet: every conflict C01–C47 and its resolution |
| [Contract Migration Plan](contract-migration-plan.md) | The executed migration, cluster by cluster (E1–E9 / I1–I6) |
| [Block Lifecycle](block-lifecycle.md) | End-to-end trace of one step: YAML → registry → executor → SDK |
| [Creating a Step](creating-a-step.md) | How-to for adding a new step (and therefore a new contract) |
| ADR-0025 (decision records) | Assertions read the declared `returns:` of the referenced step |
