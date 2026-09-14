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

# ADR-0012: Compilation and Packaging

## Context

TCK projects authored with the YAML syntax v2 (ADR-0010) need a well-defined compilation pipeline that validates all references, types, and constraints at build time — before any test is executed against a live system. The output must be a portable, self-contained artifact that can be distributed, versioned, and run on any TestLab-compatible Player without access to the original source tree.

Because TCK packages may embed secrets (OAuth2 credentials, service URLs, BPNs), the default compilation mode must encrypt the payload so that only authorized Players can execute the tests.

This ADR defines the folder structure, compilation phases, package format (`.tckpkg`), encryption model, and integrity guarantees.

**Based on:**
- [ADR-0010 — YAML Syntax v2](../shared/ADR-0010-yaml-syntax-v2.md)
- [Package Format Specification](../../../specification/reference/package-format.md)

## Status

Proposed

## Decision

### 1. Source Folder Structure

A TCK project on disk follows this layout:

```
certificate-management-tck/
├── index.yaml                                  # TCK manifest (kind: tck)
├── schemas/
│   ├── business_partner_certificate.json       # CX-0135 BPC response schema
│   └── notification_header.json                # CX-0135 notification envelope schema
├── testdata/
│   ├── available_notification.json             # JSON payload (most common format)
│   └── sample_certificate.pdf                  # Binary attachment example
└── tests/
    ├── request-certificate.yaml                # Test files (kind: test)
    ├── validate-payload.yaml
    └── available-notification.yaml
```

The TCK manifest references tests, schemas, and testdata using **bare filenames** — the parent folder is implied by the section:

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

metadata:
  name: "Certificate Management TCK"
  version: "0.0.1"
  dataspace_version: saturn

env:
  schemas:
    certificate_schema:
      file: business_partner_certificate.json
    notification_header_schema:
      file: notification_header.json
  testdata:
    available_notification:
      file: available_notification.json
      type: application/json
    sample_certificate:
      file: sample_certificate.pdf
      type: application/pdf

tests:
  - request-certificate.yaml
  - validate-payload.yaml
  - available-notification.yaml
```

**Implicit folder resolution:**

| Section | Implied folder | Example entry | Resolved path |
|---------|---------------|---------------|---------------|
| `tests:` | `tests/` | `request-certificate.yaml` | `tests/request-certificate.yaml` |
| `env.schemas:` | `schemas/` | `file: business_partner_certificate.json` | `schemas/business_partner_certificate.json` |
| `env.testdata:` | `testdata/` | `file: available_notification.json` | `testdata/available_notification.json` |

**Rules:**

- The manifest file must be named `index.yaml` and live at the project root.
- No symlinks or references outside the project directory are allowed.
- Directory nesting is permitted (e.g. `tests/notifications/available.yaml`).
- The compiler validates that testdata `file` extensions match the declared `type` and rejects mismatches.

### 1.1 Testdata Compilation

Testdata entries declared in `env.testdata` are resolved and inlined at compile time. The full testdata syntax specification is defined in [ADR-0010](../shared/ADR-0010-yaml-syntax-v2.md).

**Entry specification:**

Each `env.testdata` entry has two fields:

| Field | Description |
|-------|-------------|
| `file` | Filename relative to the `testdata/` folder |
| `type` | MIME type declaring the content format |

**Supported types:**

| Extension | MIME type |
|-----------|----------|
| `.json` | `application/json` |
| `.xml` | `application/xml` |
| `.pdf` | `application/pdf` |
| `.txt` | `text/plain` |
| `.csv` | `text/csv` |

**Compile-time resolution:**

The compiler resolves `${{ env.testdata.<key> }}` expressions by inlining the referenced file content into the step's `with:` field. For example:

```yaml
env:
  testdata:
    available_notification:
      file: available_notification.json
      type: application/json

steps:
  - uses: send_notification
    with:
      body: ${{ env.testdata.available_notification }}
```

At compile time, `${{ env.testdata.available_notification }}` is replaced with the contents of `testdata/available_notification.json`.

**Compiler validations:**

1. File exists at the resolved path (`testdata/<file>`)
2. File extension matches the declared `type` (e.g. `.json` → `application/json`)
3. The consuming block's `with:` field accepts the declared MIME type

### 2. Compilation Process

Compilation transforms the source folder into a validated, self-contained package. The Compiler performs these phases in order:

| Phase | Action | Errors |
|-------|--------|--------|
| **1. Parse** | Load TCK manifest and all referenced test files | Syntax errors, missing files |
| **2. Resolve namespaces** | Verify every test's `namespace` matches the TCK's `namespace` | Namespace mismatch |
| **3. Resolve variables** | Validate all `${{ vars.* }}` and `${{ env.* }}` references | Unresolved variable, ambiguous variable |
| **4. Validate steps** | Check `uses:` against the step registry, verify `with:` inputs match step signatures | Unknown step type, missing required input |
| **5. Validate schemas** | Load referenced JSON Schema files, verify they are valid | Missing schema file, invalid JSON Schema |
| **6. Type check** | Verify operator/type compatibility on all `validate:` blocks | Type mismatch (e.g. `gt` on a string) |
| **7. Dataspace compat** | Verify all steps are compatible with declared `dataspace_version` | Step requires newer protocol version |
| **8. Package** | Bundle all files into a `.tckpkg` archive (encrypted or plain) | — |

#### Commands

```bash
# Compile with encryption (default) — requires signing key + authorized players
testlab compile my-tck/ \
  --authorize-player ~/keys/player1.pub \
  --authorize-player ~/keys/player2.pub \
  --signing-key ./compiler_signing.pem \
  --output my-tck.tckpkg

# Compile in plain mode (development only)
testlab compile my-tck/ --plain --output my-tck.tckpkg
```

#### Compile-only validation (no package output)

```bash
testlab validate my-tck/
```

This runs phases 1–7 without producing a `.tckpkg` file. Useful for CI checks and editor integration.

#### Error reporting

The compiler reports all errors found in a single pass (not fail-on-first). Each error includes:

- **File**: which YAML file contains the error
- **Line**: approximate line number
- **Phase**: which compilation phase caught it
- **Message**: human-readable description with context (what failed, what was expected)

Example output:

```
ERROR [resolve-variables] tests/request-certificate.yaml:15
  Unresolved variable: vars.nonexistent — no preceding step returns 'nonexistent'

ERROR [type-check] tests/validate-payload.yaml:42
  Operator 'gt' requires numeric input, got 'string' from step 'get_catalog.returns.response_body'

2 errors found. Compilation failed.
```

### 3. `.tckpkg` Package Format

A `.tckpkg` file is a **ZIP archive** (renamed extension). Packages can be compiled in two modes:

- **Encrypted** (default) — Tests and assets are encrypted with AES-256-GCM. Only authorized Players holding the correct RSA private key can decrypt and execute.
- **Plain** (`--plain`) — Tests and assets are stored as-is. Intended only for local development and debugging.

#### Plain Mode Structure

```
my-tck.tckpkg (ZIP)
├── manifest.yaml               # Package manifest (metadata + test listing)
├── tests/
│   ├── request-certificate.yaml
│   ├── validate-payload.yaml
│   └── available-notification.yaml
└── assets/
    ├── schemas/
    │   ├── business_partner_certificate.json
    │   └── notification_header.json
    └── testdata/
        ├── available_notification.json
        └── sample_certificate.pdf
```

#### Encrypted Mode Structure

```
my-tck.tckpkg (ZIP)
├── manifest.yaml               # Unencrypted — metadata + security block
├── payload.enc                  # AES-256-GCM encrypted tar of tests/ + assets/
└── signature.sig                # Ed25519 signature over manifest + payload
```

In encrypted mode, tests and assets are combined into a single encrypted blob (`payload.enc`). The manifest remains unencrypted for metadata inspection. The signature provides authenticity verification.

### 4. Manifest

The `manifest.yaml` at the archive root contains package metadata. It is **always unencrypted** — even in encrypted packages — so tools can inspect metadata without decryption keys.

- **Plain mode**: the manifest contains the full TCK index structure (tests, env, everything). It is valid as both a compiled package descriptor AND a readable copy of the original TCK definition.
- **Encrypted mode**: the manifest contains only safe metadata (`kind`, `testlab`, `id`, `namespace`, `metadata`, `compilation`, `security`). All content references — test file lists, schema definitions, and testdata entries — are part of the encrypted payload and are **not** exposed in the manifest.

> **Plain mode only:** The compiled manifest preserves the full TCK index structure verbatim. The compiler appends a `compilation:` block — no fields from the source are renamed, moved, or reformatted. In encrypted mode, only high-level metadata and the `security` block appear in the manifest; content details remain sealed inside the encrypted payload.

#### Plain Package Manifest

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

metadata:
  name: "Certificate Management TCK"
  version: "v0.0.1"
  dataspace_version: saturn

env:
  schemas:
    certificate_schema:
      file: business_partner_certificate.json
    notification_header_schema:
      file: notification_header.json
  testdata:
    available_notification:
      file: available_notification.json
      type: application/json
    sample_certificate:
      file: sample_certificate.pdf
      type: application/pdf

tests:
  - request-certificate.yaml
  - validate-payload.yaml
  - available-notification.yaml

compilation:
  compiled_at: "2026-05-21T14:30:00Z"
  checksum: "blake2b:3a7bd2f1e8c9504d6b1f3e8a7c2d9f0e4b5a6c8d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3"
```

#### Encrypted Package Manifest

In encrypted mode, the manifest exposes **only safe metadata**. Test file references, schemas, and testdata entries are sealed inside the encrypted payload (`payload.enc`) and never appear in the unencrypted manifest.

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

metadata:
  name: "Certificate Management TCK"
  version: "0.0.1"
  dataspace_version: saturn

# NOTE: env and tests are NOT present in the unencrypted manifest.
# They are sealed inside the encrypted payload, which preserves:
# - The ordered tests list (execution order is guaranteed)
# - All env declarations (schemas, testdata, services, variables)

compilation:
  compiled_at: "2026-05-21T14:30:00Z"
  checksum: "blake2b:3a7bd2f1e8c9504d6b1f3e8a7c2d9f0e4b5a6c8d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3"

security:
  format: "encrypted-v1"
  algorithm: "AES-256-GCM"
  key_derivation: "hybrid:RSA-OAEP-SHA256+ML-KEM-768"
  signature_algorithm: "hybrid:Ed25519+ML-DSA-65"
  compiler_id: "compiler:blake2b:a1b2c3d4e5f67890abcdef1234567890a1b2c3d4e5f67890abcdef1234567890a1b2c3d4e5f67890abcdef1234567890a1b2c3d4e5f67890abcdef1234567890"
  authorized_players:
    - player_id: "player:blake2b:d4e5f6a1b2c3789012345678abcdef90d4e5f6a1b2c3789012345678abcdef90d4e5f6a1b2c3789012345678abcdef90d4e5f6a1b2c3789012345678abcdef90"
      encrypted_key:
        rsa: "base64:kL9mQxR2vN8pT5wZ3aY7jE1uH4cF6bD0sI2gW9oK3nM8xV5lQ7rJ4tA1yU6iP0hB3eN9mC2wX5zR8fG4dL7kO1="
        ml_kem: "base64:qR3tY7uI9oP1aS2dF4gH6jK8lZ0xC5vB7nM3wE9rT1yU4iO6pA8sD2fG5hJ7kL0zX3cV9bN1mQ4wE6rT8yU2i="
    - player_id: "player:blake2b:f6a1b2c3d4e5678901234567abcdef01f6a1b2c3d4e5678901234567abcdef01f6a1b2c3d4e5678901234567abcdef01f6a1b2c3d4e5678901234567abcdef01"
      encrypted_key:
        rsa: "base64:pW7nK4vR1xZ8mT3qY6jE9uH2cF5bD0sI7gL4oA3kN8xV1lQ5rJ2tM9yU6iP0hB3eC8wX1zR4fG7dS5kO2nL6="
        ml_kem: "base64:mN5bV2cX8zL0kJ3hG7fD1sA9pO4iU6yT8rE2wQ5nM7bV1cX3zL9kJ0hG4fD6sA2pO8iU5yT7rE3wQ1nM9bV4c="
```

#### Manifest Fields

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `string` | Always `tck` — same as source |
| `testlab` | `string` | TestLab syntax version (copied from source) |
| `id` | `string` | TCK id (copied from source) |
| `namespace` | `string` | TCK namespace (copied from source) |
| `metadata` | `object` | Full metadata block (copied from source) |
| `env` | `object` | Full env block with schemas and testdata (copied from source). **Plain mode only** — encrypted in payload for encrypted mode. |
| `tests` | `list[string]` | Test files in execution order (copied from source). **Plain mode only** — encrypted in payload for encrypted mode. |
| `compilation.compiled_at` | `string` (ISO 8601) | Timestamp of compilation |
| `compilation.checksum` | `string` | `blake2b:<hex>` BLAKE2b-512 integrity hash over tests and assets |
| `security` | `object?` | Present only in encrypted packages |
| `security.format` | `string` | Encryption format: `"encrypted-v1"` |
| `security.algorithm` | `string` | Content encryption: `"AES-256-GCM"` |
| `security.key_derivation` | `string` | Hybrid key wrapping: `"hybrid:RSA-OAEP-SHA256+ML-KEM-768"` |
| `security.signature_algorithm` | `string` | Hybrid signing: `"hybrid:Ed25519+ML-DSA-65"` |
| `security.compiler_id` | `string` | Compiler's public key BLAKE2b-512 fingerprint |
| `security.authorized_players[].player_id` | `string` | Player's public key BLAKE2b-512 fingerprint |
| `security.authorized_players[].encrypted_key` | `object` | AES key wrapped with both RSA-OAEP and ML-KEM-768 |
| `security.authorized_players[].encrypted_key.rsa` | `string` | AES key encrypted with Player's RSA public key (base64) |
| `security.authorized_players[].encrypted_key.ml_kem` | `string` | AES key encapsulated with Player's ML-KEM-768 public key (base64) |

### 5. Encryption and Signing

#### Compiler Workflow (Encrypted Mode)

1. Parse and validate all YAML tests (phases 1–7)
2. Generate a random 256-bit AES key
3. Create a tar archive of `tests/` and `assets/`
4. Encrypt the tar archive with AES-256-GCM → `payload.enc`
5. For each `--authorize-player` public key:
   - Load Player's RSA public key from PEM file
   - Encrypt the AES key with RSA-OAEP (SHA-256 padding) → `encrypted_key.rsa`
   - Load Player's ML-KEM-768 encapsulation key from PEM file
   - Encapsulate the AES key with ML-KEM-768 → `encrypted_key.ml_kem`
   - Record as `{player_id: blake2b_fingerprint, encrypted_key: {rsa: ..., ml_kem: ...}}`
6. Build `manifest.yaml` with metadata + `security` block (no secret material)
7. Compute BLAKE2b-512 checksum over the original (unencrypted) tests and assets
8. Sign (`manifest.yaml` bytes ‖ `payload.enc` bytes) with both Ed25519 AND ML-DSA-65 signing keys → `signature.sig` (contains both signatures)
9. Package `manifest.yaml`, `payload.enc`, `signature.sig` into ZIP archive

#### Key Types

| Key Type | Algorithm | Size | Purpose |
|----------|-----------|------|---------|
| Player private key | RSA | 2048-bit (min) | Decrypt AES content keys |
| Player public key | RSA | 2048-bit (min) | Shared with Compiler to wrap AES key |
| Player PQ encapsulation key | ML-KEM-768 | — | Post-quantum key encapsulation (FIPS 203) |
| Player PQ decapsulation key | ML-KEM-768 | — | Decrypt PQ-wrapped AES key |
| Compiler signing key | Ed25519 | 256-bit | Sign packages for authenticity |
| Compiler verification key | Ed25519 | 256-bit | Stored in Player's trust store |
| Compiler PQ signing key | ML-DSA-65 | — | Post-quantum package signing (FIPS 204) |
| Compiler PQ verification key | ML-DSA-65 | — | Stored in Player's trust store |

> **Why hybrid?** The hybrid approach (classical + post-quantum in parallel) follows NIST SP 800-227 recommendations for the cryptographic transition period. If either algorithm is broken, the other still protects the package. ML-KEM-768 and ML-DSA-65 are NIST FIPS 203/204 standards (finalized August 2024). BLAKE2b-512 provides 256-bit post-quantum security for integrity checks.

#### Key Management CLI

| Command | Description |
|---------|-------------|
| `testlab keygen` | Generate Player RSA key pair → `~/.testlab/keys/` |
| `testlab keygen --compiler` | Generate Compiler Ed25519 key pair |
| `testlab keygen --pq` | Generate ML-KEM-768 + ML-DSA-65 post-quantum key pairs |
| `testlab export-key --player` | Export Player public key (PEM) |
| `testlab export-key --fingerprint` | Print Player fingerprint |

> **Note:** Hybrid mode requires both classical (RSA + Ed25519) and post-quantum (ML-KEM-768 + ML-DSA-65) keys. Use `testlab keygen && testlab keygen --pq` to generate a complete key set.

#### Directory Layout

```
~/.testlab/
├── keys/
│   ├── player.pem              # Player RSA private key (permissions: 600)
│   ├── player.pub              # Player RSA public key
│   ├── player_pq.pem           # Player ML-KEM-768 decapsulation key (permissions: 600)
│   └── player_pq.pub           # Player ML-KEM-768 encapsulation key
└── trusted_compilers/
    ├── team_compiler.pub       # Trusted Compiler Ed25519 public key
    ├── team_compiler_pq.pub    # Trusted Compiler ML-DSA-65 public key
    └── ci_compiler.pub         # Another trusted Compiler key
```

### 6. Running a Compiled Package

The Player accepts only compiled `.tckpkg` files — enforcing the "one way to do things" principle (compile first, then run):

```bash
# Run a compiled package
testlab run my-tck.tckpkg

# Decompile an encrypted package (requires authorized Player key)
testlab decompile my-tck.tckpkg --output my-tck/
```

### 7. Integrity and Verification

#### Plain Package Verification

1. Extract `compilation.checksum` from `manifest.yaml`
2. Recompute BLAKE2b-512 over `tests/` and `assets/` contents
3. Compare — reject if mismatch
4. Warn if `testlab` version is not supported by running Player

#### Encrypted Package Verification

1. Read `security.authorized_players` — find own `player_id`
2. If not found → `PackageAuthorizationError: 'Player not authorized'`
3. RSA-OAEP decrypt the AES content key using Player's RSA private key (`encrypted_key.rsa`)
4. ML-KEM-768 decapsulate the AES content key using Player's PQ decapsulation key (`encrypted_key.ml_kem`)
5. Verify both decrypted keys match — reject if mismatch (`PackageDecryptionError`)
6. AES-256-GCM decrypt `payload.enc`
7. Load trusted compiler keys from `~/.testlab/trusted_compilers/`
8. Verify both Ed25519 AND ML-DSA-65 signatures in `signature.sig` — reject if either is invalid
9. Verify BLAKE2b-512 checksum over decrypted content — reject if mismatch

#### Error Types

| Error | Cause |
|-------|-------|
| `PackageAuthorizationError` | Player's fingerprint not in `authorized_players` |
| `PackageDecryptionError` | AES key decryption failed (wrong private key or key mismatch between RSA and ML-KEM) |
| `PackageSignatureError` | Ed25519 or ML-DSA-65 signature verification failed |
| `ChecksumError` | BLAKE2b-512 content integrity check failed |

### 8. Reproducibility

Given the same source directory and compiler version, `testlab compile` must produce a byte-identical `.tckpkg` (deterministic ZIP ordering, no timestamps in archive entries). This enables:

- CI caching based on `source_checksum`
- Verification that a package was built from a specific commit
- Auditable build pipelines for certification

### 9. Distribution and Versioning

Naming convention: `{namespace}-{id}.tckpkg`

```
ccm-v0.0.1-certificate-management-tck.tckpkg
```

Packages can be:
- Stored in artifact registries (e.g., GitHub Releases, OCI registries)
- Shared as files for offline execution
- Embedded in CI pipelines for automated certification runs

### 10. Plain vs. Encrypted Comparison

| Aspect | Plain Mode | Encrypted Mode |
|--------|-----------|----------------|
| Archive contents | `manifest.yaml` + `tests/` + `assets/` | `manifest.yaml` + `payload.enc` + `signature.sig` |
| Tests readable by | Anyone with the file | Only authorized Players |
| Integrity check | BLAKE2b-512 checksum | BLAKE2b-512 + hybrid Ed25519/ML-DSA-65 signature |
| Compiler requirement | None (no key needed) | Ed25519 + ML-DSA-65 signing keys |
| Player requirement | None | RSA + ML-KEM-768 key pairs + compiler in trust store |
| CLI flag | `--plain` | Default (or `--encrypt` explicit) |
| Use case | Local development, debugging | Distribution, CI, certification |

---

## Consequences

### Positive

- **Portable artifacts**: `.tckpkg` files are self-contained — no source tree or network access needed at runtime.
- **Compile-time safety**: All validation happens before execution — no runtime surprises from typos or missing references.
- **Secret protection**: Encrypted packages prevent unauthorized access to embedded credentials and service URLs.
- **Authenticity**: Hybrid Ed25519 + ML-DSA-65 signatures guarantee packages were built by a trusted Compiler.
- **Post-quantum readiness**: Hybrid cryptography (RSA + ML-KEM-768, Ed25519 + ML-DSA-65) protects against future quantum attacks per NIST SP 800-227.
- **Reproducible builds**: Deterministic packaging enables auditable CI/CD pipelines.
- **Fast execution**: Pre-compiled packages skip validation — direct to execution.
- **Simple format**: ZIP with a known structure — any tool can inspect metadata without decryption.

### Negative

- **Key management overhead**: Players and Compilers must generate and exchange both classical and post-quantum keys (mitigated by `testlab keygen` and `testlab keygen --pq` CLI).
- **Two-step workflow**: Authors must compile before running (`testlab compile my-tck/ && testlab run my-tck.tckpkg`). Over HTTP, `POST /testlab/tck-execution/run` starts a run from a TCK sent in the request.
- **Compiler version coupling**: Packages may not load on significantly newer/older runners (mitigated by compatibility warnings).
- **No partial execution**: Cannot run a single test from an encrypted package without decrypting all (acceptable — packages are small).
