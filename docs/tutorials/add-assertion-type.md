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

# How to Add a New Assertion Type

Assertions are steps. The three `validate/*` steps carry every assertion a script can write:

- `validate/assert` — apply an operator to a value
- `validate/field` — apply an operator to a field at a dot-separated path inside a value
- `validate/schema` — validate a payload against a JSON Schema document

They run in two positions: as a standalone step in `execution:`, or inline in a step's `validate:` block. Inline, `with.input` is the plain name of one of the step's declared `returns:` — the assertion reads the step's public surface, nothing else (see [ADR-0025](../developer/decision-records/shared/ADR-0025-assertions-read-declared-returns.md)):

```yaml
- id: negotiate
  uses: connector/consumer/negotiate
  with:
    counter_party_address: "${{ infrastructure.sut.connector.dsp_url }}"
  returns:
    negotiation_id:
      type: string
  validate:
    - uses: validate/assert
      with: { input: negotiation_id, operator: not_null }
```

So "adding an assertion type" almost always means adding an **operator**, not a new step.

## Step 1 — Add the operator

All operators live in one table: `_check()` in `src/tractusx_testlab/steps/utility/validate.py`, shared by `validate/assert` and `validate/field`. Add a branch:

```python
def _check(operator: str, actual: Any, expected: Any) -> tuple[bool, str]:
    ...
    if operator == "greater_than":
        passed = actual is not None and float(actual) > float(expected)
        return passed, f"Expected value > {expected!r}, got {actual!r}"
```

## Step 2 — Declare it in the contract

Extend the `AssertOperator` literal at the top of the same file so the parameter models (and the generated step reference) know about it:

```python
AssertOperator = Literal[
    "not_null",
    "null",
    "not_empty",
    "equals",
    "not_equals",
    "matches_regex",
    "contains",
    "not_contains",
    "greater_than",  # ← add this
]
```

Because `ValidateFieldParams` inherits from `ValidateAssertParams`, both steps pick the new operator up automatically.

## Step 3 — Test it

Add a case to the validate-step tests and run them:

```bash
poetry run pytest -k validate
```

## Step 4 — Regenerate the step reference

The step reference is generated from the parameter models. `poetry run testlab docs --check` fails when `docs/specification/reference/steps.md` is stale; regenerate it:

```bash
poetry run testlab docs
```

## When an operator is not enough

If the check needs a genuinely different input contract (like `validate/schema`, which takes a `schema:` document instead of an operator), add a new `validate/*` step instead: a `StepParams` model, a `StepValue` output, and a `BaseStep` subclass registered with `@step("validate/<name>")` — the same pattern as the three existing steps in `src/tractusx_testlab/steps/utility/validate.py`. See [Create a New Step Executor](create-step-executor.md) for the full walkthrough.

The visual IDE's assertion blocks live in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository and are updated there.
