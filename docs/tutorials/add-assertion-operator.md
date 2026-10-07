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
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and tested by a human committer. -->

# Add an Assertion Operator

Assertions are not steps. They are entries in a step's `validate:` block, and they check what that step published:

```yaml
- id: negotiate
  uses: connector/consumer/negotiate
  validate:
    - uses: validate/assert/not_null
      with: { input: negotiation_id }
    - uses: validate/assert/equals
      with: { input: state, value: FINALIZED }
```

There are three assertion kinds, and the vocabulary is closed:

| `uses` | Checks |
|---|---|
| `validate/assert` | the output named by `input` |
| `validate/field` | the value at `path` inside that output |
| `validate/schema` | the output against a JSON Schema |

The operator is written either as a suffix (`validate/assert/equals`) or as `operator: equals`. The compiler rejects `validate/*` as a standalone step in `setup:`, `execution:` or `teardown:`, and `with.input` must name one of the step's outputs ([ADR-0025](../developer/decision-records/shared/ADR-0025-assertions-read-declared-returns.md)).

So extending assertions nearly always means adding an **operator**. The same operators serve `validate/assert`, `validate/field` and the condition of `flow/if`. This tutorial adds `starts_with`.

## Where operators live

```text
src/tractusx_testlab/steps/assertions/
├── __init__.py     ← barrel
├── operators.py    ← the AssertOperator vocabulary and the operator table
├── vocabulary.py   ← resolves validate/assert, validate/field, validate/schema and the suffix spelling
└── engine.py       ← runs a validate: block against a step's output
```

Only `operators.py` changes. `vocabulary.py`, the `flow/if` params, the step reference and the validator all read the operator list from it.

## 1. Make room first

`operators.py` is over the 300-line limit. It is listed in `OVERSIZED` in `tests/unit/structure/test_module_layout.py`, and that test does not let a listed file grow. A new row would fail it, so split the module before adding anything.

The natural seam is the operand adapters: `OperandError`, `_numeric`, `_sized`, `_bounded` and the plain comparisons `_is_member`, `_has_key` and `_matches`. They shape raw operands and have no knowledge of the table. Move them to `steps/assertions/operands.py`, import them back into `operators.py`, and remove `operators.py` from `OVERSIZED` once it is under 300 lines. The test requires that last step.

## 2. Declare the name

Add the operator to the `AssertOperator` literal. This is the vocabulary: the parameter models of `validate/*` and `flow/if`, and the generated reference, all read it.

```python
AssertOperator = Literal[
    "not_null",
    ...
    "matches_regex",
    "starts_with",   # ← new
    ...
    "between",
]
```

## 3. Add the row

`TABLE` in the same module is the dispatch. Each row gives the name, the operands it reads, the check and the failure message, so there is no `if`-chain to extend:

```python
Operator(
    "starts_with",
    Arity.BINARY,
    _prefixed,
    "Expected {actual!r} to start with {expected!r}",
),
```

With the adapter in `operands.py`:

```python
def _prefixed(actual: object, expected: object) -> bool:
    """Ask whether text *actual* begins with text *expected*."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        raise OperandError(f"Cannot check whether {actual!r} starts with {expected!r}")
    return actual.startswith(expected)
```

The row decides three things:

- **`Arity`**: `UNARY` reads only the value under test. `BINARY` also reads `value`. `RANGE` reads `min` and `max`. The vocabulary rejects an operand the operator would not read, so `validate/assert/not_null` with a `value:` is an error, not a silently ignored key.
- **The check**: a function of `(actual, expected)`. When the operands cannot be compared at all, raise `OperandError` with a sentence saying why. `apply_operator` turns it into a failed check with that message, so it never looks like a pass.
- **The message**: a format template using `{actual!r}` and `{expected!r}`, rendered only when the check fails. The step reference prints it with those placeholders replaced by `<input>` and `<value>`.

If the name is in the literal but missing from the table, `operators.py` fails an assertion at import. You can't ship one half.

## 4. Cover it

Two tests enumerate the vocabulary and fail until the new operator is in them:

- `tests/unit/steps/assertions/test_assertion_vocabulary.py`: add `"starts_with"` to the expected operator set.
- `tests/combinations/test_assertion_matrix.py`: add one `HOLDS` and one `FAILS` entry against `SUBJECT`. The matrix then runs the operator as a real `validate/field/starts_with` on an HTTP response, in both directions and in both spellings.

```python
HOLDS["starts_with"] = {"path": "id", "value": "urn:uuid:"}
FAILS["starts_with"] = {"path": "id", "value": "urn:bpn:"}
```

Also add a unit test for the operand error, such as `starts_with` on a number.

```bash
poetry run pytest tests/unit/steps/assertions tests/combinations/test_assertion_matrix.py tests/unit/structure -q
```

## 5. Publish it

The operator table on [Validations](../api-reference/steps/validations.md) is generated:

```bash
poetry run testlab docs
poetry run testlab docs --check
```

The cx-test-suite IDE offers operators as blocks too. Add the matching block there, or TCK authors using the IDE won't see the new operator.

## When an operator is not enough

An operator compares one value with one expectation. A check that needs a different input, the way `validate/schema` takes a `schema:` document, is a new assertion **kind**. That is a language change: it touches `AssertionKind` and `_PREFIX_TO_KIND` in `vocabulary.py`, the engine, the authoring models and the generated JSON Schemas (`testlab schema`). Propose it as an ADR under `docs/developer/decision-records/` before you write it.

If the check belongs in a TCK's `execution:` rather than under a step, it isn't an assertion at all. Write it as a step: see [Create a Step](create-a-step.md).
