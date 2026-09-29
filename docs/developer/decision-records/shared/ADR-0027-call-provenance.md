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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0027: Proving the Product Made the Call — Hosted and Remote Runs

## Status

Proposed

## Date

2026-09-29

## Context

An assessment says that a product conforms to a standard. The question this
ADR answers is how the engine knows that the calls it graded were made by
that product, and not by a person with Postman or `curl`.

### What the engine can see today

In an inbound suite (CX-0135 certificate push, CX-0151 notification receipt,
CX-0127 Unique ID push) the mock sits behind an asset on the engine
connector. The access policy names the SUT's BPNL, and the mock requires the
run's API key, which only the asset's private data address carries (testlab
1.0.0a8). A call that reaches the mock therefore came through a data plane
that holds an EDR for this run's asset, negotiated by a connector that
presented the SUT's dataspace identity. The data plane can also forward the
consumer's BPN and agreement id, and the engine can check them against its
own connector.

### Why none of that proves the product made the call

Every one of those checks is about the **connector**, and the connector is
operated by the vendor. A person can open Postman against their own
connector's management API, request the engine's catalog, negotiate the
offer, read the EDR, and POST a body to their own data plane. The engine then
sees exactly what it would see if the product had done it: the right BPN,
the right agreement, the right key, the right run. There is no header, no
token and no timing the product produces that the person cannot produce as
well, because the person controls the connector *and* the product. A secret
placed in the product is a secret the product's owner can read.

This holds for any check the engine performs on what arrives. It is not a
gap in the current checks that a better check would close. It follows from
who controls the machine the call leaves. Only a party that controls where
the product runs can know that the product, and nothing else, made the call.

### Constraints

- The product speaks the Catena-X standards and nothing else. It does not
  know the engine exists, and no standard makes it carry an attestation.
- The test suite already runs its own dataspace identity services on its
  cluster (Tractus-X IdentityHub and IssuerService in
  `cx-playground-infra`), so it can issue a DID and credentials to a
  connector it deploys itself.
- The conformity assessment is done by a Conformity Assessment Body (CAB).
  The engine's report is evidence handed to that body.

## Decision

**A result is only called verified when the engine controlled where the
product ran. Every result carries its assurance level: `hosted` when the
engine ran the product in a sandbox it controls, `remote` when the product
ran at the vendor.** Remote runs keep their value as self-assessment, are
hardened against manual driving, and say plainly what they do not prove.

### Level `hosted`: the engine runs the product

The vendor hands over the product, not access to it. The engine deploys it
in a sandbox where the product is the only thing that can reach the SUT
connector.

1. **The product is submitted as images pinned by digest.** An OCI image or a
   Helm chart whose images are all pinned by `sha256` digest, plus a values
   file with the product's own configuration. Connector and identity settings
   are not in it; the engine supplies them.
2. **The engine provisions one namespace per assessment**, containing:
   - the product's pods, from the submitted digests;
   - a SUT connector, deployed by the engine from the same Tractus-X chart it
     uses for its own connector;
   - a dataspace identity for that connector: a DID and membership
     credential for a test BPNL, issued by the test suite's IssuerService;
   - a registry or other backend the kit's services require, where the
     product does not bring its own.
3. **The connector's secrets exist only inside the namespace.** The engine
   generates the management API key and the wallet credentials and injects
   them as Kubernetes secrets into the product's pods. They are never shown
   in the UI, the trace or the logs, and no person receives them.
4. **Network policy makes the product the only caller.**
   - The SUT connector's management API accepts connections only from the
     product's pods. It has no ingress, no port-forward and no route from
     outside the namespace.
   - Egress from the namespace goes only to the engine connector's DSP and
     data plane endpoints, the test suite's identity services, and the
     product's declared dependencies.
   - Nobody gets `exec`, a shell, or a Kubernetes credential for the
     namespace. The operator gets read-only logs.
5. **The operator uses the product, not the connector.** Where a kit hands
   something over for the SUT to hold (`with.source: register`) or asks for a
   business action, the operator does it through the product's own UI or API,
   which the engine exposes behind the engine login for the duration of the
   run and records in the trace. A person triggering the product is the
   product at work; a person reaching past it to the connector is what the
   sandbox rules out.
6. **The report names the digests.** A `hosted` result is issued to the image
   digests that ran, the chart version and the values file hash. A
   deployment with other digests is not what was assessed; the CAB can check
   that in an audit.

Under these rules, every call that reaches the engine connector from the SUT
connector was started by a process in the product's pods, because nothing
else can reach that connector's management API or hold its credentials.
That is the guarantee Postman cannot break.

The namespace is torn down when the run ends, the same way teardown removes
a run's assets today. Vendor code runs in the test suite's cluster, so the
sandbox also protects the cluster: a dedicated node pool, a sandboxed
runtime (gVisor or Kata), resource quotas, no service account token, and
deny-all network policy as the default.

### Level `remote`: the product runs at the vendor

Many products cannot be handed over as images: they are SaaS, depend on an
ERP, or are connectors themselves. They are still assessed, at level
`remote`, and the report says that the engine could verify the organisation
but not the program.

- **Organisation, agreement and run are checked.** The existing mock key and
  access policy stay. In addition, `mock/wait/dataplane/http_request`
  resolves the agreement id the data plane forwards on the engine connector,
  checks that its consumer is the bound `sut.connector` participant and its
  asset the one waited on, and publishes a `caller` output (`bpn`,
  `agreement_id`, `verified`) for the trace. Header names are confirmed on
  the first real push, as CX-0135's push test already notes.
- **Kits make driving by hand impractical.** A hand-driven pass should cost
  more than implementing the standard.
  - Per-run values the SUT must carry back (`util/generate_uuid`,
    `${{ execution.id }}`), so a collection recorded from one run fails the
    next.
  - Request and response chains through `labs/mock/api/dynamic`, so the
    SUT's next message depends on a reply it has not seen before.
  - Reaction windows short enough for software and too short for a person
    copying values between tabs, as a condition of the session rather than a
    conformance rule. A late reaction fails the session, not the standard.
  - Several reactions in one run where the standard allows it.
- **The operator declares.** Starting a remote assessment records the
  operator's declaration that the named product, unmodified, performed the
  run without manual intervention.

These measures stop a person with Postman. They do not stop a person who
writes a script that implements the protocol, and the ADR does not claim
they do. That residual is why the result is labelled `remote`.

### Who requires which level

The CAB decides, per standard, whether `remote` is acceptable or `hosted` is
required, and the engine enforces it: an assessment that requires `hosted`
cannot be started against a vendor-run SUT connector. The level is part of
the assessment record, the report and the certificate evidence.

### Alternatives rejected

- **Checks on the engine side alone** (key, policy, `Edc-Bpn`, agreement).
  They identify the connector, and the vendor drives the connector. They are
  kept for `remote`, never presented as proof of the program.
- **Client fingerprinting** (User-Agent, header order, TLS fingerprint). On a
  connector path the client is a data plane, not the product. On a direct
  path any tool sets the same values.
- **A required header, token or SDK inside the product.** Not in any
  standard. It would certify our library, and the product's owner can read
  any key the product holds.
- **Inspecting the SUT connector's management API.** Transfers started by the
  product and by Postman look the same there.
- **Remote attestation on the vendor's infrastructure** (confidential VMs or
  containers attesting an image digest). It would give `hosted` assurance
  without hosting, and is the right direction for products that cannot be
  handed over. It needs attestation infrastructure at every vendor and a
  verifier in the engine, so it is left for a later ADR.

## Consequences

### Positive

- `hosted` results carry a guarantee that holds against the product's owner:
  the calls came from the digests in the report, because nothing else could
  make them.
- `remote` results keep their use for self-assessment and for products that
  cannot be hosted, and no longer overstate what they prove.
- The CAB gets one field to reason about, the level, instead of inferring
  trust from a trace.
- Hosting also removes setup work from the vendor: no connector, identity or
  registry of their own is needed for an assessment.

### Negative

- The engine must deploy and isolate vendor code: namespace provisioning, a
  per-run connector and identity, network policy, a sandboxed runtime and
  image pulls from vendor registries. This is the largest piece of work in
  the ADR and the main cost.
- Not every product can be hosted. Products that depend on systems outside
  the sandbox need stubs or declared dependencies, and some can only ever
  reach `remote`.
- A hosted run assesses the product with the engine's connector, not the
  vendor's production connector. Connectors are assessed separately.
- A vendor could submit an image that relays whatever an operator sends. The
  report binds the result to that image; the CAB's audit of deployed digests,
  not the engine, catches a relay shipped as a product.
- Inbound kits become more involved for `remote`: minted values, dynamic
  mocks, paired tests and reaction windows.

### Neutral

- The mock key, the access policy and the teardown rules stay as they are
  and apply to both levels.
- Direct and outbound suites need no kit changes. They run against the hosted
  product the same way they run against a remote one.
- Which standards require `hosted` is the CAB's decision, documented in the
  assessment procedure, not here.
