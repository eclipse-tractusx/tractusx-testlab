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

# Constraints & Verification

## Technical Constraints

| ID | Constraint |
|----|-----------|
| TC-01 | Python 3.12+ required |
| TC-02 | Async execution via native `asyncio` (no external task broker) |
| TC-03 | Pydantic 2.6+ for model validation |
| TC-04 | PyYAML 6.0+ for YAML parsing |
| TC-05 | No `eval()` or dynamic code execution from YAML scripts — variable resolution limited to `${var_name}` lookups |
| TC-06 | Connector steps SHALL reuse existing `tractusx_sdk.dataspace` services via `ServiceFactory` — no duplication of connector logic |
| TC-07 | `sdk_call` step operates in allowlist mode by default — only curated SDK functions may be invoked unless `allow_sdk_calls: open` is declared |
| TC-08 | FastAPI required for callback server and Player deployment modes (already an SDK dependency) |
| TC-09 | Callback routes are ephemeral — mounted on demand and unmounted after use. No persistent route state between script executions |
| TC-10 | Managed services SHALL use `ServiceFactory` for connector services and direct instantiation for DTR/AAS services — no custom service constructors |
| TC-11 | Python `cryptography` library required for all cryptographic operations (AES-256-GCM, RSA-OAEP, Ed25519). No custom cryptographic implementations permitted |
| TC-12 | Player keys SHALL be stored in `~/.testlab/keys/` with `0600` file permissions (private key). Trust store keys in `~/.testlab/trusted_compilers/`. Key directories SHALL be created automatically on first use |

## Quality Attributes

| Attribute | Requirement |
|-----------|-------------|
| **Portability** | `.tckpkg` artifacts must be self-contained and executable on any machine with a compatible SDK version installed |
| **Extensibility** | Custom step types must be registrable without modifying SDK source code |
| **Observability** | Execution state must be queryable in real-time at step granularity; structured logs must be machine-parseable |
| **Safety** | Scripts parsed from untrusted sources (API, filesystem) must not allow arbitrary code execution. `sdk_call` in allowlist mode prevents access to internal SDK functions |
| **Reliability** | Cleanup steps must execute regardless of prior failures; resource leaks are unacceptable. Managed services must be torn down even on script failure |
| **Confidentiality** | Encrypted `.tckpkg` packages must be readable only by authorized Player instances. AES content keys must never be stored in plaintext. Private keys must be protected with appropriate file permissions |

---

## Verification Matrix

| ID | Verification | Type |
|----|-------------|------|
| V-01 | YAML parsing accepts valid scripts and rejects scripts missing `dataspace_version` | Unit |
| V-02 | Compiler fails on undeclared `${var}` references (not marked `runtime: true`) | Unit |
| V-03 | Compiler fails when step type doesn't exist in registry for the script's dataspace version | Unit |
| V-04 | Compile → package → unpack round-trip produces identical `CompiledTck` | Integration |
| V-05 | `.tckpkg` checksum is verified on load; tampered packages are rejected | Unit |
| V-06 | SDK version mismatch emits warning but does not block execution | Unit |
| V-07 | Player executes a compiled TCK and produces correct `TckResult` with step timings | Integration |
| V-08 | Step failure fails the test: execution stops and teardown runs | Integration |
| V-09 | Teardown steps keep executing after a teardown step fails | Integration |
| V-10 | Remaining steps after a failed step are reported as skipped | Integration |
| V-11 | Hard assertion failure causes step failure; soft assertion failure produces warning | Unit |
| V-12 | Assertion values from inline, file, and variable sources are resolved correctly | Unit |
| V-13 | JSON strings embedded in YAML are auto-parsed before assertion comparison | Unit |
| V-14 | `${var}` references are resolved correctly across steps (output of step N used by step N+1) | Integration |
| V-15 | Runtime variables override defaults at execution time | Unit |
| V-16 | Two TCKs running concurrently have isolated contexts and no variable leakage | Integration |
| V-17 | Script cancellation stops after current step and runs cleanup | Integration |
| V-18 | Monitor returns correct current step, status, and assertion results during execution | Integration |
| V-19 | JSON-lines log file contains correct entries with script_id, dataspace_version, step names | Integration |
| V-20 | Log file is renamed with `_PASS`/`_FAIL` suffix on completion | Integration |
| V-21 | `dataplane_call` step supports GET/POST/PUT/DELETE with custom headers, query params, and body | Integration |
| V-22 | `dataplane_call` step auto-injects EDR authorization header | Unit |
| V-23 | Custom step registered at runtime via `registry.register()` is available to scripts | Unit |
| V-24 | `sdk_call` in allowlist mode rejects functions not in the allowlist | Unit |
| V-25 | `sdk_call` in open mode (`allow_sdk_calls: open`) allows any `tractusx_sdk` function | Unit |
| V-26 | `sdk_call` correctly invokes an SDK function and stores the return value in context | Integration |
| V-27 | Managed services declared in `services` block are initialized before first step and torn down after completion | Integration |
| V-28 | `context.get_service("name")` returns the same cached instance across multiple steps | Unit |
| V-29 | `init_service` step replaces an existing service and `stop_service` tears it down | Integration |
| V-30 | Callback endpoint receives a POST, signals `asyncio.Event`, and `await_callback` step receives the payload | Integration |
| V-31 | `await_callback` step times out correctly when no callback is received within `timeout_s` | Integration |
| V-32 | Encrypted `.tckpkg` round-trip: compile with `--encrypt` → authorized Player decrypts and executes successfully | Integration |
| V-33 | Unauthorized Player (key not in `authorized_players`) is rejected with `PackageAuthorizationError` | Unit |
| V-34 | Tampered encrypted package (modified `payload.enc`) fails AES-256-GCM decryption | Unit |
| V-35 | Package signed by untrusted compiler (key not in trust store) is rejected with `PackageSignatureError` | Unit |
| V-36 | Package with invalid Ed25519 signature (modified after signing) is rejected | Unit |
| V-37 | `testlab keygen` generates valid RSA key pair and stores in `~/.testlab/keys/` with correct permissions | Unit |
| V-38 | Service-step type validation: `provision_asset` with `CONNECTOR_CONSUMER` service raises `ServiceTypeMismatchError` | Unit |
| V-39 | Service resolution priority: `params.service` takes precedence over direct `params.base_url`; absence of both raises `StepConfigError` | Unit |

---

## Traceability Matrix

The following diagram maps verification items to functional requirement areas:

```mermaid
graph LR
    subgraph "Script Authoring"
        V01[V-01]
    end

    subgraph "Compilation"
        V02[V-02]
        V03[V-03]
    end

    subgraph "Packaging"
        V04[V-04]
        V05[V-05]
        V06[V-06]
    end

    subgraph "Player / Execution"
        V07[V-07]
        V08[V-08]
        V09[V-09]
        V10[V-10]
        V14[V-14]
        V15[V-15]
        V16[V-16]
        V17[V-17]
    end

    subgraph "Assertions"
        V11[V-11]
        V12[V-12]
        V13[V-13]
    end

    subgraph "Monitoring"
        V18[V-18]
    end

    subgraph "Logging"
        V19[V-19]
        V20[V-20]
    end

    subgraph "Steps"
        V21[V-21]
        V22[V-22]
        V23[V-23]
    end

    subgraph "SDK Calls"
        V24[V-24]
        V25[V-25]
        V26[V-26]
    end

    subgraph "Managed Services"
        V27[V-27]
        V28[V-28]
        V29[V-29]
    end

    subgraph "Callbacks"
        V30[V-30]
        V31[V-31]
    end

    subgraph "Package Security"
        V32[V-32]
        V33[V-33]
        V34[V-34]
        V35[V-35]
        V36[V-36]
        V37[V-37]
    end

    subgraph "Service Binding"
        V38[V-38]
        V39[V-39]
    end

    V01 -.-> |FR-AUTH| V02
    V04 -.-> |FR-PKG| V05
    V07 -.-> |FR-PLAY| V08
    V11 -.-> |FR-ASSERT| V12
    V24 -.-> |FR-SDK| V25
    V27 -.-> |FR-SVC| V28
    V30 -.-> |FR-CB| V31
    V32 -.-> |FR-SEC| V33
    V38 -.-> |FR-SVC| V39

    style V01 fill:#e1f5fe,stroke:#0288d1
    style V02 fill:#fff3e0,stroke:#f57c00
    style V03 fill:#fff3e0,stroke:#f57c00
    style V04 fill:#e8f5e9,stroke:#388e3c
    style V05 fill:#e8f5e9,stroke:#388e3c
    style V06 fill:#e8f5e9,stroke:#388e3c
    style V07 fill:#f3e5f5,stroke:#7b1fa2
    style V08 fill:#f3e5f5,stroke:#7b1fa2
    style V09 fill:#f3e5f5,stroke:#7b1fa2
    style V10 fill:#f3e5f5,stroke:#7b1fa2
    style V14 fill:#f3e5f5,stroke:#7b1fa2
    style V15 fill:#f3e5f5,stroke:#7b1fa2
    style V16 fill:#f3e5f5,stroke:#7b1fa2
    style V17 fill:#f3e5f5,stroke:#7b1fa2
    style V11 fill:#fce4ec,stroke:#c62828
    style V12 fill:#fce4ec,stroke:#c62828
    style V13 fill:#fce4ec,stroke:#c62828
    style V18 fill:#fff9c4,stroke:#f9a825
    style V19 fill:#e8eaf6,stroke:#3f51b5
    style V20 fill:#e8eaf6,stroke:#3f51b5
    style V21 fill:#ffccbc,stroke:#e64a19
    style V22 fill:#ffccbc,stroke:#e64a19
    style V23 fill:#ffccbc,stroke:#e64a19
    style V24 fill:#dcedc8,stroke:#689f38
    style V25 fill:#dcedc8,stroke:#689f38
    style V26 fill:#dcedc8,stroke:#689f38
    style V27 fill:#e8eaf6,stroke:#3f51b5
    style V28 fill:#e8eaf6,stroke:#3f51b5
    style V29 fill:#e8eaf6,stroke:#3f51b5
    style V30 fill:#f3e5f5,stroke:#7b1fa2
    style V31 fill:#f3e5f5,stroke:#7b1fa2
    style V32 fill:#ffccbc,stroke:#bf360c
    style V33 fill:#ffccbc,stroke:#bf360c
    style V34 fill:#ffccbc,stroke:#bf360c
    style V35 fill:#ffccbc,stroke:#bf360c
    style V36 fill:#ffccbc,stroke:#bf360c
    style V37 fill:#ffccbc,stroke:#bf360c
    style V38 fill:#e8eaf6,stroke:#3f51b5
    style V39 fill:#e8eaf6,stroke:#3f51b5
```

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)