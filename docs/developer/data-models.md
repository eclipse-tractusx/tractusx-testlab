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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# Data Models

The engine's data models are Pydantic v2 classes under `src/tractusx_testlab/models/`,
organized into four sub-packages:

| Sub-package | Contains |
|-------------|----------|
| `authoring/` | the shapes of the YAML documents an author writes (scripts, TCK manifests, steps, variables, services) |
| `runtime/` | what execution produces (results, events, jobs, inspection metadata) |
| `primitives/` | enums and exceptions shared by everything else |
| `domain/` | feature-specific domain models: package security and server state |

All public models are re-exported from the package root, so
`from tractusx_testlab.models import StepDefinition` always works regardless of the
internal file layout.

The cx-test-suite IDE keeps TypeScript mirrors of the authoring shapes for
serialization; those types are documented in that repository.

## The YAML document structure

The engine compiles two document kinds, discriminated by an explicit `kind:` field
(the Kubernetes convention) and pinned to the single syntax version `v1-alpha`.

### Test scripts (`kind: test`)

A script is the executable authoring unit. Its steps are grouped into three phases —
`setup:`, `execution:`, `teardown:` — and every step uses the verb-form keys
`uses:` / `with:` / `returns:`:

```yaml
kind: test
syntax: v1-alpha
id: catalog-smoke
namespace: my-tck
metadata:
  name: "Catalog smoke test"
  version: "1.0"

execution:
  - id: query
    uses: connector/consumer/query_catalog
    name: Query the SUT catalog
    with:
      counter_party_address: ${{ env.sut_dsp_url }}
      counter_party_id: ${{ env.sut_bpn }}
    returns:
      datasets:
        type: array
    validate:
      - uses: validate/assert
        name: the SUT published at least one offer   # optional
        with: { input: datasets, operator: not_empty }
```

This maps onto `ScriptDefinition` and `StepDefinition`
(`models/authoring/definitions.py`):

```python
class StepDefinition(BaseModel):
    """Step definition using ``uses`` and ``with`` verb-form keys."""

    id: Optional[str] = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,49}$")
    uses: str
    name: Optional[str] = None
    with_: Optional[dict[str, Any]] = Field(default=None, alias="with")
    returns: Optional[dict[str, ReturnFieldDefinition]] = None
    validate: Optional[list[Assertion]] = None
    timeout_s: Optional[float] = None
    if_condition: Optional[str] = Field(default=None, alias="if")
```

- **`uses`** is the canonical step id (`<category>/<module>/<function>`), the key the
  [step registry](block-lifecycle.md) resolves to a Python executor class.
- **`with`** carries the parameters, validated into the executor's declared
  `params_model` before it runs.
- **`returns`** declares the output fields the script reads; each entry is a
  `ReturnFieldDefinition` (`type`, optional `class`). Assertions resolve against
  these declared returns, and later steps reference them as
  `${{ steps.<id>.<field> }}`.
- **`validate`** is a list of `Assertion` entries, themselves in verb form
  (`uses: validate/assert`, `with: {input, operator, expected}`), each with an
  optional `name`. Nothing in the engine reads the name; the run report calls
  the check by it, so a step carrying four `validate/assert` entries says which
  requirement each one covers instead of listing the same id four times.

When any of this does not hold up, the author is told so by
`syntax/diagnostics.py` rather than by Pydantic: the finding names the step by
its id, the line the key sits on, and — for a rejected key — the keys that
would have been accepted, with a near-miss called out as the likely typo. The
same renderer serves the compiler, the player, the IDE compile endpoint and a
step binding its `with:` block at runtime, so one wrong key reads the same
wherever it is caught.

### TCK manifests (`kind: tck`)

A TCK groups scripts into a certification package. `TckDefinition` carries
certification metadata (`authors`, `standards`, `license`, `dataspace_version`),
an `env:` block, and the ordered `tests:` list:

```python
class TckDefinition(BaseModel):
    kind: Literal["tck"] = "tck"
    syntax: Literal["v1-alpha"]
    id: str
    metadata: TckMetadataDefinition
    env: Optional[EnvDefinition] = None
    tests: list[TckTestEntry] = Field(default_factory=list)
```

Each `TckTestEntry` names a script file relative to the package's `tests/` folder,
with an optional human-readable `name` and a `skippable` flag the operator can act
on at runtime.

`EnvDefinition` is the shared environment: `variables`, `services`, `schemas`
(each a `SchemaDefinition` with `id` + `source`), and `testdata` entries.

### Variables

Variables are declared in the TCK's `env.variables` block, in the same verb-form
syntax as steps:

```yaml
env:
  variables:
    - id: provider_bpn
      description: BPN-L of the SUT certificate provider.
      uses: variable/type/string
      with:
        source: input
        scope: sut          # SUT operator provides this value
      returns:
        value:
          type: string

    - id: certificate_type
      description: Certificate type (default iso9001).
      uses: variable/type/string
      with:
        source: value
        value: iso9001      # static default — scope not required
      returns:
        value:
          type: string
```

The `source` is a `VariableSource`: `value` (static default), `input`
(operator-supplied at runtime), or `generated` (produced by a named generator such
as `uuid`). For `source: input` the `scope` (`VariableScope`) is **required** and
names the participant responsible for the value — `engine` or `sut` — enforced by
the compiler per
[ADR-0023](decision-records/backend/ADR-0023-variable-scope-annotation.md).
Scripts reference variables as `${{ env.<id> }}`, step outputs as
`${{ steps.<id>.<field> }}`, and deployment facts as `${{ infrastructure.* }}`.

### Services

`ServiceDefinition` declares an external service a run talks to:

```python
class ServiceDefinition(BaseModel):
    name: str
    type: ServiceType
    base_url: str
    auth: dict = Field(default_factory=dict)
    params: Optional[dict] = None
```

Steps never name a service in their `with:` block — connector services are seeded
into the run context at runtime, and the executor picks the right one through the
`StepContext` accessors (`get_consumer_service()`, `get_provider_service()`, …).

## Enums (`models/primitives/enums.py`)

The primitives every other model shares. The most load-bearing ones:

| Enum | Values | Used for |
|------|--------|----------|
| `StepPhase` | `SETUP`, `EXECUTION`, `TEARDOWN` | which phase a step belongs to |
| `StepStatus` | `PENDING`, `RUNNING`, `WAITING`, `PASSED`, `FAILED`, `SKIPPED` | per-step execution status |
| `ScriptStatus` | `IDLE`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `SKIPPED` | per-script and per-TCK status |
| `JobStatus` | `QUEUED`, `RUNNING`, `WAITING`, `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT` | overall job lifecycle |
| `AssertionSeverity` | `HARD`, `SOFT` | whether a failed assertion aborts or warns |
| `VariableSource` | `value`, `input`, `generated` | how a declared variable obtains its value |
| `VariableScope` | `engine`, `sut` | who provides a `source: input` variable |
| `ScriptKind` | `test`, `tck` | the document `kind:` discriminator |
| `EventKind` | `job_started`, `step_completed`, … | discriminator on every execution event |

## Runtime results (`models/runtime/results.py`)

What a run produces, nested top-down:

```text
TckResult
└── scripts: list[ScriptResult]
    ├── execution: list[StepResult]
    │   ├── request / response: HttpRequest / HttpResponse
    │   ├── exchanges: list[HttpExchange]
    │   └── assertions: list[AssertionResult]
    ├── assertion_summary: AssertionSummary
    └── callback_results: list[CallbackResult]
```

`StepResult` is the workhorse: `step_name`, `step_type`, `phase` (`StepPhase`),
`status` (`StepStatus`), timing (`started_at` / `finished_at` / `duration_s`), the
captured `request` / `response`, the serialised `output`, an optional
`error` / `error_traceback`, and the evaluated `assertions`. `exchanges` holds
*every* call the step made - both the engine's own `httpx` calls and the ones
`tractusx-sdk` made on its behalf, each naming in `context` the method that sent
it - while `request` / `response` name the one the script is about
([ADR-0016](decision-records/backend/ADR-0016-execution-trace-format.md)). `CallbackResult`
records a callback received (or timed out) on a mock listener.

## Execution events (`models/runtime/events.py`)

Frozen event models the execution monitor publishes while a job runs —
`JobStartedEvent`, `ScriptStartedEvent`, `StepCompletedEvent`,
`AssertionResultEvent`, and so on — each carrying its `EventKind` so consumers
(CLI, server SSE stream, the IDE) can dispatch on `kind` directly. The SSE wire
name is derived from the kind by turning its underscore into a dot
(`step_completed` → `step.completed`). See
[Execution Events](execution-events.md) for the full catalogue.

## Jobs (`models/runtime/jobs.py`)

`Job` tracks one submitted execution (`job_id`, `status`, timing, the current
script and step), with `JobMemory` as its mutable key-value store and `JobEvent`
entries as its event log.

## Inspection models (`models/runtime/inspection.py`)

Frozen Pydantic v2 models returned by `Tck.inspect()`. They contain static metadata
extracted from a compiled TCK without executing any steps.

### `StepMeta`

Metadata for a single step.

```python
class StepMeta(BaseModel):
    model_config = ConfigDict(frozen=True)
    step_name: str         # step.name if set, otherwise falls back to step.uses
    uses: str              # step identifier, e.g. "connector/consumer/query_catalog"
    phase: StepPhase       # SETUP | EXECUTION | TEARDOWN
    validation_count: int  # number of validate: entries on this step
```

### `ScriptInspection`

Metadata for one test script within a TCK.

```python
class ScriptInspection(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    steps: tuple[StepMeta, ...]
```

### `TckInspectionResult`

Top-level result returned by `Tck.inspect()`.

```python
class TckInspectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    total_steps: int
    total_validations: int
    scripts: tuple[ScriptInspection, ...]
```

### Usage

```python
from tractusx_testlab.scripting import Loader

loader = Loader()
tck = loader.load("my-test.tck")
result = tck.inspect()

print(result.name)              # "Certificate Management Conformity"
print(result.total_steps)       # 12
print(result.total_validations) # 8

for script in result.scripts:
    for step in script.steps:
        print(step.uses, step.phase.value)  # "connector/consumer/query_catalog" "EXECUTION"
```

See [ADR-0022: TCK Static Inspection](decision-records/backend/ADR-0022-tck-static-inspection.md)
for the full architectural rationale.

## How data flows between steps

A step's declared contract is the only channel data moves through:

1. **Declared returns.** Assertions and `${{ steps.<id>.<field> }}` references read
   the fields the step's `returns:` block declares, which the executor's
   `output_model` promises. See [Step Contracts](step-contracts.md).
2. **Published outputs.** Every step publishes all of its return outputs: each
   top-level output field becomes a context variable of the same name —
   `negotiate` returns `negotiation_id`, `do_dsp` returns the `dataplane_url` /
   `edr_token` pair, and downstream steps read exactly those.
3. **Explicit capture.** When a script needs a value under a name of its own
   choosing, the util steps (`util/json_path_extract`, `util/base64`,
   `util/parse_kv`) accept a `store_in_variable` parameter naming the context
   variable to write.
