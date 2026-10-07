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

# ADR-0006: Service Auto-Declaration on Step Insertion

## Status

Deprecated

## Date

2026-05-13

## Context

Users had to manually declare services in a separate service dialog before using service-category steps (EDC Connector, DTR, Discovery Finder). This violated the "defaults everywhere" design principle — steps should work with minimal input. New users were confused when adding a connector step that immediately showed errors because no service existed.

## Decision

Auto-declare a service when a step is added. Logic:

1. A step is added that requires a service (determined by step category).
2. If a matching service already exists → auto-select it on the step.
3. If no matching service exists → auto-create one with defaults (empty URL, type inferred from category) and select it.

The service dialog remains available for manual override and advanced configuration.

## Consequences

### Positive

- Zero-config experience for the first step added — no prerequisite dialog required.
- Follows "defaults everywhere" principle.
- Reduces onboarding friction for new users.

### Negative

- Auto-created services have empty URLs — user must configure before execution.
- Multiple steps of the same category share the auto-created service (may not always be desired).

### Neutral

- The service dialog remains the mechanism for renaming, deleting, or duplicating services.
- No duplicate services are created — matching uses service type as the key.
