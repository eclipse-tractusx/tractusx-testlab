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

<!-- It was reviewed and validated by a human committer. -->

  

# Contract conflict decision sheet

  

Tick exactly **one box per conflict**. `(on record)` marks the recommendation

made in the contract analysis that preceded this sheet;

conflicts marked **OPEN** have no recorded recommendation yet. Conflict numbers are stable identifiers referenced from other documents, so gaps in the sequence are intentional.

  

Once filled in, this sheet drives the migration commits — every unticked or

double-ticked conflict blocks the work.

  

---

  

## 1. Step ids (the `uses:` string)

  

### C01 — Negotiate

- [ ] `connector/consumer/negotiate_contract` — current engine name stays *(on record)*

- [x] `connector/consumer/negotiate` — engine renames

  

### C02 — Transfer

- [ ] `connector/consumer/transfer_data` — current engine name stays *(on record)*

- [x] `connector/consumer/initiate_transfer` — engine renames

  

### C03 — Create shell

- [x] `digital-twin-registry/provider/create_shell_descriptor` — current engine name stays *(on record)*

- [ ] `digital-twin-registry/register_shell` — engine renames

  

### C04 — Get shell (see also C27 — a lookup is semantically a search)

- [x] `digital-twin-registry/provider/get_shell_descriptor` — current engine name stays *(on record)*

- [ ] `digital-twin-registry/lookup_shell` — engine renames

  digital-twin-registry/lookup_shell -> digital-twin-registry/consumer/dataplane/lookup_shell

### C05 — Create submodel descriptor

- [x] `digital-twin-registry/provider/create_submodel_descriptor` — current engine name stays *(on record)*

- [ ] `digital-twin-registry/add_submodel` — engine renames

  

### C06 — Conditional branching — **OPEN**

Tests have no way to branch on a condition: no `flow/if` step (with a `flow/condition` composer for its condition) exists in the engine.

- [x] Implement `flow/if` (and condition composer) in the engine

- [ ] Leave conditional branching out until there is a concrete need

  

### C07 — HTTP step stutter — **OPEN**

- [ ] Rename to `http/request`

- [x] Keep `http/http_request`

  

### C08 — Mock module inconsistency — **OPEN**

`mock/wait/http_request` carries a module; `mock/api`, `mock/discovery`, `mock/dtr` do not.

- [ ] All four carry a module (e.g. `mock/api/…`, `mock/registry/dtr`, …)

- [ ] None carries a module (`mock/wait_http_request` or similar flattening)

- [x] Keep as-is (accept the inconsistency, document it)

  

---

  

## 2. Parameter names (same value, two spellings)

  

### C10 — negotiate_contract: the asset being negotiated

- [x] `asset_id` — engine renames `target`; export `catalog_target` → `catalog_asset_id` *(on record)*

- [ ] `target` — current engine spelling stays

  

### C11 — negotiate_contract: policy vs offer id (semantic, not spelling)

- [x] `policy` (ODRL document) — engine wins; fed from a catalog output *(on record)*

- [ ] `offer_id` (string) — engine gains offer-id-based negotiation

  

### C12 — transfer_data: which id starts the transfer

- [x] `negotiation_id` — engine wins; the step polls a negotiation *(on record)*

- [ ] `agreement_id` — engine reworked to accept an agreement id

  

**Resolved 2026-08-11, refactored.** `transfer_data` never issued a

`POST /v2/transferprocesses` — it polls for an EDR already produced once the

negotiation finalized, keyed by `negotiation_id`. Its body was: resolve

`negotiation_id` → `transfer_id`, then call `consumer.get_edr(transfer_id=...)`

— exactly what `connector/consumer/get_edr` does on its own. The duplicate

fetch/error-handling logic is now one function,

[`fetch_data_address`](../../src/tractusx_testlab/steps/connector/dataplane.py),

used by both steps: `get_edr` calls it directly; `transfer_data` resolves

`negotiation_id → transfer_id` and then delegates to it. `GetEdrParams` gained

`verify` for parity with `transfer_data`, and `get_edr`'s token extraction now

goes through `data_address_token()` so it picks up the `authCode` legacy

spelling the same way `transfer_data` already did.

  

### C13 — pull_data_filtered_by_policy

- [ ] `policies` — current engine spelling stays *(on record)*

- [x] `expected_policies` — engine renames -> use always expected_policies as key in consumer methods that filter by policy

  

### C14 — create_contract_definition id (engine disagrees with itself: takes `contract_id`, returns `contract_def_id`)

- [x] `contract_definition_id` — both sides change *(on record)*

- [ ] `contract_id` everywhere

- [ ] `contract_def_id` everywhere

  

### C15 — create_submodel_descriptor: the shell path parameter

- [x] `aas_identifier` — engine/AAS-spec name stays *(on record)*

- [ ] `shell_id` — engine renames

  

### C16 — util/validate_path & util/json_path_extract: the value being read

- [x] `input` — engine renames `source` (ADR-0025) *(on record)*

- [ ] `source` — current engine spelling stays

  

### C17 — mock/wait/http_request: which endpoint to wait on

- [ ] `endpoint_id` — current engine name stays *(on record)*

- [x] `mock` — engine renames and receives an instance of the mock step with all infos needed to manage it in runtime

  

### C18 — connector/dataplane/http_request: endpoint + token params

- [x] `dataplane_url` + `edr_token` — params take the name of the export that feeds them *(on record)*

- [ ] `endpoint` + `token` — current engine spelling stays

  

### C19 — the filter parameter — **OPEN** (doc and canonical examples disagree)

The contract analysis chose `filter_expression`; the canonical examples write `filters:`.

- [ ] `filter_expression` — migrate the examples

- [x] `filters` — flip the doc; engine renames the field, alias dies anyway

  

---

  

## 3. Engine-internal aliases (second spelling dies with the migration)

  

### C20 — counter-party address

- [x] `counter_party_address` stays; `provider_url` dies *(on record)*

- [ ] `provider_url` stays; `counter_party_address` dies

  

### C21 — counter-party id

- [x] `counter_party_id` stays; `bpnl` dies *(on record)*

- [ ] `bpnl` stays; `counter_party_id` dies

  

### C22 — filter operands

- [x] `operand_left` / `operand_right` on input; camelCase remains serialization-only *(on record)*

- [ ] Accept camelCase on input too (keeps the alias — violates the rule)

  

### C23 — contract-definition policy field

- [ ] `usage_policy_id` stays; `contract_policy_id` dies *(on record)*

- [x] `contract_policy_id` stays; `usage_policy_id` dies; engine renames

  

### C24 — notification/consumer/send fields

- [x] `dataplane_url`, `edr_token`, `content` stay; `endpoint_url`, `auth_token`, `payload` die *(on record)*

- [ ] The other spellings win

  

### C25 — validate/schema: the schema parameter

- [x] `schema` stays; `json_schema` dies *(on record)*

- [ ] `json_schema` stays; `schema` dies

  

---

  

## 4. Shape conflicts

  

### C26 — create_asset / create_policy / create_shell_descriptor / create_submodel_descriptor

- [ ] One document parameter (`asset`, `policy`, `shell_descriptor`, `submodel_descriptor`); assembling the document is left to the test author *(on record)*

- [ ] Flat fields; engine assembles the document internally

- [ ] Both accepted (dual shape — violates the rule)
- [x] -> We can offer the two options via parameters but like connector/provider/wizard/create_asset for example and connector/provider/create_asset receives directly the json payload
  

### C27 — DTR lookup semantics (get-one vs search)

- [x] Two steps: keep `get_shell_descriptor(aas_identifier)`, add `digital-twin-registry/provider/query_shell_descriptors(specific_asset_ids)` *(on record)*

- [ ] One step with either parameter (dual shape — violates the rule)

- [ ] Search only; drop get-by-identifier from the catalog

**Naming superseded by the C04 note.** The search step is not a local-registry
read like `get_shell_descriptor` — it reaches a counterparty's registry
through an EDC dataplane (`dataplane_url` + `edr_token`, same convention as
C18), so it doesn't belong under `digital-twin-registry/provider/*` (which calls the
locally-seeded `AasService` directly, no dataplane params at all). Final id
is the one from the C04 note, kept literal as an intentional 4-segment
exception to the category/module/function convention:
`digital-twin-registry/consumer/dataplane/lookup_shell`, params
`specific_asset_ids` + `dataplane_url` + `edr_token`.

  

---

  

## 5. Capability conflicts (implement or delete)

  

### C28 — `transfer_type` (`HttpData-PUSH`, `AmazonS3-PUSH`) on transfer — engine is PULL-only

- [ ] Leave out until the engine supports PUSH *(on record)*

- [x] Implement PUSH transfer types in the engine now

  

### C29 — `asset_selector` criteria array on create_contract_definition

- [x] Implement in the engine (EDC API takes it natively) *(on record)* -> the asset selector takes an array of filter criteria

- [ ] Leave out; single `asset_id` remains the only form

  

### C30 — `query_params` on http/http_request

- [x] Implement in the engine *(on record)*

- [ ] Leave out; query strings go in the URL

  

### C31 — `response_headers` on mock/api

- [x] Implement in the engine *(on record)*

- [ ] Leave out

  

### C32 — validate/semantic_schema (no test uses it, weaker than validate/schema)

- [x] Delete from the engine *(on record)*

- [ ] Keep it

  

---

  

## 6. Output conflicts (dead `returns:` today)

  

### C33 — negotiate_contract outputs

- [x] Engine adds `agreement_id` + `state` (polls the negotiation) *(on record)*

- [ ] Neither is added; `negotiation_id` is the only output

  

### C34 — transfer_data outputs

- [ ] Engine adds `state`, deletes `data_address` ("older spelling of `dataplane_endpoint`") *(on record)*

- [ ] Keep `data_address` too (two names for one value — violates the rule)
- [x] keep onlt data adress remove dataplane endpoimnt — and add `state` too (parity with C33's negotiate output)

  

### C35 — query_catalog output shape

- [x] Engine wraps: `catalog` (raw JSON-LD) + `datasets` — `returns:` never spells `dcat:dataset` *(on record)* -> ctalog is complete and dataset gets filtered

- [ ] Raw document stays the output; `returns:` reads `dcat:dataset` verbatim

  

### C36 — pull_data_filtered missing `agreement_id`

- [x] Engine adds it (its by-policy sibling already publishes it) *(on record)* -> found for retriving the edr

- [ ] Not added

  

### C37 — DTR step outputs

- [x] `id` + `id_short`; the `idShort` serialization alias dies; the `shell_id`/`shell_descriptor(s)`/`submodel_id` spellings die *(on record)*

- [ ] `shell_id`/`shell_descriptor(s)`/`submodel_id` win; engine renames

  

### C38 — mock/api output

- [ ] Structured: `endpoint_id`, `base_url`, `url` — replaces the bare string *(on record)*

- [ ] Bare string stays; read as `value`
- [x] mock class instance is returned (with all information about the mock), base mock ulr and full mock url are returned with the complete api from the engine (engine url + unique path generated for this mock)

  

### C39 — mock/wait/http_request outputs

- [ ] `method`, `path`, `headers`, `body`, `query_params`, `elapsed_ms` — no `request_` prefix, engine adds the last two *(on record)*

- [x] `request_*` spellings win; engine renames and adds

  

### C40 — universal extraction fallbacks — **OPEN**

`value`, `request`, `response`, `exports`, `status_code`, `headers`, `body`,

`duration_ms`, `response_body`, `response_headers` resolve on every step but are

declared in no output model.

- [ ] Formalize: fold into declared output models so the generated schema is complete

- [ ] Restrict: only declared outputs resolve; fallbacks removed
 
- [ ] Keep implicit (the generated schema for `returns:` stays incomplete)
- [x] Always when there is a request and response we should log it, incomming or outcommming, but onl outputs can be used when specified. The request and reponse may be important for debug, but not always going to be used by other steps. 
  

---

  

## 7. Execution contract

  

### C46 — SSE execution contract — **OPEN**

Execution events carry no explicit kind, so a client has to infer their meaning by string-sniffing (e.g. treating any `step_type` containing `assert` as an assertion failure); there is no shared event schema.

- [ ] Typed, versioned event schema; explicit `kind` field on events

- [ ] Keep heuristic parsing
- [x] Harmonize this to emmit events in an event manager, and be able to receive in formation from each step when execution or the state machine from their execution changes.

  

### C47 — `StepParams` extras

- [x] `extra="forbid"` — unknown `with:` keys become compile-time errors *(on record)* -> when compiling we need to give errors if the syntax of the step's inputs and outputs is not correct.

- [ ] Keep `extra="allow"` (unknown keys silently dropped)