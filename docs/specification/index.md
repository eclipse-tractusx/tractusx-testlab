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

# Introduction

This section is the requirements specification for TestLab: what the engine must do,
the models it works with, and the constraints it must satisfy.

**Version:** 2.0
**Date:** 2026-03-30
**Status:** Draft

!!! info "Looking for the YAML syntax?"
    The specification describes behaviour, not the authoring format. The `v1-alpha`
    manifest, test, step and validation syntax is defined in [TCK Syntax](../tck-syntax/index.md),
    and every step with its inputs and outputs is listed in the
    [Step Reference](../api-reference/steps/index.md). To install TestLab, see
    [Installation](../home/installation.md).

---

## Executive Summary

**TestLab** is the testing framework built on the [Tractus-X SDK](https://github.com/eclipse-tractusx/tractusx-sdk). It ships as a Python library, the `testlab` CLI and a FastAPI server. It enables you to author, compile, distribute, and execute automated TCKs against dataspace connectors and industry services — without writing any Python code.

Test authors write **declarative YAML tests** describing the steps to execute, the services to connect to, the assertions to evaluate, and the cleanup to perform. TestLab takes care of the rest: validation, encryption, packaging, execution, and structured reporting.

- **Tests** — YAML-defined test sequences composed of reusable, predefined steps
- **Compiler** — Validates tests at compile time and packages them into portable, encrypted-by-default `.tck` artifacts
- **Player** — An async executor run from the CLI, started by the server, or embedded in an existing application, with cryptographic identity for package authorization
- **Services** — Managed SDK service lifecycle for connector, provider, and DTR instances, seeded at runtime from the bound infrastructure and reused across steps
- **Server** — FastAPI app hosting the HTTP API (compile, package storage, runs, job control, SSE event stream), the callback endpoints, and the mock endpoints tests open for the SUT; run standalone with `testlab serve` or started by the player during `testlab run`

Tests declare the infrastructure they require, whose SDK services the Player initializes once and reuses (avoiding repeated initialization), configure callback endpoints to receive async responses, and leverage runtime variable resolution. These tests are compiled with strict validation, packaged into distributable artifacts, and executed by the Player — which resolves runtime variables, manages step sequencing, evaluates assertions, orchestrates managed services, and provides live execution status.

## Goals

| ID | Goal |
|----|------|
| G-1 | Enable test authors to define reusable, composable TCKs in YAML without writing Python code |
| G-2 | Provide a compile step that catches errors early — undeclared variables, incompatible step types, version mismatches — before execution |
| G-3 | Package compiled TCKs into portable `.tck` artifacts that can be shared, uploaded, stored, and versioned |
| G-4 | Execute TCK packages at runtime via a singleton async Player, with support for loading from filesystem or programmatic input (dict/string) |
| G-5 | Provide real-time, step-level execution monitoring with in-memory state queryable at any point during execution |
| G-6 | Enforce dataspace version awareness — every test declares which dataspace version it targets, and steps are resolved accordingly |
| G-7 | Support configurable expected results (assertions) per step, with values sourced from inline YAML/JSON, files, or runtime variables |
| G-8 | Produce structured, machine-parseable logs (JSON-lines) alongside human-readable console output |
| G-9 | Ship a predefined step library covering Connector capabilities (provision, negotiate, transfer, consume, cleanup) and Industry capabilities (submodel consumption, aspect model validation, schema comparison) |
| G-10 | Support arbitrary dataplane API calls (GET/POST/PUT/DELETE) authenticated via EDR tokens from prior steps |
| G-11 | Ship every step as a typed executor with a declared input and output contract, so YAML never invokes arbitrary SDK functions and every parameter is validated at compile time |
| G-12 | Provide managed service lifecycle — the SDK services a test's required infrastructure needs (connector consumer, connector provider, DTR) are initialized once and reused across steps |
| G-13 | Support async callback/webhook patterns — tests can start a lightweight listener on an ephemeral endpoint, send a request, and await a response via `asyncio.Event` with configurable timeout |
| G-14 | Support dual deployment modes for the Player — standalone CLI (`testlab run`, `testlab serve`) and embeddable library API (`TestlabPlayer`) |
| G-15 | Secure `.tck` artifacts via hybrid encryption (AES-256-GCM + RSA-OAEP) and Ed25519 signing, ensuring compiled packages can only be decrypted and executed by authorized Player instances |
| G-16 | Provide transparent service-step binding — no step names its service; the Player seeds the SDK services at runtime from the bound infrastructure and injects the correct, pre-initialized instance into each step |

## Non-Goals (Future Scope)

| ID | Non-Goal |
|----|----------|
| NG-1 | Full-featured REST API for test management (scheduling, user management) — the embedded server provides execution endpoints, package management (upload/list/delete), and callback routes |
| NG-2 | Persistent execution state in PostgreSQL (future — `SyncBackend` protocol) |
| NG-3 | Parallel step execution within a single test |
| NG-4 | Step retry policies (retry count, backoff strategy) |
| NG-5 | Cross-package test composition (`"!include"` across `.tck` boundaries) |

---

## Document Structure

| Document | Description |
|----------|-------------|
| [Concepts & Terminology](specification/concepts.md) | Conceptual model, lifecycle flow, and glossary |
| [Functional Requirements](specification/functional-requirements.md) | All FR-* requirements across 9 functional areas |
| [Data Models](specification/data-models.md) | Enumerations, definition models, and result models |
| [Constraints & Verification](specification/constraints.md) | Technical constraints, quality attributes, and verification matrix |
| [Package Security](specification/security.md) | Threat model, encrypt-by-default architecture, key management, HashiCorp Vault integration, and decompilation |
| [Walkthrough](walkthrough/index.md) | The full lifecycle — writing, compiling and executing tests — end to end |

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