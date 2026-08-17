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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# How to Add a New Service Type

Service types describe the external systems a test run connects to. The `ServiceManager` registers each `ServiceDefinition`, initialises the SDK client lazily on first access, and caches it for the lifetime of the execution.

## Step 1 — Define the service type

In `src/tractusx_testlab/models/primitives/enums.py`, add the new member to `ServiceType`:

```python
class ServiceType(str, enum.Enum):
    """Type of dataspace service a participant can expose."""

    CONNECTOR_CONSUMER = "CONNECTOR_CONSUMER"
    CONNECTOR_PROVIDER = "CONNECTOR_PROVIDER"
    DTR = "DTR"
    ...
    MY_SERVICE = "MY_SERVICE"  # ← add this
```

## Step 2 — Wire the instance creation in the factory

Service instantiation lives in `src/tractusx_testlab/services/_factory.py`. `create_instance()` dispatches on the definition's type; add a branch and a creator:

```python
def create_instance(
    service_definition: ServiceDefinition, expected_type: Optional[ServiceType] = None,
) -> object:
    """Create a live SDK service from a ServiceDefinition."""
    stype_val = service_definition.type.value

    if stype_val in _CONNECTOR_COMPATIBLE_TYPES:
        return _create_connector_service(service_definition, expected_type)
    if stype_val in _DTR_COMPATIBLE_TYPES:
        return _create_aas_service(service_definition)
    if stype_val == "MY_SERVICE":                       # ← add this
        return _create_my_service(service_definition)   # ← add this
    ...
```

The creator reads `base_url`, `auth`, and `params` off the `ServiceDefinition` and returns the live client — follow `_create_aas_service` as the template.

## Step 3 — Declare type compatibility (if any)

Steps request a service with an expected type, and `is_type_compatible()` in the same file decides which declared types satisfy that request (for example, the generic `EDC_CONNECTOR` satisfies both `CONNECTOR_CONSUMER` and `CONNECTOR_PROVIDER`). If your new type has aliases or role variants, add a compatibility set alongside `_CONNECTOR_COMPATIBLE_TYPES` and `_DTR_COMPATIBLE_TYPES`; otherwise exact equality already holds and nothing is needed.

## Step 4 — Expose it to steps

Steps never name a service — they ask their `StepContext` for the seeded service of a type. Add an accessor in `src/tractusx_testlab/player/execution/context.py`, next to the existing ones:

```python
def get_my_service(self) -> object:
    """Return the MY_SERVICE service the run was seeded with."""
    return self._first_service_of_type(ServiceType.MY_SERVICE)
```

A step executor then calls `context.get_my_service()`.

## Step 5 — Test

```bash
poetry run pytest -k service
```

> **Note:** The IDE's service configuration form (schemas, dialog fields) lives in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository and is extended there.
