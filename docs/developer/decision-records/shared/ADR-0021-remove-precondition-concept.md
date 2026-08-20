<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0021: Remove the Precondition Concept in Favor of Unified Variables

## Status

Accepted

## Date

2026-06-08

## Context

TestLab carried two unrelated authoring mechanisms for everything a test needs
before its steps run:

- **Preconditions** — a separate step family (`precondition/*`), a `preconditions:`
  manifest block, and a dedicated `PRECONDITION` execution phase. A
  `precondition/provide` step inlined a value (typically an access policy) so
  later steps could reference it.
- **Variables** — typed definitions declared in `index.yaml` under
  `env.variables` and referenced through `${{ env.<id>.<field> }}`.

The two overlapped: a `precondition/provide` policy and an `env.variables`
policy described the same thing in two different ways. ADR-0018 (Unified
Variables Model) proposed expressing preconditions *as* complex variables but
kept a backward-compatible precondition path. For the production release we want
**one** way to declare prerequisites.

The unified-variables approach has been proven end to end: the
`certificate-management-v2.0` example
(`ide/public/examples/certificate-management-v2.0/`) was migrated so that every
test pulls its access policy from a single env variable. Zero preconditions
remain in that example.

## Decision

We remove the precondition concept entirely. This is an intentional breaking
change, not a deprecation.

Removed:

- The `precondition/*` step family — `precondition/provide`,
  `precondition/generate`, `precondition/input`, `precondition/inject/connector`,
  and any other `precondition/*` verb.
- The `preconditions:` manifest block.
- The `PRECONDITION` execution phase and its runner.
- All related models, schema, IDE blocks/UI, and documentation.

Legacy `precondition/*` YAML is **no longer accepted**. The compiler rejects it
rather than translating it.

### Replacement mapping

| Was (precondition) | Now (variables) |
|--------------------|-----------------|
| `precondition/provide` inlining a policy | A complex variable in `index.yaml` `env.variables` with `uses: config/connector/policy` |
| Reference to the provided policy | `${{ env.<id> }}` |
| Data pulled "from a precondition" | A `connector/pull_data_filtered` step consuming `with.policy: ${{ env.<id> }}` |

A policy is declared once:

```yaml
env:
  variables:
    - id: ccm_usage_policy
      uses: config/connector/policy
      name: Required CCMAPI Usage Policy
      with:
        value: { permissions: [ ... ] }
      returns:
        value:
          type: object
          class: Policy
```

and referenced wherever a step needs it:

```yaml
- id: pull_data_1
  uses: connector/pull_data_filtered
  with:
    policy: ${{ env.ccm_usage_policy }}
    # ...
```

## Consequences

### Positive

- One authoring concept for prerequisites. A policy is declared once and
  referenced everywhere, instead of being inlined per test.
- Less surface area: no separate phase, runner, block family, or schema branch
  to maintain.
- Prerequisites become first-class typed variables, reusable across TCKs and
  standard versions.

### Negative

- Breaking for any existing test YAML that uses preconditions. Such tests must
  be migrated before they compile or run.
- Historical compiled artifacts and execution traces that contain
  `precondition/*` sources or a `precondition` phase no longer reflect the
  current model.

### Neutral

- Migration is mechanical: move each precondition-provided value into
  `env.variables` and repoint references to `${{ env.<id>.<field> }}`.
- Reference migrations: the `certificate-management-v2.0` (CCM) example is the
  policy-variable reference; the `connector-ping-v1.0` and `dtr-ping-v1.0`
  examples are precondition-free TCKs.

## Supersedes

This ADR supersedes the precondition-related decisions:

- ADR-0004 — Precondition as Distinct Step Phase (not published)
- ADR-0007 — Precondition Execution Logs Model (not published)
- ADR-0013 — Preconditions Specification (not published)

It affirms and finalizes [ADR-0018 — Unified Variables Model](ADR-0018-unified-variables-model.md):
the unified-variables model remains the way to declare prerequisites, and this
ADR removes the backward-compatible precondition path that ADR-0018 had retained.
