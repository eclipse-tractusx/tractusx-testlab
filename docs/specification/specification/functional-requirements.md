<!--

Eclipse Tractus-X - Tractus-X TestLab

Copyright (c) 2026 Catena-X Automotive Network e.V.
Copyright (c) 2026 Contributors to the Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

This work is made available under the terms of the
Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
which is available at
https://creativecommons.org/licenses/by/4.0/legalcode.

SPDX-License-Identifier: CC-BY-4.0

-->

# Functional Requirements

Each requirement carries its status in `1.0.0a3`: **Done** (implemented), **Partial** (implemented with the
limitation noted), or **Open** (specified, not implemented).

## Test Authoring (FR-AUTH)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-AUTH-01 | TCKs SHALL be authored in YAML: an `index.yaml` manifest (`kind: tck`) and one file per test (`kind: test`), both declaring `syntax: v1-alpha`. | Must | Done |
| FR-AUTH-02 | A TCK SHALL declare the dataspace it targets in `dataspace` (`ecosystem`, `version`, e.g. `saturn`, `jupiter`). | Must | Done |
| FR-AUTH-03 | A TCK SHALL declare shared variables in `env.variables` as a list of entries with `id`, `uses` (the variable type), `with.source` (`value` or `input`), and `returns.value`. `source: input` variables SHALL declare `scope: engine` or `scope: sut`. | Must | Done |
| FR-AUTH-04 | Step parameters SHALL reference values with `${{ }}` expressions: `env.<id>`, `env.schemas.<id>`, `env.testdata.<id>`, `setup.<step>.<output>`, `execution.<step>.<output>`, `infrastructure.<side>.<capability>.<field>`. | Must | Done |
| FR-AUTH-05 | `source: input` variables SHALL be supplied at run time (`--var`, a run config, or `runtime_vars`); a run missing one SHALL be refused before it starts, naming the variables. | Must | Done |
| FR-AUTH-06 | Steps SHALL declare a `uses:` field naming a registered step. Parameters are passed via `with:`, readable outputs declared via `returns:`, checks via `validate:`. | Must | Done |
| FR-AUTH-07 | Steps SHALL NOT declare per-step failure handling. A failed step fails the test: the remaining steps are skipped and teardown runs. | Must | Done |
| FR-AUTH-08 | Each step MAY specify `timeout_s`; a step exceeding it SHALL fail. | Should | Partial — accepted and compiled into the IR, not enforced at run time; steps with their own `timeout`/`timeout_s` parameter enforce that |
| FR-AUTH-09 | Tests MAY declare `setup` and `teardown` phases around `execution`. Teardown steps SHALL always run. | Must | Done |
| FR-AUTH-10 | The manifest SHALL list its tests in execution order (`tests[].id` = file name, optional `name`, `skippable`). Tests SHALL NOT read each other's outputs. | Must | Done |
| FR-AUTH-11 | Steps MAY declare `if:` — `success()`, `failure()`, `always()`, `steps.<id>.outcome == '…'`, or `vars.<name>` comparisons — evaluated in setup and execution. | Should | Done |

## Expected Results / Assertions (FR-ASSERT)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-ASSERT-01 | Each step MAY declare a `validate` block of assertions evaluated against the step's declared returns. | Must | Done |
| FR-ASSERT-02 | Assertions SHALL be `validate/assert` (the value at `input`), `validate/field` (the value at `path` inside `input`) or `validate/schema` (JSON Schema). The operator MAY be given as `with.operator` or as a `uses` suffix (`validate/assert/equals`). | Must | Done |
| FR-ASSERT-03 | Operators SHALL be `not_null`, `is_null`, `not_empty`, `equals`, `not_equals`, `contains`, `not_contains`, `matches_regex`, `one_of`, `none_of`, `has_key`, `not_has_key`, `gt`, `gte`, `lt`, `lte`, `length_equals`, `length_gt`, `length_lt`, `between`, shared with `flow/if` conditions. | Must | Done |
| FR-ASSERT-04 | Each assertion MAY declare `severity`: `HARD` (default; failure fails the step) or `SOFT` (failure is a warning). | Must | Done |
| FR-ASSERT-05 | Each assertion MAY carry a `name`, used by the run report to identify it. | Should | Done |
| FR-ASSERT-06 | Assertion results SHALL be recorded per step in `StepResult.assertions` and summarised per test in `TestResult.assertion_summary`. | Must | Done |

## Compilation (FR-COMP)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-COMP-01 | The Compiler SHALL accept a manifest file (`testlab validate`, `testlab compile`) and a YAML document posted to `POST /testlab/compile`. | Must | Done |
| FR-COMP-02 | Compilation SHALL reject a `${{ }}` reference that names nothing the TCK supplies, listing what is available. | Must | Done |
| FR-COMP-03 | Compilation SHALL reject a `uses:` id not registered for the TCK's dataspace version. | Must | Done |
| FR-COMP-04 | Compilation SHALL reject a manifest or test that does not match the JSON Schemas, a `source: input` variable without `scope`, a variable whose `returns` disagrees with its type, and a test whose file is missing. | Must | Done |
| FR-COMP-05 | Compilation SHALL reject a `with:` key the step does not accept. | Should | Open — rejected at run time, when the step validates its parameters |
| FR-COMP-06 | Compilation SHALL stamp the compilation timestamp, compiler version, fingerprint, and a `blake2b` package checksum. | Must | Done |

## Packaging (FR-PKG)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-PKG-01 | The Compiler SHALL produce a `.tck` ZIP archive containing `manifest.yaml`, `tck-bundle.yaml`, `tck-execution.json`, `tests/` and `assets/`. | Must | Done |
| FR-PKG-02 | `manifest.yaml` SHALL record the package format and checksum, the TCK id, metadata, dataspace and infrastructure, the compilation fingerprint, the test list with source hashes, and asset digests. | Must | Done |
| FR-PKG-03 | On load, the checksum SHALL be verified over every entry; a package whose contents differ SHALL be refused. | Must | Done |
| FR-PKG-04 | Schemas and testdata declared in `env` SHALL be bundled under `assets/`. | Must | Done |
| FR-PKG-05 | `testlab inspect` SHALL report a package's tests, steps, validations, variables, infrastructure and manifest without executing it, and `--extract` SHALL write its verified contents. | Must | Done |

## Player / Execution (FR-PLAY)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-PLAY-01 | The Player SHALL be usable as `TestlabPlayer(config)` and from the CLI (`testlab run`) and server. | Must | Done |
| FR-PLAY-02 | `testlab run` SHALL accept a manifest (compiled to a temporary package first) or a `.tck`; `TestlabPlayer.run` SHALL accept a `.tck` and `run_tck` a loaded TCK. | Must | Done |
| FR-PLAY-03 | Before the first test, the Player SHALL refuse a run whose required infrastructure is not bound, whose input variables are missing, or whose `skip_tests` names an unknown or non-skippable test. | Must | Done |
| FR-PLAY-04 | The Player SHALL execute tests with `asyncio`, sequentially, in manifest order, each with its own `StepContext`. | Must | Done |
| FR-PLAY-05 | For each step the Player SHALL evaluate `if:`, resolve references, look the step up by `(uses, dataspace_version)`, validate `with:`, execute, publish every output field under the step id, and evaluate `validate:`. | Must | Done |
| FR-PLAY-06 | A failed step SHALL stop its phase and skip the rest of the test; teardown SHALL run and keep executing when one of its steps fails. | Must | Done |
| FR-PLAY-07 | Tests marked `skippable: true` and named in `skip_tests` SHALL be reported `SKIPPED` and not counted as passes. | Must | Done |
| FR-PLAY-08 | Jobs SHALL be cancellable, pausable and resumable by `job_id`. | Should | Done |

## Job Lifecycle (FR-JOB)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-JOB-01 | Every execution SHALL create a `Job` with a unique `job_id`, status `QUEUED`, runtime variables, memory, and a creation timestamp. | Must | Done |
| FR-JOB-02 | Jobs SHALL move through `QUEUED` → `RUNNING` (↔ `PAUSED`) → `COMPLETED` / `FAILED` / `CANCELLED`. | Must | Done |
| FR-JOB-03 | A job blocked on an external callback SHALL be `WAITING`, with `waiting_for` naming the listener, and time out as `TIMED_OUT`. | Should | Open — the states exist; a waiting step keeps the job `RUNNING` and a timeout fails the step |
| FR-JOB-04 | The Job SHALL record lifecycle events and, on completion, the `TckResult`. | Must | Done |
| FR-JOB-05 | Jobs SHALL be queryable: `GET /testlab/tck-execution[?status=]`, `GET /testlab/tck-execution/{job_id}`. | Must | Done |

## Monitoring and Events (FR-MON)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-MON-01 | The `ExecutionMonitor` SHALL publish typed events (`EventKind`) for job, test, step, call, listener and assertion transitions to registered callbacks. | Must | Done |
| FR-MON-02 | The server SHALL stream a job's events over SSE at `GET /testlab/tck-execution/{job_id}/stream`, replaying missed events after `Last-Event-ID`. | Must | Done |
| FR-MON-03 | Job state SHALL be persistable across restarts. | Could | Open — jobs are held in memory |

## Logging (FR-LOG)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-LOG-01 | Every run SHALL write a CloudEvents v1.0 JSON-lines execution trace to `<data_dir>/<date>/<time>_<job_id>.jsonl`. | Must | Done |
| FR-LOG-02 | Every run SHALL write a plain-text transcript of its console output to `<logs_dir>/<date>/<time>_<job_id>.log`. | Must | Done |
| FR-LOG-03 | The console SHALL end with one result table per test and a run summary table. | Must | Done |
| FR-LOG-04 | For steps that make HTTP calls, the trace SHALL record the request and response, and every call under `exchanges` when there are several. | Must | Done |
| FR-LOG-05 | A failed step SHALL record `errors[]` with `code`, `origin` (`sut` or `engine`), `retryable`, `message` and, where available, structured `context`. | Must | Done |
| FR-LOG-06 | Credential headers SHALL be redacted (`***`) in the trace and transcript. | Must | Done |

## Step Registry (FR-REG)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-REG-01 | The registry SHALL map `uses` ids to step classes, either for every dataspace version or for one (`(step_type, dataspace_version)`). | Must | Done |
| FR-REG-02 | Steps SHALL register with `@step("<category>/<module>/<function>")` from `tractusx_testlab.authoring.registry`, and be imported by `tractusx_testlab.steps`. | Must | Done |
| FR-REG-03 | The registry SHALL enumerate step types, optionally per dataspace version (`StepRegistry.list_step_types`). | Should | Done |
| FR-REG-04 | The step reference SHALL be generated from the registered contracts (`testlab docs`) and checked for drift (`testlab docs --check`). | Must | Done |

## Predefined Steps (FR-STEP)

The complete list, with every input and output, is the generated [Step Reference](../../api-reference/steps/index.md).
The core connector and data-plane steps are:

| ID | Step Id | Outputs | Priority | Status |
|----|---------|---------|----------|--------|
| FR-STEP-01 | `connector/provider/create_asset` | `asset_id` | Must | Done |
| FR-STEP-02 | `connector/provider/create_policy` | `policy_id` | Must | Done |
| FR-STEP-03 | `connector/provider/create_contract_definition` | `contract_definition_id` | Must | Done |
| FR-STEP-04 | `connector/consumer/query_catalog` | `catalog`, `datasets` | Must | Done |
| FR-STEP-05 | `connector/consumer/negotiate` | `negotiation_id`, `agreement_id`, `state` | Must | Done |
| FR-STEP-06 | `connector/consumer/initiate_transfer` | `transfer_id`, `state`, `edr_entry`, `dataplane_url`, `edr_token`, `data_address` | Must | Done |
| FR-STEP-07 | `connector/consumer/get_edr` | `dataplane_url`, `edr_token`, `data_address` | Must | Done |
| FR-STEP-08 | `connector/provider/delete_contract_definition`, `delete_asset`, `delete_policy` | `status_code` | Must | Done |
| FR-STEP-09 | `connector/dataplane/http_request` | The response body; `dataplane_url` / `edr_token` fall back to the context variables of those names | Must | Done |
| FR-STEP-10 | `connector/consumer/pull_data_filtered` | `dataplane_url`, `edr_token`, `token_prefix`, `catalog`, `datasets`, `asset_id`, `negotiation_id`, `agreement_id`, `transfer_id` | Must | Done |

## Typed Step Execution (FR-SDK)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-SDK-01 | Every step SHALL be a typed executor with a declared input model and output model. YAML SHALL NOT be able to invoke arbitrary SDK functions. | Must | Done |
| FR-SDK-02 | Input models SHALL forbid unknown keys; malformed parameters SHALL fail the step with a message naming the field. | Must | Done |
| FR-SDK-03 | Steps SHALL publish exactly the fields of their declared output; `returns:` names and assertions SHALL resolve against that contract. | Must | Done |

## Infrastructure and Services (FR-SVC)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-SVC-01 | A TCK SHALL declare required capabilities per side in `infrastructure` (`engine`/`sut` × `connector`/`dtr`, each `required` and optionally `standard`). | Must | Done |
| FR-SVC-02 | The operator SHALL bind capabilities in `testlab.config.yaml` or `TESTLAB_<SIDE>_<CAPABILITY>_<FIELD>` environment variables; `testlab config` SHALL show what resolved. | Must | Done |
| FR-SVC-03 | The Player SHALL seed SDK services for the bound capabilities once per run and tear them down afterwards. | Must | Done |
| FR-SVC-04 | Steps SHALL NOT name a service; connector steps SHALL default the counter-party to the bound SUT connector. | Must | Done |
| FR-SVC-05 | A step whose capability was not seeded SHALL fail with an error naming the missing service type. | Must | Done |

## Mock Endpoints and Callbacks (FR-CB)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-CB-01 | `mock/api` SHALL register an endpoint (`path`, `method`, canned `response_status` / `response_body` / `response_headers`) and output the `mock` and its `full_mock_url`. | Must | Done |
| FR-CB-02 | `mock/wait/http_request` SHALL block until a request arrives on the given `mock`, up to `timeout_s`, and output `request_method`, `request_path`, `request_headers`, `request_query_params`, `request_body`, `elapsed_ms`; on timeout the step SHALL fail. | Must | Done |
| FR-CB-03 | `mock/dtr` and `mock/discovery` SHALL serve a protocol-aware Digital Twin Registry and BPN Discovery mock. | Should | Done |
| FR-CB-04 | The Player SHALL start the TestLab server on `server_port` for a run; mock registrations SHALL last for that run. | Must | Done |

## Server (FR-SRV)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-SRV-01 | `testlab serve` SHALL start the FastAPI server (`--host`, `--port`, default `0.0.0.0:8000`). | Must | Done |
| FR-SRV-02 | The server SHALL expose package endpoints (`POST`/`GET /testlab/packages`, `DELETE /testlab/packages/{id}`), limited to `max_upload_bytes`. | Must | Partial — every package is reported `format: ENCRYPTED`; the listing reports the file stem as `name` and no `version` |
| FR-SRV-03 | The server SHALL run an uploaded or on-disk package (`POST /testlab/run/package`) and a posted YAML TCK (`POST /testlab/tck-execution/run`). | Must | Partial — encrypted packages cannot be run through the server |
| FR-SRV-04 | The server SHALL validate a posted YAML document (`POST /testlab/compile`), answering `{status, errors[{path, message}]}`. | Must | Done |
| FR-SRV-05 | The server SHALL serve callback endpoints under `/testlab/callbacks/{path}` and refuse paths no step registered. | Must | Done |
| FR-SRV-06 | The Player SHALL be mountable into a host FastAPI application. | Could | Open |

## Package Security (FR-SEC)

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-SEC-01 | `testlab keygen` SHALL generate an RSA-4096 encryption pair and an Ed25519 signing pair into `<out-dir>/<label>/`. | Must | Done |
| FR-SEC-02 | Given `--compiler-keys` and one or more `--player-pub`, the Compiler SHALL encrypt the content with AES-256-GCM, wrap the key with RSA-OAEP-SHA256 for each Player, and sign with the Compiler's Ed25519 key. Supplying only one of the two SHALL be an error. | Must | Done |
| FR-SEC-03 | The encrypted package's `manifest.yaml` SHALL stay readable and carry `security.compiler_id` and `authorized_players[{player_id, encrypted_key}]`, without test files or asset paths. The Compiler's signature SHALL cover it together with `payload.enc`. | Must | Done |
| FR-SEC-04 | The Player SHALL refuse an encrypted package without `--player-keys`, without `--compiler-pub`, without a signature, or with a signature that does not verify. | Must | Done |
| FR-SEC-05 | The Player SHALL decrypt with the key block matching its own fingerprint and load the TCK. | Must | Done |
| FR-SEC-06 | Players SHALL accept packages from Compilers in a trust store, and keys MAY be kept in HashiCorp Vault. | Could | Partial — the server Player reads its identity from `keys_dir` and trusted Compilers from `trust_store_dir`; `vault` is not wired in |

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)