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

# Certificate Management v2 — Full Lifecycle Example

This folder demonstrates the complete lifecycle of a TCK from raw YAML authoring to compiled package to execution trace.

## Structure

```
certificate-management-v2/
├── raw/                        ← Source YAML (what the test author writes)
│   ├── tck.yaml                  TCK definition (env, services)
│   ├── tests/
│   │   └── request-certificate.yaml   Test steps
│   ├── schemas/
│   │   ├── business_partner_certificate.json
│   │   └── notification_header.json
│   └── testdata/
│       └── request_certificate_body.json
│
├── plain/                      ← Plain compiled .tck contents (development mode)
│   ├── manifest.yaml             Package metadata (allow_asset_override: true)
│   ├── tck-execution.json        Full compiled IR (env + symbol tables + instructions)
│   └── assets/
│       ├── schemas/              Validated schemas (copied from source)
│       │   ├── business_partner_certificate.json
│       │   └── notification_header.json
│       └── testdata/             Resolved testdata (variables substituted)
│           └── request_certificate_body.json
│
├── encrypted/                  ← Encrypted compiled .tck contents (certification mode)
│   ├── manifest.yaml             Unencrypted metadata + security block (allow_asset_override: false)
│   ├── payload.enc               AES-256-GCM encrypted tar (tck-execution.json + assets/)
│   └── signature.sig             Hybrid Ed25519 + ML-DSA-65 signature
│
└── execution/                  ← Test execution output
    └── execution-trace.jsonl     Line-by-line execution trace (steps + summary)
```

## Lifecycle Flow

```
raw/tck.yaml + raw/tests/*.yaml
        │
        ▼  (testlab compile)
plain/manifest.yaml + plain/tck-execution.json + plain/assets/
        │
        ▼  (testlab compile --encrypt)
encrypted/manifest.yaml + encrypted/payload.enc + encrypted/signature.sig
        │
        ▼  (testlab run *.tck)
execution/execution-trace.jsonl
```

## Key Differences Between Modes

| Aspect | Plain | Encrypted |
|--------|-------|-----------|
| `allow_asset_override` | `true` | `false` |
| IR visibility | Human-readable JSON | Encrypted binary |
| Asset override | Permitted | Rejected (`AssetOverrideProhibitedError`) |
| Signature verification | Optional | Required before decryption |
| Use case | Development & debugging | Official certification distribution |

## Running the Plain Package

```bash
# With default assets
testlab compile raw/index.yaml

# With custom testdata override
testlab run certificate-management-tck-v0.0.1.tck
```

## Running an encrypted packege

```bash

## Generate keys in .keys directory
testlab keygen --output .keys/default

## .keys/default
##   |_ encryption.pem
##   |_ encryption.pub
##   |_ signing.pem
##   |_ signing.pub

testlab compile index.yaml --compiler-keys .keys/default --player-pub .keys/default/encryption.pub --output ccm-encrypted.tck 

```


## Related ADRs

- [ADR-0012 — Compilation and Packaging](../../developer/decision-records/backend/ADR-0012-compilation-and-packaging.md)
- [ADR-0014 — Flat Compilation IR](../../developer/decision-records/backend/ADR-0014-flat-compilation-intermediate-representation.md)
- [ADR-0015 — Package Asset Resolution](../../developer/decision-records/backend/ADR-0015-package-asset-resolution.md)
