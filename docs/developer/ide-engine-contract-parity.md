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
<!-- This document was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and validated by a human committer. -->

# IDE ↔ Engine Contract Parity — inputs and outputs

> Date: 2026-08-10 | Branch: `feat/run_security_consitency`
> Engine: this repository, step registry as registered by `tractusx_testlab.steps`
> IDE: `cx-test-suite`, block catalog under `public/blocks/`
> Reproduce: `poetry run python tools/compare_ide_parity.py --ide <cx-test-suite>`

## Why a name-level comparison is not enough

A `uses:` value is only a third of the contract. The IDE also writes a `with:`
mapping and a `returns:` block, and all three have to agree:

```yaml
- id: negotiate_it
  uses: connector/consumer/negotiate     # 1. the step name
  with:
    offer_id: ${{ execution.query.offer_id }}   # 2. the input keys
  returns:
    agreement_id: { type: string }              # 3. the output keys
```

Comparing only line 1 reports parity for a step whose every parameter the engine
throws away, because [`StepParams`](../../src/tractusx_testlab/steps/_contracts.py)
is `extra="allow"`: an unrecognised `with:` key raises nothing, it is simply not
bound to any field. The step then runs on its defaults. Likewise, a `returns:`
name the output cannot resolve is set to `None` rather than rejected — the
failure surfaces several steps later as an empty URL or a null ID.

So the interesting question is not "does the name exist" but "does the payload
survive". This document answers that one, key by key.

## How the comparison is done

Both sides are read from their real definitions, not from generated
documentation:

| Side | Read from | Why not the obvious source |
| --- | --- | --- |
| Engine | `model_fields` of each step's `params_model` / `output_model` / `exports_model` | The JSON Schema in `testlab docs --json` renders an `AliasChoices` field under one name only, so a parameter the engine *does* accept (`filters` → `filter_expression`) reads as missing. |
| IDE | Every `*.json` under `public/blocks/`, indexed or not | `index.json` omits structural blocks that are still reachable in the toolbox. |

Aliases are resolved, because the question being answered is "what does the
runtime do today". A `with:` key counts as accepted if any field's
`validation_alias` lists it; a `returns:` name counts as readable if it matches
an output field's serialisation alias, an export name, or one of the names
[`_checks/extraction.py`](../../src/tractusx_testlab/steps/_checks/extraction.py)
resolves for every step regardless of the declared output — `value`, `request`,
`response`, `exports`, `status_code`, `headers`, `body`, `duration_ms`,
`response_body`, `response_headers`.

Resolving an alias is not the same as approving it. A key that binds only
because a second spelling exists is reported as class **G** and counted as a
divergence like any other — see [the rule](#the-rule-one-name-one-shape). It is
the mildest class, because it fails no run today; it is still two names for one
field, and the whole point of this exercise is that there be one.

That last group matters: it is the reason `util/base64`'s `value` return and
`http/http_request`'s `response_body` return work despite not appearing in any
output model. A comparison that ignored it would report nine false breaks.

## Headline

| | Count |
| --- | ---: |
| IDE blocks in the catalog | 31 |
| Engine steps registered | 44 |
| `uses:` values that do not resolve (**A**) | 6 |
| IDE parameters the engine silently drops (**B**) | 29, across 13 steps |
| IDE returns the engine never produces (**C**) | 18, across 9 steps |
| Required in IDE, optional in engine — benign (**D**) | 14 steps |
| Engine parameters the IDE does not offer (**E**) | 20 steps |
| Engine steps with no IDE block (**F**) | 14 |

**15 of the 31 blocks are fully wired** — every parameter binds and every return
resolves: `connector/consumer/query_catalog_with_filters`,
`connector/dataplane/http_request`,
`flow/delay`, `flow/retry`, `util/log`, `util/base64`, `util/generate_bpn`,
`util/generate_uuid`, `util/json_path_extract`, `util/parse_kv`,
`mock/discovery`, `mock/dtr`, `validate/assert`, `validate/field`,
`validate/schema`. The other 16 lose part of their payload.

The failure severity ranks A > B > C:

- **A fails loudly.** The compiler rejects the script with
  `Unknown step type '<uses>'`
  ([`validator.py:99`](../../src/tractusx_testlab/compiler/validation/validator.py#L99)).
- **B fails silently and wrongly.** The step runs with defaults, so
  `connector/provider/create_asset` publishes an empty asset rather than the one
  the author drew.
- **C fails at a distance.** The variable is `None`, and the error shows up in
  whichever later step consumed it.

## A — `uses:` does not resolve

`StepRegistry.get` is exact-match, and no engine step registers an alias, so
these six names produce no step at all.

| IDE block | Emits `uses:` | Engine name |
| --- | --- | --- |
| Negotiate Contract | `connector/consumer/negotiate` | `connector/consumer/negotiate_contract` |
| Initiate Transfer | `connector/consumer/initiate_transfer` | `connector/consumer/transfer_data` |
| Register Shell | `digital-twin-registry/register_shell` | `digital-twin/provider/create_shell_descriptor` |
| Lookup Shell | `digital-twin-registry/lookup_shell` | `digital-twin/provider/get_shell_descriptor` |
| Add Submodel Descriptor | `digital-twin-registry/add_submodel` | `digital-twin/provider/create_submodel_descriptor` |
| Filter Expression | `connector/consumer/filter_expression` | *(none — structural)* |

`filter_expression` is not a break: it is a structural block
(`custom_registration: true`) that composes the `filters` parameter of other
steps and is never emitted as a step of its own.

`connector/consumer/pull_data_filtered_by_policy` **was** a seventh entry here.
Its registration had been dropped by an unresolved merge conflict in
[`steps/pull_data/__init__.py`](../../src/tractusx_testlab/steps/pull_data/__init__.py) —
the executor class existed and was imported, but `step(...)` was never called on
it. Restored as part of this analysis; the engine now registers 44 steps.

## B — IDE parameters the engine drops

Every one of these is accepted by the YAML, ignored by the step, and produces no
diagnostic. `*` marks a parameter the IDE declares **required** — the author
cannot avoid sending it.

### Same capability, different shape

The engine models these as one document parameter; the IDE models them as the
individual fields of that document. Neither side is wrong, but nothing bridges
them.

| Step | IDE sends | Engine wants |
| --- | --- | --- |
| `connector/provider/create_asset` | `name*`, `description`, `base_url*`, `content_type`, `properties` | `asset` — one dict carrying `base_url`, `dct_type`/`properties`, `version`, `semantic_id`, `proxy_params`, `headers`, `private_properties` |
| `connector/provider/create_policy` | `permissions*`, `prohibitions`, `obligations` | `policy` — one ODRL dict carrying exactly those three keys |
| `digital-twin-registry/register_shell` | `id_short*`, `global_asset_id`, `specific_asset_ids`, `submodel_descriptors` | `shell_descriptor` — the whole AAS descriptor |
| `digital-twin-registry/add_submodel` | `id_short*`, `semantic_id*`, `endpoint_url*` | `submodel_descriptor` — the whole submodel descriptor |

The engine's design intent is visible in the field descriptions: `asset` and
`policy` are meant to come from a manifest variable
(`${{ env.<id>.asset }}`). The IDE instead offers a form. Bridging them means
the engine accepting the flat fields and assembling the document when the
document parameter is absent.

### Same field, different name

| Step | IDE sends | Engine field | Note |
| --- | --- | --- | --- |
| `connector/consumer/negotiate` | `asset_id*` | `target` | Same value. |
| `connector/consumer/negotiate` | `offer_id*` | `policy` | **Not** the same value — the engine wants the ODRL policy document, the IDE sends an offer ID. |
| `connector/consumer/initiate_transfer` | `agreement_id*` | `negotiation_id` | Different identifiers; the engine polls a negotiation for its EDR. |
| `connector/consumer/pull_data_filtered_by_policy` | `expected_policies*` | `policies` | Same value, same shape — the engine already coerces a bare object to a one-element list. Pure name drift; one spelling has to go. |
| `digital-twin-registry/lookup_shell` | `asset_ids*` | `aas_identifier` | Different lookup: the IDE searches by specific asset IDs, the engine fetches one descriptor by identifier. A genuine capability gap. |
| `digital-twin-registry/add_submodel` | `shell_id*` | `aas_identifier` | Same value. |
| `util/validate_path` | `input*` | `source` | Same value. |
| `mock/wait/http_request` | `mock*` | `endpoint_id` | Same value — the engine already accepts a URL, an ID, or a path. |

### Capability the engine does not have

| Step | IDE sends | Status |
| --- | --- | --- |
| `connector/consumer/initiate_transfer` | `transfer_type` (`HttpData-PULL` / `HttpData-PUSH` / `AmazonS3-PUSH`) | Engine is PULL-only. |
| `connector/provider/create_contract_definition` | `asset_selector*` (array of criteria) | Engine takes a single `asset_id`. |
| `connector/provider/create_contract_definition` | `contract_def_id` | Engine takes `contract_id` — and hands the same value back as `contract_def_id` on its output. The two spellings are the engine's own, not the IDE's. |
| `http/http_request` | `query_params` | No equivalent; must be folded into the URL. |
| `mock/api` | `response_headers` | Engine's mock returns status and body only. |

## C — IDE returns the engine never produces

Each of these resolves to `None` at runtime and is written into the context
under that name, so the failure appears wherever the value is consumed.

| Step | Dead returns | Engine actually exposes |
| --- | --- | --- |
| `connector/consumer/negotiate` | `agreement_id`, `state` | `negotiation_id` only |
| `connector/consumer/initiate_transfer` | `state` | `edr_entry`, `edr_token`, `data_address`, `data_address_raw`, `dataplane_endpoint`, `transfer_id` |
| `connector/consumer/query_catalog` | `catalog` | the catalog document itself — `@context`, `@id`, `@type`, `dcat:dataset` |
| `connector/consumer/pull_data_filtered` | `agreement_id` | `endpoint`, `token_prefix`, `dataplane_endpoint`, `edr_token`, `dataplane_url`, `asset_id`, `negotiation_id`, `transfer_process_id` |
| `digital-twin-registry/register_shell` | `shell_id`, `shell_descriptor` | `id`, `idShort` |
| `digital-twin-registry/lookup_shell` | `shell_ids`, `shell_descriptors` | `id`, `idShort` |
| `digital-twin-registry/add_submodel` | `submodel_id` | `id`, `idShort` |
| `mock/api` | `mock`, `base_mock_url`, `full_mock_url` | a bare string — the callback URL, readable as `value` |
| `mock/wait/http_request` | `request_method`, `request_headers`, `request_body`, `query_params`, `elapsed_ms` | `method`, `path`, `headers`, `body` |

Two patterns dominate. The DTR trio is a **naming** problem: the engine returns
the registry's own `id`/`idShort` and the IDE asks for a domain name. `mock/api`
and `mock/wait/http_request` are **shape** problems: the engine returns less than
the IDE offers to read.

Note `connector/consumer/query_catalog`: the engine's output *is* the catalog, so a `returns:`
block asking for `catalog` gets nothing while `dcat:dataset` would work.

## D — required in the IDE, optional in the engine

Benign in every case and listed for completeness. The engine makes these
optional because each falls back to a context variable published by an earlier
step (`counter_party_address` ← `provider_url`, `target` ← `catalog_target`) or
to a default. The IDE marking them required only means the author cannot leave
the field blank — the resulting YAML is still valid.

Affected: `connector/consumer/negotiate`,
`connector/consumer/query_catalog`,
`connector/consumer/query_catalog_with_filters`,
`connector/consumer/pull_data_filtered`,
`connector/consumer/pull_data_filtered_by_policy`,
`connector/dataplane/http_request`,
`connector/provider/create_contract_definition`, `flow/delay`, `util/log`,
`http/http_request`, `mock/api`, `validate/assert`, `validate/field`,
`validate/schema`.

## E — engine parameters the IDE does not offer

Not breaks — capability the IDE cannot reach. The recurring ones are worth
noting because they are cross-cutting rather than per-step:

| Parameter | On | Effect of its absence |
| --- | --- | --- |
| `store_in_variable` | `util/base64`, `util/json_path_extract`, `util/parse_kv`, `util/validate_path` | The IDE relies on `returns:` alone. Harmless duplication of mechanism. |
| `timeout` | `http/http_request`, `connector/dataplane/http_request` | No per-request timeout override. |
| `verify` | `connector/consumer/transfer_data` | No TLS-verification override. |
| `prefix` | `util/generate_uuid` | No prefixed UUIDs. |

## F — engine steps with no IDE block

Fourteen registered steps cannot be authored in the IDE. Hand-written YAML using
them still runs, so this is a toolbox gap rather than a defect.

`connector/consumer/do_dsp`, `connector/consumer/do_dsp_with_bpnl`,
`connector/consumer/extract_dataset`, `connector/consumer/get_edr`,
`connector/consumer/query_catalog_by_asset_id`,
`connector/consumer/query_catalog_by_bpnl`,
`connector/provider/delete_asset`,
`connector/provider/delete_contract_definition`,
`connector/provider/delete_policy`,
`digital-twin/provider/delete_shell_descriptor`,
`digital-twin/submodel/upload`,
`notification/consumer/discover_assets`, `notification/consumer/send`,
`validate/semantic_schema`.

The three `connector/provider/delete_*` steps plus
`digital-twin/provider/delete_shell_descriptor` are the notable group: the IDE
can create connector and registry resources but cannot clean them up, so an
IDE-authored test leaves its fixtures behind.

## The rule: one name, one shape

Aliasing the divergences away would close every count in the headline without
closing a single gap. It also cannot work: an alias equates two *spellings*, and
half of what is listed above is not a spelling difference. `offer_id` is not
`policy`, `agreement_id` is not `negotiation_id`, `asset_ids` is not
`aas_identifier`, `mock`'s bare string is not a structured result. An alias
placed over those would bind a value of the wrong type to a field that cannot
use it — trading a silent drop for a silent corruption, which is worse.

So the rule for this repository is:

> **Every parameter, every output and every step id has exactly one spelling and
> exactly one shape.** No `AliasChoices` kept for compatibility, no parameter
> that accepts either a document or the flat fields of that document, no output
> published twice under two names. Where the two sides disagree, one of them is
> changed; nothing is added to bridge them.

The version is `0.0.6-alpha`. There is no compatibility promise to break, and
every script in the repository — `docs/examples`, the TCK, the test fixtures —
is migrated in the same commit as the rename that affects it.

Three consequences follow, and they are the reason the rule is worth its cost.

**`StepParams` becomes `extra="forbid"`.** Today it is `extra="allow"`
([`base.py:53`](../../src/tractusx_testlab/steps/base.py#L53)), justified by
"a script written against a newer revision of a step still runs against an older
engine" — which is backward compatibility, and is precisely what makes all 29
class-B findings silent. Forbidding extras converts every one of them into a
compile-time error naming the key. After that, a divergence of this kind cannot
be introduced again without someone seeing it fail.

**The JSON Schema becomes a faithful description of the contract.** The reason
this analysis had to read `model_fields` instead of `testlab docs --json` is
that JSON Schema renders an `AliasChoices` field under one name only. With no
aliases left, the generated schema *is* the contract.

**Which makes the block catalog generable.** A hand-written catalog and a
hand-written registry will drift again, whatever this document concludes. Once
the schema is faithful, `public/blocks/*.json` should be emitted from the
registry — one command, run in CI, output committed — so that class A, B and C
become impossible by construction rather than merely watched for. The remaining
work is then only what a generator cannot invent: the genuine capability gaps in
sections E and F, and the labels and grouping a human writes for the toolbox.

## The canonical contract

Each row states the one surviving name and which side changes. "Engine" means a
rename in this repository; "IDE" means the block catalog is rewritten (or
regenerated, once it is generated).

### Step ids

A step id is `<category>/<module>/<function>`. The **category** is the domain
under test (`connector`, `digital-twin`, `notification`) or the engine facility
being used (`util`, `flow`, `validate`, `http`, `mock`). The **module** is the
component or access path within that category — the connector's `consumer`,
`provider` and `dataplane` faces; the digital twin reached at its `provider`
registry rather than through a data plane. The **function** is the operation.

The module segment is **omitted when the category has no sub-division**:
`util/log`, `flow/delay`, `validate/assert` are complete ids, not truncated
ones. It appears as soon as one exists, and then it appears on every id in that
category — `digital-twin/provider/get_shell_descriptor` and
`digital-twin/submodel/upload`, never a bare `digital-twin/upload` alongside
them.

Within the function segment the engine's spellings win. They form consistent
triads (`create_`/`get_`/`delete_shell_descriptor`) and name the resource the
API actually operates on — a shell *descriptor*, not a shell.

| Canonical | Replaces | Moves |
| --- | --- | --- |
| `connector/consumer/negotiate_contract` | `connector/consumer/negotiate` | IDE |
| `connector/consumer/transfer_data` | `connector/consumer/initiate_transfer` | IDE |
| `digital-twin/provider/create_shell_descriptor` | `dtr/create_shell_descriptor`, `digital-twin-registry/register_shell` | **Engine** + IDE |
| `digital-twin/provider/get_shell_descriptor` | `dtr/get_shell_descriptor`, `digital-twin-registry/lookup_shell` | **Engine** + IDE |
| `digital-twin/provider/create_submodel_descriptor` | `dtr/create_submodel_descriptor`, `digital-twin-registry/add_submodel` | **Engine** + IDE |
| `digital-twin/provider/delete_shell_descriptor` | `dtr/delete_shell_descriptor` | **Engine** |
| `digital-twin/submodel/upload` | `submodels/upload` | **Engine** |
| `notification/consumer/send` | `notifications/send` | **Engine** |
| `notification/consumer/discover_assets` | `notifications/discover_assets` | **Engine** |

`provider` is the module because it names how the twin is reached — the
provider's own registry API, with no data plane in between. It reads the same way
as `connector/provider/*`, and it leaves `dataplane` free for its counterpart: a
DTR fronted by a connector data plane is a different access path and becomes
`digital-twin/dataplane/…`, a different step rather than an extra parameter on
these ones.

Two ids still sit outside the scheme and are left for a separate decision:
`http/http_request` stutters (`http/request` would read better), and `mock` has
one sub-divided id (`mock/wait/http_request`) beside three that are not
(`mock/api`, `mock/discovery`, `mock/dtr`) — by the rule above, either all four
carry a module or none does.

`connector/consumer/filter_expression` is unaffected — it is a composer block
and emits no `uses:` of its own. Its output key becomes `filter_expression`
(below).

### Parameters

| Step | Canonical | Replaces | Moves | Why this one |
| --- | --- | --- | --- | --- |
| `connector/consumer/negotiate_contract` | `asset_id` | `target` | **Engine** | It is the asset ID, and every other step already calls it that. The export feeding it renames with it: `catalog_target` → `catalog_asset_id`. |
| `connector/consumer/negotiate_contract` | `policy` | `offer_id` | IDE | Not a rename — a negotiation request carries the ODRL document, and an offer ID alone cannot build one. The block is wired from a catalog output instead of typed by hand. |
| `connector/consumer/transfer_data` | `negotiation_id` | `agreement_id` | IDE | The step polls a negotiation for its EDR. It never sees an agreement ID. |
| `connector/consumer/pull_data_filtered_by_policy` | `policies` | `expected_policies` | IDE | Same value, same shape. |
| `connector/provider/create_contract_definition` | `contract_definition_id` | `contract_id` (in), `contract_def_id` (out) | **Engine** + IDE | The engine currently takes one spelling and returns another for the same value. Both become the full word. |
| `digital-twin/provider/create_submodel_descriptor` | `aas_identifier` | `shell_id` | IDE | The AAS spec's own name for the path parameter. |
| `util/validate_path`, `util/json_path_extract` | `input` | `source` | **Engine** | Every assertion in every script already writes `input`, and `source` is spoken for three times over — `source: INLINE \| VARIABLE` in the expected-value resolution, `ValueSource` in the frontend, and `source: value \| input \| generated` on a variable declaration. See [ADR-0025](decision-records/shared/ADR-0025-assertions-read-declared-returns.md). |
| `mock/wait/http_request` | `endpoint_id` | `mock` | IDE | Names what it is; `mock` names the block. |
| `connector/dataplane/http_request` | `dataplane_url`, `edr_token` | `endpoint`/`url`, `token` | **Engine** | A parameter is spelled the same as the export that feeds it — these are fed by `connector/consumer/pull_data_filtered`'s `dataplane_url` and `edr_token`. |

That last row is the general principle behind several of these: **a parameter
carries the same name as the export it consumes**, so wiring a script is a
matter of matching names rather than remembering translations.

### Parameters that are a shape difference, not a name

`connector/provider/create_asset`, `connector/provider/create_policy`,
`digital-twin/provider/create_shell_descriptor` and
`digital-twin/provider/create_submodel_descriptor` keep their single document
parameter — `asset`, `policy`, `shell_descriptor`,
`submodel_descriptor`. The engine does **not**
also accept the flat fields and assemble the document; that is exactly the
dual-shape acceptance the rule forbids, and it would silently produce a
different document than the one an author who supplied both expected.

The document is the right shape to keep: it is the EDC / AAS payload verbatim,
so it does not go stale as those standards add fields, and a script can hand it
straight from a manifest variable (`${{ env.<id>.asset }}`).

The IDE keeps its form. It becomes a **composer block** — the pattern
`filter_expression` already uses — that assembles the document in the editor and
emits one `asset:` (or `policy:`, …) mapping into the YAML. The form stays; what
changes is that it produces a document instead of loose keys.

### Outputs

| Step | Canonical | Replaces / adds | Moves |
| --- | --- | --- | --- |
| `connector/consumer/negotiate_contract` | `negotiation_id`, `agreement_id`, `state` | `agreement_id` and `state` are new — the step polls the negotiation and publishes both | **Engine** (capability) |
| `connector/consumer/transfer_data` | + `state`; `dataplane_endpoint` only | adds `state`; deletes `data_address`, documented in the model as "older spelling of `dataplane_endpoint`" | **Engine** |
| `connector/consumer/query_catalog` | `catalog`, `datasets` | the raw JSON-LD document is wrapped, so `returns:` never has to spell `dcat:dataset` | **Engine** |
| `connector/consumer/pull_data_filtered` | + `agreement_id` | its by-policy sibling already publishes it; the two outputs stop disagreeing | **Engine** |
| `digital-twin/provider/*` | `id`, `id_short` | drops the `idShort` serialisation alias — YAML is snake_case throughout | **Engine** + IDE (`shell_id`, `submodel_id`, `shell_descriptor` → `id`, `id_short`) |
| `mock/api` | `endpoint_id`, `base_url`, `url` | replaces the bare string; `mock`, `base_mock_url`, `full_mock_url` map onto these three | **Engine** + IDE |
| `mock/wait/http_request` | `method`, `path`, `headers`, `body`, `query_params`, `elapsed_ms` | IDE drops the `request_` prefix; the last two are new and the mock server already has both | **Engine** + IDE |

### Capability gaps — implement or delete

The rule applies here too: **a block may not offer a parameter the engine does
not implement.** Each of these is implemented or deleted from the catalog — not
accepted and ignored.

| Item | Decision |
| --- | --- |
| `query_params` on `http/http_request` | Implement. Small, and folding query strings into the URL by hand is a recurring annoyance. |
| `asset_selector` on `connector/provider/create_contract_definition` | Implement. The EDC API takes a criteria array natively; the engine's single `asset_id` is the narrower thing. |
| `response_headers` on `mock/api` | Implement. The mock server can already set them. |
| lookup by `asset_ids` on DTR | Implement as a *separate* step — `digital-twin/provider/query_shell_descriptors`, taking `specific_asset_ids` and returning `descriptors`. It is a different registry endpoint from `digital-twin/provider/get_shell_descriptor`, so it is a different step, not an alternative parameter. |
| `transfer_type` on `connector/consumer/transfer_data` | Delete from the block until the engine does more than PULL. Offering `HttpData-PUSH` in a form that silently performs a PULL is the worst of the failure modes in this document. |

### Assertion blocks

The `validate/*` blocks are part of the same contract and settled in
[ADR-0025](decision-records/shared/ADR-0025-assertions-read-declared-returns.md).
Three steps make up the family — `validate/assert`, `validate/field` and
`validate/schema` — each a registered step, usable inline in a `validate:` list
or standalone in `execution:`, with one implementation behind both. `input:` is
the one name for the value being checked, on the assertion steps and on the
utility steps that read a value the same way, and an assertion may only read a
name the step declared in `returns:`. That last rule is what lets a validate
block's input list be populated from the preceding step rather than typed.

`validate/semantic_schema` — listed in section F above as an engine step with no
IDE block — is deleted rather than given one. It checks that a payload carries a
semantic model's required top-level keys, which is a weaker check than
`validate/schema` already performs against the JSON Schema derived from the same
model, expressed in a second vocabulary (`schema_ref`, `required_keys`). No
script uses it. That takes section F from fourteen orphaned steps to thirteen.

## Aliases already in the engine

Thirteen fields accept a second spelling today. Under the rule they go, and each
is a small migration of the scripts that use the losing spelling.

| Field | Surviving name | Also accepted today | Note |
| --- | --- | --- | --- |
| [`_contracts.py:91`](../../src/tractusx_testlab/steps/_contracts.py#L91) | `counter_party_address` | `provider_url` | |
| [`_contracts.py:96`](../../src/tractusx_testlab/steps/_contracts.py#L96) | `counter_party_id` | `bpnl` | |
| [`_contracts.py:117`](../../src/tractusx_testlab/steps/_contracts.py#L117) | `operand_left` | `operandLeft` | camelCase is the wire format; it stays as the *serialisation* alias and stops being accepted on input |
| [`_contracts.py:124`](../../src/tractusx_testlab/steps/_contracts.py#L124) | `operand_right` | `operandRight` | as above |
| [`_contracts.py:154`](../../src/tractusx_testlab/steps/_contracts.py#L154) | `filter_expression` | `filters` | |
| [`dataplane.py:70`](../../src/tractusx_testlab/steps/connector/dataplane.py#L70) | `dataplane_url` | `url`, `endpoint` | three spellings, one field |
| [`dataplane.py:79`](../../src/tractusx_testlab/steps/connector/dataplane.py#L79) | `edr_token` | `token` | |
| [`provision.py:309`](../../src/tractusx_testlab/steps/connector/provision.py#L309) | `usage_policy_id` | `contract_policy_id` | |
| [`json_extract.py:118`](../../src/tractusx_testlab/steps/utility/json_extract.py#L118) | `input` | `source`, `variable` | the surviving name is `input`, not either spelling accepted today |
| [`notification.py:81`](../../src/tractusx_testlab/steps/industry/notification.py#L81) | `dataplane_url` | `endpoint_url` | |
| [`notification.py:86`](../../src/tractusx_testlab/steps/industry/notification.py#L86) | `edr_token` | `auth_token` | |
| [`notification.py:91`](../../src/tractusx_testlab/steps/industry/notification.py#L91) | `content` | `payload` | |
| [`validate.py:214`](../../src/tractusx_testlab/steps/utility/validate.py#L214) | `schema` | `json_schema` | |

`CatalogFilter` ([`_contracts.py:134`](../../src/tractusx_testlab/steps/_contracts.py#L134))
goes with them. Its docstring calls it "an alternative spelling of
`filter_expression`", which is the same thing one level up: a nested `filter:`
block that duplicates a top-level parameter.

Serialisation aliases that map to a *foreign* wire format — `@id`, `@context`,
`dcat:dataset`, `operandLeft` on the way out — are not in scope. Those are not
two names for one thing; they are the JSON-LD and EDC documents, and the engine
has to speak them.

## Order of work

1. **One breaking commit, engine-side.** Delete the thirteen aliases and
   `CatalogFilter`, apply the engine renames from the tables above, switch
   `StepParams` to `extra="forbid"`. Migrate `docs/examples`, the TCK and the
   test fixtures in the same commit — with `extra="forbid"` in place, a missed
   script fails its next run rather than drifting on silently.
2. **Additive engine work.** The new outputs, then the five capability items.
   Nothing here breaks a script.
3. **Catalog.** Rewrite (or generate) `public/blocks/*.json` against the settled
   contract, including the four composer blocks and the split DTR lookup.
4. **Enforcement.** `--check` in CI, once the count reaches zero.

Steps 1 and 2 are entirely within this repository. Step 3 is the only one that
needs a coordinated change in `cx-test-suite`, and it is a rewrite rather than a
negotiation, because by then the contract has one side.

## Keeping it from drifting again

`tools/compare_ide_parity.py --check` exits non-zero while any class-A, -B, -C
or -G divergence remains. It needs a `cx-test-suite` checkout, so it fits a
scheduled or manually-triggered job rather than the per-commit test run.

A checker is the weaker of the two guards, though, and it is worth being honest
about which does the work. `extra="forbid"` on `StepParams` stops class B at the
moment a script runs, in this repository, with no external checkout — that is
what makes the class impossible rather than merely visible. Generating the block
catalog from the registry does the same for A and C. The comparison tool is then
what catches a catalog that was hand-edited or left stale, which is a narrower
job than the one it does today.
