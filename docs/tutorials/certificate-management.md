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
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# Certificate Management — Documentation

For documentation on the Certificate Management (CX-0135) test suite, see the audience-specific guides:

- **[Business Guide](ccm-business-guide.md)** — For product managers, certification officers, and business stakeholders
- **[Developer Guide](ccm-developer-guide.md)** — For developers running and debugging tests
- **[Architecture Guide](ccm-architecture-guide.md)** — For architects designing test suites and integrations

For the detailed test reference, see [CCM Conformity Testing](ccm-conformity-testing.md).

## Where is the IDE?

The visual TestLab IDE (Blockly-based authoring and execution monitoring) lives in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository. This repository contains the TestLab **engine**: the `tractusx_testlab` Python package, the `testlab` CLI, and the backend server the IDE connects to (`testlab serve`).

To run the shipped Certificate Management suite from the engine CLI:

```bash
# Validate the suite without executing it
testlab validate docs/examples/certificate-management-v2/raw/index.yaml

# Compile it into a distributable .tck package
testlab compile docs/examples/certificate-management-v2/raw/index.yaml

# Execute it (variables can come from a config file or --var KEY=VALUE)
testlab run docs/examples/certificate-management-v2/raw/index.yaml --config run-config.yaml
```
