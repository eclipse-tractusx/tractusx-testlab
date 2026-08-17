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

Executable handoff plan for the IDE ↔ engine contract harmonization. The
decisions being implemented are in
[contract-conflict-decisions.md](contract-conflict-decisions.md) (every
conflict C01–C47 now has exactly one ticked box; margin notes beside a ticked
box override it — notably C04's note supersedes C27's step id). The analysis
behind them is [ide-engine-contract-parity.md](ide-engine-contract-parity.md).

**Repos:**

- Engine: `tractusx-testlab` (this repo). Python 3.12, pydantic v2, pytest.
  Test: `poetry run pytest -q` (narrow with a path or `-k`).
- IDE: `cx-test-suite` at `/Users/matbmoser/catenax-eV/cx-test-suite`
  (github `catenax-eV/cx-test-suite`, branch `feat/ai`). TypeScript, Blockly,
  vitest. Test: `npx vitest run <path>`; full: `npm test`.
- Parity ground truth:
  `poetry run python tools/compare_ide_parity.py --ide /Users/matbmoser/catenax-eV/cx-test-suite`
  — run from the engine repo. Baseline before this migration: **62 breaking
  divergences across 33 IDE blocks**. Acceptance: **0**, both test suites green.

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

## ENGINE TRACK (tractusx-testlab)

### E1 — Internal aliases ✅ DONE (commit `3be95d1`)

Already implemented; recorded here for context:

- C20/C21: `CounterPartyParams` (`steps/_contracts.py`) lost the
  `provider_url`/`bpnl` `AliasChoices` — only `counter_party_address` /
  `counter_party_id` validate now.
- C22: `FilterExpression` input accepts only `operand_left`/`operand_right`;
  `operandLeft`/`operandRight` remain **serialization-only**
  (`serialization_alias`), used by `to_sdk()`.
- C25: `validate/schema` (`steps/utility/validate.py`) — field `json_schema`
  now has `validation_alias="schema"` only; scripts write `schema:`, the
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
   `docs/examples/**` and `stubs/**` scripts.

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
   SDK's name — only the script-facing param renames.
2. **C14** `create_contract_definition` (`provision.py`): param
   `contract_id` → `contract_definition_id`; output field `contract_def_id` →
   `contract_definition_id`. One name both directions.
3. **C23** same step: field `usage_policy_id` → `contract_policy_id` (the IDE
   already sends `contract_policy_id`; the on-record recommendation was
   overridden). The value still lands in the EDC `contractPolicyId` API field.
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
   The IDE's `returns:` then reads `catalog` and `datasets` — never
   `dcat:dataset`.
6. **C36** `pull_data_filtered` (`pull_data/_executor.py` + its step wrapper in
   `pull_data/__init__.py` or `consume.py` — locate with grep
   `pull_data_filtered`): add `agreement_id` to its output/exports, sourced
   the same way its `_by_policy` sibling publishes it.

Update callers/tests: grep `contract_id`, `contract_def_id`,
`usage_policy_id`, `"policies"` (script-facing), plus e2e/docs/stubs.

Test: `poetry run pytest tests -k "provision or contract or pull_data or catalog" -q`.

### E4 — DTR (C37 + new C04/C27 lookup step)

File: `steps/industry/dtr.py` (~230 lines; read fully first — its shared
`DtrParams`/`DescriptorPayload` pattern is the style to follow).

1. **C37** `DescriptorPayload.id_short`: change
   `alias="idShort"` → `validation_alias="idShort"` so the AAS API's camelCase
   is accepted on input but the field ALWAYS serializes as `id_short`.
   Verify with a quick check that step output rendering (`.of(body)` →
   `bind_output`) dumps `id_short`. C03/C05/C15 are already correct on the
   engine side (ids `digital-twin/provider/create_shell_descriptor`,
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
  (param `policy`), `digital-twin/provider/create_shell_descriptor`
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
  - `digital-twin/provider/wizard/create_shell_descriptor` — fields
    `id` (opt, generate UUID urn if absent), `id_short`, `global_asset_id`
    (opt), `specific_asset_ids` (opt list), `submodel_descriptors` (opt list)
    → assembles a ShellDescriptor.
  - `digital-twin/provider/wizard/create_submodel_descriptor` — fields
    `aas_identifier`, `id` (opt), `id_short`, `semantic_id`, `endpoint_url`
    → assembles a SubModelDescriptor (semantic_id becomes the AAS
    `semanticId` reference structure; endpoint_url becomes the single
    SUBMODEL-3.0 endpoint entry — mirror what the IDE's old
    `add_submodel.json` flat fields meant; see the parity report section B).
  Field names above deliberately match the IDE's existing flat block fields
  (parity section B: `name`, `description`, `base_url`, `content_type`,
  `properties`; `permissions`, `prohibitions`, `obligations`; `id_short`,
  `global_asset_id`, `specific_asset_ids`, `submodel_descriptors`;
  `id_short`, `semantic_id`, `endpoint_url`) so the IDE blocks re-target with
  a rename only.

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
   - `flow/condition` is NOT an engine step — it's an IDE composer block that
     assembles the `condition` string (same as
     `connector/consumer/filter_expression`). Do not register it.
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
     `player/execution/_helpers.py` / `scripting` expression resolution).
     When the first segment is NOT in the declared field set (and not a key
     of a dict `value`), return `None` instead of falling through to
     response internals. Delete `_fallback_resolution` if nothing legitimate
     remains, or gate it on the declared-field check.
   - Fix tests that relied on blanket fallbacks (`status_code`, `body`,
     `duration_ms`, `response_body` references in test scripts) to use
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
the IDE never string-sniffs `step_type` again.

- Event kinds (minimum): `job_started`, `job_completed`, `job_failed`,
  `job_cancelled`, `step_started`, `step_completed`, `step_failed`,
  `step_skipped`, `assertion_result`.
- Payloads reuse `StepStatus` / `StepResult` from
  `models/primitives/enums.py` / `models/runtime/results.py`; each step event
  carries `step_id`, `uses`, `status`, and a short error/output summary.
  `assertion_result` additionally carries pass/fail + message (this is what
  replaces the IDE's `step_type.includes("assert")` hack).
- Wire through the existing SSE stack: `server/streaming/routes.py`,
  `lifecycle.py`, `_event_buffer.py` (ordering/ids come from `EventBuffer`,
  not wall-clock), `formatter.py` (keep `TERMINAL_EVENTS` names
  `job.completed`/`job.failed`/`job.cancelled` on the wire).
- Write `docs/developer/execution-events.md`: every kind, payload shape, one
  example JSON each. This document is the contract the IDE track (I6)
  implements against — it must be complete.

Test: `poetry run pytest tests -k "stream or sse or event or monitor" -q`.

### E9 — extra="forbid" + full-suite gate + docs regen (C47)

MUST run last on the engine side.

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
   `docs/specification/reference/steps.md`).
4. Update `docs/developer/ide-engine-contract-parity.md` to describe the
   post-migration contract (final names), keeping the reproduce instructions.
5. Run the parity checker; capture output in the commit message. Engine-side
   acceptance: categories B–G empty except entries that require the IDE-side
   work (sections A and B referencing IDE-only spellings disappear only after
   the IDE track).

---

## IDE TRACK (cx-test-suite)

Block catalog = source of truth artifacts: `public/blocks/**/*.json` +
`public/blocks/index.json`, loaded by
`src/features/ide/features/block-editor/blocks/common/catalog/catalogLoader.ts`,
registered generically by `…/registration/steps/catalogBlocks.ts`.
Serialization (blocks → YAML):
`…/serialization/serialize/writer/blockToStepSerializer.ts` (+
`ifBlockSerializer.ts`, tests beside them).

### I1 — Connector blocks (C01, C02, C09, C10, C13, C14, C19, C23, C28, C29, C33, C34, C36)

Files: `public/blocks/connector/**/*.json`, `public/blocks/index.json`,
`…/catalog/stepAliases.ts`, `…/common/stepIdGenerator.ts` (check for
hardcoded ids).

- C01/C02: ensure `negotiate.json` `uses` = `connector/consumer/negotiate`,
  `initiate_transfer.json` `uses` = `connector/consumer/initiate_transfer`
  (files already named right; the `uses` VALUE inside is what the parity
  checker failed on — it previously pointed nowhere).
- C09: delete `stepAliases.ts` and every import/call (document importer).
  Old documents using `flow/log`, `util/wait`, `http/call_dataplane`, bare
  `base64`/`parse_kv` stop resolving — intended.
- C10: `negotiate.json` param `asset_id` (delete `offer_id` field — C11
  decided ODRL-policy negotiation; the block feeds `policy` from a catalog
  output instead). Rename any `catalog_target` output reference to
  `catalog_asset_id`.
- C13: `pull_data_filtered_by_policy.json` param stays `expected_policies`
  (engine renamed to match — verify the block, no change expected).
- C14/C23: `create_contract_def.json`: `contract_def_id` →
  `contract_definition_id` (input + declared output); `contract_policy_id`
  stays (engine renamed to match).
- C19: blocks already write `filters` — verify all four
  (query_catalog_with_filters, both pull_data shortcuts, filter_expression
  composer) and remove any `filter_expression` spelling.
- C28: `initiate_transfer.json` keeps `transfer_type` dropdown
  (HttpData-PULL default / HttpData-PUSH / AmazonS3-PUSH) + add
  `data_destination` (JSON field, only meaningful for PUSH).
  Delete `agreement_id`/`asset_id` params from the block — the engine step
  takes `negotiation_id` (verify the block offers `negotiation_id`).
- C29: `create_contract_def.json` gains `asset_selector` — an array of
  criteria entries; reuse the filter-expression structural block pattern
  (`…/registration/structure/filterExpressionBlock.ts`) for the repeatable
  `operand_left/operator/operand_right` rows.
- C33/C34/C36 declared outputs: `negotiate.json` → `negotiation_id`,
  `agreement_id`, `state`; `initiate_transfer.json` → `data_address`,
  `edr_token`, `state` (NO `dataplane_endpoint`); `pull_data_filtered.json`
  → add `agreement_id`.

Test: `npx vitest run src/features/ide/features/block-editor/blocks/common/catalog`.

### I2 — DTR blocks (C03, C05, C15, C37, C04/C27 split)

Files: `public/blocks/digital-twin-registry/*.json` → move/rename;
`public/blocks/index.json`.

- C03: `register_shell.json` → `public/blocks/digital-twin/provider/create_shell_descriptor.json`,
  `uses: digital-twin/provider/create_shell_descriptor`. NOTE C26: its flat
  fields (`id_short`, `global_asset_id`, `specific_asset_ids`,
  `submodel_descriptors`) now match the engine's
  `digital-twin/provider/wizard/create_shell_descriptor` — decide per block:
  the flat-field block targets the WIZARD id; add a separate raw-JSON block
  for the plain id (JSON editor modal pattern, see
  `…/blocks/json/`). Same logic for C05.
- C05: `add_submodel.json` → `digital-twin/provider/wizard/create_submodel_descriptor`
  (flat fields incl. `aas_identifier` — C15 rename from `shell_id`), plus a
  raw `create_submodel_descriptor` block (params `aas_identifier`,
  `submodel_descriptor`).
- C37: every DTR block's declared outputs use `id` + `id_short`
  (rename `shell_id`/`submodel_id`/`idShort` spellings).
- C04/C27: replace `lookup_shell.json` with TWO blocks:
  1. `digital-twin/provider/get_shell_descriptor.json` — param
     `aas_identifier`; outputs `id`, `id_short` (+ document passthrough).
  2. `digital-twin-registry/consumer/dataplane/lookup_shell.json` — uses id
     EXACTLY that 4-segment string; params `specific_asset_ids` (array),
     `dataplane_url`, `edr_token` — copy the class-typed input pattern from
     `public/blocks/connector/dataplane/http_call_dataplane.json` (its
     `dataplane_url`/`edr_token` fields accept matching prior outputs);
     outputs `shell_ids`, `shell_descriptors`.
- Update `index.json` for all adds/removes/moves.

Test: `npx vitest run -t dtr` plus catalog tests.

### I3 — Wizard blocks, mock/http fields, flow/if wiring (C26, C17, C30, C31, C38, C39, C06)

- C26: add `public/blocks/connector/provider/wizard/create_asset.json` and
  `wizard/create_policy.json` matching the engine wizard field lists (E5).
  The EXISTING `create_asset.json`/`create_policy.json` flat-field blocks:
  re-point their flat fields to the wizard ids OR convert them to raw-JSON
  payload blocks (`asset`/`policy` single JSON field via the JSON editor
  modal) — end state: one block per engine step, names aligned with E5.
- C30: `http/http_call.json` gains `query_params` (key/value rows or JSON
  object field).
- C31: `mock/mock_endpoint.json` gains `response_headers`.
- C38: `mock_endpoint.json` outputs → `endpoint_id`, `base_mock_url`,
  `full_mock_url` (replace `mock` bare-string output; the whole-instance
  output is what C17's wait block consumes — declare the step output class so
  the wait block's `mock` input can accept it).
- C17: `wait/wait_for_call.json` `mock` input becomes class-typed, accepting
  the mock/api output instance (dropdown-of-prior-outputs pattern —
  `…/common/fields/dropdownProviders.ts` / `typedInputs.ts`).
- C39: `wait_for_call.json` outputs: `request_method`, `request_path`,
  `request_headers`, `request_body`, `request_query_params`, `elapsed_ms`.
- C06: engine now has `flow/if` — align `public/blocks/flow/if.json` params
  (`condition`, `then`, `else`) and outputs (`branch_taken`,
  `condition_result`); verify `ifBlockSerializer.ts` emits nested step lists
  under `then:`/`else:`; `flow/condition.json` stays a structural composer
  (no standalone `uses` execution) feeding the condition string. Remove any
  "engine doesn't have it" special-casing (grep `flow/if` in
  `monacoSetup.ts`, `complianceRules.ts`).

Tests: `npx vitest run src/features/ide/features/block-editor` (serialization
+ catalog suites).

### I4 — SSE typed events (C46)

BLOCKED until E8's `docs/developer/execution-events.md` exists in the engine
repo — read it first; do not guess shapes.

Files (all currently string-sniff `step_type` / hardcode `ASSERTION_FAILED`):
`src/features/ide/store/execution/sseStream.ts`,
`src/features/tck-executions/models/sse.ts`,
`src/features/tck-executions/adapters/parseSse.ts`,
`src/features/tck-executions/views/execution/liveTrace.ts`,
`src/features/tck-executions/services/tckExecutionsService.ts`,
`src/features/tck-executions/services/realTckExecutionsService.ts`,
fixtures `src/features/tck-executions/data/fixtures/*`.

- `models/sse.ts`: discriminated union on `kind`, one member per engine event
  kind, shapes copied exactly from execution-events.md.
- `parseSse.ts` / `sseStream.ts` / `liveTrace.ts` / services: switch on
  `kind`; `ASSERTION_FAILED` display state comes from the `assertion_result`
  event, not from `step_type.includes("assert")`.
- Update fixtures (`extraTraceSpecs.ts`, `sseFromSpec.test.ts`) to emit the
  new event shapes.
- Behavior-preserving: same UI outcomes for the same underlying happenings.

Test: `npx vitest run src/features/tck-executions`.

### I5 — Ownership & sync cleanup (C41–C45)

- C41: IDE catalog stays source of truth — a standing constraint, no code.
- C42: delete `…/catalog/runtimeStepRegistry.ts` + all imports; the loaded
  catalog is the only registry the IDE consults.
- C43: delete `STEP_PARITY.md` (repo root).
- C45: `src/features/ide/features/yaml-editor/monacoSetup.ts` and
  `src/features/ide/services/validation/complianceRules.ts`: replace
  hardcoded step-id lists with derivations from the loaded catalog
  (`catalogLoader.ts` exports). New steps must never require a hand-edit
  there again.
- C44: `…/serialize/writer/blockToStepSerializer.ts` (+
  `utilityStepSerializers.ts` if still present — search first): replace
  per-step special cases with a generic walk over the block's catalog entry
  (declared `with:` fields → params, declared `returns:` → outputs).
  Composer/structural blocks legitimately keep custom code: filter/condition
  expressions, flow/if nested lists, JSON payload modal blocks, wizard forms.
  HIGHEST-RISK cluster — run the entire serialization test suite, not a
  slice.

After: repo-wide grep `runtimeStepRegistry|STEP_PARITY` must be empty.

Test: `npx vitest run src/features/ide` then `npm test`.

### I6 — Docs regen

- Regenerate/update `AVAILABLE_STEPS.md` from the final catalog (check
  `package.json` scripts for a generator; if hand-maintained, update the
  step tables to the final ids/params/outputs — cross-check against
  `public/blocks/index.json`).
- `CHANGELOG.md` entry for the contract migration.

---

## FINAL VERIFICATION (both repos)

1. Engine: `poetry run pytest -q` → all green.
2. IDE: `npm test` → all green.
3. Parity: `poetry run python tools/compare_ide_parity.py --ide <cx-test-suite>`
   → **0 divergences**. Every remaining line is a bug in this migration;
   fix it, don't rationalize it.
4. The parity checker itself may need updating where decisions changed the
   rules of the game (e.g. it must know `flow/condition` and
   `connector/consumer/filter_expression` are composer blocks, and that
   `digital-twin-registry/consumer/dataplane/lookup_shell` is a real engine
   step) — read `tools/compare_ide_parity.py` (353 lines) and adjust its
   expectations to the new contract if it hard-codes old ones.
5. Commit messages: one commit per cluster (`E2`…`I6`), message naming the
   conflict ids covered. Do not push or open PRs without the owner's say-so.
