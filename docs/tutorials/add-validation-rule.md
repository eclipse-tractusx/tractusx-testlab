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

# Add a Validation Rule

Static validation is what `testlab validate` reports and what `testlab compile` refuses to compile past. Its job is to turn a mistake that would surface twenty steps into a run into a sentence pointing at the line that caused it.

This tutorial adds a real missing check: **two steps in one phase must not share an id.** Today this test validates:

```yaml
execution:
  - id: send_notification
    uses: http/http_request
    ...
  - id: send_notification        # same id again
    uses: mock/wait/http_request
    ...
```

Afterwards, `${{ execution.send_notification.request_body }}` can only reach one of the two steps, and nothing says which.

## Pick the layer

`Compiler.validate()` runs every layer and merges the findings. The right layer is decided by what the rule needs to know:

| The rule needs… | Put it in | Example |
|---|---|---|
| only the shape of one key: a type, an enum, a required field | the **authoring models** (`models/authoring/`), then regenerate the JSON Schemas | `kind: test`, `syntax: v1-alpha` |
| the raw documents: a file on disk, one test file as a whole, the manifest's `env:` | a **rule function** collected by `compiler/validation/_manifest_validation.py` | referenced schema files exist, banned `uses:` prefixes, variable declarations |
| the step registry: what a `uses:` id accepts and publishes | **`TestValidator`** in `compiler/validation/validator.py` | unknown step ids, `returns:` names the step doesn't publish, assertion inputs |

Duplicate ids need neither the registry nor a type. They need one test file as a whole, so this is a rule function.

The layout rules apply here too. `_manifest_validation.py` and `validator.py` are both over the 300-line limit and listed in `tests/unit/structure/test_module_layout.py`, so they may not grow beyond their recorded size. New logic goes in its own module named for what it checks, as `_variable_declarations.py` already does. The existing module only gains the line that calls it.

## 1. Write the rule in its own module

`src/tractusx_testlab/compiler/validation/_step_ids.py` (after the license header and AI notice):

```python
"""Step ids are how a test refers to a step, so within a phase each names one step."""

from __future__ import annotations

from collections import Counter
from typing import Any

#: The phases a test file lists steps in; ``${{ <phase>.<id>.<output> }}`` reads one.
_PHASES = ("setup", "execution", "teardown")


def reject_duplicate_step_ids(test_data: dict[str, Any], source_label: str) -> list[str]:
    """Reject a step id used twice in one phase, which makes its outputs unreachable."""
    errors: list[str] = []
    for phase in _PHASES:
        steps = test_data.get(phase)
        if not isinstance(steps, list):
            continue
        counts = Counter(step.get("id") for step in steps if isinstance(step, dict))
        errors.extend(
            f"{source_label}: step id '{step_id}' is used by {count} steps in '{phase}'. "
            f"'${{{{ {phase}.{step_id}.<output> }}}}' can only name one of them — rename the others."
            for step_id, count in counts.items()
            if step_id and count > 1
        )
    return errors
```

A rule function has a fixed shape: it takes the parsed test document and the label to name it by, and returns every problem it found. It returns an empty list when there are none, and it never raises and never stops at the first finding. The author should see every problem in one run, not one per compile.

## 2. Register it in the table

Per-file rules are rows in `_TEST_FILE_RULES`, at the bottom of `_manifest_validation.py`. Every row runs against every test file the manifest lists, so there is no call site to remember:

```python
from tractusx_testlab.compiler.validation._step_ids import reject_duplicate_step_ids

_TEST_FILE_RULES: tuple[Callable[[dict[str, Any], str], list[str]], ...] = (
    _check_test_schema,
    _reject_banned_steps,
    reject_duplicate_step_ids,
)
```

Two rules there are already tables. Extend the table rather than writing a function:

- **A `uses:` prefix the dialect no longer accepts**: add a `BannedStep(prefix, reason)` row to `_BANNED_STEPS`. `reason` completes the sentence `'<uses>' …`.
- **An `env:` collection whose entries name a file**: add a `FileCollection(key, noun)` row to `_FILE_COLLECTIONS`.

A rule about the manifest itself, rather than about each test, takes the manifest data and joins the list at the top of `validate_tck_manifest()`, next to `_validate_file_refs`.

## 3. Write the message for the TCK author

The reader is someone certifying a component, not someone who knows the engine. A finding is a defect if it:

- quotes Pydantic, jsonschema or YAML library output,
- gives a list position (`execution.1`) where a step id would do, or
- says what is wrong without saying what to write instead.

Name the file, the phase and the step id, and end with the fix. When a finding comes from a Pydantic `ValidationError` or a YAML error, render it through `tractusx_testlab.syntax.diagnostics` (`explain`, `unparseable`). That module adds the line number, the keys that would have been accepted and a did-you-mean.

In `TestValidator`, report through the `ValidationResult` instead of returning strings. Pass `step_index`, `field` and `phase` so the CLI prints `(execution step 2)`. `add_error()` makes the TCK invalid, while `add_warning()` is shown but doesn't block. Use a warning only when the construct can be right: a warning that is usually noise trains people to ignore all of them.

## 4. Test it

Tests for `compiler/validation` live in `tests/unit/compiler/`. Cover the rule directly and through the command an author runs:

```python
from tractusx_testlab.compiler.validation._step_ids import reject_duplicate_step_ids


def test_a_repeated_id_in_one_phase_is_named() -> None:
    test = {"execution": [{"id": "fetch", "uses": "http/http_request"}] * 2}

    [error] = reject_duplicate_step_ids(test, "tests/fetch.yaml")

    assert "'fetch' is used by 2 steps in 'execution'" in error


def test_the_same_id_in_different_phases_is_allowed() -> None:
    step = {"id": "fetch", "uses": "http/http_request"}

    assert reject_duplicate_step_ids({"setup": [step], "execution": [step]}, "t") == []
```

Then confirm the rule doesn't reject anything that ships. The example TCKs are validated in `tests/examples/`:

```bash
poetry run pytest tests/unit/compiler tests/examples tests/unit/structure -q
poetry run testlab validate docs/examples/certificate-management-v2/raw/index.yaml
```

## 5. If you changed the models

A constraint added to `models/authoring/` also changes the JSON Schemas under `compiler/schemas/`. The cx-test-suite IDE validates against those schemas, and they are generated, not hand-written:

```bash
poetry run testlab schema
poetry run testlab schema --check    # CI fails when the committed schemas are stale
```

A constraint that changes what a valid TCK looks like is a change to the language, not only to the engine. Update the [TCK syntax](../tck-syntax/index.md) pages in the same change.
