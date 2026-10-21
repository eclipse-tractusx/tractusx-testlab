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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5). -->
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
    - player_id: "d4e5f6a1…"            # SHA-256 of the Player's encryption.pub
      alg: "hybrid:RSA-OAEP-SHA256+ML-KEM-768"
      rsa_ciphertext: "kL9mQxR2…"       # RSA-OAEP-encrypted random secret
      kem_key_id: "4f1c09d2…"           # SHA-256 of the Player's encryption_pq.pub
      kem_ciphertext: "qR3tY7uI…"       # ML-KEM-768 ciphertext
      wrapped_key: "3vR8aQ2m…"          # nonce ‖ AES-256-GCM-wrapped content key
    - player_id: "f6a1b2c3…"            # a Player without an ML-KEM-768 key
      encrypted_key: "pW7nK4vR…"        # RSA-OAEP-wrapped content key
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
| `security.key_derivation` | `string` | Every key wrap the entries use, comma-separated: `"hybrid:RSA-OAEP-SHA256+ML-KEM-768"`, `"RSA-OAEP-SHA256"`, or both |
| `security.signature_algorithm` | `string` | Hybrid signing: `"hybrid:Ed25519+ML-DSA-65"` |
| `security.compiler_id` | `string` | Compiler's public key BLAKE2b-512 fingerprint |
| `security.authorized_players[].player_id` | `string` | Player's public key BLAKE2b-512 fingerprint |
| `security.authorized_players[].alg` | `string?` | `"hybrid:RSA-OAEP-SHA256+ML-KEM-768"`; absent for the RSA-OAEP wrap ([Hybrid Key Wrap](#hybrid-key-wrap)) |
| `security.authorized_players[].rsa_ciphertext` | `string` | Hybrid: random secret, RSA-OAEP-SHA256-encrypted for the Player (base64) |
| `security.authorized_players[].kem_key_id` | `string` | Hybrid: SHA-256 of the Player's ML-KEM-768 public key PEM |
| `security.authorized_players[].kem_ciphertext` | `string` | Hybrid: ML-KEM-768 ciphertext for the Player (base64) |
| `security.authorized_players[].wrapped_key` | `string` | Hybrid: nonce ‖ content key under the HKDF-derived key, AES-256-GCM (base64) |
| `security.authorized_players[].encrypted_key` | `string` | RSA-OAEP only: content key RSA-OAEP-SHA256-encrypted for the Player (base64) |

### 5. Encryption and Signing

#### Compiler Workflow (Encrypted Mode)

1. Parse and validate all YAML tests (phases 1–7)
2. Generate a random 256-bit AES key
3. Create a tar archive of `tests/` and `assets/`
4. Encrypt the tar archive with AES-256-GCM → `payload.enc`
5. For each `--player-pub` public key, wrap the AES key with the [hybrid key wrap](#hybrid-key-wrap) when the
   Player's ML-KEM-768 key lies beside it, else with RSA-OAEP-SHA256 alone
6. Build `manifest.yaml` with metadata + `security` block (no secret material)
7. Compute BLAKE2b-512 checksum over the original (unencrypted) tests and assets
8. Sign (`manifest.yaml` bytes ‖ `payload.enc` bytes) with both Ed25519 AND ML-DSA-65 signing keys → `signature.sig` (contains both signatures). *Implemented: Ed25519 only; ML-DSA-65 is still proposed — see [Hybrid Key Wrap](#hybrid-key-wrap).*
9. Package `manifest.yaml`, `payload.enc`, `signature.sig` into ZIP archive

#### Hybrid Key Wrap

*Amendment, 2026-10-21.* The workflow above first described the hybrid as two independent copies of the content
key — RSA-OAEP-encrypted, and "encapsulated" with ML-KEM-768 — checked against each other. That cannot be built
as written, and would not be hybrid if it were: ML-KEM encapsulates a random secret of its own, not a chosen key,
and a copy of the content key under RSA alone opens the package for whoever breaks RSA. A quantum computer breaks
RSA from the public key, so a package recorded today would open once one exists ("harvest now, decrypt later").
The format that shipped until then wrapped with RSA-OAEP only. This section fixes the hybrid as implemented: one
key-encryption key derived from **both** secrets, so recovering the content key takes breaking RSA *and* ML-KEM —
the hybrid BSI TR-02102-1 asks for while post-quantum schemes mature.

A Player identity has an optional ML-KEM-768 pair, `encryption_pq.pem` (PKCS#8, the seed-only form of RFC 9935)
and `encryption_pq.pub` (SPKI PEM). `testlab keygen` writes it with every new identity and adds it to an existing
one without touching the other keys. `cryptography` 48.0.0 is the first release whose wheels provide ML-KEM.

##### The wrap

For a Player with an ML-KEM-768 key, the Compiler:

1. RSA-OAEP-SHA256-encrypts a fresh random 32-byte `rsa_secret` → `rsa_ciphertext`;
2. encapsulates against the Player's ML-KEM-768 key → `kem_secret`, `kem_ciphertext`;
3. derives `KEK = HKDF-SHA256(ikm = rsa_secret ‖ kem_secret, salt = none, info)` with

    ```text
    info = "tractusx-testlab/tck-key-wrap/v2" 0x00 ‖ SHA-256(rsa_ciphertext)
           ‖ SHA-256(kem_ciphertext) ‖ kem_key_id
    ```

4. encrypts the content key under `KEK` with AES-256-GCM, a fresh 12-byte nonce and the
   associated data `hybrid:RSA-OAEP-SHA256+ML-KEM-768` → `wrapped_key = nonce ‖ ciphertext`.

The entry in `security.authorized_players` is

```yaml
- player_id: <SHA-256 of encryption.pub>
  alg: hybrid:RSA-OAEP-SHA256+ML-KEM-768
  rsa_ciphertext: <base64>
  kem_key_id: <SHA-256 of encryption_pq.pub>
  kem_ciphertext: <base64>
  wrapped_key: <base64>
```

Concatenating both shared secrets as the HKDF input is the combiner NIST SP 800-56C
and SP 800-227 describe. Recovering the content key takes both secrets, so it takes
breaking RSA **and** ML-KEM. Binding both ciphertexts and the ML-KEM key into `info`
keeps a secret from being replayed under another ciphertext or key. `kem_key_id` lets
a Player say which ML-KEM key a package was sealed for when it holds another one.

The manifest is signed as before (`manifest.yaml ‖ payload.enc`), so the new fields
are covered by the Compiler's Ed25519 signature. `security.key_derivation` lists every
wrap the entries use, for example `RSA-OAEP-SHA256, hybrid:RSA-OAEP-SHA256+ML-KEM-768`.

##### Format 1 stays

An entry without `alg` is the RSA-OAEP wrap (`player_id`, `encrypted_key`), byte for
byte what packages carried before. The Compiler writes it for a Player with no ML-KEM
key, and the Player reads it as before. One package may mix both kinds of entry.

##### How keys reach the Compiler and the Player

- **Compiler:** `--player-pub <dir>/<name>.pub` pairs with `<dir>/<name>_pq.pub`. The
  hybrid key travels in the same directory as the RSA key, so there is no second flag
  to forget. Pairing by the file's own name keeps a collection of several Players'
  keys from handing one Player another's ML-KEM key.
- **Player (CLI):** `--player-keys <dir>` reads `encryption_pq.pem` when it is there.
- **Player (engine):** `engine_package_keys` reads it from `keys_dir`.
- **API:** `Loader.load` and `open_encrypted_package` take `player_kem_private_key`.

##### A Player may require the hybrid wrap

`require_hybrid` on `Loader.load` / `open_encrypted_package`, and
`require_pq_encryption` (`TESTLAB_REQUIRE_PQ_ENCRYPTION`) for an engine, refuse a
package whose entry for this Player is RSA-OAEP only. It is off by default, so packages
compiled before this amendment keep loading.

##### Consequences

- Packages compiled for a Player with an ML-KEM-768 key cannot be opened by breaking
  RSA alone. Their entries grow by about 1.7 KB per Player, most of it the base64 of
  the 1088-byte ML-KEM-768 ciphertext.
- An older testlab cannot open a hybrid entry: it looks for `encrypted_key` and finds
  none. A Compiler that must serve such Players leaves their `_pq.pub` out.
- `cryptography` is required at 48.0.0 or later.
- `encrypt_for_recipients` returns the manifest entries instead of
  `(player_id, encrypted_key)` pairs.
- A package compiled before this amendment stays RSA-only until it is recompiled. A
  catalogue that keeps packages (an engine) re-seals them to give them the hybrid wrap.

##### Dual signatures (Ed25519 + ML-DSA-65)

Still proposed, not implemented. A forged signature needs a quantum computer at the time of forging, not a
recording made today, so the "harvest now" argument that makes the key wrap urgent does not apply; a package can be
re-signed once ML-DSA-65 is added. Adding it changes the signature entry, the trust store (a Compiler's ML-DSA key
next to its Ed25519 key) and every verification path, and is left to its own change.

##### Alternatives considered

- **ML-KEM-768 alone.** Simpler, but it would bet the confidentiality of every package
  on a scheme deployed for a short time. BSI and ANSSI recommend hybrid.
- **HPKE (RFC 9180) with a hybrid KEM (X25519 + ML-KEM-768).** A standard construction
  that `cryptography` is starting to expose. Its hybrid KEM is not yet a stable,
  released API, and it would need a new X25519 key in every identity while the RSA key
  stays for format 1. Worth revisiting once the hybrid HPKE KEMs are final.
- **ML-KEM-1024.** NIST category 5, against category 3 for ML-KEM-768. The RSA-4096
  half and the package's AES-256 already set the bar; ML-KEM-768 is what TLS
  (X25519MLKEM768) and BSI's recommendation use by default.
- **A second CLI flag for the ML-KEM key.** Explicit, but a Compiler that forgets it
  silently produces RSA-only packages. The `<name>_pq.pub` convention cannot be
  forgotten.

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
3. Hybrid entry: RSA-OAEP decrypt `rsa_ciphertext` (RSA private key), ML-KEM-768 decapsulate `kem_ciphertext`
   (`encryption_pq.pem`), derive the key-encryption key with HKDF-SHA256 from both, AES-256-GCM unwrap `wrapped_key`
4. RSA-OAEP entry: RSA-OAEP decrypt `encrypted_key`; refused when the Player requires the hybrid wrap
5. A tampered ciphertext, or another Player's key, fails the AES-GCM unwrap (`PackageDecryptionError`)
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
