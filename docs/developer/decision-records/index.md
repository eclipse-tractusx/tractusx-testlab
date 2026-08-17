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

# Decision Records

Architecture Decision Records (ADRs) document significant technical decisions made during the development of Tractus-X TestLab.

## Format

Each ADR follows the [Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):

| Section | Purpose |
|---------|---------|
| Status | Proposed, Accepted, Deprecated, or Superseded |
| Date | When the decision was made |
| Context | Forces at play and constraints |
| Decision | What was decided |
| Consequences | Trade-offs accepted |

## Records

ADRs are grouped by the part of the system they primarily affect: the **backend** Python
library (`src/tractusx_testlab/`) or **shared** concerns that span the system. The
[template](ADR-0000-template.md) lives at the root of this folder.

### Backend

| ADR | Title | Status |
|-----|-------|--------|
| [0005](backend/ADR-0005-filesystem-participant-manager-with-protocol.md) | Filesystem Participant Manager with Protocol | Accepted |
| [0012](backend/ADR-0012-compilation-and-packaging.md) | Compilation and Packaging | Proposed |
| [0014](backend/ADR-0014-flat-compilation-intermediate-representation.md) | Flat Compilation Intermediate Representation | Accepted |
| [0015](backend/ADR-0015-package-asset-resolution.md) | Package Asset Resolution | Accepted |
| [0016](backend/ADR-0016-execution-trace-format.md) | Execution Trace Format | Proposed |
| [0017](backend/ADR-0017-input-callback-endpoint.md) | Input Callback Endpoint | Proposed |
| [0019](backend/ADR-0019-service-requirements-and-engine-bindings.md) | Service Requirements and Engine Bindings | Proposed |
| [0022](backend/ADR-0022-tck-static-inspection.md) | TCK Static Inspection | Accepted |
| [0023](backend/ADR-0023-variable-scope-annotation.md) | Variable Scope Annotation (`engine` / `sut`) | Accepted |
| [0024](backend/ADR-0024-test-skip-configuration.md) | Test-Level Skip Configuration | Accepted |

### Shared

| ADR | Title | Status |
|-----|-------|--------|
| [0003](shared/ADR-0003-sse-for-live-ide-execution.md) | SSE for Live IDE Execution | Accepted |
| [0008](shared/ADR-0008-test-case-to-tck-rename.md) | Test-Case to TCK Rename | Accepted |
| [0009](shared/ADR-0009-typed-variable-class-system.md) | Typed Variable Class System | Accepted |
| [0010](shared/ADR-0010-yaml-syntax-v2.md) | YAML Syntax v2 (GHA-Inspired) | Accepted |
| [0011](shared/ADR-0011-environment-and-services.md) | Environment Variables and Services Management | Proposed |
| [0018](shared/ADR-0018-unified-variables-model.md) | Unified Variables Model (Preconditions as Complex Variables) | Accepted (finalized by [0021](shared/ADR-0021-remove-precondition-concept.md)) |
| [0021](shared/ADR-0021-remove-precondition-concept.md) | Remove the Precondition Concept in Favor of Unified Variables | Accepted |
| [0025](shared/ADR-0025-assertions-read-declared-returns.md) | Assertions Read Declared Returns | Proposed |

### Deprecated / Superseded

These ADRs are not published and remain as plain-text history only.

| ADR | Title | Status |
|-----|-------|--------|
| 0004 | Precondition as Distinct Step Phase | Superseded by [0021](shared/ADR-0021-remove-precondition-concept.md) (not published) |
| 0006 | Service Auto-Declaration on Block Drop | Deprecated (not published) |
| 0007 | Precondition Execution Logs Model | Superseded by [0021](shared/ADR-0021-remove-precondition-concept.md) (not published) |
| 0013 | Preconditions Specification | Superseded by [0021](shared/ADR-0021-remove-precondition-concept.md) (not published) |

## Creating a New ADR

1. Copy `ADR-0000-template.md` to `ADR-NNNN-short-title.md` (next available number).
2. Fill in all sections.
3. Place the file in the correct subfolder — `frontend/`, `backend/`, or `shared/` — based on which part of the system the decision primarily affects.
4. Add the entry to the matching subsection in this index table, using the subfolder path (for example `[NNNN](backend/ADR-NNNN-short-title.md)`).
5. Add the file to `mkdocs.yml` under the Decision Records nav section, in the matching `Frontend:` / `Backend:` / `Shared:` group.
