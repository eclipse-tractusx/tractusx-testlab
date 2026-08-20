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

# How to Add a New Validation Rule

Static validation runs in the compiler, before anything executes. It lives in `src/tractusx_testlab/compiler/validation/` and has two layers:

- **`validator.py`** — `ScriptValidator` walks the parsed `ScriptDefinition` step by step: unknown `uses:` ids, unresolved `${var}` references, inline `validate.with.input` values that are not declared in `returns:`, and so on.
- **`_rules.py`** — JSON-Schema validation of the raw TCK manifest and test files, plus rule functions that reject shapes the schema cannot express.

## Adding a script-level rule

Open `src/tractusx_testlab/compiler/validation/validator.py` and extend `_validate_step()` (or `validate()` for script-wide rules). Findings are reported through the `ValidationResult`:

```python
# Example: warn when a step declares returns but never validates them
if step_def.returns and not step_def.validate:
    result.add_warning(
        f"Step '{step_def.uses}' declares returns but has no validate block",
        step_index=idx,
        field="validate",
        phase=phase,
    )
```

`add_error()` makes the script invalid (`ValidationResult.valid` becomes `False`); `add_warning()` is reported but does not block. `step_index`, `field`, and `phase` locate the finding for the CLI output.

## Adding a manifest-level rule

Schema-expressible constraints go into the JSON schemas under `src/tractusx_testlab/compiler/schemas/` (`tck_index.schema.json`, `tck_test.schema.json`). Anything beyond the schema's reach becomes a rule function in `src/tractusx_testlab/compiler/validation/_rules.py`, returning a list of error strings that `validate_tck_manifest()` collects:

```python
def _reject_my_shape(test_data: dict[str, Any], source_label: str) -> list[str]:
    """Reject <the shape>, with the file name in every message."""
    errors: list[str] = []
    ...
    return errors
```

Add it to the `_TEST_FILE_RULES` table at the bottom of the module; every rule in it runs against every test file, so there is no call site to remember. A rule about the manifest itself instead takes the manifest data and is called from `validate_tck_manifest()` alongside `_validate_file_refs` and `_validate_variable_scopes`.

Two rules are already tables rather than code, and a new entry belongs in the table rather than in a new function:

- **A `uses:` prefix the dialect no longer takes** — add a `BannedStep(prefix, reason)` row. `reason` completes the sentence `'<uses>' …`, and `_reject_banned_steps` walks `setup`, `execution` and `teardown` for you.
- **A new `env:` collection whose entries name a file on disk** — add a `FileCollection(key, noun)` row. Both spellings of an entry (a list of `{id, source}` and a mapping of `name: {file}`) are already handled.

## Try it

```bash
poetry run testlab validate path/to/test.yaml --version saturn
poetry run pytest -k valid
```

> **Note:** The IDE performs its own real-time validation as the user edits; that counterpart lives in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository.
