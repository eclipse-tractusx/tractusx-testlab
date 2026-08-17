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

# Infrastructure Bindings

> How the deployment a run targets is configured, and how it reaches a step.

A TCK declares *what* it needs — `infrastructure.sut.connector.required: true` —
and never says where that connector is. Where it is comes from whoever operates
the engine, as a **binding**: a typed object naming the engine's own connector,
registry and submodel server, and the system under test. Requirements are
authored; bindings are operated. The two meet once per run, before the first
step.

## The model

```text
Infrastructure
├── engine                 # infrastructure TestLab operates — it holds credentials
│   ├── connector          # management_url, api_key, api_key_header,
│   │                      # participant_id, dsp_url, name
│   ├── dtr                # base_url
│   └── submodel_server    # base_url
└── sut                    # infrastructure TestLab talks to — an identity and an endpoint
    ├── connector          # same fields as above
    └── dtr                # base_url
```

Every capability, on both sides, additionally carries **`version`**,
**`standard`** and **`standard_version`** — see [What a run certifies
against](#what-a-run-certifies-against).

The asymmetry is deliberate (ADR-0019 §4). The engine side is driven through
management APIs, so it carries credentials — and it has a registry of its own,
alongside the connector and the submodel server. The SUT side is a
counter-party reached over DSP. The submodel server is engine-only: the engine
hosts the data a test provisions, and a test that could name its own backend
would be testing an address rather than the provider's.

## What a run certifies against

Where a deployment *is* comes from the operator. What it is expected to
*implement* comes from the TCK, and travels onto the bindings at run start:

| Binding field | Filled from | Meaning |
|---|---|---|
| `version` | `dataspace.version` | Ecosystem release — `saturn` or `jupiter`. **Picks the SDK dialect built for the capability.** |
| `standard` | `infrastructure.<side>.<cap>.standard.id`, else the capability's usual standard | `CX-0018` for a connector, `CX-0002` for a registry |
| `standard_version` | `…standard.version`, inheriting `dataspace.version` when omitted | Version of that standard, e.g. `2.1.3` |

So a TCK declaring `dataspace: {version: jupiter}` gets Jupiter connector
services without anyone repeating "jupiter" in a config file — the release
reaches the SDK through the binding, and a step never names a dialect.

An operator who knows better may state any of the three on the binding and it
is kept. Stating one that *contradicts* what the TCK certifies — a Jupiter
connector under a Saturn TCK — raises `StandardConflictError` before the first
step, because such a run cannot prove what it claims.

What each release means concretely lives in one table,
[`infrastructure/standards.py`](../../src/tractusx_testlab/infrastructure/standards.py):
the connector dialect the SDK builds, and the AAS API path a registry answers
on. A new ecosystem release is an entry there rather than a branch in the
seeder.

## One field, three surfaces

Every binding field appears in three places, and all three are **generated from
the model** — there is no lookup table, so they cannot drift apart:

| Surface | Form | Example |
|---|---|---|
| Config file | `<side>.<capability>.<field>` | `sut.connector.dsp_url` |
| Context variable / `--var` | `infrastructure.<side>.<capability>.<field>` | `infrastructure.sut.connector.dsp_url` |
| Environment variable | `TESTLAB_<SIDE>_<CAPABILITY>_<FIELD>` | `TESTLAB_SUT_CONNECTOR_DSP_URL` |

A key that names no field is rejected where it is written, with the accepted
keys listed beside it. A misspelled `managment_url` used to be dropped in
silence and surface as an empty URL twenty steps later.

## The four doors, in precedence order

Lowest to highest — each layer writes over the one below it, and a layer that
states nothing about a field leaves it alone:

1. **`testlab.config.yaml`** — the whole deployment, under an `infrastructure:` block:

   ```yaml
   infrastructure:
     engine:
       connector:
         management_url: https://engine.example.com/management
         api_key: engine-key
         participant_id: BPNL000000000TLB
       submodel_server:
         base_url: https://backend.example.com
       dtr:
         base_url: https://engine.example.com/semantics/registry
     sut:
       connector:
         management_url: https://sut.example.com/management
         participant_id: BPNL000000000001
         dsp_url: https://sut.example.com/api/v1/dsp
         # version / standard / standard_version are normally left out —
         # they come from the TCK. State one only to override it.
   ```

2. **Environment** — single fields of it, which is how one container image is
   pointed at a different connector per stage:

   ```console
   $ export TESTLAB_SUT_DTR_BASE_URL=https://sut.example.com/semantics/registry
   ```

3. **The embedding application** — see below.

4. **The run** — `--var infrastructure.sut.dtr.base_url=…`, the same keys in a
   run-config's `variables:` block, or `runtime_vars` over the HTTP API. These
   apply to that run only; the registered deployment is not modified.

## Embedding the player

An adopter states the deployment by handing the player an
`InfrastructureManager`. It is an object, not a name — the deployment is
constructed and type-checked by the caller, not looked up out of a string:

```python
from tractusx_testlab import (
    ConnectorBinding, DtrBinding, EngineBindings, Infrastructure,
    InfrastructureManager, SubmodelServerBinding, SutBindings, TestlabPlayer,
)

integration = Infrastructure(
    engine=EngineBindings(
        connector=ConnectorBinding(
            management_url="https://engine.example.com/management",
            api_key="engine-key",
            participant_id="BPNL000000000TLB",
        ),
        submodel_server=SubmodelServerBinding(base_url="https://backend.example.com"),
    ),
    sut=SutBindings(
        connector=ConnectorBinding(
            management_url="https://sut.example.com/management",
            participant_id="BPNL000000000001",
            dsp_url="https://sut.example.com/api/v1/dsp",
        ),
        dtr=DtrBinding(base_url="https://sut.example.com/semantics/registry"),
    ),
)

infrastructure = InfrastructureManager(integration, name="integration")
infrastructure.register("staging", staging_deployment)

player = TestlabPlayer(infrastructure=infrastructure)
result = await player.run("my_tck.yaml")

infrastructure.activate("staging")          # same player, next deployment
```

The manager holds several deployments in memory at once, which is the point of
the registry: running the same TCKs against local, integration and staging is a
call to `activate`, not a second player.

Omitting the argument builds a manager from the engine's own configuration, so
a CLI or server run needs no code at all.

## What happens at run start

1. The active deployment is taken as the starting point.
2. The run's own `infrastructure.*` variables are written over it.
3. Every capability the TCK marks `required: true` is checked against the
   result. An unbound one raises `MissingBindingError` **before the first
   step**, naming every missing capability at once and the key each one owes.
4. The release and standards the TCK certifies against are written onto every
   bound capability that does not state its own; a binding that contradicts
   them raises `StandardConflictError`.
5. The resolved deployment is published back into the variable namespace, so
   `${{ infrastructure.sut.connector.dsp_url }}` resolves identically whether
   the value came from a profile, the environment, or the CLI.
6. SDK services are registered from the typed bindings — the engine connector as
   consumer, the SUT connector as provider, the registries as DTR, each built
   for the release its binding carries.

A step reads engine-side infrastructure from `context.infrastructure` rather
than from a variable a script supplied, because where the engine's own backend
lives is the operator's decision and not the test's.

## Reading the requirements off a package

An operator meets a TCK as a compiled `.tck`, and the first question they ask
of it is what they have to bind. The compiler answers it in the package
manifest, so nothing has to be decompiled to find out:

```yaml
tck:
  id: certificate-management-tck-v0.0.1
  dataspace:
    ecosystem: Catena-X
    version: saturn
  infrastructure:
    engine:
      connector: {required: true, standard: {id: CX-0018, version: v4.2.0}}
    sut:
      connector: {required: true, standard: {id: CX-0018, version: v4.2.0}}
```

The section is **resolved, not copied**: a TCK may state its requirements once
at the manifest level or leave each test to state its own, and the compiler
applies the same rule the player applies at run start — the manifest-level
block wins when present, per-test blocks are merged otherwise
(`required: true` wins, the first stated `standard` wins). So what the package
says is what step 3 above will demand.

Both keys are omitted when the TCK states nothing: an empty requirement set is
a TCK that binds nothing, and a release nobody named is the engine's default
rather than a claim the package makes. The same view is available without
unzipping anything:

```bash
testlab inspect certificate-management.tck --infrastructure
```

## References

- [ADR-0019 — Service Requirements and Engine Bindings](decision-records/backend/ADR-0019-service-requirements-and-engine-bindings.md)
- [Environment & Context Injection — Analysis Report](environment-injection-analysis.md)
