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

# ADR-0008: Test-Case to TCK Rename

## Status

Accepted

## Date

2026-05-13

## Context

The product concept "test case" was too generic and caused multiple problems:

- **Naming collision**: Python's `unittest.Tck` made class naming awkward and confusing in code.
- **Conceptual ambiguity**: users couldn't tell whether "test case" meant the overarching container or an individual test inside it.
- **Weak product identity**: the name didn't communicate that this is a Technology Compatibility Kit for certification testing.

The product scope (`docs/developer/product-scope.md`) defines these containers as conformance test packages that validate Tractus-X standard implementations against a specification version.

## Decision

Rename the overarching container concept from **"test-case"** to **"tck"** (Technology Compatibility Kit).

Specific changes:

- YAML `kind: test-case` → `kind: tck`
- All Python class names: `Tck` → `Tck` (e.g., `TckModel`, `TckCompiler`)
- All method/variable names: `test_case` → `tck`
- File extension: `.testpkg` → `.tckpkg`
- UI labels: "Test Case" → "TCK"
- Individual "test" tests within a TCK keep their name unchanged

**No backward compatibility** — this is a clean break at this early stage.

## Consequences

**Positive**:

- Clearer product identity — users immediately understand this is certification tooling
- No naming collision with `unittest.Tck`
- Aligns terminology with industry-standard "TCK" concept (Java TCK, Jakarta TCK)

**Negative**:

- Breaking change for existing YAML files (must update `kind:` field)
- All documentation, examples, and tutorials must be updated
