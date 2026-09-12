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

# ADR-0003: SSE for Live IDE Execution

## Status

Accepted

## Date

2026-05-13

## Context

The IDE needs real-time step execution visualization. The backend `ExecutionMonitor` already emits granular events (step start, step complete, assertion result, error). Three transport options were evaluated:

1. **WebSocket**: bidirectional, complex setup, requires connection management.
2. **SSE (Server-Sent Events)**: unidirectional server→client, simple, auto-reconnect.
3. **REST polling**: simple but introduces latency and unnecessary load.

The IDE only needs to receive events — it never sends data back during execution.

## Decision

Use Server-Sent Events via FastAPI `StreamingResponse` on the backend and browser `fetch` with `ReadableStream` on the frontend. Event types map directly to `ExecutionMonitor` event kinds.

## Consequences

### Positive

- Simpler than WebSocket — no bidirectional connection management needed.
- Native browser `EventSource` provides auto-reconnect.
- No additional dependencies on either side.
- Works through HTTP proxies and CDNs without special configuration.

### Negative

- No bidirectional messaging — if future features need client→server during execution, a separate mechanism is required.
- Limited to ~6 concurrent connections per domain in some browsers (mitigated by HTTP/2).

### Neutral

- Event format uses standard SSE `data:` lines with JSON payloads.
- Connection lifecycle tied to test execution duration.
