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

# Walkthrough

This walkthrough guides you through the complete Testlab lifecycle — from writing your first YAML test scripts, through compiling them into a portable `.tck` package, to executing tests and interpreting results.

## What You'll Build

By the end of this walkthrough, you will have:

1. **Written** two YAML test scripts that validate connector data exchange end-to-end
2. **Organized** them into a TCK with shared variables and supporting assets
3. **Compiled** the TCK into a distributable `.tck` package
4. **Executed** the tests against live connectors and reviewed the results

## Workflow Overview

```mermaid
flowchart LR
    subgraph "1. Write"
        A["YAML tests<br/>+ assets<br/>+ TCK definition"]
    end

    subgraph "2. Compile"
        B["Validate & package<br/><code>testlab compile</code>"]
    end

    subgraph "3. Execute"
        C["Run tests<br/><code>testlab run</code>"]
    end

    subgraph "4. Results"
        D["JSON-lines logs<br/>+ summary report"]
    end

    A --> B --> C --> D

    style A fill:#e1f5fe,stroke:#0288d1
    style B fill:#fff3e0,stroke:#f57c00
    style C fill:#f3e5f5,stroke:#7b1fa2
    style D fill:#e8f5e9,stroke:#388e3c
```

## Prerequisites

- Python 3.12+
- `tractusx-sdk` installed (`pip install tractusx-sdk`)
- Access to a provider and consumer connector (URLs + API keys or OAuth2 credentials)

## Sections

| Section | Description |
|---------|-------------|
| [Writing Test Scripts](writing-test-scripts.md) | Create YAML tests, declare variables, define steps and assertions, organize into a TCK with assets |
| [Compiling Packages](compiling-packages.md) | Validate and package scripts into `.tck`, inspect the compiled output, compile with encryption |
| [Executing Tests](executing-tests.md) | Run tests via CLI, provide runtime variables, read results, use the Player API programmatically |

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)