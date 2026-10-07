# IDE Knowledge Base — Tractus-X TestLab

> This file is the living domain memory of `testlab-ide-master`.
> It is read at the start of every session and updated when notable patterns, gotchas, or lessons are discovered.
> Organized by category. Append new entries — never delete old ones (use strikethrough if superseded).

---

## Patterns

<!-- Format: ### PAT-{n}: {Title} -->

### PAT-1: SSE stream module extraction
When `executionApi.ts` grew past 300 lines after adding reconnection, the SSE streaming logic (parser + `connectJobStream`) was extracted to `store/sseStream.ts`. The API file re-exports `connectJobStream` so callers don't need to change imports. SSE event *handlers* (type guards + dispatch) live in `store/sseEventHandlers.ts` to avoid circular deps with the Zustand store.

### PAT-2: Fire-and-forget API calls for immediate UI feedback
`cancel()` aborts the local stream immediately for instant UX, then POSTs to the backend endpoint as fire-and-forget. Pause/resume use `await` because the user needs feedback if the API call fails.

- **Modularity directive**: The 300-line limit is a symptom check, not the goal. Code must be written modular from the start — small single-responsibility units with typed boundaries. When a file is split, extract **reusable** units along responsibility seams (hooks, pure functions, helper modules, one step/class per file), not arbitrary fragments. Shared logic is extracted into importable helpers; never duplicated.

---

## Gotchas

<!-- Format: ### GOTCHA-{n}: {Title} -->

### GOTCHA-1: SSE event handler state types and circular deps
Extracting `handleSseEvent` from the store creates a potential circular import (`sseEventHandlers → useExecutionStore → sseEventHandlers`). Solution: define a narrow `SseHandlerState` interface in the handlers file instead of importing `ExecutionStore`. Zustand's `set()` accepts partials, so the narrow type is structurally compatible.

---

## Anti-Patterns

<!-- Format: ### ANTI-{n}: {Title} -->

_No entries yet. Append anti-patterns here as they are discovered._

---

## Lessons Learned

<!-- Format: ### LESSON-{n}: {Title} -->

_No entries yet. Append lessons here as they are discovered._

---

## Reusable Fixes

<!-- Format: ### FIX-{n}: {Title} -->

_No entries yet. Append reusable fixes here as they are discovered._

---

## API Quirks

<!-- Format: ### API-{n}: {Title} -->

### API-1: Backend execution API path migration
The backend migrated from `/testlab/run/` and `/testlab/jobs/` to `/testlab/tck-execution/`. Key endpoints: `POST .../run/yaml` (submit), `GET .../{id}/stream` (SSE), `POST .../{id}/cancel|pause|resume`. Health stays at `/testlab/health`. SSE stream now includes `id:` lines for Last-Event-ID replay.

<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 Licensed under the Creative Commons Attribution 4.0 International License
 (the "License"); you may not use this file except in compliance with the
 License. You may obtain a copy of the License at

    https://creativecommons.org/licenses/by/4.0/

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 SPDX-License-Identifier: CC-BY-4.0
-->
