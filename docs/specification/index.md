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

<p align="center">
  <img src="../assets/images/test-lab-app-logo-white-claim.png#only-light" alt="Tractus-X TestLab" width="380"/>
  <img src="../assets/images/test-lab-app-logo-black-claim.png#only-dark" alt="Tractus-X TestLab" width="380"/>
</p>

# Testlab Extension Module — Requirements Specification

**Module:** `tractusx_sdk.extensions.testlab`
**Version:** 2.0
**Date:** 2026-03-30
**Status:** Draft

---

## Executive Summary

**TestLab** is the testing framework built into the [Tractus-X SDK](https://github.com/eclipse-tractusx/tractusx-sdk). It enables you to author, compile, distribute, and execute automated TCKs against dataspace connectors and industry services — without writing any Python code.

Test authors write **declarative YAML tests** describing the steps to execute, the services to connect to, the assertions to evaluate, and the cleanup to perform. TestLab takes care of the rest: validation, encryption, packaging, execution, and structured reporting.

- **Tests** — YAML-defined test sequences composed of reusable, predefined steps
- **Compiler** — Validates tests at compile time and packages them into portable, encrypted-by-default `.tck` artifacts
- **Player** — An async executor deployable as standalone CLI or embeddable in an existing application, with cryptographic identity for package authorization
- **Services** — Managed SDK service lifecycle for connector, provider, and DTR instances with automatic initialization and reuse across steps
- **Server** — FastAPI-based callback/webhook engine with dynamically mounted routes for async request/response patterns

Tests can declare long-lived services that persist for the test duration (avoiding repeated initialization), configure callback endpoints to receive async responses, and leverage runtime variable resolution. These tests are compiled with strict validation, packaged into distributable artifacts, and executed by the Player — which resolves runtime variables, manages step sequencing, evaluates assertions, orchestrates managed services, and provides live execution status.

Tests with steps like (e.g., `connector/provider/create_asset`, `connector/consumer/negotiate`, `validate/schema`) can be included inside of TCKs, which enable reusability and personalized configurations for different scenarios.

Example:

```yaml
# A minimal test — provision an asset and verify it was created
kind: test
testlab: v1-alpha
id: my-first-test
metadata:
  name: "My First Test"
  version: "1.0"
  dataspace_version: saturn

steps:
  - id: create_asset
    uses: connector/provider/create_asset
    with:
      asset_id: "test-asset-001"
    returns:
      asset_id:
        type: string
        class: AssetId
    validate:
      - uses: validate/assert
        with: { input: asset_id, operator: equals, value: "test-asset-001" }
```



---

## Goals

| ID | Goal |
|----|------|
| G-1 | Enable test authors to define reusable, composable TCKs in YAML without writing Python code |
| G-2 | Provide a compile step that catches errors early — undeclared variables, incompatible step types, version mismatches — before execution |
| G-3 | Package compiled TCKs into portable `.tck` artifacts that can be shared, uploaded, stored, and versioned |
| G-4 | Execute test packages at runtime via a singleton async Player, with support for loading from filesystem or programmatic input (dict/string) |
| G-5 | Provide real-time, step-level execution monitoring with in-memory state queryable at any point during execution |
| G-6 | Enforce dataspace version awareness — every script declares which dataspace version it targets, and steps are resolved accordingly |
| G-7 | Support configurable expected results (assertions) per step, with values sourced from inline YAML/JSON, files, or runtime variables |
| G-8 | Produce structured, machine-parseable logs (JSON-lines) alongside human-readable console output |
| G-9 | Ship a predefined step library covering Connector capabilities (provision, negotiate, transfer, consume, cleanup) and Industry capabilities (submodel consumption, aspect model validation, schema comparison) |
| G-10 | Support arbitrary dataplane API calls (GET/POST/PUT/DELETE) authenticated via EDR tokens from prior steps |
| G-11 | Ship every step as a typed executor with a declared input and output contract, so YAML never invokes arbitrary SDK functions and every parameter is validated at compile time |
| G-12 | Provide managed service lifecycle — scripts declare required SDK services (connector consumer, connector provider, DTR) that are initialized once and reused across steps |
| G-13 | Support async callback/webhook patterns — scripts can start a lightweight listener on an ephemeral endpoint, send a request, and await a response via `asyncio.Event` with configurable timeout |
| G-14 | Support dual deployment modes for the Player — standalone CLI (`testlab serve`) and embeddable library API (`TestlabPlayer.from_app(app)`) |
| G-15 | Secure `.tck` artifacts via hybrid encryption (AES-256-GCM + RSA-OAEP) and Ed25519 signing, ensuring compiled packages can only be decrypted and executed by authorized Player instances |
| G-16 | Provide transparent service-step binding — steps reference managed services by name and the Player guarantees that the correct, pre-initialized SDK service instance is injected into each step |

## Non-Goals (Future Scope)

| ID | Non-Goal |
|----|----------|
| NG-1 | Full-featured REST API for test management (scheduling, user management) — the embedded server provides execution endpoints, package management (upload/list/delete), and callback routes |
| NG-2 | Persistent execution state in PostgreSQL (future — `SyncBackend` protocol) |
| NG-3 | Parallel step execution within a single script |
| NG-4 | Step retry policies (retry count, backoff strategy) |
| NG-5 | Cross-package script composition (`"!include"` across `.tck` boundaries) |

---

## Document Structure

This specification is organized into the following sections:

### Specification

| Document | Description |
|----------|-------------|
| [Concepts & Terminology](specification/concepts.md) | Conceptual model, lifecycle flow, and glossary |
| [Functional Requirements](specification/functional-requirements.md) | All FR-* requirements across 9 functional areas |
| [Data Models](specification/data-models.md) | Enumerations, definition models, and result models |
| [Constraints & Verification](specification/constraints.md) | Technical constraints, quality attributes, and verification matrix |
| [Package Security](specification/security.md) | Threat model, encrypt-by-default architecture, key management, HashiCorp Vault integration, and decompilation |

### Reference

| Document | Description |
|----------|-------------|
| [YAML Format Reference](reference/yaml-format.md) | Test and TCK authoring examples, assertion formats |
| [Package Format](reference/package-format.md) | `.tck` archive structure and manifest specification |
| [Module Structure](reference/module-structure.md) | Source code layout and component responsibilities |

### Walkthrough

| Document | Description |
|----------|-------------|
| [Overview](walkthrough/index.md) | End-to-end walkthrough introduction and prerequisites |
| [Writing Tests](walkthrough/writing-test-scripts.md) | Step-by-step guide to authoring YAML tests and TCKs |
| [Compiling Packages](walkthrough/compiling-packages.md) | Validating, compiling, and encrypting `.tck` packages |
| [Executing Tests](walkthrough/executing-tests.md) | Running packages via CLI, vars files, Python API, and server mode |

!!! info "Implementation Detail Level"
    This specification includes detailed pseudocode, resolution algorithms, and API signatures
    intended to serve as an implementation guide. These details prescribe the exact behavior
    required by each component.

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)