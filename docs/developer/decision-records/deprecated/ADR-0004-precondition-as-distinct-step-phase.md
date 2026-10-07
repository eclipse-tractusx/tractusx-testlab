<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0004: Precondition as Distinct Step Phase

## Status

Superseded by [ADR-0021](../ADR-0021-remove-precondition-concept.md)

## Date

2026-05-13

## Context

Preconditions run before setup. They do not call APIs — they generate execution logs instructing users what to configure in external systems. Two modeling options:

1. Sub-phase of Setup — precondition blocks live inside the setup container.
2. Distinct phase — `PRECONDITION` is a first-class phase with its own runner.

Preconditions differ from setup: they produce instructions rather than performing actions, and their failure semantics differ (skip setup+main but still run cleanup).

## Decision

Add a new `StepPhase.PRECONDITION` enum value. Implement a separate `execute_precondition_steps()` runner. Execution order becomes: precondition → setup → main → cleanup.

Precondition steps use dedicated executor classes that produce `PreconditionLog` entries instead of making HTTP calls.

## Consequences

### Positive

- Clean phase boundary — preconditions are not conflated with setup actions.
- Precondition results are clearly identifiable in `TestResult`.
- Precondition failure skips setup and main while still running cleanup.

### Negative

- Slightly more complex player logic (four phases instead of three).
- Phase enum grows — all phase-aware code must handle the new value.

### Neutral

- Precondition blocks get their own toolbox phase section.
- YAML format gains a `preconditions:` key at test-case level.
