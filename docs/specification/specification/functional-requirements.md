<!--

Eclipse Tractus-X - Software Development KIT

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

## Script Authoring (FR-AUTH)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-AUTH-01 | Scripts SHALL be authored in YAML format. | Must |
| FR-AUTH-02 | Each script SHALL declare a `dataspace_version` field specifying the target connector protocol version (e.g., `"saturn"`, `"jupiter"`). If omitted, it defaults to `"saturn"`. | Must |
| FR-AUTH-03 | Scripts SHALL declare variables in a `variables` block. Each variable SHALL specify a `type` and optionally a `default` value, a `runtime: true` flag, and a `description`. | Must |
| FR-AUTH-04 | Step parameters SHALL support `${variable_name}` template syntax. These references are resolved at execution time from the `StepContext`. | Must |
| FR-AUTH-05 | Variables marked `runtime: true` SHALL NOT require a default value. Their values MUST be provided at execution time via `runtime_vars`. | Must |
| FR-AUTH-06 | Steps SHALL declare a `uses:` field naming a registered step id in the Step Registry (e.g., `connector/provider/create_asset`). Parameters are passed via `with:` and declared outputs via `returns:`. | Must |
| FR-AUTH-07 | Steps SHALL NOT declare per-step failure handling. A failing step fails the test: execution stops and cleanup runs. Failed validations (hard assertions) fail their step. | Must |
| FR-AUTH-08 | Each step MAY specify a `timeout_s` value. If the step exceeds this timeout, it SHALL be treated as a failure. | Should |
| FR-AUTH-09 | Scripts SHALL define an optional `cleanup` block — a list of steps that always execute regardless of prior step failures. | Must |
| FR-AUTH-10 | Test cases SHALL be authored as YAML files (`tck.yaml`) containing an ordered `tests` list and optionally `shared_variables` available to all tests. Test cases SHALL support importing predefined tests via `import:` with optional `override:` blocks. | Must |

## Expected Results / Assertions (FR-ASSERT)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-ASSERT-01 | Each step MAY declare an `validate` block containing a list of assertions to evaluate against the step's output. | Must |
| FR-ASSERT-02 | Assertions SHALL support the following types: `exact` (deep equality), `schema` (JSON Schema validation), `contains` (subset match), `regex` (pattern match), `status_code` (HTTP status comparison). | Must |
| FR-ASSERT-03 | Each assertion SHALL declare a `severity`: `hard` (assertion failure = step failure) or `soft` (assertion failure = warning, step still passes). | Must |
| FR-ASSERT-04 | Expected values SHALL be sourceable from three origins via the `source` field: `inline` (value embedded directly in YAML), `file` (loaded from a file path, resolved relative to `.tck` assets or local filesystem), `variable` (value is a `${var}` reference resolved from context). Default: `inline`. | Must |
| FR-ASSERT-05 | Inline values SHALL accept both native YAML structures and raw JSON strings. When a string value is valid JSON, the assertion engine SHALL auto-parse it before comparison. | Must |
| FR-ASSERT-06 | Each assertion MAY specify a `field` property (dot-notation path with bracket indexing, e.g., `response.submodels[0].payload.catenaXId`) to target a specific field in the step output. When omitted, the assertion evaluates against the entire output. | Should |
| FR-ASSERT-07 | Assertion results SHALL be recorded per step in `StepResult.assertions` and summarized per script in `ScriptResult.assertion_summary` (total, passed, failed_hard, failed_soft). | Must |

## Compilation (FR-COMP)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-COMP-01 | The Compiler SHALL accept YAML source as a file path, string, or dict (for programmatic/API input). | Must |
| FR-COMP-02 | Compilation SHALL validate all `${var}` references in step parameters. Every reference MUST match a declared variable or a `shared_variable` (in TCKs). Unresolved references that are not declared `runtime: true` SHALL cause compilation failure. | Must |
| FR-COMP-03 | Compilation SHALL validate every step's `uses:` id exists in the Step Registry for the script's declared `dataspace_version`. Unknown step ids SHALL cause compilation failure. | Must |
| FR-COMP-04 | Compilation SHALL stamp metadata: SDK version, compilation timestamp, SHA-256 checksum. | Must |
| FR-COMP-05 | Compilation failures SHALL produce a `ValidationResult` containing a list of errors and warnings with clear, actionable messages. | Must |
| FR-COMP-06 | For TCKs, the Compiler SHALL perform cross-test validation: shared variables must be consistent, and all tests must be individually valid. The Compiler SHALL resolve `import:` references from the library path and merge `override:` blocks. | Must |

## Packaging (FR-PKG)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PKG-01 | The Packager SHALL produce a `.tck` file — a ZIP archive containing: `manifest.yaml`, `scripts/` directory with compiled script YAML files, and an optional `assets/` directory with bundled files (schemas, sample data). | Must |
| FR-PKG-02 | The `manifest.yaml` SHALL contain: package name, version, SDK version, compilation timestamp, list of dataspace versions used across scripts, list of script names, and SHA-256 checksum. | Must |
| FR-PKG-03 | The Packager SHALL support unpacking: `unpack(path) -> CompiledTck`. On unpack, the SHA-256 checksum SHALL be verified. Tampered packages SHALL be rejected. | Must |
| FR-PKG-04 | A single `.tck` SHALL support bundling multiple tests (a TCK). | Must |
| FR-PKG-05 | File-sourced assertion values (schemas, expected payloads) SHALL be bundled in the `assets/` directory of the `.tck` and resolved at execution time via `StepContext.resolve_asset_path()`. | Must |

## Player / Execution (FR-PLAY)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PLAY-01 | The Player SHALL be a singleton instance (module-level), accessible as `testlab.player`. | Must |
| FR-PLAY-02 | The Player SHALL load test packages from: `.tck` file path, raw YAML file/string (compile-on-load), or pre-compiled dict. | Must |
| FR-PLAY-03 | On loading a `.tck`, the Player SHALL verify the SHA-256 checksum and emit a warning if the SDK version in the manifest differs from the running SDK version. It SHALL NOT hard-fail on SDK version mismatch. | Must |
| FR-PLAY-04 | The Player SHALL execute scripts asynchronously using `asyncio`. | Must |
| FR-PLAY-05 | For each script, the Player SHALL create an isolated `StepContext` initialized with the script's `dataspace_version`, declared variable defaults, and any provided `runtime_vars`. The context SHALL also hold a reference to the parent `Job`. | Must |
| FR-PLAY-06 | Steps SHALL be executed sequentially in declared order. For each step, the Player SHALL: (1) resolve `${var}` references from the context, (2) look up the step implementation from the registry by `(uses id, dataspace_version)`, (3) execute with `asyncio.wait_for(timeout)`, (4) evaluate assertions from the `validate` block, (5) record the `StepResult` in the Monitor. | Must |
| FR-PLAY-07 | Step implementations SHALL publish all of their return outputs into the `StepContext` after execution: every top-level field of the declared output becomes a context variable of the same name, and a `None` value leaves the variable unset. These variables become available to subsequent steps via variable references; explicit capture into a named variable uses `store_in_variable` on the utility steps that offer it. Steps MAY also write to job memory via `context.job.memory.set(key, value)` for cross-script persistence. | Must |
| FR-PLAY-08 | On step failure, the Player SHALL stop execution immediately, mark the remaining steps as skipped, run cleanup, and fail the test. Cleanup steps SHALL keep executing even when one of them fails. | Must |
| FR-PLAY-09 | Cleanup steps SHALL always execute regardless of prior step outcomes. | Must |
| FR-PLAY-10 | The Player SHALL support running multiple jobs concurrently (each in a separate `asyncio.Task` with an isolated `StepContext` and independent `Job` instance). | Should |
| FR-PLAY-11 | The Player SHALL support cancellation by `job_id`. Cancellation SHALL transition the job to `CANCELLED`, stop execution after the current step completes, and run cleanup steps. | Should |
| FR-PLAY-12 | For TCKs, tests SHALL execute sequentially. Shared variables SHALL be propagated to each test's context. Each test SHALL have an isolated context (no variable leakage between tests beyond shared variables). Job memory SHALL be shared across all tests within the same job. | Must |

## Job Lifecycle (FR-JOB)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-JOB-01 | Every test execution (CLI, API, or Python) SHALL create a `Job` entity with a unique `job_id`, status `QUEUED`, an empty `JobMemory`, and a creation timestamp. | Must |
| FR-JOB-02 | The Job SHALL transition through defined lifecycle states: `QUEUED` → `RUNNING` → (`WAITING` ↔ `RUNNING`)* → `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT`. Invalid transitions SHALL be rejected. | Must |
| FR-JOB-03 | When a step enters a wait state (e.g., `mock/wait/http_request`, polling for a state transition), the Job SHALL transition to `WAITING`. The `waiting_for` field SHALL describe the pending condition (e.g., `"callback: /callbacks/notif-ack"`, `"poll: transfer state=COMPLETED"`). | Must |
| FR-JOB-04 | When the awaited condition is met (callback received, poll condition satisfied), the Job SHALL automatically transition back to `RUNNING` and resume execution from the waiting step. | Must |
| FR-JOB-05 | The `JobMemory` SHALL provide a persistent key-value store (`set`, `get`, `has`) and an event log (`log_event`). Memory SHALL persist across all steps, scripts, wait/resume cycles, and cleanup phases within the same job. | Must |
| FR-JOB-06 | Steps SHALL publish every top-level field of their declared output as a context variable after execution; utility steps that offer `store_in_variable` SHALL store their result under the given variable name. Step implementations MAY additionally write to job memory programmatically via `context.job.memory.set(key, value)`. Published variables SHALL be accessible in subsequent steps via variable references. | Must |
| FR-JOB-07 | The Player SHALL record `JobEvent` entries for significant lifecycle transitions: job created, script started/completed, step started/completed/failed, job entered/exited waiting state, job completed/failed/cancelled. | Must |
| FR-JOB-08 | If a job remains in `WAITING` state beyond the step's configured `timeout_s`, the job SHALL transition to `TIMED_OUT` with an error message identifying the unmet wait condition. Cleanup steps SHALL still execute. | Must |
| FR-JOB-09 | The `Job` entity SHALL be queryable at any time: `get_job(job_id) -> Job`, `list_jobs(status?) -> list[Job]`. The query SHALL return current status, memory contents, event log, and result (if completed). | Must |

## Monitoring (FR-MON)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-MON-01 | The Monitor SHALL maintain in-memory state for all active and completed jobs, tests, and TCK runs. | Must |
| FR-MON-02 | The Monitor SHALL be queryable at any time: `get_job(job_id) -> Job`, `get_status(script_id) -> ScriptResult`, `get_current_step(script_id) -> StepResult`, `get_tck_status(tck_id) -> TckResult`, `list_jobs(status?) -> list[Job]`, `list_runs() -> list`. | Must |
| FR-MON-03 | The Monitor SHALL support event callbacks: `on_step_start`, `on_step_complete`, `on_script_complete`, `on_tck_complete`, `on_failure`, `on_job_waiting`, `on_job_resumed`. Users SHALL be able to register async callbacks. | Should |
| FR-MON-04 | The Monitor SHALL be thread-safe (protected by `asyncio.Lock`). | Must |
| FR-MON-05 | The Monitor SHALL expose a `SyncBackend` protocol interface for future persistence backends (e.g., PostgreSQL) to persist job state and memory across restarts. | Should |

## Logging (FR-LOG)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-LOG-01 | The logging system SHALL produce structured JSON-lines (`.jsonl`) log files. | Must |
| FR-LOG-02 | Each log entry SHALL contain: `timestamp`, `level`, `tck_id`, `script_id`, `script_name`, `dataspace_version`, `step_name`, `step_type`, `status`, `duration_ms`, `request`, `response`, `assertions`, `error`, `message`, `data`. | Must |
| FR-LOG-03 | Log files SHALL be organized as: `logs/testlab/{tck_name}/{YYYY-MM-DD}/{HH-MM-SS}_{tck_id}.jsonl`. | Must |
| FR-LOG-04 | On completion, the log file SHALL be renamed with a `_PASS` or `_FAIL` suffix. | Should |
| FR-LOG-05 | Console output SHALL provide a human-readable summary table (formatted like the existing TCK `print_summary` output). | Must |
| FR-LOG-06 | Assertion results (including soft failures) SHALL be logged with their expected vs. actual values. | Must |
| FR-LOG-07 | For HTTP-based steps, each log entry SHALL include the full request (`method`, `url`, `headers`, `body`) and full response (`status_code`, `headers`, `body`, `duration_ms`) as structured sub-objects. Non-HTTP steps SHALL set these fields to `null`. | Must |
| FR-LOG-08 | For failed or stopped steps, the log entry SHALL include an `error` object containing `type`, `message`, and `traceback`. | Must |
| FR-LOG-09 | Sensitive headers (e.g., `Authorization`) SHALL be automatically redacted in log output and API responses. Additional headers MAY be configured for redaction via `--redact-headers`. | Must |

## Step Registry (FR-REG)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-REG-01 | The registry SHALL map `(step_id, dataspace_version)` tuples to `BaseStep` implementations, where the step id is the `uses:` value (e.g., `connector/consumer/negotiate`). | Must |
| FR-REG-02 | Step implementations SHALL declare which dataspace versions they support via `supported_versions: list[str]`. | Must |
| FR-REG-03 | The registry SHALL auto-discover and register steps from the `steps/connector/` and `steps/industry/` packages at import time via the `@step` decorator. | Must |
| FR-REG-04 | Users SHALL be able to register custom step implementations at runtime: `registry.register("my_step", MyStepClass, versions=["saturn"])`. | Must |
| FR-REG-05 | The registry SHALL provide `list_available(version=None) -> list[str]` to enumerate available step types, optionally filtered by dataspace version. | Should |

## Predefined Steps (FR-STEP)

### Connector Steps

| ID | Step Id | Description | Priority |
|----|---------|-------------|----------|
| FR-STEP-01 | `connector/provider/create_asset` | Create a single asset on a provider connector. Output: `asset_id`. | Must |
| FR-STEP-02 | `connector/provider/create_policy` | Create a single policy (access or contract/usage) on a provider connector. Output: `policy_id`. | Must |
| FR-STEP-03 | `connector/provider/create_contract_definition` | Bind an asset to an access and a contract policy, making it appear in the provider's catalog. Output: `contract_definition_id`. | Must |
| FR-STEP-04 | `connector/consumer/query_catalog` | Query a provider's catalog from a consumer connector. Outputs: `catalog`, `datasets`. | Must |
| FR-STEP-05 | `connector/consumer/negotiate` | Initiate and poll contract negotiation until it settles. Outputs: `negotiation_id`, `agreement_id`, `state`. | Must |
| FR-STEP-06 | `connector/consumer/initiate_transfer` | Initiate a data transfer for a negotiated contract and wait for it to settle. Outputs: `transfer_id`, `state`, and for PULL transfers `dataplane_url`, `edr_token`, and the full `data_address` document. | Must |
| FR-STEP-07 | `connector/consumer/get_edr` | Retrieve the EDR (Endpoint Data Reference) for a completed transfer. Outputs: `endpoint`, `authorization`. | Must |
| FR-STEP-08 | `connector/provider/delete_contract_definition` | Delete a contract definition during teardown. | Must |
| FR-STEP-09 | `connector/provider/delete_asset` | Delete an asset during teardown. | Must |
| FR-STEP-10 | `connector/provider/delete_policy` | Delete a policy during teardown. | Must |

### Dataplane Steps

| ID | Step Id | Description | Priority |
|----|---------|-------------|----------|
| FR-STEP-11 | `connector/dataplane/http_request` | Perform an HTTP call to a dataplane endpoint using an EDR token. Supports configurable HTTP method (GET/POST/PUT/DELETE), path, custom headers, and request body. The `dataplane_url` and `edr_token` parameters fall back to the context variables of the same names published by prior steps, so the EDR authorization is injected automatically. Output: the response body (parsed JSON when the server sent JSON, otherwise raw text). | Must |

### Consumption & Validation Steps

| ID | Step Id | Description | Priority |
|----|---------|-------------|----------|
| FR-STEP-12 | `connector/consumer/pull_data_filtered` | Run the full DSP consumption flow in one step (catalog → negotiate → transfer → EDR), optionally constrained to one policy. Outputs include `dataplane_url`, `edr_token`, `asset_id`, `negotiation_id`, `agreement_id`, `transfer_id`. | Must |
| FR-STEP-13 | `validate/schema` | Validate a payload against a JSON Schema document (e.g., an aspect model schema declared in `env.schemas`). | Must |
| FR-STEP-14 | `validate/field` | Assert that a field at a dot-separated path of a payload satisfies an operator condition. | Should |

---

## Typed Step Execution (FR-SDK)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SDK-01 | Every step SHALL be a typed executor registered in the Step Registry under its `uses:` id, with a declared input contract (its `with:` parameters) and output contract (what `returns:` and assertions read). YAML SHALL NOT be able to invoke arbitrary SDK functions — SDK access happens only inside step implementations. | Must |
| FR-SDK-02 | Step parameters SHALL be validated against the step's declared input contract at compile time. Unknown step ids and malformed parameters SHALL be rejected with a clear error message. | Must |
| FR-SDK-03 | Steps SHALL publish exactly the fields of their declared output contract; `returns:` names and assertions SHALL be resolvable against that same contract. | Must |

## Managed Service Lifecycle (FR-SVC)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SVC-01 | Scripts MAY declare a `services` block listing SDK services to be initialized before step execution begins. Each service declaration SHALL specify: a `name` (unique identifier for `context.get_service()`), a `type` (one of `connector_consumer`, `connector_provider`, `dtr`), and connection parameters (`base_url`, `auth`). | Must |
| FR-SVC-02 | The Service Manager SHALL initialize all declared services before the first step executes. Initialization includes creating the SDK service instance via `ServiceFactory` (for connector services) or direct instantiation (for DTR/AAS), and performing authentication (e.g., OAuth2 token acquisition). | Must |
| FR-SVC-03 | Initialized services SHALL be accessible from steps via `context.get_service("service_name")`. The returned instance SHALL be the same (cached) object for the lifetime of the script, avoiding repeated initialization. | Must |
| FR-SVC-04 | All managed services SHALL be torn down (connections closed, resources released) after script execution completes, regardless of success or failure. Teardown SHALL occur after cleanup steps. | Must |
| FR-SVC-05 | The `init_service` step type SHALL allow initializing a new service or replacing an existing service during step execution. The `stop_service` step type SHALL allow explicitly tearing down a service before script completion. | Should |
| FR-SVC-06 | Steps SHALL NOT name their service in their parameters. Connector services are seeded into the run at startup from the declared `services` block; each step resolves the service for its role (provider, consumer, DTR) from the `StepContext` (e.g., `context.get_provider_service()`). | Must |
| FR-SVC-07 | Each predefined step SHALL resolve the service type its role requires (e.g., `connector_provider`, `connector_consumer`, `dtr`). When no seeded service satisfies the step's role, execution SHALL fail with a clear error identifying the step and the missing service type. | Must |
| FR-SVC-08 | Service resolution SHALL come exclusively from the services seeded into the run context — steps SHALL NOT construct one-off services from inline connection parameters. | Must |
| FR-SVC-09 | The `StepContext` SHALL expose service access methods: `get_service(name) -> Any` (raises `ServiceNotFoundError` or `ServiceNotReadyError`), `has_service(name) -> bool`, `get_service_type(name) -> ServiceType`, and `list_services() -> dict[str, ServiceType]`. | Must |
| FR-SVC-10 | The `ServiceManager` SHALL support: `initialize_all(services, dataspace_version)`, `get(name) -> (instance, type)`, `replace(name, definition, version)`, `stop(name)`, and `teardown_all()`. Duplicate service names during `initialize_all` SHALL raise `DuplicateServiceError`. | Must |
| FR-SVC-11 | Services in a non-READY state (failed initialization, explicitly stopped) SHALL NOT be returned by `ServiceManager.get()`. Accessing a non-ready service SHALL raise `ServiceNotReadyError`. | Must |

## Async Callbacks / Webhook Endpoints (FR-CB)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-CB-01 | Scripts MAY register a callback endpoint on the TestLab mock server via the `mock/api` step, declaring a `path` (e.g., `/callbacks/notification-ack`), an HTTP `method` (default: `POST`), and the canned response (`response_status`, `response_body`, `response_headers`). The step SHALL output the registered `mock` and its `full_mock_url` — the address a script hands to the system under test. | Must |
| FR-CB-02 | Registering a mock endpoint SHALL also register a callback listener for that `(path, method)` pair, so a later wait step can block on inbound requests to it. Inbound requests SHALL be answered with the canned response and signalled to the waiting step via an `asyncio.Event`. | Must |
| FR-CB-03 | The `mock/wait/http_request` step SHALL transition the parent Job to `WAITING` state, then block until an inbound request arrives on the referenced `mock`, up to `timeout_s`. On receipt, the request (`request_method`, `request_path`, `request_headers`, `request_query_params`, `request_body`) SHALL be exposed as the step's output for `returns:` and assertions. On timeout, the Job SHALL transition to `TIMED_OUT` and the step SHALL fail, failing the test. | Must |
| FR-CB-04 | Mock endpoint registrations SHALL live for the duration of the run; the mock server (and all registrations with it) SHALL be torn down when the run finishes. No mock state SHALL persist between runs. | Must |

## Player Deployment / Server (FR-SRV)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SRV-01 | The Player SHALL support **standalone mode** via a CLI command `testlab serve` that starts a FastAPI server on a configurable port (default: `8100`). The server SHALL expose job management endpoints (`/jobs`, `/jobs/{job_id}`, `/jobs/{job_id}/cancel`, `/jobs/{job_id}/memory`, `/jobs/{job_id}/events`), execution endpoints (`/run`), package management endpoints (`/packages`), and callback routes. | Must |
| FR-SRV-02 | The Player SHALL support **embedded mode** via `TestlabPlayer.from_app(fastapi_app)`, which mounts the testlab routes as a sub-application on an existing FastAPI instance. The Player SHALL share the host application's lifecycle (startup/shutdown). | Must |
| FR-SRV-03 | Dynamic API routes declared in YAML `listen` blocks SHALL be mountable and unmountable at runtime without restarting the server. In embedded mode, routes SHALL be mounted on the host application's router. | Should |
| FR-SRV-04 | The server SHALL expose a `POST /api/v1/packages` endpoint that accepts `.tck` files via multipart form upload. Both encrypted and plain packages SHALL be accepted. The server SHALL validate the package structure (manifest presence, checksum if plain) and store it in a configurable storage directory (default: `~/.testlab/packages/`). On success, the response SHALL return the `package_id` (derived from `name-version`), name, version, format (`PLAIN` or `ENCRYPTED`), size, upload timestamp, and checksum. | Must |
| FR-SRV-05 | The server SHALL expose `GET /api/v1/packages` (list all uploaded packages), `GET /api/v1/packages/{package_id}` (get metadata), and `DELETE /api/v1/packages/{package_id}` (remove a package). The `/run` endpoint SHALL accept a `package` field referencing either an uploaded `package_id` or a filesystem path. | Must |
| FR-SRV-06 | Package storage SHALL be scoped per server instance. The storage directory SHALL be configurable via `--storage-dir <path>` CLI flag or `TESTLAB_STORAGE_DIR` environment variable. The server SHALL reject uploads that exceed a configurable maximum size (default: 50 MB, configurable via `--max-upload-size`). | Should |

## Package Security (FR-SEC)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SEC-01 | The Compiler SHALL encrypt the `.tck` payload **by default** using AES-256-GCM with a randomly generated 256-bit key. An explicit `--plain` flag SHALL disable encryption for local development use only. When `--plain` is used, the Compiler SHALL emit a warning that the package contains unprotected secrets. | Must |
| FR-SEC-02 | The Compiler SHALL accept one or more `--authorize-player <public_key_file>` arguments. Each Player's RSA public key (2048-bit minimum) SHALL be used to wrap the AES content-encryption key via RSA-OAEP with SHA-256 padding. The resulting key blocks SHALL be stored in `manifest.yaml` under `security.authorized_players`. | Must |
| FR-SEC-03 | The Compiler SHALL sign the package (manifest + encrypted payload) using Ed25519 with a `--signing-key <compiler_pem>` argument. The signature SHALL be stored in the archive as `signature.sig`. The Compiler's public key fingerprint SHALL be recorded in `security.compiler_id`. | Must |
| FR-SEC-04 | The Player SHALL, on loading an encrypted `.tck`, locate its own `player_id` (public key fingerprint) in `security.authorized_players`. If not found, the Player SHALL abort with a clear `PackageAuthorizationError`. | Must |
| FR-SEC-05 | The Player SHALL decrypt the AES content-encryption key using its RSA private key (RSA-OAEP-SHA256), then decrypt `payload.enc` using AES-256-GCM. Decryption failures SHALL raise `PackageDecryptionError`. | Must |
| FR-SEC-06 | The Player SHALL verify the Ed25519 signature against compiler public keys stored in the trust store (`~/.testlab/trusted_compilers/`). If no matching trusted compiler key is found, or if the signature is invalid, the Player SHALL abort with `PackageSignatureError`. | Must |
| FR-SEC-07 | The CLI SHALL provide key management commands: `testlab keygen` (generate Player RSA key pair to `~/.testlab/keys/`), `testlab keygen --compiler` (generate Compiler Ed25519 + RSA key pair), and `testlab export-key --player` (export Player public key for sharing). | Must |
| FR-SEC-08 | Player identity SHALL be derived from the SHA-256 fingerprint of the DER-encoded RSA public key, formatted as `player:sha256:<hex_digest>`. Compiler identity SHALL use the same scheme with a `compiler:sha256:` prefix. | Must |
| FR-SEC-09 | Packages compiled with `--plain` SHALL remain fully functional (backward compatibility). The absence of a `security` block in `manifest.yaml` SHALL indicate an unencrypted (plain) package. When compiling without `--plain` and without `--authorize-player` or `--signing-key`, the Compiler SHALL raise `MissingEncryptionArgsError` with guidance to provide keys or use `--plain`. | Must |
| FR-SEC-10 | The `manifest.yaml` in an encrypted package SHALL remain unencrypted and human-readable, containing metadata, security block (algorithm, authorized players, compiler ID), but no secret material. Only the `payload.enc` blob SHALL be encrypted. | Must |
| FR-SEC-11 | The security module SHALL support an optional **HashiCorp Vault** backend for storing and retrieving signing keys (Compiler Ed25519 keys and Player RSA keys). When `vault_url`, `vault_token`, and `vault_secret_path` are configured, the `keygen`, `compile`, and `run` commands SHALL read/write keys from Vault instead of the local filesystem. | Should |
| FR-SEC-12 | Vault integration SHALL be configurable via a `testlab.config.yaml` configuration file, environment variables (`TESTLAB_VAULT_URL`, `TESTLAB_VAULT_TOKEN`, `TESTLAB_VAULT_SECRET_PATH`), or CLI flags (`--vault-url`, `--vault-token`, `--vault-secret-path`). The precedence order SHALL be: CLI flags > environment variables > configuration file > filesystem defaults. | Should |

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)