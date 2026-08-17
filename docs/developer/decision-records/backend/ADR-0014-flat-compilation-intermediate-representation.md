<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This work is made available under the terms of the
 Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
 which is available at
 https://creativecommons.org/licenses/by/4.0/legalcode.

 SPDX-License-Identifier: CC-BY-4.0
-->

<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0014: Flat Compilation Intermediate Representation (IR)

## Status

Accepted

## Date

2026-05-21 (updated 2026-05-28)

## Based On

- [ADR-0010 — YAML Syntax v2](../shared/ADR-0010-yaml-syntax-v2.md)
- [ADR-0011 — Environment and Services](../shared/ADR-0011-environment-and-services.md)
- [ADR-0012 — Compilation and Packaging](ADR-0012-compilation-and-packaging.md)
- ADR-0013 — Preconditions Specification (superseded, not published)

## Context

The TestLab compilation pipeline (ADR-0012) transforms YAML v2 source files into a portable package. However, the internal representation between the compiler output and the Player input has not been formally specified. Without a well-defined Intermediate Representation (IR), the compiler and Player are tightly coupled — changes to one break the other, and tooling (debuggers, trace viewers, decompilers) cannot interoperate.

### Forces

- The **compiler** must perform ALL intelligence: variable resolution, type checking, reference validation, phase flattening, and assertion wiring. It emits a fully-resolved, self-describing output.
- The **Player** must be dumb: iterate instructions sequentially, resolve `$ref` values from a flat dictionary, dispatch step executors, store outputs, and run inline assertions. Zero parsing, zero graph traversal, zero ambiguity resolution at runtime.
- The IR must be **decompilable** back to source YAML without data loss (supporting round-trip editing).
- The IR must support **O(1) variable lookup** at runtime — no tree walking or scope chain resolution.
- The IR must be **self-describing** — every instruction carries enough metadata to be understood in isolation (phase, position, type, expected inputs/outputs).
- The IR must support **structured tracing** — every instruction has a stable `index` that correlates compiled IR to execution trace logs.
- The format must be **JSON-serializable** for embedding in `.tckpkg` archives, streaming over SSE, and storage in databases.

### Design Constraints

| Constraint | Rationale |
|------------|-----------|
| Flat instruction array | No recursion, no nesting, no conditional branches at IR level |
| All references pre-resolved | `${{ }}` syntax does not exist in the IR — only `$ref` objects |
| Phase metadata preserved | Each instruction knows its origin phase for decompilation |
| Inline assertions | Validation blocks are properties of their parent instruction, not separate instructions |
| Deterministic ordering | Same source YAML always produces the same IR (byte-identical with same compiler version) |
| Forward-reference prohibition | `produced_by` index must always be less than the consumer's index |

## Decision

### 1. Design Philosophy

The Flat Compilation IR follows three core principles:

**1.1 Compiler Does All Thinking**

The compiler is the intelligent component. It resolves all variable references, validates type compatibility, checks temporal ordering (no forward references), inlines testdata, resolves service configurations, and flattens the three-phase structure (setup → steps → teardown) into a single ordered instruction array. The compiled output is a **fully-resolved execution plan** — the Player performs zero interpretation.

**1.2 Flat Structures Only**

The IR uses two primary data structures:

- **Symbol table**: A flat dictionary mapping canonical keys to symbol metadata. O(1) lookup by key.
- **Instructions**: A flat ordered array. The Player iterates index 0 to N-1, no branching, no recursion.

There are no nested scopes, no scope chains, no tree structures that require traversal at runtime.

**1.3 Self-Describing Instructions**

Every instruction carries all metadata needed to:
- Execute it (type, parameters, timeout)
- Trace it (index, id, phase)
- Decompile it (phase, phase_index)
- Validate its results (inline assertions)

An instruction can be extracted from the array and understood in isolation — no external context is required beyond the symbol table values.

---

### 2. Two-File Compilation Output

The compiler produces **two files** — not a standalone JSON per test:

| File | Purpose | Contains |
|------|---------|----------|
| `manifest.yaml` | Package metadata, integrity, test registry | TCK identity, compilation fingerprint, test list |
| `tck-execution.json` | Execution payload | env, tests, preconditions, all compiled tests |

#### 2.1 `manifest.yaml` Schema

```yaml
kind: manifest

package:
  format: tckpkg
  format_version: "1.0.0"
  testlab: v1-alpha

tck:
  id: "<tck-id>"
  namespace: "<namespace>"
  metadata:
    name: "<string>"
    version: "<string>"
    description: "<string>"
    authors: [...]
    copyright_holders: [...]
    license: Apache-2.0
    standards: [...]
    tags: [...]
    dataspace_version: "<string>"

compilation:
  compiled_at: "<ISO 8601 UTC>"
  compiler_version: "<semver>"
  fingerprint:
    nonce: "blake2b:<hex>"        # unique per compilation (blake2b of random bytes)
    public_key: "ed25519:<base64>" # persistent compiler installation key
    checksum: "blake2b:<hex>"      # blake2b hash of tck-execution.json

tests:                             # NOT present in encrypted mode
  - id: "<test-id>"
    file: "<source path>"
    source_hash: "blake2b:<hex>"
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `kind` | Always `manifest` — identifies the file type |
| `package.format` | Always `tckpkg` |
| `compilation.fingerprint.nonce` | blake2b hash of random bytes — unique per compilation |
| `compilation.fingerprint.public_key` | Ed25519 public key of the compiler installation |
| `compilation.fingerprint.checksum` | blake2b hash of the entire `tck-execution.json` content |
| `tests` | Registry of compiled tests with source hashes (omitted in encrypted mode) |

#### 2.2 `tck-execution.json` Schema

```json
{
  "env": {
    "variables": [...],
    "services": [...],
    "schemas": {...},
    "testdata": {...}
  },
  "tests": [
    { "id": "<test-id>", "file": "<source path>", "source_hash": "blake2b:<hex>" }
  ],
  "preconditions": [
    { "id": "...", "uses": "...", "name": "...", "with": {...}, "returns": {...}, "seed": {...} }
  ],
  "compiled_tests": [
    {
      "id": "<test-id>",
      "metadata": { "name": "...", "version": "...", "description": "..." },
      "symbol_table": { "<canonical_key>": {...} },
      "instructions": [ {...}, {...} ]
    }
  ]
}
```

**Root-level sections:**

| Section | Description |
|---------|-------------|
| `env` | Shared environment: variables, services, schemas (asset refs), testdata (asset refs) |
| `tests` | Test registry with source file paths and integrity hashes |
| `preconditions` | Pre-execution requirements (at root level, NOT inside `env`). May include `seed` mapping (see ADR-0013 §10) |
| `compiled_tests` | Array of compiled test units — the core IR |

#### 2.3 `compiled_tests[]` Entry (CompiledTest)

Each entry in `compiled_tests` represents one compiled test:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Test identifier (lowercase kebab-case) |
| `metadata` | object | Yes | Human-readable metadata (name, version, description) |
| `symbol_table` | object | Yes | Flat dictionary of all symbols for this test (see §5) |
| `instructions` | array | Yes | Ordered array of instruction objects (see §4) |

!!! note "No duplication of package-level fields"
    `compiled_tests` entries do NOT contain `format_version`, `compiled_at`, `compiler_version`, `namespace`, or `testlab`. Those belong exclusively in the manifest.

---

### 3. Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| All tests in one `tck-execution.json` | Single file load, atomic execution, simpler Player |
| `id` field name (not `test_id`) | Consistent naming across all objects |
| Preconditions at root level | They apply to ALL tests, not to a specific env |
| blake2b hashing (not SHA-256) | Faster, equally secure, native in Python |
| Fingerprint block (nonce + public_key + checksum) | Tamper detection without full PKI |
| Manifest uses grouped sections | Clear separation: package / tck / compilation |
| `kind: manifest` discriminator | Enables tooling to identify file type without parsing |

---

### 4. Instruction Schema

Each instruction in the `instructions` array follows this schema:

```json
{
  "index": 0,
  "id": "<step_id>",
  "uses": "<step_type>",
  "name": "<human label>",
  "with": { "<param>": "<value or $ref>" },
  "returns": { "<output_name>": { "type": "<type>", "class": "<class>" } },
  "validate": [ { "uses": "validate/...", "with": {...} } ],
  "phase": "setup|steps|teardown",
  "phase_index": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `index` | integer | Yes | Global position (0-based). Monotonically increasing. |
| `id` | string | Yes | Step identifier (unique within the test). |
| `uses` | string | Yes | Step executor type (e.g., `connector/create_asset`). |
| `name` | string | Yes | Human-readable label for tracing/debugging. |
| `with` | object | Yes | Input parameters. Values are literals or `$ref` objects. |
| `returns` | object | Yes | Declared outputs with type metadata. |
| `validate` | array | No | Inline assertions executed after the step. |
| `phase` | string | Yes | Origin phase: `setup`, `steps`, or `teardown`. |
| `phase_index` | integer | Yes | Position within the phase (for decompilation). |

---

### 5. Symbol Table

The symbol table is a flat dictionary providing O(1) lookup for all resolvable values:

```json
{
  "env.provider_url": { "source": "env.variables", "type": "string", "default": "" },
  "env.testlab_dsp_url": { "source": "env.variables", "type": "string", "default": "", "seeded_by": "testlab_connector.dsp_url" },
  "setup.gen_id.generated_id": { "source": "step_output", "produced_by": 0, "type": "string" },
  "env.services.testlab_connector": { "source": "env.services", "produced_by": -1, "type": "class", "class": "ConnectorService" }
}
```

| Field | Description |
|-------|-------------|
| `source` | Origin: `env.variables`, `env.services`, `env.schemas`, `env.testdata`, `env.preconditions`, `step_output` |
| `produced_by` | Instruction index that produces this value. `-1` for environment values. Omitted for `env.variables` entries. |
| `type` | Runtime type: `string`, `integer`, `object`, `class` |
| `class` | (Optional) Semantic class: `ConnectorService`, `MockInstance`, `Uuid`, etc. |
| `default` | (Optional) Default value for `env.variables` entries. Empty string if not explicitly set. |
| `seeded_by` | (Optional) `<precondition_id>.<return_field>` — indicates this variable is seeded by a precondition output (see ADR-0013 §10). |

**Invariant:** For any symbol with `produced_by >= 0`, any instruction referencing it via `$ref` must have a higher `index`. No forward references.

---

### 6. `$ref` Resolution

All variable references in the IR use `{ "$ref": "<symbol_key>" }`. The Player resolves by looking up the key in the symbol table, then fetching the runtime value. O(1) — no parsing, no interpolation.

---

## Consequences

### Positive

1. **Decoupled compiler/Player**: The IR is a stable contract between the two components.
2. **Tooling ecosystem**: Debuggers, trace viewers, and decompilers can operate on the IR independently.
3. **Single-file execution**: `tck-execution.json` contains everything the Player needs — one read, one parse.
4. **Predictable execution**: Flat instruction array with no branching means deterministic behavior.
5. **Fast symbol resolution**: O(1) lookup at runtime — no scope chain walking.

### Negative

1. **Larger file size**: All tests in one JSON file can be large for big TCKs.
2. **No selective execution from IR alone**: The Player must load all compiled tests even to run one (filtering is done after load).

---

## Supersedes

This ADR supersedes the original single-file-per-test design. All compilation now produces the two-file output described in §2.
