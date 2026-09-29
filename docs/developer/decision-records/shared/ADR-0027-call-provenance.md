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

# ADR-0027: Call Provenance — the Product Made the Call, Not a Replay

## Status

Proposed

## Date

2026-09-29

## Context

An assessment says that a product conforms to a standard. The run reaches
that product over HTTP, and HTTP has no notion of *which program* sent a
request. Whatever a product sends, `curl` or a Postman collection can send
byte for byte. A vendor could therefore pass an inbound suite without the
product ever taking part: read the run wizard's SUT Setup step, drive their
own connector's management API by hand (negotiate the engine's offer, fetch
the EDR), call the mock through their data plane with a body copied from a
previous run, and collect the report. Outbound suites have the mirror image:
the thing answering the engine's connector may be a stand-in server, not the
product.

What the runs already establish, and what they do not:

- **Inbound suites** (CX-0135 certificate push, CX-0151 notification receipt,
  CX-0127 Unique ID push) never hand out the mock URL. The mock sits behind an
  asset on the engine connector, under an access policy that names the SUT's
  BPNL, and requires the run's API key, which only the asset's private data
  address carries (testlab 1.0.0a8). A keyless call is refused with 401 and
  fails the open wait at once (`MOCK_CALL_REFUSED`). This proves that the
  call came through a data plane holding an EDR for *this run's* asset, and
  that the connector which negotiated it presented the SUT's dataspace
  identity. It says nothing about the software behind that connector.
- **Outbound suites** negotiate with the SUT's connector over DSP. The
  dataspace verifies that connector's identity (its membership credential),
  so the counterparty *organisation* is proven. Which backend served the
  data behind the connector is not.
- **Direct suites** (CX-0002 registry, OAuth2-protected) call the SUT as a
  server. Replay does not apply; a stand-in does, as for outbound suites.

The constraints are fixed by what the assessment is for. The product speaks
the Catena-X standards and nothing else: it does not know the engine exists,
and no standard makes it send a header, token or attestation that a script
could not send too. Requiring one would certify our SDK, not the vendor's
product. There is therefore no purely technical proof that the product made
the call, and a decision that pretends otherwise would be wrong. What the
runs *can* do is make a hand-driven pass expensive, leave evidence that a
reviewer can weigh, and bind the result to a named product and a named
connector so that a replay is a false declaration rather than a gap in the
test.

The conformity assessment itself is done by a Conformity Assessment Body
(CAB). The engine's report is evidence handed to that body, not the
certificate. The decision below is written for that division of labour.

## Decision

**We do not try to recognise the client at the HTTP layer. We bind every
call to an identity and a run, write kits so that a pass cannot be replayed
from a recording, and record evidence a reviewer can act on.** Three layers,
each with an owner.

### 1. Every call is bound to an identity and a run (testlab, engine)

The mock key already binds a call to the run. The wait step will also bind it
to the organisation and to the agreement:

- `mock/wait/dataplane/http_request` reads the consumer's identity from what
  the engine connector's data plane adds to the forwarded call. The Tractus-X
  data plane forwards the negotiating party's BPN and the agreement id as
  request headers (`Edc-Bpn`, `Edc-Contract-Agreement-Id`); the exact names
  are confirmed on the first real push, as CX-0135's push test already
  notes, and are looked up in one place rather than in every kit.
- The step resolves the agreement id on the engine connector's management API
  (`/v3/contractagreements/{id}`) and checks that the agreement's consumer is
  the bound `sut.connector` participant and its asset is the one waited on.
  A call whose agreement belongs to another party, another asset or another
  run is refused the way a keyless call is: the wait fails at once with the
  reason, it does not time out.
- The step publishes a `caller` output — `bpn`, `agreement_id`, `verified`
  — so a kit can assert on it and the trace records it (ADR-0016). Where the
  data plane forwards nothing, `verified` is false and the report says so;
  the run does not invent a caller.
- Outbound steps already hold the agreement they negotiated. `caller` gets
  its counterpart there, `counterparty`, taken from the agreement's provider
  id, so every exchange in a report names the organisation on the other side.

This closes "someone else's connector" and "an EDR from an earlier run". It
does not close "the right connector, driven by hand", which layers 2 and 3
address.

### 2. Kits are written so a recording cannot pass them (kits, testlab)

A collection captured from one run must not pass the next. Kit authors apply
these rules; static inspection (ADR-0022) warns where it can see they were
not.

- **Per-run values the SUT must carry back.** Anything the engine sends that
  the SUT must answer carries a value minted for this run
  (`util/generate_uuid`, `${{ execution.id }}`): a request id, a
  notification id, a certificate type or BPNL chosen for the run, a
  correlation id. The assertions compare against that value, never against a
  literal the last run also used. A replayed body carries the old value and
  fails.
- **Chains, not single shots.** Where the standard has a request/response or
  push/status pair, the kit tests the pair: the engine's reply is worked out
  from what the SUT sent (`labs/mock/api/dynamic`), and the SUT's next message
  must depend on that reply. A collection cannot precompute a reply it has
  not seen.
- **Reaction windows.** A message that is a *reaction* to something the engine
  sent (a status after a push, a response to a request) is waited on with a
  short window, distinct from the setup window a human needs to register an
  offer. The window is a property of the assessment session, set by the
  operator, not a normative requirement from the standard: a reaction that
  arrives late does not fail conformance, it fails the session, and the
  report says which reactions were late. Software answers in seconds; a
  person copying values between tabs does not.
- **Unsolicited messages are marked as such.** A test the engine cannot
  seed — a provider push that the standard leaves unsolicited, as CX-0135's
  push is in Saturn — proves delivery of a well-formed message by the
  organisation's connector, and no more. Its description says so, and the
  report weighs it as delivery evidence rather than as proof of behaviour.

### 3. The result is bound to a named product, with evidence a person reviews (engine, procedure)

- **The assessment names the product.** An assessment carries the product's
  name, version and vendor, and the SUT connector record it ran against. The
  report is issued to that product and connector, and the trace records, for
  every inbound call, the caller identity and agreement from layer 1 and the
  time elapsed since the engine action it reacts to.
- **The vendor declares.** Starting an assessment run records the operator's
  declaration that the named product, unmodified, performs the exchanges of
  the run without manual intervention. A replay is then a false declaration
  toward the CAB, with the trace as the record against which it is checked.
- **The CAB may witness.** The live trace (ADR-0003) and interactive
  sessions (testlab 1.0.0a11) already let a reviewer watch a run as it goes.
  A witnessed session, where the CAB observes the product's own screens or
  logs alongside the trace, is the assessment body's procedure to require;
  the engine provides the trace and marks the session as witnessed when the
  CAB says so.

### Alternatives rejected

- **Client fingerprinting** (User-Agent, header order, TLS fingerprint). On
  every connector path the client is a data plane, not the product, so
  there is nothing of the product to fingerprint; on a direct path the
  values are trivially set by any tool and differ across proxies, so a
  fingerprint would fail conformant products and pass replays.
- **A required header, token or SDK inside the product.** Not in any
  standard; it would certify our attestation library rather than the
  vendor's implementation of the standard, and a script would send the same
  header.
- **Inspecting the SUT connector's management API.** The engine holds the
  SUT connector's management URL for outbound suites, and could read the
  transfer processes behind an inbound push. They look the same whether the
  product or a person started them, so the check would prove nothing and
  would give inbound suites a dependency on management access they do not
  otherwise need.
- **Timing as the verdict.** A fast script beats a slow product. Timing is
  evidence in the report and a session condition (layer 2), never a
  conformance failure on its own.

## Consequences

### Positive

- Every inbound call in a report names the organisation and the agreement it
  came through, checked against the engine connector, not inferred from
  headers alone. "Which connector" and "which run" are settled technically.
- A collection recorded from one run fails the next by construction, so a
  hand-driven pass costs a person a live, interactive session against per-run
  values, under a window and a declaration. That is the deterrent HTTP
  allows.
- The division of labour is explicit: the engine proves identity, run and
  timing; the kit proves behaviour that cannot be precomputed; the CAB
  weighs the evidence and holds the vendor to its declaration. Nobody has to
  believe the engine proves what it cannot.

### Negative

- There is no absolute proof, and the ADR says so. A person with the right
  connector, enough time and a live session can still pass a suite by hand.
  The declaration and the witnessed session, not the engine, carry that case.
- Inbound kits become more involved: dynamic mocks, minted values, paired
  tests and two windows instead of one. Existing inbound suites (CX-0127,
  CX-0135, CX-0151) need a pass to adopt the rules.
- Layer 1 depends on what the Tractus-X data plane forwards. The header names
  are confirmed against a real push before any kit asserts on them; a
  deployment whose data plane forwards nothing gets `verified: false` in its
  reports rather than a pass.
- The engine gains an assessment field set (product name, version, vendor,
  declaration) and a report section; the wizard gains the declaration step.

### Neutral

- The mock key and the access policy stay as they are; layer 1 adds to them.
- Direct and outbound suites change only in what the report records
  (`counterparty`); their assertions do not change.
- Whether a witnessed session is required, and for which standards, is the
  CAB's decision and is documented in the assessment procedure, not here.
