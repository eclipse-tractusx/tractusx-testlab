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

# How to Debug Common Issues

For issues in the visual IDE (blocks, toolbox, YAML sync), see the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository — this page covers the engine.

## "Unknown step type" at validation or runtime

1. Check the `uses:` id against the generated [step reference](../specification/reference/steps.md), or ask the CLI directly:

    ```bash
    poetry run testlab docs --step connector/consumer/negotiate --json
    ```

    An unknown id makes the command exit with an error listing it.

2. If you are writing a new step, check the `@step("...")` decorator — the registered id must match `uses:` exactly, and the step's module must be imported (directly or via its package) in `src/tractusx_testlab/steps/__init__.py`, which is what registers everything.
3. For version-specific steps, `@step` takes a `dataspace_version`; a step registered only for one version produces a warning when validating with another. Pass the version explicitly:

    ```bash
    poetry run testlab validate my_test.yaml --version saturn
    ```

## Contract validation errors

`testlab validate` (and `testlab run`, before executing) reports every finding with its step index and field:

- **`Unknown step type '...'`** — see above.
- **`Variable '${...}' referenced ... is not declared`** — a warning: the variable is not in the script's own declarations, but may still arrive via shared variables, runtime overrides (`--var KEY=VALUE`), or a previous step's `returns:`.
- **`'validate.with.input' value '...' is not declared in 'returns'`** — inline assertions read only the step's declared `returns:`; add the name there or fix the typo.
- **Schema errors like `... is not valid under any of the given schemas (at 'steps.0' in tests/x.yaml)`** — the raw YAML violates `tck_index.schema.json` / `tck_test.schema.json`; the location in parentheses points at the offending key.

## A `returns:` value comes back empty

A `returns:` name must be one the step declares — its output fields, its published context variables, or the universal response fields (`status_code`, `headers`, `body`, `response_body`, `response_headers`, `duration_ms`, `value`, `request`, `response`, `exports`). An undeclared name fails at extraction rather than resolving to `None`. Check what a step actually declares:

```bash
poetry run testlab docs --step http/http_request --json
```

To capture a derived value under a name of your own, use the util steps that take `store_in_variable` (`util/json_path_extract`, `util/base64`, `util/parse_kv`).

## A mock endpoint is never hit

1. `mock/api` returns `full_mock_url` — that is the address to hand to the system under test; `base_mock_url` is only the server root.
2. `mock/wait/http_request` needs the `mock` object returned by the registering step, and fails after `timeout_s` (default 30s) — raise it if the SUT is slow to call back.
3. The mock server binds locally; make sure the SUT can actually reach the engine's host and port.

## Where to look at runtime

- `testlab run` writes its log files to `./logs` by default; point it elsewhere with `--logs-dir`.
- `testlab inspect <package>` shows what a compiled `.tck` actually contains (`--show-variables`, `--show-infrastructure`, `--json`).
- Every failed step reports the step id, the exception, and — for `validate/*` steps — the operator and the compared values in its error message.
