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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0024: Test-Level Skip Configuration

## Status

Accepted

## Date

2026-07-20

## Context

TCK authors occasionally need to mark certain tests as *optional* — tests that cover
features the SUT may not yet support or optional capabilities that are not required for
conformance. Operators running these TCKs need a safe, explicit way to bypass those
tests at runtime without modifying the TCK package itself.

Before this ADR there was no mechanism for this. All tests in a TCK always executed.
Operators worked around it by editing the TCK manifest to remove tests — which is a
destructive, non-repeatable change that modifies the package under test.

The requirement is:

1. The TCK **author** decides which tests may be skipped. A test that is not explicitly
   marked skippable can never be skipped — this prevents accidental or malicious
   bypassing of conformance requirements.
2. The **operator** provides the list of tests to skip at runtime, using an existing
   mechanism (`--var` or a config YAML), not a new CLI flag.
3. A skipped test must produce a **distinct, identifiable result** (`SKIPPED`) so that
   reports and dashboards can distinguish it from both passing (`COMPLETED`) and
   failing (`FAILED`) tests.
4. **Validation happens before the run starts.** An invalid or disallowed skip request
   must raise an error before any test executes, not mid-run.

## Decision

### 1. `TckTestEntry.skippable: bool = False`

A new opt-in field on `TckTestEntry` (in `models/authoring/definitions.py`). Default
is `False` — tests are **not** skippable unless the author explicitly sets
`skippable: true` in the TCK manifest.

```yaml
tests:
  - id: catalog_policy_validation.yaml
    name: Validate catalog policy constraints
    skippable: true        # operator may skip this at runtime
  - id: request_certificate.yaml
    name: Request a certificate
                           # skippable omitted → defaults to false
```

### 2. `skip_tests` runtime variable

The operator provides the list of tests to skip via the standard `runtime_vars`
mechanism — no new CLI flag is introduced:

```bash
# Single test — via --var
testlab run index.yaml --var skip_tests=catalog_policy_validation.yaml

# Multiple tests — via config YAML (--var overwrites; use config for lists)
# skip-config.yaml:
#   skip_tests:
#     - catalog_policy_validation.yaml
#     - error_handling.yaml
testlab run index.yaml --config skip-config.yaml
```

`skip_tests` accepts either a single string or a list of strings. These are test file
IDs (`TckTestEntry.id`), not display names.

### 3. Pre-run validation via `resolve_skip_ids()`

Before any test executes, the player calls `resolve_skip_ids(tck, runtime_vars)`
(in `player/execution/_skip.py`). This function:

- Returns a `frozenset[str]` of validated IDs if all checks pass.
- Raises `SkipNotAllowedError` if any requested ID is:
  - **Unknown** — not present in the TCK's test list.
  - **Not skippable** — present but `skippable: false` (the default).

Validation happens once before the first test runs. Mid-run partial failures are not
possible.

### 4. `TestStatus.SKIPPED`

A new value on the `TestStatus` enum. Used exclusively for tests that were
intentionally skipped by the operator. It is semantically distinct from:

- `FAILED` — test ran and did not pass.
- `CANCELLED` — run was aborted externally.
- `COMPLETED` — test ran and passed.

`build_tck_result` treats `SKIPPED` as non-failing: an overall TCK is `COMPLETED`
when all tests are either `COMPLETED` or `SKIPPED`. A single `FAILED` test makes
the entire TCK `FAILED`.

### 5. `SkipNotAllowedError` domain exception

New exception in `models/primitives/exceptions.py`, exported via `models/__init__.py`.
Includes the list of invalid IDs and the reason (unknown vs. not skippable).

### 6. Visibility in `testlab inspect`

`TestInspection` gains a `skippable: bool = False` field.  `testlab inspect` shows a
`Skippable: Yes / No` column for each test. The `--json` envelope includes
`"skippable": true/false` per test entry.

## Consequences

### Positive

- Authors retain full control: only explicitly opted-in tests can be skipped.
- Validation is strict and early — operators learn about invalid requests before any
  test runs, not after partial execution.
- `SKIPPED` is a first-class result status — dashboards, reports, and the engine can
  distinguish it from failures without special-casing.
- No new CLI flags are needed — `skip_tests` uses the existing `--var` / config YAML
  mechanism operators already know.

### Negative / Trade-offs

- Skip-by-ID means the operator must know the exact file IDs (`catalog_policy_validation.yaml`),
  not display names. This is intentional — display names are non-unique.
- Repeating `--var skip_tests=...` multiple times on the CLI overwrites the value;
  operators must use a config YAML to skip more than one test at a time. This is a
  limitation of the existing `--var` mechanism, not of this ADR.

## Related

- [ADR-0022: TCK Static Inspection](ADR-0022-tck-static-inspection.md) — `TestInspection.skippable` field added.
- [ADR-0016: Execution Trace Format](ADR-0016-execution-trace-format.md) — `TestStatus.SKIPPED` added.
