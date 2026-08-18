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

# Environment & Context Injection — Analysis Report

> Date: 2026-08-06 | Branch: `feat/run_security_consitency`
> Scope: how operator-supplied configuration, infrastructure bindings, and test
> variables enter a run and reach a step. Backend only (`src/tractusx_testlab/`).
> Status: **partly implemented** — F5 and F7 are fixed, and §4 A (the binding
> half), §4 B and §4 E.3 shipped with the `InfrastructureManager`. See
> [Infrastructure Bindings](infrastructure-bindings.md) for the result. The
> findings below are recorded as they were measured; the sections that have
> since been addressed say so where they are stated.

## Summary

There is no single injection mechanism. There are **three unrelated entry doors**,
**two unrelated configuration axes that never meet**, **nine write sites** into one
untyped dictionary, and **two independent expression resolvers** with inverse
normalization rules — only one of which ever executes.

The binding half of [ADR-0019](decision-records/backend/ADR-0019-service-requirements-and-engine-bindings.md)
was never implemented. The typed model that exists (`InfrastructureConfig`) describes
*requirements* and is never consulted by the player; the data that is actually used
(the operator's binding values) is unmodelled and recovered by string-prefix scraping
at runtime.

The practical symptom is that an unresolved variable reference is not an error. It
silently becomes the literal template string, passes step validation, and surfaces
several layers later as a connector or HTTP failure.

| Area | Findings |
|------|----------|
| Dead / misleading code | F1, F10 |
| Silent failure | F2, F3 |
| Duplicated or divergent logic | F4 |
| Missing architecture (ADR-0019 §2/§3) | F5 |
| Unbounded, unspecified input surface | F11 |
| Order-dependent behavior | F6 |
| Inconsistent behavior across entry points | F7, F8 |
| Namespace collisions | F9 |

---

## 1. The pipeline as it actually runs

```text
                  ┌─ CLI      --config file.yaml + --var K=V ──┐
 operator input ──┼─ HTTP     POST /jobs {runtime_vars: {...}} ─┼──> runtime_vars: dict
                  └─ Library  player.run(runtime_vars={...})  ──┘         │
                                                                          │
 TestlabConfig ── testlab.config.yaml + TESTLAB_* env ──> (never meets ────┘ ... it doesn't)
                                                            runtime_vars)
                                                                          v
                            StepContext._variables : dict[str, object]  <-- 9 writers
                                                                          │
                                    string-prefix scrape ─────────────────┤
                                    ("infrastructure.*")                  │
                                              v                           v
                                       ServiceManager              regex substitution
                                       (ServiceDefinition)         ${{ }} / ${} / @var
                                              └──────────> step execute()
```

### Injection hops, in execution order

| # | Where | What it writes |
|---|-------|----------------|
| 1 | `cli/run.py:108` | config-YAML `variables:` → `runtime_vars` (**all values `str()`-cast**) |
| 2 | `player/execution/_context_seeder.py:59` | `_tck_root` |
| 3 | `player/execution/_context_seeder.py:136-137` | `testdata.<id>` **and** `env.testdata.<id>`; same for schemas |
| 4 | `player/execution/_context_seeder.py:63-67` | `shared_variables` defaults — **dead code, see F1** |
| 5 | `player/execution/_context_seeder.py:94-97` | `env.variables` with `source: value` → `<id>` and `<id>.<field>` |
| 6 | `player/execution/_context_seeder.py:72-73` | `runtime_vars` verbatim, overwriting everything |
| 7 | `player/execution/infrastructure_seeder.py:158` | scrapes `infrastructure.*` string keys → `ServiceDefinition`s; writes back `infrastructure.engine.connector` as a *service-name string* |
| 8 | `player/execution/_helpers.py:34` | per-script `variables:` defaults |
| 9 | `player/execution/step_runner.py:117-119`, `steps/base.py:302-304`, `player/execution/player.py:261-262` | step returns (`<field>` **and** `steps.<id>.<field>`), step exports, script outputs (`<name>` **and** `!<script>:<name>`) |

Everything lands in the same `dict[str, object]` at `player/execution/context.py:54`.
There is no schema, no namespace object, no provenance, and no type information.

---

## 2. Findings

### F1 — The documented priority ladder is partly dead code

`_context_seeder.py:49-56` documents a three-level priority: shared variables →
`env.variables` → `runtime_vars`. **Level 1 never executes.**
`getattr(tck.definition, "shared_variables", None)` always returns `None`, because
`TckDefinition` (`models/authoring/definitions.py:198`) has no such field — the
block is `env.variables`.

The compiler validator still directs authors to it
(`compiler/validation/validator.py:133`). The docstring describes an architecture
that is not present.

### F2 — `source: input` variables are silently never seeded

`seed_env_variables` (`_context_seeder.py:76`) only handles `with.value`. Every
`source: input` variable — which is *the entire SUT-supplied surface* per ADR-0019 §4
— is skipped, with no log line and no error. The variable's `returns:` fields are
skipped with it, so `${{ env.sut_counter_party_id.value }}` has nothing behind it.

### F3 — Unresolved references silently become literal strings

This is the direct cause of the painful manual debugging that motivated this report.
Verified against the running code:

```python
store = {'sut_counter_party_id': 'BPNL0001'}
resolve_str('${{ env.sut_counter_party_id.value }}', ctx)
# → '${{ env.sut_counter_party_id.value }}'   <-- the literal template
```

`player/loading/resolver.py:74-77` returns the original string when the lookup yields
`None`. That literal then passes Pydantic validation, because `CounterPartyParams`
(`steps/_contracts.py:99`) declares `counter_party_address: str = Field(default="")`
— any string is valid. An unset variable therefore becomes an HTTP request to a URL
literally named `${{ env.… }}`, and the failure surfaces several layers away as a
connector error.

There is a naming trap on top of it: the operator writes `sut_counter_party_id: BPNL0001`
in the run-config, but the script reads `.value`. Nothing bridges the two, and nothing
warns.

### F4 — Two expression resolvers with different rules, only one of which runs

- **Compiler** — `compiler/validation/_expressions.py:70` normalizes `testdata.x` →
  `env.testdata.x` and emits `$ref` / `$concat` IR.
- **Player** — `player/loading/resolver.py:44` strips `env.` and does a flat lookup.

These are inverse transforms of the same syntax. The player never consumes the IR:
`compile_tck` bundles **raw YAML** (`tck-bundle.yaml`, `compiler/compiler.py:169`) and
the loader `yaml.safe_load`s it back. Compile-time validation therefore validates a
representation that never executes, and any divergence is invisible until runtime.

This also explains the dead double-write at `_context_seeder.py:137`:
`env.testdata.<id>` is never read, because the resolver strips `env.` before looking up.

### F5 — `infrastructure.*` is string-scraped, not modelled — **fixed**

> Fixed by the `Infrastructure` model and `InfrastructureManager`: the fields
> below are declared, the three surfaces are generated from them, an unknown key
> is an error, and requirements are checked against bindings before the first
> step. Suffix-stripping remains, deriving `base_url` and `dma_path` from the
> declared `management_url`. What follows is the state that motivated it.

ADR-0019 §2 specifies a structured `bindings:` profile with a schema and a loader. It
was never built — `grep -rn "bindings" src/**/*.py` returns nothing. Instead,
`player/execution/infrastructure_seeder.py` does
`key.startswith("infrastructure.engine.connector.")` over the flat dict and
hand-assembles a `ServiceDefinition`. Consequences:

- `InfrastructureConfig` (`models/authoring/infrastructure.py:73`) — the typed model
  that *does* exist — models only *requirements* (`required`, `standard`). It is used
  by `testlab inspect` and never by the player. Requirements are declared and never
  checked against what was actually bound.
- Field names (`management_url`, `api_key`, `api_key_header`, `participant_id`,
  `dsp_url`, `name`, `version`) exist only as string literals inside the seeder.
  Nothing validates them; a typo yields a skipped service and a `logger.debug`.
- `_strip_management_suffix` (`infrastructure_seeder.py:83`) guesses `base_url` by
  pattern-matching two hardcoded suffixes, reconstructing information the operator
  already had.
- `infrastructure.engine.connector` is used as **both a key prefix and a leaf key**
  (`infrastructure_seeder.py:186`), the leaf holding the sentinel
  `"__engine_connector__"`. A flat namespace cannot express "node and leaf".
- The alias branch at `infrastructure_seeder.py:192-206` registers the engine
  connector a *second* time as a PROVIDER under `infrastructure.engine.connector.name`,
  with a comment stating it exists so `service: testlab` resolves. That is a
  name-string workaround for a missing role model.

### F6 — Service selection depends on dict insertion order

`_first_service_of_type` (`player/execution/context.py:122`) iterates `service_names`
and returns the first match. Registration order is: infrastructure seeder (engine, then
engine-alias, then SUT) → per-script `services:`. **Which connector a step talks to is
therefore a function of seeding order, not of anything declared.**

`context.py:133` additionally reaches into `self._services._definitions` — a private
field of another class.

### F7 — CLI `run` bypasses `ConfigLoader` entirely — **fixed**

> `cli/run.py` now loads through `ConfigLoader`, passing only the log directory
> as a CLI override, so the file and the environment reach a CLI run exactly as
> they reach the server.

`cli/run.py:79` constructs `TestlabConfig(logs_dir=...)` directly. `TestlabPlayer`
only falls back to `ConfigLoader.load()` when `config is None`
(`player/execution/player.py:87`).

Net effect: **`testlab.config.yaml` and every `TESTLAB_*` environment variable are
silently ignored on the CLI run path** — vault config, `TESTLAB_SERVER_PORT`,
`TESTLAB_KEYS_DIR`, all of it. The server path (`server/app.py:58`) honours them.
Same product, two behaviours.

### F8 — Type fidelity depends on which door you entered

`_load_config_variables` casts everything with `str()` (`cli/run.py:123-125`). So
`sut_response_timeout: 60` in `stubs/ccm-sut/run-config.yaml:34` arrives as `"60"`.
The same key supplied via `POST /jobs` or the library API arrives as `int`. Steps that
do arithmetic or comparison behave differently depending on the entry point.

### F9 — Ten naming conventions in one flat namespace

Coexisting inside `_variables`, with no separator discipline:

`_tck_root` · `testdata.<id>` · `env.testdata.<id>` · `<var_id>` · `<var_id>.<field>` ·
`infrastructure.<side>.<cap>` · `infrastructure.<side>.<cap>.<field>` ·
`steps.<id>.<field>` · `<field>` (same value, flat) · `!<script>:<export>` · plus the
`syntax/context_vars.py` constants (`catalog_target`, `datasets`, `edr_token`, …).

A step export named `datasets` collides with a user variable named `datasets`; last
writer wins, silently.

### F10 — Two generations of documentation, both wrong

`docs/tutorials/ccm-developer-guide.md:206` documents the V1 flat model
(`testlab_management_url`, `provider_address`). The shipped example
`docs/examples/certificate-management-v2/raw/index.yaml:70` uses the V2 `env.variables`
verb form. The code path that makes the V2 example work (the `infrastructure.*`
prefixes) is documented **only** in `tests/test_infrastructure_seeder.py:57`.

An operator has no correct document from which to write a run-config.

### F11 — Declaring a capability obliges the operator to nothing — **partly fixed**

> The key vocabulary is now declared per capability, and a `required: true`
> capability with no binding fails before the first step naming the key it
> owes. What is not yet built is the rest of §4 E: only the identifying address
> is obligatory (not a full per-capability contract), and `auth` is still the
> flat `api_key` / `api_key_header` pair rather than the discriminated union of
> §4 E.2 — so OAuth-protected infrastructure remains unexpressible.

`infrastructure.sut.connector.required: true` states that the run needs a SUT connector.
It does **not** state what the operator must supply for it, and nothing anywhere does.
The required keys are distributed across three places that cannot be reconciled:

- the scraper's string literals (`infrastructure_seeder.py:105-127`) — `management_url`,
  `api_key`, `api_key_header`, `participant_id`, `dsp_url`;
- whatever the TCK author named their `source: input` variables — the CCM TCK picked
  `sut_counter_party_id` / `sut_counter_party_address`
  (`docs/examples/certificate-management-v2/raw/index.yaml:72-89`), but nothing constrained
  that choice, so a second TCK needing the same connector may name them differently;
- the step contracts that ultimately consume them (`steps/_contracts.py:99`).

`ServiceDefinition.auth` is a bare `dict` (`models/authoring/definitions.py:69`) and the
seeder populates it only for the API-key case (`infrastructure_seeder.py:126-127`), so
**OAuth-protected infrastructure is not expressible at all** — there is no key an operator
could supply for a token URL, client ID, or secret.

The result is an input surface with no boundary: the operator cannot know what is
obligatory, the engine cannot check it, and a missing key is discovered as a step failure.
This is the finding that §4 E addresses.

---

## 3. Root causes

The individual findings all descend from three structural causes.

1. **The context is a `dict[str, object]`, not a model.** Nine writers, no schema, no
   provenance, no types, no collision detection. Every consumer re-derives structure
   with string prefixes and `getattr` chains. This is why F5, F6, and F9 exist, and why
   debugging a single variable requires reading nine files.

2. **ADR-0019's binding half was never implemented.** The requirements half
   (`InfrastructureConfig`) is modelled and unused; the bindings half (the operator
   profile, with a schema and loader) is used and unmodelled. The seeder occupies the
   seam where a typed model belongs, and it is written in `startswith()`. Because that
   half is missing, a declared requirement carries no obligation and no vocabulary — F11.

3. **Resolution is untyped textual substitution with a silent-failure default.**
   Missing → literal passthrough → permissive `str` field → error surfaces three layers
   downstream. Combined with F4's two divergent resolvers, nothing catches a bad
   reference at any stage.

---

## 4. Proposed target architecture

Five pieces, ordered so that each is independently shippable.

### A. One typed `RunEnvironment`, built once, before the player

```text
RunEnvironment
├── config:   TestlabConfig          # engine settings (logs, ports, vault) — one loader, all doors
├── bindings: BindingProfile         # ADR-0019 §2, Pydantic-modelled, schema-validated
│     ├── engine: {connector: ConnectorBinding, dtr: DtrBinding}
│     └── sut:    {connector: ConnectorBinding, dtr: DtrBinding}
└── inputs:   dict[str, Any]         # operator answers to `source: input` variables, typed
```

All three doors (CLI / HTTP / library) construct this same object through one factory.
F7 and F8 disappear, because there is one construction path with one type contract.

### B. Replace the string scrape with a resolver over the typed profile

`seed_infrastructure_services` becomes:

```python
bind_infrastructure(
    requirements: InfrastructureConfig,
    profile: BindingProfile,
) -> list[ServiceDefinition]
```

It matches each `required: true` capability against a binding and **fails fast with a
typed error naming the unbound capability** — ADR-0019 §3, currently unimplemented.
`management_url`, `api_key_header`, and `dsp_url` become model fields with validators
instead of string literals. Suffix-stripping goes away: `ConnectorBinding` carries
`base_url` and `management_path` as separate declared fields.

### C. Namespaced context with explicit scopes

Replace the flat dict with scoped stores — `env`, `infrastructure`, `steps`, `exports`,
`internal` — each with a declared key shape. A write to an occupied key in a different
scope is an error, not a silent overwrite. This resolves F9, F6 (services looked up by
role and side, not insertion order), and the node-vs-leaf collision in F5.

### D. Make resolution strict and single-implementation

- Unresolved reference raises `UnresolvedReferenceError`, naming the expression, the
  scope searched, and the nearest keys — not a literal passthrough. This alone converts
  a multi-layer debug into a one-line message.
- One resolver shared by compiler and player. Either the player consumes the `$ref` IR,
  or the compiler validates against the player's resolution rules. Two inverse
  normalizations of the same syntax cannot both be correct.
- Add a `dump_context` / `--explain-vars` diagnostic printing every key with its value,
  its type, and **which of the nine writers set it**. This is the highest-value
  debugging artifact and is cheap once (A) and (C) exist.

### E. A capability contract registry — declaring a capability makes its keys obligatory

This is the piece that closes the open-ended input surface. Today `infrastructure:` says
*whether* a capability is needed but says nothing about *what the operator must supply for
it*, so the required keys live only in the scraper's string literals
(`infrastructure_seeder.py:105-127`) and in whatever the TCK author happened to name their
`source: input` variables. Two TCKs needing the same SUT connector can demand different key
names, and nothing detects a missing key until a step fails mid-run.

**Rule: each `(side, capability)` pair has exactly one contract, and
`required: true` binds the operator to it.** Nothing else may be required, and nothing in
the contract may be omitted.

```text
infrastructure.sut.connector.required: true
        │
        └── obliges the operator to supply CONTRACTS[("sut", "connector")] in full
            → validated at load, before any step runs
```

#### E.1 The registry

| Side + capability | Required keys | Optional keys (with defaults) |
|---|---|---|
| `sut.connector` | `counter_party_id` (BPNL), `counter_party_address` (DSP URL) | — |
| `sut.dtr` | `base_url` | `api_path` = `/api/v3.0`, `auth` = `{type: none}` |
| `engine.connector` | `base_url`, `participant_id` (BPNL), `auth` | `management_path` = `/management`, `dsp_path` = `/api/v1/dsp`, `version` ← `dataspace.version` |
| `engine.dtr` | `base_url`, `auth` | `api_path` = `/api/v3.0` |

The asymmetry is deliberate and follows ADR-0019 §4. The **engine** side is infrastructure
TestLab *operates*, so it needs management access and therefore credentials. The **SUT**
side is a counter-party TestLab only *talks to* over DSP, so it needs an identity and an
endpoint and no credentials at all — which is exactly the pair
`connector/consumer/query_catalog` and every negotiation step consume via
`CounterPartyParams` (`steps/_contracts.py:99`), and exactly the two variables the CCM TCK
declares by hand today as `sut_counter_party_id` / `sut_counter_party_address`
(`docs/examples/certificate-management-v2/raw/index.yaml`). Under this design the TCK stops
declaring them: requiring `sut.connector` *is* the declaration.

#### E.2 Auth is a closed discriminated union, never a free-form dict

`ServiceDefinition.auth` is `dict` today (`models/authoring/definitions.py:69`), and the
scraper populates it only for the API-key case — OAuth is unrepresentable. Replace it with a
tagged union so the shape is decided by `type` and validated at load:

```yaml
# API key
auth:
  type: api_key
  header: X-Api-Key          # optional, this is the default
  value: ${TESTLAB_ENGINE_CONNECTOR_AUTH_VALUE}

# OAuth2 client credentials
auth:
  type: oauth2_client_credentials
  token_url: https://idp.example.com/realms/cx/protocol/openid-connect/token
  client_id: testlab-engine
  client_secret: ${TESTLAB_ENGINE_CONNECTOR_AUTH_CLIENT_SECRET}
  scope: ""                  # optional
  audience: ""               # optional

# Explicitly unauthenticated — must be stated, never inferred from absence
auth:
  type: none
```

```python
AuthConfig = Annotated[
    Union[ApiKeyAuth, OAuth2ClientCredentialsAuth, NoAuth],
    Field(discriminator="type"),
]
```

Three properties follow, none of which hold today:

- An unknown `type` is a load-time error listing the permitted values.
- `client_secret` missing under `oauth2_client_credentials` is a load-time error at the
  exact path — not a `401` from the connector twenty steps later.
- Secret fields are typed `SecretStr`, so the provenance dump (D) and the
  `tck.boot.binding.*` events (ADR-0019 §4) redact them structurally rather than by
  key-name guesswork.

#### E.3 One mechanical naming rule across all three surfaces

Every contract key appears in three places, and all three derive from the same path — no
lookup table, no per-capability special cases. This is what replaces the ten colliding
conventions of F9 within the infrastructure namespace:

| Surface | Form | Example |
|---|---|---|
| Binding profile YAML | `<side>.<capability>.<field>` | `sut.connector.counter_party_address` |
| Context variable | `infrastructure.<side>.<capability>.<field>` | `infrastructure.sut.connector.counter_party_address` |
| Environment variable | `TESTLAB_<SIDE>_<CAPABILITY>_<FIELD>` | `TESTLAB_SUT_CONNECTOR_COUNTER_PARTY_ADDRESS` |

Nested fields extend the path (`engine.connector.auth.client_id` →
`TESTLAB_ENGINE_CONNECTOR_AUTH_CLIENT_ID`). The env-var form is generated from the model,
so it cannot drift from the YAML form.

#### E.4 Validation is fail-fast and total

`bind_infrastructure` (B) checks the requirements against the profile before the first step
and reports **every** problem at once, rather than aborting on the first:

| Condition | Error |
|---|---|
| `required: true` capability with no binding block | `MissingBindingError(side, capability, required_keys)` |
| Binding block missing a contract key | `IncompleteBindingError` at the exact path |
| Capability key not in the registry | `UnknownCapabilityError(side, capability, known)` |
| Binding supplied for a capability that is not `required: true` | `UnusedBindingError` — warning by default |

The first error is the important one: it can print the full list of keys the operator still
owes, because the registry knows them.

#### E.5 Generating the operator's starting point

Because the registry is data, the exact set of obligatory keys for a given TCK is
derivable, so operators stop guessing:

```console
$ testlab bindings template ./certificate-management-tck
# Required by infrastructure.sut.connector (required: true)
sut:
  connector:
    counter_party_id: ""            # BPNL of the system under test
    counter_party_address: ""       # DSP endpoint URL

# Required by infrastructure.engine.connector (required: true)
engine:
  connector:
    base_url: ""
    participant_id: ""
    auth:
      type: api_key                 # api_key | oauth2_client_credentials | none
      value: ""
```

The same registry drives the IDE form and the `tck.boot.requirements` event that ADR-0019 §3
already specifies but that nothing emits today.

#### E.6 What this fixes

- **F2** — `source: input` largely disappears for infrastructure. The SUT surface is
  supplied by contract rather than by hand-declared, per-TCK input variables.
- **F5** — the scraper's implicit key vocabulary becomes an explicit, typed, tested model.
- **F3** — most unresolved-reference failures were missing infrastructure keys; those now
  fail at load with a named key instead of resolving to a literal string.
- **F9** — one derivation rule replaces ad-hoc naming inside `infrastructure.*`.

---

## 5. Suggested sequencing

| Step | Change | Risk | Unblocks |
|---|---|---|---|
| 1 | Strict resolution + `UnresolvedReferenceError` + provenance dump | low, high signal | immediately exposes how many F2/F3 failures are latent today |
| 2 | Delete dead `shared_variables` branch; fix validator message; remove dead `env.<folder>.<id>` write | trivial | removes misleading code |
| 3 | ~~Single `RunEnvironment` factory; route CLI through `ConfigLoader`~~ — **done** for the config and binding halves; `inputs` still unmodelled, so F8 stands | low | fixes F7 |
| 4 | Add the capability contract registry + `AuthConfig` union (§4 E) | medium | makes required keys declarable and verifiable at all |
| 5 | ~~`BindingProfile` model + `bind_infrastructure` replacing the scraper~~ — **done** as `Infrastructure` + `InfrastructureManager` | medium | fixed F5; ADR-0019 §3 fail-fast now enforced |
| 6 | `testlab bindings template` + `tck.boot.requirements` event | low | operators stop guessing key names |
| 7 | Scoped context, role-based service lookup | medium-high | fixes F6, F9 |
| 8 | Unify compiler/player resolvers | medium | fixes F4 |
| 9 | Rewrite operator-facing config docs against the real format | low | fixes F10 |

**Step 1 should precede everything else.** It will report empirically how much of the
current suite passes on literal-string parameters rather than real values, which sizes
the remaining work.

---

## 6. Open decisions

Four questions must be answered before implementation begins.

1. **Binding profile location.** Should `BindingProfile` be a **separate operator file**
   (`--bindings profile.yaml`, as ADR-0019 §2 describes) or remain merged into the
   existing `--config` variables block? ADR-0019 explicitly left this open
   ("Open: exact binding-profile location"). The contract registry (§4 E) argues for the
   separate file: a flat `variables:` map cannot carry the nested `auth:` union, and the
   generated template needs somewhere of its own to be written.

2. **Strictness rollout.** Should strict resolution be **hard-fail** from the first
   release, or **warn-then-fail-at-end** for one release cycle? Hard-fail will break
   tests that currently report as passing while sending literal template strings.

3. **Are the contracts closed or extensible?** A closed registry gives the consistency
   this design is for, but a deployment needing one extra field per capability then has
   nowhere to put it. Recommendation: closed for v1, with the escape hatch being a new
   registry entry rather than an open `extra:` map — an open map reintroduces exactly the
   ambiguity being removed.

4. **Migration of the hand-declared SUT variables.** The CCM TCK declares
   `sut_counter_party_id` / `sut_counter_party_address` as `source: input` variables today.
   Should the contract keys be **aliased** to those names for one release, or should the
   TCKs be rewritten to reference `${{ infrastructure.sut.connector.counter_party_id }}`
   directly? (ADR-0019 §4's 2026-07 amendment already permits the direct form.)

## References

- [ADR-0019 — Service Requirements and Engine Bindings](decision-records/backend/ADR-0019-service-requirements-and-engine-bindings.md)
- [ADR-0018 — Unified Variables Model](decision-records/shared/ADR-0018-unified-variables-model.md)
- [ADR-0011 — Environment and Services](decision-records/shared/ADR-0011-environment-and-services.md)
- [ADR-0010 — YAML Syntax v2](decision-records/shared/ADR-0010-yaml-syntax-v2.md)
- [Backend Refactor Plan](refactor-plan/backend-refactor-plan.md)
