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
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and tested by a human committer. -->

# Certificate Management — Business Guide

This page explains what the Certificate Management TCK certifies, and why that matters. It has no code. To run the suite, see the [Developer Guide](ccm-developer-guide.md).

## Why it matters

Suppliers in Catena-X must show their customers certificates such as ISO 9001, IATF 16949 or ISO 14001. The standard **CX-0135** (Company Certificate Management) defines how they do it. Partners do not email documents. They exchange structured messages through the **Company Certificate Management API (CCMAPI)**. Each partner's **connector** protects its API, and data flows only after the two sides agree on a usage policy.

If a provider's implementation does not follow the standard, customers cannot automate certificate exchange with it. The TCK finds those gaps before a business partner does.

## What a passing run certifies

The TCK tests the **provider**: the company whose connector and CCMAPI implementation is the system under test (SUT). TestLab plays the customer. A run passes only when all four tests pass. No test can be skipped.

| Test | What TestLab checks | What a pass means for the business |
| --- | --- | --- |
| **Catalog Policy Validation** | The provider's connector offers a CCMAPI asset. The offer is made under the CX-0135 usage policy (purpose `cx.ccm.base:1`, Data Exchange Governance framework agreement 1.0). TestLab can agree to it and receive access. | Customers can find the certificate service and connect to it on standard terms, without extra negotiation. |
| **Request Certificate** | A certificate request sent through the connector gets a successful, well-formed answer. That answer is also checked against the Business Partner Certificate data model. | Customers can ask for a certificate, and the answer is machine-readable. |
| **Send Feedback Notification** | The provider accepts a status notification about a certificate (for example "accepted"). It then sends TestLab a well-formed acknowledgement that names the right partners, message version and status. | Both sides agree on where a certificate stands, with no manual follow-up. |
| **Error Handling** | A request for a certificate type that does not exist is answered with a proper rejection, not an error or a silent acceptance. | Bad requests are refused clearly, so a customer knows to fix them. |

Each result is **Pass** or **Fail**, at test level and at check level. A failed check names the value TestLab expected and the value it got. The report also flags a test whose checks never ran, for example because the connector could not be reached. Such a test is not a pass: it verified nothing about the provider.

## What it does not certify

This version of the suite covers the four exchanges above and nothing else. In particular, it does **not** test:

- A provider pushing a new or renewed certificate without being asked
- A provider announcing that a certificate is available for download
- Downloading the certificate document itself
- The provider acting as a *customer* of someone else's certificate service

A passing run says nothing about those areas.

## What the provider must have in place

Before a run can succeed, the provider needs:

- **A connector on the dataspace**, reachable by TestLab, with a known Business Partner Number (BPNL).
- **One CCMAPI asset** in that connector's catalog, described as the Company Certificate Management notification API, version 3.0.
- **The CX-0135 usage policy** on that offer. It must match exactly: an offer with extra or different constraints is not accepted.
- **A CCMAPI implementation behind the connector** that answers certificate requests and status notifications, and rejects unknown certificate types.
- **Network reach back to TestLab**, because the acknowledgement is an inbound call from the provider to TestLab.

The operator running the test also gives TestLab its own connector and the partner details. The [Developer Guide](ccm-developer-guide.md) lists every value.

## Glossary

| Term | Meaning |
| --- | --- |
| **BPNL** | Business Partner Number (legal entity): a company's unique ID in Catena-X |
| **BPNS** | Business Partner Number (site): the ID of one location of a company |
| **CCMAPI** | Company Certificate Management API, the interface CX-0135 defines |
| **Connector (EDC)** | The Eclipse Dataspace Connector, a gateway that publishes offers, negotiates usage policies and grants access to data |
| **Usage policy** | The terms under which a connector offers data, for example "for certificate management only" |
| **SUT** | System under test: the provider's connector and CCMAPI implementation |
| **TCK** | Test Case Kit: a versioned package of tests that checks conformity with a standard |
| **CX-0135** | The Catena-X standard for Company Certificate Management |
