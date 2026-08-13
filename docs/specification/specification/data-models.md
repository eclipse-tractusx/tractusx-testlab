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

# Data Models

## Enumerations

| Enum | Values | Description |
|------|--------|-------------|
| `StepStatus` | `PENDING`, `RUNNING`, `WAITING`, `PASSED`, `FAILED`, `SKIPPED` | Lifecycle state of a single step |
| `ScriptStatus` | `IDLE`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `SKIPPED` | Lifecycle state of a script run |
| `JobStatus` | `QUEUED`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT` | Lifecycle state of a job (test execution) |
| `AssertionType` | `EXACT`, `SCHEMA`, `CONTAINS`, `REGEX`, `STATUS_CODE` | Type of assertion check |
| `AssertionSeverity` | `HARD`, `SOFT` | Whether assertion failure fails the step or is a warning |
| `ValueSource` | `INLINE`, `FILE`, `VARIABLE` | Where the expected assertion value originates |
| `SdkCallMode` | `ALLOWLIST`, `OPEN` | SDK function invocation security mode |
| `ServiceType` | `CONNECTOR_CONSUMER`, `CONNECTOR_PROVIDER`, `DTR` | Type of managed SDK service |
| `PackageFormat` | `PLAIN`, `ENCRYPTED` | Whether the `.tckpkg` payload is unencrypted or encrypted |
| `ServiceState` | `DECLARED`, `INITIALIZING`, `READY`, `ACTIVE`, `STOPPING`, `STOPPED`, `FAILED` | Lifecycle state of a managed service instance |

---

## Definition Models (Authoring / Compile-time)

These models represent the structure of YAML tests and TCKs as parsed by the Compiler.

```mermaid
classDiagram
    class VariableDefinition {
        +str name
        +str type
        +Any default?
        +bool runtime = False
        +str description?
    }

    class Assertion {
        +AssertionType type
        +AssertionSeverity severity = HARD
        +ValueSource source = INLINE
        +Any value?
        +str path?
        +str description?
    }

    class StepDefinition {
        +str type
        +str name
        +dict params
        +float timeout_s?
        +list~Assertion~ validate?
    }

    class ScriptDefinition {
        +str name
        +str version
        +str dataspace_version
        +str description?
        +dict~str, VariableDefinition~ variables
        +list~ServiceDefinition~ services?
        +list~StepDefinition~ steps
        +list~StepDefinition~ cleanup?
    }

    class ServiceDefinition {
        +str name
        +ServiceType type
        +str base_url
        +dict auth
        +dict params?
    }

    class TckTestEntry {
        +str id
        +str name?
        +bool skippable = False
    }

    class TckDefinition {
        +str name
        +str version
        +str description?
        +dict~str, VariableDefinition~ shared_variables?
        +list~TckTestEntry~ tests
        +list~ImportDefinition~ imports?
    }

    class ImportDefinition {
        +str import_ref
        +dict override?
    }

    class PackageManifest {
        +str name
        +str version
        +str sdk_version
        +datetime compiled_at
        +list~str~ dataspace_versions
        +list~str~ scripts
        +str checksum
        +SecurityBlock security?
    }

    class PlayerIdentity {
        +str player_id
        +RSAPublicKey public_key
        +str fingerprint
        +Path private_key_path?
        +from_key_file(path)$ PlayerIdentity
        +generate(output_dir)$ PlayerIdentity
    }

    class EncryptedKeyBlock {
        +str player_id
        +bytes encrypted_key
    }

    class SecurityBlock {
        +str format = "encrypted-v1"
        +str algorithm = "AES-256-GCM"
        +str key_derivation = "RSA-OAEP-SHA256"
        +str compiler_id
        +list~EncryptedKeyBlock~ authorized_players
    }

    SecurityBlock --> "*" EncryptedKeyBlock : authorized_players
    PackageManifest --> "0..1" SecurityBlock : security

    ScriptDefinition --> "*" VariableDefinition : variables
    ScriptDefinition --> "*" StepDefinition : steps
    ScriptDefinition --> "*" StepDefinition : cleanup
    ScriptDefinition --> "*" ServiceDefinition : services
    StepDefinition --> "*" Assertion : validate
    TckDefinition --> "*" TckTestEntry : tests
    TckDefinition --> "*" VariableDefinition : shared_variables
    TckDefinition --> "*" ImportDefinition : imports
```

---

## Server Models

These models represent the state of packages uploaded to the server and server-related configuration.

```mermaid
classDiagram
    class UploadedPackage {
        +str package_id
        +str name
        +str version
        +PackageFormat format
        +int size_bytes
        +datetime uploaded_at
        +str checksum
        +Path file_path
    }

    class VaultConfig {
        +str vault_url
        +str vault_token
        +str vault_secret_path
    }

    class TestlabConfig {
        +Path keys_dir = "~/.testlab/keys/"
        +Path trust_store_dir = "~/.testlab/trusted_compilers/"
        +Path storage_dir = "~/.testlab/packages/"
        +int server_port = 8100
        +int max_upload_bytes = 52428800
        +VaultConfig vault?
        +Path library_path?
    }

    TestlabConfig --> "0..1" VaultConfig : vault
```

---

## Job Models (Execution-time)

Every test execution is modeled as a **Job** — a stateful, persistent entity that tracks the full lifecycle of a run. Jobs can pause (enter `WAITING` state) when a step needs to listen for an external callback, maintain in-memory state ("memory") across steps, and automatically resume when the expected response arrives.

```mermaid
classDiagram
    class Job {
        +str job_id
        +JobStatus status
        +str package_name?
        +str tck_id?
        +dict runtime_vars
        +JobMemory memory
        +datetime created_at
        +datetime started_at?
        +datetime finished_at?
        +float total_duration_s?
        +str current_script?
        +str current_step?
        +str waiting_for?
        +TckResult result?
        +str error?
    }

    class JobMemory {
        +dict~str, Any~ state
        +list~JobEvent~ events
        +set(key, value)
        +get(key, default?) Any
        +has(key) bool
        +log_event(event)
    }

    class JobEvent {
        +datetime timestamp
        +str event_type
        +str description
        +dict data?
    }

    Job --> "1" JobMemory : memory
    Job --> "0..1" TckResult : result
    JobMemory --> "*" JobEvent : events
```

### Job Fields

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Unique identifier (e.g., `a1b2c3d4-e5f6-7890-abcd-1234567890ab`) |
| `status` | `JobStatus` | Current lifecycle state (`QUEUED`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`) |
| `package_name` | `str?` | Name of the `.tckpkg` being executed |
| `tck_id` | `str?` | Test case identifier |
| `runtime_vars` | `dict` | Runtime variables provided at job creation |
| `memory` | `JobMemory` | Persistent state bag — survives across steps and wait/resume cycles |
| `created_at` | `datetime` | When the job was created (enqueued) |
| `started_at` | `datetime?` | When execution began |
| `finished_at` | `datetime?` | When execution completed (success, failure, or timeout) |
| `current_script` | `str?` | Name of the script currently executing (null when waiting or finished) |
| `current_step` | `str?` | Name of the step currently executing or waiting on |
| `waiting_for` | `str?` | Description of what the job is waiting for (e.g., `"callback: /callbacks/notif-ack"`, `"poll: transfer state=COMPLETED"`) |
| `result` | `TckResult?` | Final result — populated when job completes |
| `error` | `str?` | Error message if the job failed or timed out |

### JobMemory

The `JobMemory` provides a persistent key-value store and event log that survives across the entire job lifecycle, including wait/resume cycles:

| Method | Signature | Description |
|--------|-----------|-------------|
| `set` | `set(key: str, value: Any)` | Store a value by key — persists across steps and wait/resume |
| `get` | `get(key: str, default: Any = None) -> Any` | Retrieve a stored value (returns default if missing) |
| `has` | `has(key: str) -> bool` | Check if a key exists |
| `log_event` | `log_event(event: JobEvent)` | Append a timestamped event to the history |

Steps can write to job memory via `context.job.memory.set(key, value)`. Unlike step context variables (which are scoped to a single script), job memory persists across all scripts in a TCK and survives wait/resume cycles.

---

## Result Models (Execution-time)

These models represent the runtime state and outcomes produced by the Player.

```mermaid
classDiagram
    class AssertionResult {
        +Assertion assertion
        +bool passed
        +Any expected
        +Any actual
        +str message
        +AssertionSeverity severity
    }

    class HttpRequest {
        +str method
        +str url
        +dict headers?
        +Any body?
    }

    class HttpResponse {
        +int status_code
        +dict headers?
        +Any body?
        +float duration_ms
    }

    class StepResult {
        +str step_name
        +str step_type
        +StepStatus status
        +datetime started_at?
        +datetime finished_at?
        +float duration_s?
        +HttpRequest request?
        +HttpResponse response?
        +str error?
        +str error_traceback?
        +Any output?
        +list~AssertionResult~ assertions
    }

    class CallbackResult {
        +str listener_name
        +str path
        +str method
        +dict headers
        +Any payload
        +datetime received_at
        +bool timed_out
    }

    class ScriptResult {
        +str script_id
        +str script_name
        +str dataspace_version
        +ScriptStatus status
        +list~StepResult~ steps
        +datetime started_at?
        +datetime finished_at?
        +float total_duration_s?
        +dict metadata?
        +AssertionSummary assertion_summary
    }

    class AssertionSummary {
        +int total
        +int passed
        +int failed_hard
        +int failed_soft
    }

    class TckResult {
        +str tck_id
        +str package_name
        +ScriptStatus status
        +list~ScriptResult~ scripts
        +datetime started_at?
        +datetime finished_at?
    }

    ScriptResult --> "*" StepResult : steps
    ScriptResult --> "1" AssertionSummary : assertion_summary
    ScriptResult --> "*" CallbackResult : callback_results
    StepResult --> "0..1" HttpRequest : request
    StepResult --> "0..1" HttpResponse : response
    StepResult --> "*" AssertionResult : assertions
    TckResult --> "*" ScriptResult : scripts
    AssertionResult --> "1" Assertion : assertion
```

---

## Security Models Detail

### PlayerIdentity

Represents a Player's cryptographic identity. Generated via `testlab keygen` and stored in `~/.testlab/keys/`.

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | `str` | Formatted identifier: `player:sha256:<hex_digest>` |
| `public_key` | `RSAPublicKey` | RSA public key (2048-bit minimum) |
| `fingerprint` | `str` | SHA-256 of DER-encoded public key (hex) |
| `private_key_path` | `Path?` | Path to private key PEM file (only on local Player) |

### EncryptedKeyBlock

One entry per authorized Player in a package's `security.authorized_players` list.

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | `str` | Fingerprint-based Player identifier |
| `encrypted_key` | `bytes` | AES-256 content key encrypted with this Player's RSA public key via RSA-OAEP-SHA256 |

### SecurityBlock

Top-level security metadata in `manifest.yaml` for encrypted packages.

| Field | Type | Description |
|-------|------|-------------|
| `format` | `str` | Always `"encrypted-v1"` for the current encryption scheme |
| `algorithm` | `str` | Content encryption algorithm: `"AES-256-GCM"` |
| `key_derivation` | `str` | Key wrapping algorithm: `"RSA-OAEP-SHA256"` |
| `compiler_id` | `str` | Fingerprint-based Compiler identifier (`compiler:sha256:<hex>`) |
| `authorized_players` | `list[EncryptedKeyBlock]` | One key block per authorized Player |

### Service Binding Error Types

| Exception | Raised When | Contains |
|-----------|------------|----------|
| `ServiceNotFoundError` | `context.get_service(name)` called with unknown service name | `name` |
| `ServiceNotReadyError` | Service exists but is in FAILED or STOPPED state | `name`, `state` |
| `ServiceTypeMismatchError` | Managed service type doesn't match step's `expected_service_type` | `step_type`, `expected`, `actual` |
| `StepConfigError` | Step has neither `params.service` nor direct connection params | `step_type`, `message` |
| `DuplicateServiceError` | Two services in `services` block share the same name | `name` |
| `ServiceInitError` | Service fails to initialize (connection, auth failure) | `name`, `cause` |
| `SkipNotAllowedError` | `skip_tests` runtime variable references an unknown ID or one not marked `skippable: true` | `test_ids`, `reason` |

---

## State Transitions

### Step Status

```mermaid
stateDiagram-v2
    [*] --> PENDING : Step queued
    PENDING --> RUNNING : Player starts step
    RUNNING --> PASSED : Execution + assertions OK
    RUNNING --> FAILED : Exception or hard assertion fail
    PENDING --> SKIPPED : earlier step failed
    FAILED --> [*]
    PASSED --> [*]
    SKIPPED --> [*]
```

### Script Status

```mermaid
stateDiagram-v2
    [*] --> IDLE : Script loaded
    IDLE --> RUNNING : Player starts execution
    RUNNING --> COMPLETED : All steps finished (pass or soft fail)
    RUNNING --> FAILED : Step failed with abort policy
    RUNNING --> CANCELLED : External cancellation
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

---

## Service Lifecycle

### Managed Service Status

```mermaid
stateDiagram-v2
    [*] --> DECLARED : Service in services block
    DECLARED --> INITIALIZING : Player starts init
    INITIALIZING --> READY : Auth + connection OK
    INITIALIZING --> FAILED : Init error
    READY --> ACTIVE : Steps using service
    ACTIVE --> READY : Step completes
    READY --> STOPPING : Script ends or stop_service
    ACTIVE --> STOPPING : Script ends or stop_service
    STOPPING --> STOPPED : Connections closed
    FAILED --> [*]
    STOPPED --> [*]
```

### Callback Lifecycle

```mermaid
stateDiagram-v2
    [*] --> MOUNTING : listen block parsed
    MOUNTING --> WAITING : Route mounted on server
    WAITING --> RECEIVED : Callback payload arrives
    WAITING --> TIMED_OUT : timeout_s exceeded
    RECEIVED --> UNMOUNTED : Route removed
    TIMED_OUT --> UNMOUNTED : Route removed
    UNMOUNTED --> [*]
```

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)