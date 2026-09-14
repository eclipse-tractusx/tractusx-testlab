<!--

Eclipse Tractus-X - Tractus-X TestLab

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

This section shows how to validate a TCK and compile it into a portable `.tck` package — readable, or signed and
encrypted for specific Players.

## Prerequisites

You've completed [Writing Tests](writing-tests.md) and have:

```
my-certificate-tck/
├── index.yaml
├── tests/
│   ├── ping_catalog.yaml
│   └── request_certificate.yaml
├── schemas/
│   └── certificate_schema.json
└── testdata/
    └── request_body.json
```

---

## Step 1 — Validate Without Packaging

`testlab validate` checks the manifest and every test it lists against the syntax — JSON Schema, known step types,
declared variables, references that resolve, test files and assets that exist — without writing anything:

```bash
testlab validate my-certificate-tck/index.yaml
```

```text
OK — index.yaml is valid (no issues)
```

With errors, each is printed with the file it is in, and the command exits `1`:

```text
  [ERROR] (execution step 0) tests/ping_catalog.yaml: Unknown step type 'connector/consumer/query_catalogue'
  [ERROR] (step 1) tests/request_certificate.yaml: '${{ execution.pull_endpont.edr_token }}' in param 'edr_token' names nothing this TCK supplies. Available: env.callback_timeout_s, env.ccm_usage_policy, …

Invalid — 2 error(s)
```

`--version <dataspace-version>` validates against a specific dataspace release.

---

## Step 2 — Compile

```bash
testlab compile my-certificate-tck/index.yaml -o dist/
```

```text
Compiled → dist/my-certificate-tck.tck
  Package checksum : blake2b:0fbeddc9f130b975e6d4a6b84b4145b95c9d023fc44625bcb8f5e6d4939431a5
  Fingerprint digest: blake2b:b5b6209acfaaf378ea38812f5aa1c2c4fb682d7233f2bb25ae0d09ad53430727
```

`compile` re-runs the validation first and stops on any error. `-o` takes a directory (the file is named
`<tck-id>.tck`) or a file path; without it, the package is written next to the manifest.

A `.tck` is a ZIP archive:

```bash
unzip -l dist/my-certificate-tck.tck
```

```text
  Length      Date    Time    Name
---------  ---------- -----   ----
      107  09-12-2026 23:54   assets/schemas/certificate_schema.json
      113  09-12-2026 23:54   assets/testdata/request_body.json
     1996  09-12-2026 23:54   manifest.yaml
     1450  09-12-2026 23:54   tck-bundle.yaml
     8880  09-12-2026 23:54   tck-execution.json
      693  09-12-2026 23:54   tests/ping_catalog.yaml
     2412  09-12-2026 23:54   tests/request_certificate.yaml
---------                     -------
    15651                     7 files
```

| Entry | Contents |
|-------|----------|
| `manifest.yaml` | Package identity: format, checksum, TCK id and metadata, dataspace, infrastructure, compilation fingerprint, the test list and the asset digests |
| `tck-bundle.yaml` | The manifest as authored, which the Player loads |
| `tck-execution.json` | The compiled, flat intermediate representation of every step |
| `tests/` | The test files as authored |
| `assets/` | The declared schemas and testdata |

The package `checksum` covers every entry. A Player refuses a package whose contents differ from the ones it was sealed with.

`--plain` writes the compiled files to a directory instead of an archive (default `<manifest dir>/plain`), which is
convenient for looking at `tck-execution.json` while developing.

---

## Step 3 — Inspect the Compiled Package

`testlab inspect` reports what a package contains without executing it:

```bash
testlab inspect dist/my-certificate-tck.tck --variables --infrastructure --manifest
```

```text
========================================================================
  Testlab Inspect — my-certificate-tck.tck
========================================================================
  Name             : Certificate Verification TCK
  Total Steps      : 5
  Total Validations: 5
  Tests            : 2

  Test: Ping Catalog  |  ID: ping_catalog.yaml  |  Skippable: No
  Step Name                                Uses                                Phase      Validations
  ---------------------------------------- ----------------------------------- ---------- -----------
  Query SUT catalog                        connector/consumer/query_catalog    Execution  1

  Test: Request Certificate  |  ID: request_certificate.yaml  |  Skippable: No
  Step Name                                Uses                                Phase      Validations
  ---------------------------------------- ----------------------------------- ---------- -----------
  Expose the callback endpoint the SUT an  mock/api                            Setup      0
  Negotiate access to the CCMAPI offer     connector/consumer/pull_data_filte  Execution  1
  Send the certificate request through th  connector/dataplane/http_request    Execution  2
  Wait for the SUT to call back            mock/wait/http_request              Execution  1

========================================================================

  VARIABLES
  ID                             Source       Scope      Type
  ------------------------------ ------------ ---------- ----------
  callback_timeout_s             input        sut        number
  ccm_usage_policy               value        —          object

========================================================================

  INFRASTRUCTURE
  Capability                Required   Standard
  ------------------------- ---------- --------------------
  engine.connector          True       —
  sut.connector             True       —

========================================================================

  MANIFEST
  TCK                  my-certificate-tck
  Checksum             blake2b:0fbeddc9f130b975e6d4a6b84b4145b95c9d023fc44625bcb8f5e6d4939431a5
  Encrypted            no

========================================================================
```

`--variables` shows what the operator will have to supply, `--infrastructure` what must be bound, and `--json`
combines every requested section into one JSON object.

### Extracting a Package

`--extract` writes the verified contents of a package to a directory:

```bash
testlab inspect dist/my-certificate-tck.tck --extract extracted
```

```text
Extracted my-certificate-tck.tck -> extracted/
  assets/schemas/certificate_schema.json
  assets/testdata/request_body.json
  manifest.yaml
  tck-bundle.yaml
  tck-execution.json
  tests/ping_catalog.yaml
  tests/request_certificate.yaml
```

The package is checked before anything is written, and the bytes written are the checked ones.

---

## Step 4 — Sign and Encrypt for a Player (Optional)

To restrict a package to specific Players, give `compile` a Compiler identity and each Player's public key.
See [Package Security](../specification/security.md) for the design.

### Generate identities (one-time setup)

Each identity is an RSA-4096 encryption pair plus an Ed25519 signing pair:

```bash
testlab keygen -o .keys -l compiler     # on the compiling machine
testlab keygen -o .keys -l player       # on each Player machine
```

```text
Keys saved to .keys/player/
  encryption.pem / encryption.pub  (RSA-4096)
  signing.pem    / signing.pub     (Ed25519)
  Encryption fingerprint: 78caa839aede1dab4880e0c3c9c1b74d...
  Signing    fingerprint: a3b14f337356d32eda6a2196a517e7e1...
```

Share each Player's `encryption.pub` with the Compiler, and the Compiler's `signing.pub` with the Players. Keys that
already exist are reused unless you pass `--override-keys`.

### Compile encrypted

```bash
testlab compile my-certificate-tck/index.yaml \
  --compiler-keys .keys/compiler \
  --player-pub .keys/player/encryption.pub \
  -o dist/my-certificate-tck-encrypted.tck
```

```text
  Authorized player: encryption.pub (78caa839aede1dab...)

Compiled (encrypted .tck) → dist/my-certificate-tck-encrypted.tck
  Checksum : blake2b:365287b57cd5fe2f0e916133...
  Signed by: 2320064d0401fea99abba121e9c3d448...
  Players  : 1
```

Repeat `--player-pub` to authorize several Players. The archive now holds only the redacted manifest, the encrypted
payload and the signature:

```text
  Length      Date    Time    Name
---------  ---------- -----   ----
     2141  09-12-2026 23:54   manifest.yaml
     5556  09-12-2026 23:54   payload.enc
       88  09-12-2026 23:54   signature.sig
```

`--compiler-keys` and `--player-pub` go together:

```text
Error: --player-pub is required to encrypt a package. Supply both --compiler-keys and --player-pub, or neither.
```

An encrypted package is inspected and extracted with the Player's identity and the Compiler's public key:

```bash
testlab inspect dist/my-certificate-tck-encrypted.tck \
  --player-keys .keys/player --compiler-pub .keys/compiler/signing.pub
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `testlab validate <index.yaml> [-v <dataspace-version>]` | Validate a TCK without packaging |
| `testlab compile <index.yaml> [-o <dir or file>]` | Compile into a readable `.tck` |
| `testlab compile <index.yaml> --plain [-o <dir>]` | Write the compiled files to a directory |
| `testlab compile <index.yaml> -c <compiler-dir> -p <player.pub> [-p …]` | Compile a signed, encrypted `.tck` |
| `testlab keygen [-o <dir>] [-l <label>] [--override-keys]` | Generate an identity in `<dir>/<label>/` |
| `testlab inspect <package>` | Show the tests, steps and validations a package contains |
| `testlab inspect <package> --variables --infrastructure --manifest` | Add the variables, infrastructure requirements and manifest |
| `testlab inspect <package> --json` | One JSON object with every requested section |
| `testlab inspect <package> --extract <dir>` | Write the verified contents out |
| `testlab inspect <package> -k <player-dir> -c <signing.pub>` | Inspect an encrypted package |

---

You now have a compiled `.tck` ready to distribute and execute. Continue to [Executing Tests](executing-tests.md).

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-testlab](https://github.com/eclipse-tractusx/tractusx-testlab)