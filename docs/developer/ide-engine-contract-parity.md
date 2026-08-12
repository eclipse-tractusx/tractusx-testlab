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

> Engine: this repository, step registry as registered by `tractusx_testlab.steps`
> IDE: `cx-test-suite`, block catalog under `public/blocks/`
> Reproduce: `poetry run python tools/compare_ide_parity.py --ide <cx-test-suite>`
> Gate: the same command with `--check` exits non-zero while any class-A, -B, -C
> or -G divergence remains.

This page is the **status** of the two-sided contract: what the comparison
measures, what the rule is, and what is still divergent. The individual
decisions — which of two spellings survives, and why — are the numbered record
in [Contract conflict decisions](contract-conflict-decisions.md); where an
earlier revision of this page proposed a name that the decision record later
settled differently, **the decision record is authoritative**.

## Why a name-level comparison is not enough

A `uses:` value is only a third of the contract. The IDE also writes a `with:`
mapping and a `returns:` block, and all three have to agree:

```yaml
- id: negotiate_it
  uses: connector/consumer/negotiate     # 1. the step name
  with:
    asset_id: ${{ execution.query.catalog_asset_id }}   # 2. the input keys
  returns:
    agreement_id: { type: string }                      # 3. the output keys
```

Comparing only line 1 reports parity for a step whose every parameter the engine
refuses. So the interesting question is not "does the name exist" but "does the
payload survive". This document answers that one, key by key.

## How the comparison is done

Both sides are read from their real definitions, not from generated
documentation:

| Side | Read from | Why not the obvious source |
| --- | --- | --- |
| Engine | `model_fields` of each step's `params_model` / `output_model` / `exports_model` | Reading the models keeps the tool honest even about fields the JSON Schema renders under one name only. |
| IDE | Every `*.json` under `public/blocks/`, indexed or not | `index.json` omits structural blocks that are still reachable in the toolbox. |

A `returns:` name counts as readable if it matches an output field, an export
name, or one of the universal slots
[`_checks/extraction.py`](../../src/tractusx_testlab/steps/_checks/extraction.py)
resolves for every step regardless of the declared output — `value`, `request`,
`response`, `exports`, `status_code`, `headers`, `body`, `duration_ms`,
`response_body`, `response_headers`. That group is the reason `util/base64`'s
`value` return and `http/http_request`'s `response_body` return work despite not
appearing in any output model. A comparison that ignored it would report nine
false breaks.

Anything **outside** that set now resolves only when the step declared it
(C40): a `returns:` name the step does not produce is no longer quietly filled
in from the raw HTTP response, so class C is a real break rather than a value
that arrives by accident.

A field that accepts **more than one** key is reported as class **G** and
counted as a divergence like any other. It is the mildest class, because it
fails no run today; it is still two names for one field, and the whole point of
this exercise is that there be one. A field whose single accepted key merely
differs from its Python attribute name is not class G — see
[what is left](#what-is-left-by-class).

## Where the counts stand

The engine side of the migration is complete. Every divergence that remains is
in the block catalog.

Measured by the tool, the breaking count went from **62** before the migration
to **35**, across 33 of the catalog's blocks:

| Class | Gated | Count |
| --- | --- | ---: |
| **A** — `uses:` does not resolve | yes | 5 |
| **B** — IDE parameters the engine does not accept | yes | 22 |
| **C** — IDE returns the engine never produces | yes | 8 |
| **G** — parameters that bind only through an alias | yes | 0 |
| **D** — required in IDE, optional in engine | no | 15 steps |
| **E** — engine parameters the IDE does not offer | no | 20 steps |
| **F** — engine steps with no IDE block | no | 18 |

Classes **D**, **E** and **F** are not breaks and are not gated on. **E** and
**F** grew over the migration because the engine gained capability the catalog
has not caught up with yet — the wizard composer steps, the DTR dataplane
lookup, PUSH transfers.

The failure severity ranks A > B > C:

- **A fails loudly.** The compiler rejects the script with
  `Unknown step type '<uses>'`
  ([`validator.py:99`](../../src/tractusx_testlab/compiler/validation/validator.py#L99)).
- **B now also fails loudly.** Since C47, `StepParams` is `extra="forbid"`, so
  an undeclared `with:` key is a validation error naming the key. This is the
  change that turned the largest and most dangerous class from silent to
  visible — see [the rule](#the-rule-one-name-one-shape).
- **C fails at a distance.** The variable is `None`, and the error shows up in
  whichever later step consumed it.

## What is left, by class

Run the tool for the current list; this is the shape of it.

**A — five `uses:` values do not resolve.** The three
`digital-twin-registry/*` blocks still emit the pre-rename ids and are repointed
at `digital-twin/provider/*` (and, for the lookup, split onto the separate
dataplane step). `connector/consumer/filter_expression` is not a break — it is a
structural composer block that emits no step of its own. `flow/condition` is:
the block exists in the toolbox and names a step the engine never had; the
engine's conditional is `flow/if`.

**B — twenty-two parameters are rejected.** Two kinds. The `create_asset` /
`create_policy` / `register_shell` / `add_submodel` forms send the *flat fields*
of a document the engine takes whole; those blocks become composer blocks
feeding the wizard steps the engine now registers
(`connector/provider/wizard/create_asset`,
`connector/provider/wizard/create_policy`,
`digital-twin/provider/wizard/create_shell_descriptor`,
`digital-twin/provider/wizard/create_submodel_descriptor`). The rest are stale
spellings — `offer_id`, `filter`, `contract_def_id`, `source`, and the
`asset_id` that `initiate_transfer` never took.

**C — eight returns resolve to nothing.** All stale output names on the DTR
blocks, plus `contract_def_id`, `transfer_process_id` and `query_params`, each
of which the engine now publishes under exactly one other name.

**G — none.** The last three engine aliases (`notification/consumer/send`'s
`endpoint_url`, `auth_token` and `payload`) are gone. Two fields still carry a
`validation_alias` — `flow/if`'s `else` and `validate/schema`'s `schema` — but
neither is a second spelling: `else` and `schema` are the only accepted keys,
and the differing attribute names exist because `else` is a Python keyword and
`schema` shadows a `BaseModel` method. Both models turn `validate_by_name` off
so the attribute name cannot be written in a script, and the checker counts a
field as an alias divergence only when it accepts more than one key.

## The rule: one name, one shape

Aliasing the divergences away would close every count above without closing a
single gap. It also cannot work: an alias equates two *spellings*, and much of
what is listed is not a spelling difference. `offer_id` is not `policy`,
`asset_ids` is not `aas_identifier`. An alias placed over those would bind a
value of the wrong type to a field that cannot use it — trading a silent drop
for a silent corruption, which is worse.

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

**`StepParams` is `extra="forbid"`** — done, C47.
[`base.py`](../../src/tractusx_testlab/steps/base.py) no longer keeps unknown
keys "so a script written against a newer revision still runs against an older
engine", which was backward compatibility, and was precisely what made every
class-B finding silent. A `with:` key no step declares is now a validation error
naming the key. `tests/test_step_contracts.py` asserts it for every registered
step, so a step cannot loosen back to `allow` without a test saying so.

**The JSON Schema is a faithful description of the contract.** The reason the
original analysis had to read `model_fields` instead of `testlab docs --json` is
that JSON Schema renders an `AliasChoices` field under one name only. With the
aliases gone, the generated schema *is* the contract.

**Which makes the block catalog generable.** A hand-written catalog and a
hand-written registry will drift again, whatever this document concludes. Now
that the schema is faithful, `public/blocks/*.json` should be emitted from the
registry — one command, run in CI, output committed — so that classes A, B and C
become impossible by construction rather than merely watched for. The remaining
work is then only what a generator cannot invent: the genuine capability gaps in
classes E and F, and the labels and grouping a human writes for the toolbox.

## Step ids

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

`provider` names how the twin is reached — the provider's own registry API, with
no data plane in between. It reads the same way as `connector/provider/*`, and
it leaves `dataplane` free for its counterpart: a DTR fronted by a connector
data plane is a different access path and is
`digital-twin-registry/consumer/dataplane/lookup_shell`, a different step rather
than an extra parameter on the registry one.

## The general principle behind the renames

**A parameter carries the same name as the export it consumes.** Wiring a script
is then a matter of matching names rather than remembering translations:
`connector/consumer/pull_data_filtered` publishes `dataplane_url` and
`edr_token`, and those are exactly the parameter names
`connector/dataplane/http_request` reads them under.

The corollary is that a step never publishes one value twice under two names,
and never publishes a value it did not produce. `pull_data_filtered` used to
report the transfer id three times over — as `negotiation_id`,
`transfer_process_id` and `agreement_id` — which is the same drift one level
down.

## Documents stay documents

`connector/provider/create_asset`, `connector/provider/create_policy` and the
`digital-twin/provider/create_*` steps keep their single document parameter —
`asset`, `policy`, `shell_descriptor`, `submodel_descriptor`. Those steps do
**not** also accept the flat fields and assemble the document; that is exactly
the dual-shape acceptance the rule forbids, and it would silently produce a
different document than an author who supplied both expected.

The document is the right shape to keep: it is the EDC / AAS payload verbatim,
so it does not go stale as those standards add fields, and a script can hand it
straight from a manifest variable (`${{ env.<id>.asset }}`).

Authoring the document by hand is a separate job, and it gets a separate step.
The `wizard/*` steps take the flat fields, assemble the document, and create the
resource — one step id per shape, so which one a script uses is visible in the
`uses:` line rather than inferred from which keys were filled in.

## Keeping it from drifting again

`tools/compare_ide_parity.py --check` exits non-zero while any class-A, -B, -C
or -G divergence remains. It needs a `cx-test-suite` checkout, so it fits a
scheduled or manually-triggered job rather than the per-commit test run.

A checker is the weaker of the two guards, though, and it is worth being honest
about which does the work. `extra="forbid"` on `StepParams` stops class B at the
moment a script runs, in this repository, with no external checkout — that is
what makes the class impossible rather than merely visible. C40 does the same
for class C: a `returns:` name is resolved only against what the step declared.
Generating the block catalog from the registry would close class A the same way.
The comparison tool is then what catches a catalog that was hand-edited or left
stale, which is a narrower job than the one it does today.
