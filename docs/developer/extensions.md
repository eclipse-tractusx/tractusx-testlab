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

# Extensions

!!! warning "Experimental"
    Everything under `tractusx_testlab.extensions` is **experimental**. An extension can change shape or be
    removed without a syntax version bump. Do not build a certification TCK on one unless you accept that.

An **extension** is an addition to TestLab that is not part of the `v1-alpha` syntax yet: a new key on
steps, an extra `with:` parameter on an existing step, or a step whose contract is still being tested. It lives in its own package, a TCK has to enable it
by name, and the compiler refuses it everywhere else.

This page covers how extensions work and how to add one. For the extensions TCK authors can use today,
see [Proposed Extensions](../tck-syntax/extensions.md).

## How a TCK uses one

A TCK lists the extensions it opts into in `index.yaml`:

```yaml
kind: tck
syntax: v1-alpha
id: certificate-management-tck-v0.0.1
metadata: { … }
extensions: [cac, labs]
```

When a TCK is compiled or validated:

| The TCK… | Result |
|---|---|
| names an extension that does not exist | Error: `'nope' is not allowed here — expected 'cac' or 'labs'` |
| uses an extension's key, `with:` parameter or step without enabling it | Error naming the extension and the line to add: `Add 'extensions: [cac]' to index.yaml` |
| enables an extension | One warning per extension saying it is experimental |
| enables an extension that has its own checks | Those checks run. For example, `cac` requires each standard it references to be in `metadata.standards` |

The compiled package records the enabled extensions under `tck.extensions` in `manifest.yaml`, so anyone
reviewing a package can see it was built on experimental features.

Keys, parameters and steps are checked everywhere in a test: `setup`, `execution` and `teardown`, and inside the branches
of `flow/if` and the `steps` of `flow/retry`.

## Available extensions

| Name | Contributes | Documented in |
|---|---|---|
| `cac` | `cac:` on tests, steps and `validate:` entries: the CACs a test, step or check verifies | [§9.1](../tck-syntax/extensions.md#91-cac-traceability-cac-p1) |
| `labs` | Steps under the `labs/` prefix, and `with:` parameters on core steps, whose contract is still being tested | [Experimental steps](#experimental-steps-labs), [Step parameters](#adding-parameters-to-an-existing-step) |

What ships under `labs` today:

| Contribution | On | What it does |
|---|---|---|
| `retry_on`, `retry_attempts`, `retry_delay_s` | `connector/dataplane/http_request` | Calls again while the answer's status is in `retry_on`, up to `retry_attempts` calls in total. Each attempt is its own `tck.test.step.call` event. A transport error is not retried. Source: `extensions/labs/dataplane_retry.py` |
| `labs/flow/for_each` | new step | Runs its nested `steps:` once per entry of `items:`. A nested step reads the entry as `${{ each.item }}` and its position as `${{ each.index }}`; the compiler refuses both names outside the loop. The nested steps resolve their `with:` when they run, as the nested steps of `flow/retry` and `flow/if` do. Source: `extensions/labs/steps/for_each.py` |
| `labs/connector/provider/query_assets`, `query_policies`, `query_contract_definitions` | new steps | List the ids the provider connector holds, page by page, keeping those that start with `id_prefix`. The contract-definition query also matches on `asset_id_prefix` and publishes the `policy_ids` and `asset_ids` the kept definitions bind, so a test can withdraw an offer whose ids the connector generated. Source: `extensions/labs/steps/provider_query.py` |

## Layout

```
src/tractusx_testlab/extensions/
├── __init__.py          # EXTENSIONS: the registry, one entry per extension
├── extension.py         # Extension, ExtensionFinding, written_steps()
├── step_keys.py         # TestExtensionKeys / StepExtensionKeys / AssertionExtensionKeys: keys every extension adds
├── step_modules.py      # imports every module that registers a labs/ step or step parameters
├── cac/                 # a syntax-key extension
│   ├── __init__.py      # EXTENSION = Extension(name="cac", …)
│   ├── references.py    # the cac: field and its models
│   └── certified.py     # its compile-time check
├── labs/                # experimental steps and parameters
│   ├── __init__.py      # EXTENSION = Extension(name="labs", step_prefix="labs/")
│   ├── dataplane_retry.py  # retry_on: a step parameter extension on connector/dataplane/http_request
│   └── steps/           # labs/ step modules
└── <name>/
    └── <what_it_adds>.py  # a step parameter extension: extra with: keys on a core step
```

Outside the package:

- `steps/step_extension.py` holds the machinery for step parameters: `ExtensionParams`, `StepExtension`,
  `@extends` and `invoke_extended`. It lives with the step contract because it builds on it.
- `compiler/validation/_extension_gate.py` is the compiler side. It is generic: it reads the `Extension`
  records and the `@extends` registry, and never names a specific extension.

## The `Extension` record

```python
Extension(
    name="cac",                               # what index.yaml writes under `extensions:`
    summary="Name the CACs a test, a step or a check verifies with `cac:`.",  # quoted in the warning
    test_keys=frozenset({"cac"}),             # keys it adds to the top level of a test file
    step_keys=frozenset({"cac"}),             # keys it adds to a step
    validation_keys=frozenset({"cac"}),       # keys it adds to a validate: entry
    step_prefix=None,                         # a reserved step-id prefix, e.g. "labs/"
    check=uncertified_cac,                    # optional (tck, test) -> list[ExtensionFinding]
    docs="tck-syntax/extensions.md#91-cac-traceability-cac-p1",
)
```

`stability` is always `"experimental"`.

## Adding a syntax-key extension

The steps below add a key `owner:` to steps. Replace `owner` with your extension's name.

**1. Create the package** `src/tractusx_testlab/extensions/owner/`.

**2. Declare the key as a field.** In `owner/fields.py` (use a file name that no other module in the
package has, because a structure test forbids duplicate basenames):

```python
from pydantic import BaseModel


class OwnerStepKeys(BaseModel):
    """The key this extension adds to a step."""

    #: The expert group responsible for this step's requirement.
    owner: str | None = None
```

Leave out `model_config`. The core models apply the strict config. The key's default must be `None` so a
test that does not write it is unaffected.

**3. Declare the extension** in `owner/__init__.py`:

```python
from tractusx_testlab.extensions.extension import Extension

EXTENSION = Extension(
    name="owner",
    summary="Record which expert group owns a step with `owner:`.",
    step_keys=frozenset({"owner"}),
    docs="tck-syntax/extensions.md#owner",
)
```

**4. Add the key to the core models** in `extensions/step_keys.py`:

```python
class StepExtensionKeys(CacStepKeys, OwnerStepKeys):
    """Every key an extension adds to a step."""
```

For keys on `validate:` entries, do the same with `AssertionExtensionKeys` and set `validation_keys`. For keys
at the top level of a test file, use `TestExtensionKeys` and set `test_keys`; the gate reports those with
`field` set and no step index or phase.

**5. Register it** in `extensions/__init__.py`:

```python
EXTENSIONS = {extension.name: extension for extension in (CAC, LABS, OWNER)}
```

This also adds `owner` to the values `extensions:` accepts.

**6. Optionally, add a check.** Write a function `(tck, test) -> list[ExtensionFinding]` and pass it as
`check=`. It runs only for TCKs that enabled the extension. Iterate with `written_steps(test)`, which yields
every step as written, nested flow steps included, together with its phase and top-level index. A finding
about a test-level key sets `step_index` and `phase` to `None`. See `cac/certified.py`.

Extension modules must not import `tractusx_testlab.models` or `tractusx_testlab.compiler` at runtime,
because the models import the extensions. Import them under `TYPE_CHECKING` for type hints only.

**7. If the run should use the key**, read it where it is needed. `cac`, for example, is copied onto
`StepResult.cac` in `player/execution/step_runner.py` and `phase.py`, falling back to the test's `cac`,
which `run_phase` binds on the `StepContext` (`bind_test_cac`) so nested flow steps see it too, and into
the trace in `player/execution/_trace_events.py`. Keep those reads minimal and point to the extension in a comment.

**8. Regenerate the published files:**

```bash
testlab schema     # the JSON Schemas the IDE reads now include the key
testlab docs       # the step reference lists the key on flow steps' nested definitions
```

**9. Test it** under `tests/unit/extensions/`. The gate itself is already tested. Cover what is specific to
yours: the key is refused without the extension (the gate handles this once `step_keys` is set, but a test
proves you set it), accepted with it, and your check's findings. `tests/unit/extensions/test_cac.py` is a
template.

**10. Document it** as a subsection of [Proposed Extensions](../tck-syntax/extensions.md): what it adds, a
YAML example including `extensions: [owner]`, and any rules the check enforces. Add a row to the table
under [Available extensions](#available-extensions).

## Adding parameters to an existing step

An extension can add `with:` parameters to a step that already exists, without changing the step. The
parameters are declared like a step's own, as a model, and the behaviour is written like a step, as a class.
Both live in the extension's package, not in `tractusx_testlab.steps`. A test writes them under `with:`
like any other key. `retry_on`, which ships under `labs`, is the working example:

```yaml
- id: fetch_certificate
  uses: connector/dataplane/http_request
  name: Fetch the certificate, retrying while the provider is still preparing it
  with:
    dataplane_url: "${{ execution.pull.dataplane_url }}"
    edr_token: "${{ execution.pull.edr_token }}"
    retry_on: [404, 503]            # added by the labs extension
    retry_attempts: 5               # added by the labs extension
```

**1. Pick the extension.** Use a named extension of your own (add it first, steps 1, 3 and 5 of
[Adding a syntax-key extension](#adding-a-syntax-key-extension)), or `labs` for a one-off parameter still
being tried out.

**2. Declare the parameters and the behaviour** in a module of the extension's package, named for what it
adds (e.g. `extensions/<name>/<what_it_adds>.py`). This is `extensions/labs/dataplane_retry.py`, shortened:

```python
from pydantic import Field

from tractusx_testlab.steps.step_extension import ExtensionParams, StepExtension, extends


class DataplaneRetryParams(ExtensionParams):
    """Retry the call while the data plane answers with one of ``retry_on``."""

    retry_on: list[int] = Field(min_length=1, description="Status codes that make the call run again.")
    retry_attempts: int = Field(default=3, ge=2, le=10, description="Calls in total, the first one included.")
    retry_delay_s: float = Field(default=1.0, ge=0, le=60, description="Seconds to wait between two calls.")


@extends("connector/dataplane/http_request", extension="labs")
class DataplaneRetry(StepExtension[DataplaneRetryParams]):
    """Run the call again while its status is one the test listed."""

    params_model = DataplaneRetryParams

    async def around(self, params, context, definition, proceed):
        for _ in range(1, params.retry_attempts):
            output = await proceed()
            if output.response is None or output.response.status_code not in params.retry_on:
                return output
            await asyncio.sleep(params.retry_delay_s)
        return await proceed()
```

A parameter with no default, like `retry_on`, is required only once the test writes any of the extension's
keys. A test that writes none of them never runs the extension.

`ExtensionParams` has the same rule as `StepParams`: unknown keys are rejected. Give every field a
`description`, because that is what the step reference shows.

**3. Register the module** in `extensions/step_modules.py`:

```python
import tractusx_testlab.extensions.<name>.<what_it_adds>
```

**4. Regenerate the step reference** with `testlab docs`. The step's page gains an **Experimental inputs**
table naming the extension.

**5. Test it** under `tests/unit/extensions/`:

- `test_step_params.py` covers the mechanism: running a step through `run_step` with a throwaway
  extension, and the compiler check.
- `test_dataplane_retry.py` covers one real extension: patching the HTTP client and counting the calls.

**6. Run it for real** if it touches the dataspace. The e2e TCK enables `cac` and `labs`, and
`tests/e2e/connector-dtr-smoke/tests/experimental_extensions.yaml` uses both against the live Umbrella
deployment. The workflow then reads the trace back to prove the extension ran. Add your parameter to that
test, or a new test next to it, and add a matching offline run to
`tests/combinations/test_e2e_extensions_offline.py`.

### How it runs

1. The compiler rejects the parameters in any TCK that does not list the extension, reporting them as
   `with.<key>`.
2. At run time the runner resolves `with:` as usual, then `invoke_extended` takes each extension's keys out
   **before** the step binds its own parameters. The step never sees them.
3. Each extension whose keys were written gets its parameters bound to `params_model`. A bad value fails
   the step with *"Invalid parameters of the experimental extension '<name>' on step '<id>'"*.
4. The extensions wrap the step, the first registered outermost. `around` receives `proceed`, which runs
   the rest of the chain and the step, and returns the step's output.
5. An extension whose keys the test did not write does not run at all. Its defaults never apply.

### Rules for `around`

- **May:** do work before or after `proceed()`, call `proceed()` again to retry, raise to fail the step,
  or read the output.
- **Must not:** replace or change the output. The step has already published its values to the run by the
  time `proceed()` returns, so a change would reach assertions but not later steps.
- **Must call `proceed()`** unless it deliberately fails the step. Not calling it skips the step silently.
- A parameter name that the step, or another extension on the same step, already declares is an engine
  fault. The step fails with `origin: engine`.

### When it graduates

Move the fields into the step's own `params_model` and the behaviour into its `execute`. Then delete the
`StepExtension` and its import in `step_modules.py`, and drop `extensions: [<name>]` from TCKs that enabled
it only for this.

## Experimental steps (`labs`)

A step whose inputs, outputs or behaviour are not settled goes under `labs/` instead of into
`tractusx_testlab.steps`. It is written exactly like any other step (see [Creating a Step](creating-a-step.md)).
Only the id and the location differ:

```python
# src/tractusx_testlab/extensions/labs/steps/submodel_diff.py
from tractusx_testlab.authoring.registry import step
from tractusx_testlab.steps.step_contract import BaseStep


@step("labs/digital-twin-registry/submodel_diff")
class SubmodelDiffStep(BaseStep[SubmodelDiffParams, SubmodelDiffOutput]):
    """Compare two submodel documents and publish what changed. Experimental."""
    ...
```

1. Use the id `labs/<category>/<module>/<function>`: the normal [step id scheme](creating-a-step.md) with
   `labs/` in front. Drop `<module>` when the category has no sub-division, as elsewhere.
2. Put the module in `extensions/labs/steps/` and import it from `extensions/labs/steps/__init__.py`.
   Registration happens on import.
3. A structure test enforces both directions: every `labs/` step lives in that package, and every step in
   that package has a `labs/` id.
4. The step shows up in `testlab docs` like any other step. Say in its docstring that it is experimental.

A TCK can use it only with `extensions: [labs]`.

## Graduating or removing an extension

An extension leaves this package in one change, either promoted or deleted. There are no aliases in
either case.

**Promoting a key:**

- Move the field from the extension's model into `StepDefinition` or `Assertion`.
- Move its check into the compiler.
- Delete the extension package and its entry in `EXTENSIONS` and `step_keys.py`.
- Remove `extensions: [<name>]` from every TCK in the repository. It would now be refused as unknown.
- Move its documentation out of *Proposed Extensions* into the syntax reference.

**Promoting a step:**

- Move the module into `tractusx_testlab.steps` under its final id, without `labs/`.
- Migrate every TCK that used the `labs/` id.

**Removing:** delete the package and its registry entries, and migrate or delete the TCKs that used it.

Record a graduation in `CHANGELOG.md` as a breaking change for any TCK that used the experimental form.
