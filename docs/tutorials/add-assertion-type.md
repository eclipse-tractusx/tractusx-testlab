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

## Step 1 — Declare it in the contract

Every operator lives in one module: `src/tractusx_testlab/steps/assertions/operators.py`, shared by `validate/assert`, `validate/field` and `flow/if`. Extend the `AssertOperator` literal so the parameter models (and the generated step reference) know about it:

```python
AssertOperator = Literal[
    "not_null",
    "is_null",
    ...
    "between",
    "greater_than",  # ← add this
]
```

Because `ValidateFieldParams` inherits from `ValidateAssertParams`, both steps pick the new operator up automatically.

## Step 2 — Add the row to the operator table

`_TABLE` in the same module is the dispatch: a name, the operands it reads, the comparison, and how a failure reads. Add a row — there is no branch to extend, and a name declared in Step 1 but missing here fails the module's import-time consistency check:

```python
Operator(
    "greater_than", Arity.BINARY,
    _numeric(lambda left, right: left > right),
    "Expected {actual!r} to be greater than {expected!r}",
),
```

Three things the table decides for you:

- **`Arity`** — `UNARY` reads only the value under test, `BINARY` also reads `value`, `RANGE` reads the `min`/`max` pair instead. The assertion engine uses it to decide which params to resolve.
- **The operand adapter** — `_numeric`, `_sized` and `_bounded` shape the operands and reject the pairs that cannot be compared at all, so the comparison itself is a one-line lambda over values of the right type.
- **The message** — a format template naming `{actual}` and `{expected}`, rendered only when the check fails.

When operands cannot be read at all (a missing bound, a word where a number belongs), raise `OperandError` with a message that says so; `apply_operator` turns it into a failure rather than letting it look like a passing check.

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
