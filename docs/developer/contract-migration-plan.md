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
<!-- This document was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5). -->
<!-- It is an implementation handoff plan; review before executing. -->

# Contract migration — implementation plan

Executable handoff plan for the step-contract harmonization. The
decisions being implemented are in
[contract-conflict-decisions.md](contract-conflict-decisions.md) (every
conflict now has exactly one ticked box; margin notes beside a ticked
box override it — notably C04's note supersedes C27's step id).

**Repo:** `tractusx-testlab` (this repo). Python 3.12, pydantic v2, pytest.
Test: `poetry run pytest -q` (narrow with a path or `-k`). Acceptance: the full
suite green.

**Ground rules (non-negotiable):**

1. One canonical name, one canonical shape per concept. Never keep an alias,
   a deprecated-but-accepted spelling, or dual input shapes. Rename fully and
   migrate every caller.
2. After any rename, grep the WHOLE repo (src, tests, docs/examples, stubs,
   e2e fixtures) for the old spelling and fix every hit.
3. Steps never name their connector service — services are seeded at runtime.
   The only sanctioned way to address a *remote* party's data is the
   `dataplane_url` + `edr_token` parameter pair.
4. Copy the Apache-2.0 header verbatim from a neighboring file when creating
   files. Match existing docstring/comment style. No speculative abstraction.
5. Commit per cluster, in the order below (later clusters depend on earlier
   renames; C47 last because it hard-fails any stale spelling left behind).

**Branch state right now (engine, `feat/run_security_consitency`):**

- Cluster E1 is DONE — commit `3be95d1` ("refactor: drop engine-internal alias
  spellings…"). Details below so nobody redoes it.
- These uncommitted files are the repo owner's separate WIP — do NOT commit,
  revert, or fold them into migration commits:
  `models/__init__.py`, `models/primitives/enums.py`,
  `models/runtime/events.py` (untracked), `player/execution/_trace_formatter.py`,
  `player/execution/monitor.py`, `player/execution/phases/_run_phase.py`,
  `player/execution/player.py`, `docs/developer/contract-conflict-decisions.md`.
  (The `events.py`/player files look like the beginnings of C46 — see E8;
  coordinate with them rather than duplicating.)

---

## CLUSTERS (tractusx-testlab)

### E1 — Internal aliases ✅ DONE (commit `3be95d1`)

Already implemented; recorded here for context:

- C20/C21: `CounterPartyParams` (`steps/_contracts.py`) lost the
  `provider_url`/`bpnl` `AliasChoices` — only `counter_party_address` /
  `counter_party_id` validate now.
- C22: `FilterExpression` input accepts only `operand_left`/`operand_right`;
  `operandLeft`/`operandRight` remain **serialization-only**
  (`serialization_alias`), used by `to_sdk()`.
- C25: `validate/schema` (`steps/utility/validate.py`) — field `json_schema`
  now has `validation_alias="schema"` only; tests write `schema:`, the
  `json_schema:` spelling is dead.
- C19 (shared-model half): `FilterExpressionParams.filter_expression` renamed
  to `filters` (no alias); `CatalogFilter` (the nested `filter:` block dual
  shape) deleted; `QueryCatalogParams`/`QueryCatalogByBpnlParams` now declare
  `filters`; callers in `catalog_query.py`, `catalog_filter.py` updated
  (`do_dsp.py`/`pull_data/_executor.py` go through the untouched
  `sdk_filter_expression()` helper, which now reads `self.filters`).
- Tests updated: `tests/test_catalog_query_contract.py` (alias tests replaced
  with canonical + rejection tests), `tests/test_step_docs.py` (alias test now
  uses the local `_Sample.aliased` field; page test asserts `provider_url`
  absent), `tests/test_ccm_steps.py`, `tests/test_connector_do_dsp.py`
  (inputs snake_case, SDK asserts camelCase), e2e yaml
  `tests/e2e/connector-dtr-smoke/tests/connector_negotiation.yaml`
  (`filter_expression:` → `filters:`).
- KNOWN DEBT for E9: `tests/test_step_docs.py::TestGeneratedPage::
  test_committed_page_matches_the_code` fails until the docs page is
  regenerated (see E9). Do not "fix" it before then.

### E2 — Negotiate / transfer (C01, C02, C10, C11, C28, C33, C34, plus C18's engine half)

Files: `steps/connector/negotiate.py`, `transfer.py`, `dataplane.py`,
`_contracts.py`, `syntax/context_vars.py`, `catalog_query.py` (exports).

1. **C01** rename step id `connector/consumer/negotiate_contract` →
   `connector/consumer/negotiate` (`@step(...)` in `negotiate.py`; class/docstring
   references too).
2. **C10** in `NegotiateContractParams`: rename field `target` → `asset_id`.
   The context-var fallback chain: rename `CATALOG_TARGET = "catalog_target"`
   → `CATALOG_ASSET_ID = "catalog_asset_id"` in `syntax/context_vars.py`, and
   rename the `catalog_target` export field in
   `QueryCatalogByAssetIdExports` (`catalog_query.py`) to `catalog_asset_id`
   (alias = the new constant). Grep for `catalog_target` and `CATALOG_TARGET`
   across repo (also used in `negotiate.py` and possibly `do_dsp.py`).
3. **C11** verify-only: `policy` param stays an ODRL document fed from
   `catalog_policy` — already correct today, no `offer_id` support.
4. **C33** negotiate outputs gain `agreement_id` + `state`: after
   `start_edr_negotiation`, poll the negotiation until terminal
   (FINALIZED/TERMINATED) or timeout. SDK surface available on the consumer
   service (verified by introspection): `contract_negotiations` (controller
   accessor), `get_edr_entry(negotiation_id=…)`, plus `edrs`,
   `transfer_processes`. The EDC management API answer for one negotiation is
   `GET /v3/contractnegotiations/{id}` → `{"state": …, "contractAgreementId": …}`.
   Inspect `consumer.contract_negotiations` for a `get_by_id`-style method; if
   the SDK exposes none, do a plain `requests.get` against
   `context.get_consumer_endpoint_url("contract_negotiations", negotiation_id)`
   with the seeded management headers (look at how `context.get_consumer_endpoint_url`
   is used in `transfer.py`/`dataplane.py`). Add `agreement_id` + `state` to
   `NegotiationOutput` and `NegotiationExports` (context var name:
   `contract_agreement_id` already exists as `DSP_CONTRACT_AGREEMENT_ID`; add
   a plain `AGREEMENT_ID = "agreement_id"` constant — do not overload the DSP
   ones, they belong to the raw-DSP step family). Poll with the same
   delay/timeout style `transfer.py`'s neighbors use; keep it short (a few
   seconds default).
5. **C02** rename step id `connector/consumer/transfer_data` →
   `connector/consumer/initiate_transfer` (`transfer.py`). Keep behavior:
   resolve `negotiation_id` → `transfer_id` → `fetch_data_address(...)`.
6. **C28** add `transfer_type: Optional[str]` to the params
   (`HttpData-PULL` default when omitted; accepted: `HttpData-PUSH`,
   `AmazonS3-PUSH`). PUSH mode issues a real
   `POST /v3/transferprocesses` via the SDK (`consumer.transfer_processes`
   controller — inspect it; else raw POST to
   `context.get_consumer_endpoint_url("transfer_processes")`) with body
   `{transferType, contractId (the agreement id), counterPartyAddress,
   dataDestination}` and then polls the transfer process state. Add a
   `data_destination: Optional[dict]` param for the PUSH target (required when
   `transfer_type` is `*-PUSH`; validate that in a `model_validator`). PULL
   path unchanged.
7. **C34** output canonicalization — `data_address` stays, `dataplane_endpoint`
   dies **everywhere** (they're two names for one value):
   - `syntax/context_vars.py`: delete `DATAPLANE_ENDPOINT`; keep
     `DATA_ADDRESS = "data_address"`; delete the "older spelling" comment.
   - `_contracts.py` `DataplaneExports`: rename field `dataplane_endpoint` →
     `data_address` (alias `DATA_ADDRESS`).
   - `transfer.py` `TransferDataExports`: drop its duplicated `data_address`
     field (now inherited) and stop exporting `dataplane_endpoint`.
   - `transfer.py` output/exports gain `state` (the transfer/negotiation state
     string, mirroring C33).
   - `dataplane.py` `GetEdrStep.execute`: `DataplaneExports(data_address=…)`.
   - `dataplane.py` `DataplaneCallStep.execute`: fallback var becomes
     `DATA_ADDRESS`.
   - Grep `dataplane_endpoint` repo-wide (docs/examples too).
8. **C18 engine half** in `dataplane.py` `DataplaneCallParams`: rename field
   `endpoint` → `dataplane_url` and `token` → `edr_token`; delete both
   `AliasChoices` (the `url`, `endpoint`, `token` spellings die). Keep the
   dict-or-string coercion in `endpoint_url()` (rename to match). Drop the
   now-unused `AliasChoices` import.
9. Update ALL callers/tests: grep `negotiate_contract`, `transfer_data`,
   `"target"` (in negotiate contexts), `catalog_target`, `dataplane_endpoint`,
   `"endpoint"`/`"token"` raw-param keys in tests
   (`tests/test_transfer_and_dataplane.py`, `test_connector_negotiate*.py` if
   present — discover with grep), e2e yaml under `tests/e2e/`, and
   `docs/examples/**` and `stubs/**` tests.

Test: `poetry run pytest tests -k "negotiate or transfer or dataplane or edr" -q`.

### E3 — Catalog / pull_data / contract-definition (C13, C14, C23, C29, C35, C36)

Files: `steps/connector/provision.py`, `pull_data/_executor.py`,
`pull_data/_constants.py`, `catalog_query.py`, `do_dsp.py`,
`catalog_filter.py`, `consume.py`.

1. **C13** `expected_policies` is THE param name for every consumer-side
   policy filter: rename `policies` → `expected_policies` in
   `pull_data_filtered_by_policy` params, `query_catalog_by_asset_id` params
   (`catalog_query.py`), and `do_dsp`/`do_dsp_with_bpnl` params (`do_dsp.py`).
   The kwarg passed INTO the SDK (`consumer.do_dsp(policies=…)`) keeps the
   SDK's name — only the test-facing param renames.
2. **C14** `create_contract_definition` (`provision.py`): param
   `contract_id` → `contract_definition_id`; output field `contract_def_id` →
   `contract_definition_id`. One name both directions.
3. **C23** same step: field `usage_policy_id` → `contract_policy_id` (the
   on-record recommendation was overridden). The value still lands in the EDC `contractPolicyId` API field.
4. **C29** same step: add `asset_selector: list[FilterExpression]`
   (reuse `FilterExpression` from `_contracts.py` — same
   `operand_left/operator/operand_right` shape, serialized camelCase via
   `to_sdk()`), passed to the EDC contract-definition `assetsSelector` array.
   `asset_id` remains as the simple single-asset form; when both given,
   `asset_selector` wins (document that in the field description); when only
   `asset_id` given, build the one-criterion selector from it (that is what
   the step already does implicitly today — check how `provision.py` builds
   the definition body).
5. **C35** `query_catalog` output wrap: today `QueryCatalogStep` returns the
   raw `CatalogPayload` as value. Change its output to the
   `FilteredCatalogOutput` shape already defined in `catalog_filter.py`
   (`catalog` + `datasets`) — move that model into `_contracts.py` (or import
   it) so both steps share one output model, and return
   `catalog=<full document>`, `datasets=as_dataset_list(catalog)`.
   A test's `returns:` then reads `catalog` and `datasets` — never
   `dcat:dataset`.
6. **C36** `pull_data_filtered` (`pull_data/_executor.py` + its step wrapper in
   `pull_data/__init__.py` or `consume.py` — locate with grep
   `pull_data_filtered`): add `agreement_id` to its output/exports, sourced
   the same way its `_by_policy` sibling publishes it.

Update callers/tests: grep `contract_id`, `contract_def_id`,
`usage_policy_id`, `"policies"` (test-facing), plus e2e/docs/stubs.

Test: `poetry run pytest tests -k "provision or contract or pull_data or catalog" -q`.

### E4 — DTR (C37 + new C04/C27 lookup step)

File: `steps/industry/dtr.py` (~230 lines; read fully first — its shared
`DtrParams`/`DescriptorPayload` pattern is the style to follow).

1. **C37** `DescriptorPayload.id_short`: change
   `alias="idShort"` → `validation_alias="idShort"` so the AAS API's camelCase
   is accepted on input but the field ALWAYS serializes as `id_short`.
   Verify with a quick check that step output rendering (`.of(body)` →
   `bind_output`) dumps `id_short`. C03/C05/C15 are already correct on the
   engine side (ids `digital-twin-registry/provider/create_shell_descriptor`,
   `…/create_submodel_descriptor`, param `aas_identifier`) — verify, no change.
2. **C04+C27** new step — id EXACTLY
   `digital-twin-registry/consumer/dataplane/lookup_shell`
   (deliberate 4-segment exception; do not normalize). It searches a
   COUNTERPARTY's registry through an EDC dataplane — it must NOT call
   `context.get_aas_service()` (that's the locally-seeded registry).
   - Params: `specific_asset_ids: list[dict]` (AAS specificAssetIds criteria,
     `[{"name": …, "value": …}]`), `dataplane_url: str`, `edr_token: str`.
   - Behavior: the AAS registry lookup API is
     `GET {base}/lookup/shells?assetIds=<base64url(JSON of each criterion)>`
     (one `assetIds` query param per criterion, each a base64url-encoded JSON
     object — this is the AAS v3 spec encoding; check
     `tractusx_sdk.industry` for an existing encoder before hand-rolling).
     Issue it with `requests.get(dataplane_url + "/lookup/shells", …)`,
     header `Authorization: <edr_token>` — same bare-HTTP pattern as
     `DataplaneCallStep.execute` in `steps/connector/dataplane.py`.
     The response is `{"result": [<shell ids>]}` (v3 paginated shape:
     `{"paging_metadata": …, "result": […]}`).
   - Optionally follow up with `GET {dataplane_url}/shell-descriptors/{b64(id)}`
     per id to fill `shell_descriptors`; keep it simple — one page, no
     pagination loop.
   - Output model: `shell_ids: list[str]` + `shell_descriptors: list[dict]`.
   - Return a real `HttpRequest`/`HttpResponse` pair in the `StepOutput` like
     every other step in the file.

Test: `poetry run pytest tests -k "dtr or shell or submodel" -q` (add a unit
test for the new step with a mocked `requests` — copy the mocking style of
existing dataplane tests).

### E5 — Wizard creation steps (C26)

Files: `steps/connector/provision.py`, `steps/industry/dtr.py`.

Two shapes = two separate steps (never one step accepting either shape):

- Existing raw-payload steps stay as-is: `connector/provider/create_asset`
  (param `asset`: full document), `connector/provider/create_policy`
  (param `policy`), `digital-twin-registry/provider/create_shell_descriptor`
  (param `shell_descriptor`), `…/create_submodel_descriptor`
  (param `submodel_descriptor`).
- NEW wizard siblings with flat guided fields that assemble the document and
  then call the SAME underlying creation logic (extract a module-level helper
  from each raw step's `execute`; no duplicated API calls):
  - `connector/provider/wizard/create_asset` — fields `asset_id`, `name`,
    `description` (opt), `base_url`, `content_type` (opt), `properties`
    (opt dict) → assembles the EDC asset document.
  - `connector/provider/wizard/create_policy` — fields `policy_id`,
    `permissions` (list), `prohibitions` (opt list), `obligations` (opt list)
    → assembles the ODRL policy document.
  - `digital-twin-registry/provider/wizard/create_shell_descriptor` — fields
    `id` (opt, generate UUID urn if absent), `id_short`, `global_asset_id`
    (opt), `specific_asset_ids` (opt list), `submodel_descriptors` (opt list)
    → assembles a ShellDescriptor.
  - `digital-twin-registry/provider/wizard/create_submodel_descriptor` — fields
    `aas_identifier`, `id` (opt), `id_short`, `semantic_id`, `endpoint_url`
    → assembles a SubModelDescriptor (semantic_id becomes the AAS
    `semanticId` reference structure; endpoint_url becomes the single
    SUBMODEL-3.0 endpoint entry).

Test: `poetry run pytest tests -k "asset or policy or wizard or provision" -q`.

### E6 — HTTP / mock (C17, C30, C31, C38, C39; C24 verify-only)

Files: `steps/server/mock.py`, `steps/server/wait.py`,
`server/mock_registry.py`, HTTP step (grep `http/http_request` — likely
`steps/utility/` or `steps/server/`), `steps/industry/notification.py`.

1. **C30** `http/http_request`: add `query_params: dict[str, str]` (default
   `{}`), merged into the URL (pass `params=` to `requests.request`).
2. **C31** `mock/api`: add `response_headers: dict[str, str]` param; the mock
   endpoint replies with them (thread through `server/mock_registry.py` /
   `player/execution/mock_server.py` — find where status/body are stored per
   endpoint and add headers alongside).
3. **C38** `mock/api` output becomes a structured mock instance (replaces the
   bare string): fields `endpoint_id`, `base_mock_url` (mock server root),
   `full_mock_url` (root + the unique generated path — directly callable).
   Build it from what the registry already knows when registering the mock.
4. **C17** `mock/wait/http_request` param: `endpoint_id: str` → `mock`, typed
   as the C38 mock-instance object (dict/model with at least `endpoint_id`).
   The step reads `mock["endpoint_id"]` (or model attr) to find the endpoint.
   Accept ONLY the object — not a bare id string (no dual shape).
5. **C39** `mock/wait/http_request` outputs: keep/ensure `request_method`,
   `request_path`, `request_headers`, `request_body`; ADD `request_query_params`
   and `elapsed_ms` (wall-clock waited). Rename any un-prefixed spellings.
6. **C24** verify `notification/consumer/send` uses `dataplane_url`,
   `edr_token`, `content` (should already; fix any `endpoint_url`/`auth_token`
   /`payload` leftovers).
7. C07 (`http/http_request` name) and C08 (mock module inconsistency): keep
   as-is — no-ops by decision.

Test: `poetry run pytest tests -k "mock or wait or http" -q`.

### E7 — flow/if, semantic_schema deletion, C16, fallback restriction (C06, C32, C16, C40)

1. **C06** new file `steps/flow/if.py` (id `flow/if`), modeled on
   `steps/flow/retry.py` (read it first — nested `list[StepDefinition]`
   params, global-registry lookup via `_ANY_VERSION`, sequential nested
   execution, `StepValue[list[Any]]` output):
   - Params: `condition: str` (a `${{ }}` expression — evaluate with the
     EXISTING evaluator in `steps/conditions.py` / `_condition_parsing.py`;
     do not write a new parser), `then: list[StepDefinition]` (required,
     `min_length=1`), `else_: list[StepDefinition]` (default `[]`,
     `validation_alias="else"`, `serialization_alias="else"`).
   - Behavior: evaluate once; run `then` steps in order when truthy, `else`
     when falsy (no-op if empty). Nested failures propagate like retry's do.
   - Output: `branch_taken` (`"then"`/`"else"`/`"none"`),
     `condition_result: bool`, `outputs: list` (executed branch's outputs).
   - Register the module import wherever `steps/flow/__init__.py` /
     `steps/__init__.py` imports `delay`/`retry`.
   - `flow/condition` is NOT an engine step — `condition` is the expression
     string itself. Do not register it.
2. **C32** delete `validate/semantic_schema` entirely: grep `semantic_schema`
   (step likely in `steps/industry/semantic.py`); remove the step class +
   registration; keep any unrelated code in the file; update `__init__`
   imports; grep docs.
3. **C16** `util/json_path_extract` (`steps/utility/json_extract.py` line ~118)
   currently has `validation_alias=AliasChoices("source", "variable")`. The
   canonical name is `input` (ADR-0025 renamed `util/validate_path` already —
   verify). Rename the field to `input` with NO aliases (`source` and
   `variable` both die), update callers/tests/examples.
4. **C40** restrict universal output fallbacks —
   `steps/_checks/extraction.py`:
   - `request`/`response` stay on every `StepOutput` and stay visible in
     logs/trace (do not touch logging).
   - But `${{ execution.<step>.<name> }}` resolution must only resolve names
     the step's declared `output_model` actually has. The blanket fallthrough
     lives in `_fallback_resolution()` (tries `output.response` attrs →
     `response.body` dict keys → `StepOutput` slots for ANY name) and the
     `response_body`/`response_headers` aliases in `_resolve_first_segment()`.
   - Implementation: thread the resolving step's `output_model` (or its
     `model_fields` name-set) into `extract_path` from the call site (find
     callers: grep `extract_path(` — resolver lives around
     `player/execution/_helpers.py` / `authoring` expression resolution).
     When the first segment is NOT in the declared field set (and not a key
     of a dict `value`), return `None` instead of falling through to
     response internals. Delete `_fallback_resolution` if nothing legitimate
     remains, or gate it on the declared-field check.
   - Fix tests that relied on blanket fallbacks (`status_code`, `body`,
     `duration_ms`, `response_body` references in tests) to use
     declared outputs. `validate/assert`-family steps that deliberately read
     `input:` values are unaffected (they receive values, not paths into
     other steps).

Test: `poetry run pytest tests -k "flow or condition or extract or validate" -q`,
then the full suite briefly — C40 has wide blast radius.

### E8 — Typed execution events (C46)

⚠️ The repo owner's uncommitted WIP (`models/runtime/events.py`,
`player/execution/monitor.py`, `_trace_formatter.py`, `_run_phase.py`,
`player.py`, `models/primitives/enums.py`) appears to BE the start of this
work. READ those diffs first (`git diff` + the untracked events.py). Build on
them; do not start parallel.

Target design (per decision C46): an event manager every execution component
publishes typed lifecycle events through, with an explicit `kind` field, so
no client ever has to string-sniff `step_type`.

- Event kinds (minimum): `job_started`, `job_completed`, `job_failed`,
  `job_cancelled`, `step_started`, `step_completed`, `step_failed`,
  `step_skipped`, `assertion_result`.
- Payloads reuse `StepStatus` / `StepResult` from
  `models/primitives/enums.py` / `models/runtime/results.py`; each step event
  carries `step_id`, `uses`, `status`, and a short error/output summary.
  `assertion_result` additionally carries pass/fail + message, so no client
  has to infer an assertion failure from `step_type`.
- Wire through the existing SSE stack: `server/streaming/routes.py`,
  `lifecycle.py`, `_event_buffer.py` (ordering/ids come from `EventBuffer`,
  not wall-clock), `formatter.py` (keep `TERMINAL_EVENTS` names
  `job.completed`/`job.failed`/`job.cancelled` on the wire).
- Write `docs/developer/execution-events.md`: every kind, payload shape, one
  example JSON each. This document is the contract the server's SSE clients
  implement against — it must be complete.

Test: `poetry run pytest tests -k "stream or sse or event or monitor" -q`.

### E9 — extra="forbid" + full-suite gate + docs regen (C47)

MUST run last.

1. `steps/base.py` (where `StepParams`' `ConfigDict` lives — it may be in
   `steps/base.py` or `_contracts.py`; grep `extra="allow"` under `steps/`):
   flip StepParams to `extra="forbid"`. Unknown `with:` keys are now
   validation errors surfaced at compile/run.
2. Run the FULL suite: `poetry run pytest -q`. Every failure is a stale
   spelling somewhere — fix the caller, never loosen back to `allow`.
   Also flip/keep `DescriptorPayload`-style *output* payloads on
   `extra="allow"` — the forbid applies to `StepParams` (inputs) only;
   AAS/DCAT documents legitimately carry unknown keys.
3. Regenerate the step reference page (fixes the E1 known-debt test):
   the generator is `cli/docs.py` — run
   `poetry run python -m tractusx_testlab docs` (check `cli/docs.py` for the
   exact subcommand/output path; the committed page is
   `docs/api-reference/steps.md`).

---

## FINAL VERIFICATION

1. Engine: `poetry run pytest -q` → all green.
2. Commit messages: one commit per cluster (`E2`…`E9`), message naming the
   conflict ids covered. Do not push or open PRs without the owner's say-so.
