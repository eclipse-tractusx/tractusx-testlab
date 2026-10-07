<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0019: Service Requirements and Engine Bindings

## Status

Proposed (amends ADR-0011 §1–§4)

## Date

2026-06-04

## Context

ADR-0011 places the full service configuration — URLs, paths, auth, credentials — inside
every TCK manifest (`env.services`). In practice this configuration is identical across most
TCKs: a connector is a connector regardless of which standard is being certified. Repeating it
per TCK is redundant, couples reusable test content to one deployment, and forces test authors
to handle infrastructure secrets they should never see.

Two distinct concerns are conflated today:

1. **What a TCK needs** — an abstract capability ("an EDC connector, Saturn, CX-0018"). Stable,
   portable, authored once by the test author.
2. **How that capability is satisfied** — concrete endpoint, paths, and credentials. Volatile,
   deployment-specific, supplied by the operator running the run.

The wider ecosystem separates these the same way: Helm/npm `peerDependencies` (declare a
requirement, the consumer provides the instance), Kubernetes resource *requests* vs the cluster
that *schedules* them, Terraform `required_providers` vs provider config, and ports-and-adapters
dependency injection (required interface vs bound implementation).

A second case is the System Under Test. Almost every TCK needs the SUT to expose a connector to
TestLab. That is not TestLab configuration — it is a requirement the operator must satisfy
before the run, declared as a requirement and surfaced to steps as a variable (ADR-0018), not
configured as a service.

A third case is the **dataspace** itself — which ecosystem and version the run targets (e.g.
Catena-X, saturn). This is not a service to bind; it is the *context* the engine and SUT are
certified within. It belongs at the top level, alongside `infrastructure`, and supplies the
default `version`/`ecosystem` that capability constraints inherit.

## Decision

Declare the topology with two top-level blocks. `dataspace:` states the ecosystem context
(`ecosystem`, `version`). `infrastructure:` names the two bindable sides — `engine` (what the
embedding host operates, i.e. TestLab as a library) and `sut` (what the System Under Test must
provide). Under each side, capabilities are keyed by name; there is no `name`, `role`, or list.
The operator supplies concrete `bindings` mirroring the `infrastructure` structure.

The side is named `engine`, not `testlab`, so the manifest stays host-agnostic: TestLab remains a
library that any embedding system can drive without the YAML hardcoding the product name. Side
keys are plain identifiers (`engine`, `sut`) — not hyphenated — so they stay valid in
`${{ ... }}` dot-path references.

### 1. Requirements — TCK level, keyed by side and capability

The capability is the key, so it never repeats as a field. The value is always an object with an
explicit `required` flag plus optional constraints. Direction (provider vs consumer) is **not**
modelled here — a connector is one engine-side instance, and how a step drives it is decided per
step.

```yaml
dataspace:                  # ecosystem context the run targets
  ecosystem: Catena-X
  version: saturn

infrastructure:
  engine:                   # infrastructure the embedding host (TestLab) operates
    connector:
      required: true
      standard:
        id: CX-0018
        version: 2.1.3

  sut:                      # what the operator must provide → request variables
    connector:
      required: true
      standard:
        id: CX-0018
        version: 2.1.3
    dtr:
      required: true
      standard:
        id: CX-0002
        version: 1.0.0
```

`required: false` declares a capability the TCK knows about but does not require for this run — so
`required` is also how a dependency is marked required (`true`) vs optional (`false`).
The `standard` constraint is optional and only worth writing when the TCK genuinely certifies
against a specific standard — typically the SUT capability under test. It is an object with the
standard `id` and `version`; when `standard.version` is omitted it inherits from
`dataspace.version`. The common case is just `required: true`.

The `required` flag exists because not every certification needs every capability. A connector is
only relevant when the test performs connector-mediated data exchange (DSP contract negotiation,
transfer). Many TCKs certify capabilities that authorize and operate **without** a connector — for
example Discovery Finder, BPN/EDC discovery, or shared services such as BPDM — where access is
governed by IAM (OAuth2/OIDC token) rather than connector contract authorization. Such a TCK marks
`connector: { required: false }` (or omits it) and the engine neither demands a connector binding
nor accepts connector steps, while still requiring the capabilities those tests do exercise.

Capability keys come from a registry. Per side:

| Side | Typical capabilities |
|------|----------------------|
| `engine` | `connector`, `dtr` |
| `sut` | `connector`, `dtr` |

The mock server is **not** a bindable capability — it is the engine's own built-in component
(TestLab operates it internally), so it is never declared here or in `bindings`.

### 2. Engine Bindings — operator level, same structure

The operator supplies one binding profile mirroring the `infrastructure` shape — same sides, same
capability keys. Secrets stay here, never in the portable TCK.

```yaml
bindings:
  engine:
    connector:
      base_url: https://connector.local
      management_path: /management/v3
      dsp_path: /api/v1/dsp
      auth: { type: api_key, api_key: ${ENV_PROVIDER_KEY}, api_key_header: X-Api-Key }
  sut:
    connector:
      dsp_url: https://sut.example.com/api/v1/dsp
      bpn: BPNL000000000SUT
```

### 3. Matching and validation (fail fast)

Before a run the engine resolves every required `infrastructure.<side>.<capability>` against the
matching `bindings.<side>.<capability>`, checks each constraint, and aborts with a typed error on
any unbound or violated requirement. Unbound `sut` capabilities surface as unresolved `request`
variables for the operator to fill (ADR-0021), not configuration errors.

At boot the engine announces this resolved topology once via `tck.boot.requirements` (ADR-0016) \u2014
each side's capabilities with their `required` flag (`true` = enabled, `false` = declared but not
exercised) \u2014 so the operator and any client know up front what each side, especially the SUT, must
provide. Engine-operated components it then starts (the connector service client, the built-in mock
server) are logged via `tck.boot.service.*`, distinct from the endpoint validation of
`tck.boot.binding.*`.

### 4. Steps reference variables, never infrastructure or bindings

> **Amendment (2026-07):** The strict separation below is the *recommended* architecture for
> production TCKs. In practice, V2 test files MAY reference `${{ infrastructure.<side>.<capability>.<field> }}`
> directly as a convenience — the player seeds these from the operator's binding profile into
> the variable context at boot time. This shorthand avoids requiring authors to redeclare every
> infrastructure field as an explicit `env` variable. The compiler and player resolve these
> identically to `env.*` references. See ADR-0010 Appendix A.4.

A step's only reference surface is a **variable** (ADR-0018) — `${{ env.<name>.<field> }}` or
another step's output. Steps never name `infrastructure.*` or `bindings.*`; that topology is
engine-internal. The two sides surface to authoring differently:

- **Engine side is hidden plumbing, injected by capability.** The player resolves the engine
  binding from the operator profile and **injects** it into a step by the step's capability — a
  `connector/*` step drives `engine.connector`, a `dtr/*` step drives `engine.dtr` — with no handle
  in the step. The injection happens once at boot and is recorded there (`tck.boot.binding.*`,
  ADR-0016): non-secret config (urls, paths, bpn, version) in the event `outputs`, secret fields
  (`auth`, credentials) JWE-encrypted. This honours "hide plumbing" — authors never wire the
  engine's own connector or DTR into a step, and the concrete EDC/DTR config enters the run in
  exactly one place.
- **SUT side surfaces as a variable.** Each required `infrastructure.sut.<capability>` resolves to a
  variable: `known` when the operator pre-supplied a binding, `request` when unbound (the operator
  fills it at run start). A step targets the SUT by referencing that variable's fields, e.g.
  `${{ env.sut_connector.counter_party_address }}`.

What a step *references* is always a variable, never the capability handle.

A capability gates its own steps. A step may only be used when its capability is declared
`required: true` on the relevant side. If a TCK uses a step whose capability is missing or
`required: false`, the compiler aborts with a typed error naming the step and the capability it
needs. There is no implicit enablement: using a step is the contract that its capability must be
required.

## Consequences

- TCKs become portable: the same TCK runs against any deployment by swapping the binding profile.
- A capability gates its steps: a step whose capability is not `required: true` cannot be used,
  failing fast at compile time with a typed error — no silent no-ops at runtime.
- Test authors never touch URLs or secrets; operators own all deployment configuration.
- The keyed form is minimal — a typical TCK nests `connector: { required: true }` under
  `infrastructure.engine` and `infrastructure.sut`; the `standard` constraint is an object
  (`id`, `version`) whose `version` inherits from `dataspace.version` and is spelled out only when
  a capability certifies a specific standard.
- `dataspace.version` is the single source of the ecosystem version; the old
  `metadata.dataspace_version` is removed — nothing duplicates it.
- SUT requirements unify with the variables model (ADR-0018, ADR-0021) — an unbound
  `infrastructure.sut` capability surfaces as a `request` variable the operator fills at run start,
  and steps reference that variable, never the capability handle.
- Engine EDC/DTR configuration enters the run in exactly one place — injected by capability at boot
  and recorded in `tck.boot.binding.*` (ADR-0016), with secret fields JWE-encrypted — so the
  concrete config never appears in authored YAML or per-step inputs.
- ADR-0011 §1–§4 (full config in `env.services`) is superseded; a migration converts existing
  `env.services` into the `infrastructure` block plus a default binding profile.
- One capability = one instance per side. A TCK that genuinely needs two distinct connectors on
  the same side is out of scope; revisit with explicit provider/consumer keys only if a real case
  appears (deliberately deferred — do not pre-build it).
- New maintained surfaces: the capability registry and the binding-profile schema/loader.
- Open: exact binding-profile location (CLI flag, engine config file, or env injection).
