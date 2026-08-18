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

# Compiling Packages

This section shows how to validate your test scripts and compile them into a portable `.tck` package.

## Prerequisites

You've completed [Writing Test Scripts](writing-test-scripts.md) and have:

```
my-connector-tests/
├── tests/
│   ├── provision_and_consume.yaml
│   └── submodel_validation.yaml
├── assets/
│   └── schemas/
│       └── serial-part-3.0.json
└── tck.yaml
```

---

## Step 1 — Validate Without Packaging

Before packaging, you can validate that your YAML scripts are correct — all `${var}` references resolve, step types exist in the registry, and the dataspace version is supported:

```bash
testlab validate tck.yaml
```

**Expected output (success):**

```
Test case "connector_e2e" validated successfully

  Tests: 2
    provision_and_consume (saturn) — 6 steps, 1 cleanup
    submodel_validation (saturn)  — 3 steps

  Variables: 8 declared (7 runtime, 1 with default)
  Services: 3 declared (CONNECTOR_PROVIDER, CONNECTOR_CONSUMER ×2)
  Assertions: 9 total (7 hard, 2 soft)
  Assets: 1 file (schemas/serial-part-3.0.json)

  No errors. No warnings.
```

**Example output (with errors):**

```
Test case "connector_e2e" validation failed

  Errors (2):
    x provision_and_consume.yaml:42 — Undefined variable "${provider_bpnn}" (did you mean "${provider_bpn}"?)
    x submodel_validation.yaml:18 — Unknown step type "consume_submodell" for dataspace version "saturn"

  Warnings (1):
    provision_and_consume.yaml:87 — Asset file "schemas/serial-part-3.1.json" not found in assets/
```

---

## Step 2 — Generate Keys (One-time Setup)

Packages are **encrypted by default** to protect secrets embedded in test scripts. Before compiling, you need cryptographic keys for both the Compiler and the Player(s) that will run the tests.

### Player Key (on the machine that will execute tests)

```bash
testlab keygen
```

```
Generated Player key pair
   Private key: ~/.testlab/keys/player.pem (permissions: 0600)
   Public key:  ~/.testlab/keys/player.pub
   Fingerprint: player:sha256:d4e5f6a1b2c3...

   Share player.pub with the Compiler to authorize this Player.
```

### Compiler Key (on the machine that will compile packages)

```bash
testlab keygen --compiler
```

```
Generated Compiler signing key pair
   Signing key:      ./compiler_signing.pem (permissions: 0600)
   Verification key: ./compiler_signing.pub
   Fingerprint:      compiler:sha256:a1b2c3d4e5f6...

   Share compiler_signing.pub with Players so they can verify your packages.
```

### Trust Store Setup (Player-side)

Copy the Compiler's verification key to the Player's trust store so it accepts packages from this Compiler:

```bash
cp compiler_signing.pub ~/.testlab/trusted_compilers/
```

---

## Step 3 — Compile (Encrypted by Default)

Compile and package the TCK. Encryption is automatic — you provide the Player public keys and the Compiler signing key:

```bash
testlab compile tck.yaml \
  --authorize-player ~/.testlab/keys/player1.pub \
  --authorize-player ~/.testlab/keys/player2.pub \
  --signing-key ./compiler_signing.pem \
  --output connector_e2e-1.0.tck
```

**Expected output:**

```
Validating TCK "connector_e2e"...
Validation passed (2 tests, 9 steps, 9 assertions)

Encrypting package...
   Content encryption: AES-256-GCM (256-bit random key)
   Wrapping key for player:sha256:d4e5f6a1... (RSA-OAEP-SHA256)
   Wrapping key for player:sha256:f6a1b2c3... (RSA-OAEP-SHA256)
   Signing with compiler:sha256:a1b2c3d4... (Ed25519)

Packaging...
   Writing manifest.yaml (unencrypted metadata + security block)
   Writing payload.enc (encrypted scripts + assets)
   Writing signature.sig (Ed25519 signature)

Encrypted package created: connector_e2e-1.0.tck (14.1 KB)
   Authorized players: 2
```

**If you forget the keys:**

```bash
testlab compile tck.yaml --output connector_e2e-1.0.tck
```

```
Error: Encryption is enabled by default. You must provide:
  --authorize-player <player.pub>   (at least one authorized Player)
  --signing-key <compiler.pem>      (Compiler signing key)

To compile without encryption (development only), use --plain.
```

---

## Step 4 — Inspect the Compiled Package

The compiled `.tck` is **not human-readable**. Tests and assets are encrypted inside `payload.enc`:

```bash
unzip -l connector_e2e-1.0.tck
```

```
Archive:  connector_e2e-1.0.tck
  Length      Date    Time    Name
---------  ---------- -----   ----
      892  2026-03-30 14:25   manifest.yaml
     5520  2026-03-30 14:25   payload.enc
       64  2026-03-30 14:25   signature.sig
---------                     -------
     6476                     3 files
```

Only the `manifest.yaml` is readable — it contains metadata and the security block, but **no secrets**:

```bash
unzip -p connector_e2e-1.0.tck manifest.yaml
```

```yaml
# ── Auto-generated by testlab compiler ── DO NOT EDIT ──
name: "connector_e2e"
version: "1.0"
sdk_version: "0.5.0"
compiled_at: "2026-03-30T14:25:00Z"
dataspace_versions:
  - "saturn"
scripts:
  - "provision_and_consume"
  - "submodel_validation"
checksum: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

security:
  format: "encrypted-v1"
  algorithm: "AES-256-GCM"
  key_derivation: "RSA-OAEP-SHA256"
  compiler_id: "compiler:sha256:a1b2c3d4e5f6..."
  authorized_players:
    - player_id: "player:sha256:d4e5f6a1b2c3..."
      encrypted_key: "base64:YWVzLWtleS1lbmNyeXB0ZWQtd2l0aC1wbGF5ZXIxLXJzYS1wdWJsaWMta2V5..."
    - player_id: "player:sha256:f6a1b2c3d4e5..."
      encrypted_key: "base64:YWVzLWtleS1lbmNyeXB0ZWQtd2l0aC1wbGF5ZXIyLXJzYS1wdWJsaWMta2V5..."
```

| Field | Value | Purpose |
|-------|-------|---------|
| `name` | `connector_e2e` | Test case name from `tck.yaml` |
| `version` | `1.0` | Test case version from `tck.yaml` |
| `sdk_version` | `0.5.0` | SDK version used to compile — Player warns on mismatch |
| `compiled_at` | ISO 8601 timestamp | Compilation timestamp |
| `dataspace_versions` | `["saturn"]` | All dataspace versions referenced across scripts |
| `scripts` | List of names | Execution order |
| `checksum` | `sha256:<hex>` | Integrity hash — Player rejects tampered packages |
| `security` | Block | Encryption metadata — algorithm, compiler ID, authorized Players |

### Extracting a Package

An authorized Player can write a package's contents back out — the manifest, the
compiled instructions, the test scripts and the bundled assets — with
`testlab inspect --extract`. For an encrypted package this needs the Player's
private key (to decrypt) and the Compiler's public key (to verify the signature):

```bash
testlab inspect connector_e2e-1.0.tck \
  --player-keys .keys/player \
  --compiler-pub .keys/compiler/signing.pub \
  --extract ./extracted
```

```
Extracted connector_e2e-1.0.tck -> ./extracted/
  manifest.yaml
  tck-bundle.yaml
  tck-execution.json
  tests/negotiate-and-transfer.yaml
```

What lands on disk is what was verified: the package is checked before anything
is written, and the bytes written are the checked ones. There used to be a
separate `testlab decompile` that wrote out only the authoring YAML, and only
for encrypted packages.

!!! note "Extraction requires authorization"
    The Player's key must be listed in the package's `authorized_players` block.
    Unauthorized Players cannot unwrap the AES content key and will receive an error.

---

## Step 5 — Plain Mode (Development Only)

For local development and debugging, you can opt out of encryption with `--plain`:

```bash
testlab compile tck.yaml --plain --output connector_e2e-1.0.tck
```

```
WARNING: Package compiled in plain mode. Tests and assets are NOT encrypted.
         Do not distribute plain packages — they may contain secrets.
         Use encrypted mode (default) for any shared or production package.

Validating TCK "connector_e2e"...
Validation passed (2 tests, 9 steps, 9 assertions)

Packaging...
   Bundling tests/provision_and_consume.yaml
   Bundling tests/submodel_validation.yaml
   Bundling assets/schemas/serial-part-3.0.json
   Stamping metadata (SDK v0.5.0, 2026-03-30T14:22:00Z)
   Computing SHA-256 checksum

Package created: connector_e2e-1.0.tck (12.4 KB)
```

Plain packages store tests as-is — human-readable, no encryption, no keys needed:

```bash
unzip -l connector_e2e-1.0.tck
```

```
Archive:  connector_e2e-1.0.tck
  Length      Date    Time    Name
---------  ---------- -----   ----
      487  2026-03-30 14:22   manifest.yaml
     2841  2026-03-30 14:22   tests/provision_and_consume.yaml
     1203  2026-03-30 14:22   tests/submodel_validation.yaml
      892  2026-03-30 14:22   assets/schemas/serial-part-3.0.json
---------                     -------
     5423                     4 files
```

!!! warning "Never distribute plain packages"
    Plain packages contain secrets (OAuth2 credentials, service URLs, BPNs) in cleartext.
    Use plain mode only during local script development. Always compile with encryption
    (the default) before sharing, uploading to CI, or distributing to other teams.

---

## Command Reference

| Command | Description |
|---------|-------------|
| `testlab validate <tck.yaml>` | Validate tests without packaging |
| `testlab compile <tck.yaml> --authorize-player <key.pub> --signing-key <key.pem>` | Compile into encrypted `.tck` (default) |
| `testlab compile <tck.yaml> --plain` | Compile without encryption (development only) |
| `testlab compile <tck.yaml> --output <file>` | Specify output filename |
| `testlab compile <tck.yaml> --library-path <dir>` | Set path for resolving imported tests |
| `testlab keygen` | Generate Player RSA key pair |
| `testlab keygen --compiler` | Generate Compiler Ed25519 signing key pair |
| `testlab keygen --force` | Overwrite existing keys (key rotation) |
| `testlab export-key --player` | Print Player public key to stdout |
| `testlab export-key --fingerprint` | Print Player fingerprint |
| `testlab inspect <package>` | Show what a package contains, without running it |
| `testlab inspect <package> --manifest` | Show manifest metadata |
| `testlab inspect <package> --extract <dir>` | Write the verified contents out (needs `--player-keys`/`--compiler-pub` if encrypted) |
| `testlab inspect <package> --json` | One JSON object with every requested section |

---

You now have a compiled `.tck` ready to distribute and execute. Continue to [Executing Tests](executing-tests.md).

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)