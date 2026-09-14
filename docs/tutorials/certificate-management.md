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

# Certificate Management (CX-0135)

TestLab ships a Certificate Management TCK, `certificate-management-tck-v0.0.1`. It checks a provider's Company Certificate Management API (CCMAPI) against **CX-0135 v3.1.0**. Every call goes through the provider's Eclipse Dataspace Connector. The suite lives at `docs/examples/certificate-management-v2/raw/` and holds four tests:

| Order | Test | Proves |
| --- | --- | --- |
| 1 | Catalog Policy Validation | The CCMAPI offer can be found and is made under the CX-0135 usage policy |
| 2 | Request Certificate | A certificate request through the data plane is answered |
| 3 | Send Feedback Notification | A status notification is accepted and acknowledged back to TestLab |
| 4 | Error Handling | A request for an unknown certificate type is rejected |

## Which page to read

| Page | Read it for |
| --- | --- |
| [Business Guide](ccm-business-guide.md) | What a passing run certifies, what it does not, and what the provider must have in place |
| [Developer Guide](ccm-developer-guide.md) | Configuring a run, running it, reading the results, and fixing failures |
| [Architecture Guide](ccm-architecture-guide.md) | How the suite is built: manifest, test phases, the connector flow, mocks and callbacks |
| [CCM Conformity Testing](ccm-conformity-testing.md) | Test-by-test reference: every step, every check, every value it reads |

## At a glance

```bash
# Check the manifest and its tests against the syntax and the step registry
testlab validate docs/examples/certificate-management-v2/raw/index.yaml

# Build a package and list what a run of it will ask for
testlab compile docs/examples/certificate-management-v2/raw/index.yaml --output ccm.tck
testlab inspect ccm.tck --variables --infrastructure

# Run it (see the Developer Guide for run-config.yaml)
testlab run docs/examples/certificate-management-v2/raw/index.yaml --config run-config.yaml
```
