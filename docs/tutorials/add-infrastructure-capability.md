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

# Add an Infrastructure Capability

A test never names the connector or registry it talks to. The TCK **requires** capabilities (`infrastructure.sut.connector.required: true`). Whoever runs the engine **binds** them to real addresses through a config file, `TESTLAB_*` environment variables or the embedding API. At run start the player **seeds** one SDK service per bound capability, and steps reach those services through `context.dataspace`. See [Infrastructure Bindings](../developer/infrastructure-bindings.md) and ADR-0019.

Today the capabilities are `connector` and `dtr` on both sides. This tutorial adds a SUT-side Discovery Finder, `sut.discovery_finder`. Follow `dtr` through the same files as your reference; it is the closest existing capability.

Adding a capability changes what a TCK may declare, so agree on the name and side first. Capability keys are public contract, like step ids.

## What changes, and what doesn't

| File | Change |
|---|---|
| `models/domain/capabilities.py` | the binding model: the fields an operator supplies |
| `models/domain/infrastructure.py` | one field on `SutBindings` or `EngineBindings` |
| `models/primitives/enums.py` | a `ServiceType` member, if none fits |
| `services/_sdk_services.py` | build the SDK object for that service type |
| `player/execution/infrastructure_seeder.py` | register a service when the capability is bound |
| `contracts/services.py` | a `Protocol` naming the SDK methods steps call |
| `player/execution/dataspace_access.py` | the accessor steps call |

You don't touch anything that enumerates capabilities. The config keys, the `TESTLAB_SUT_DISCOVERY_FINDER_BASE_URL` environment variable, the `${{ infrastructure.sut.discovery_finder.base_url }}` context variable, the `required:` check in a TCK manifest and `testlab inspect --infrastructure` are all derived from the binding model by `capability_bindings()` and `infrastructure/mapping.py`. If you find yourself adding a capability name to a list, stop: that list shouldn't exist.

## 1. Declare the binding

In `src/tractusx_testlab/models/domain/capabilities.py`:

```python
class DiscoveryFinderBinding(CapabilityBinding):
    """A Discovery Finder, which answers where a participant's services are registered."""

    identity_field: ClassVar[str] = "base_url"

    base_url: str = Field(
        default="",
        description="Base URL of the Discovery Finder API.",
        json_schema_extra=OPERATOR_SUPPLIED,
    )
```

- **`identity_field`** is the field whose presence means "bound". An unbound capability seeds nothing.
- **`OPERATOR_SUPPLIED`** marks the fields an operator must give when a TCK requires the capability. When they are missing, the run names every one of them in a single error, before any test starts. Don't mark fields that have a working default or that come from the TCK (`version`, `standard`, `standard_version`, which the base class already carries).
- Bindings are frozen and `extra="forbid"`, so a misspelled key is refused, not dropped.

Then place it on its side in `models/domain/infrastructure.py`:

```python
class SutBindings(BaseModel):
    """Infrastructure under test, which the engine only talks to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector: SutConnectorBinding = Field(default_factory=SutConnectorBinding)
    dtr: DtrBinding = Field(default_factory=DtrBinding)
    discovery_finder: DiscoveryFinderBinding = Field(default_factory=DiscoveryFinderBinding)
```

The sides are asymmetric on purpose. Put a capability on the `engine` side only when the engine operates it and holds its credentials. Put it on `sut` when the engine only talks to it.

## 2. Build the service

`ServiceType.DISCOVERY_FINDER` already exists. For a service with no member, add one to `models/primitives/enums.py`. `SERVICE_TYPE_ALIASES` in `player/loading/_constants.py` still maps `DISCOVERY_FINDER` to `DTR`. Nothing reads that table any more, so delete it in the same change rather than leave one name pointing at two services.

In `services/_sdk_services.py`, dispatch the type in `create_instance()` and add a creator next to `_create_aas_service`:

```python
if stype_val == ServiceType.DISCOVERY_FINDER.value:
    return _create_discovery_finder_service(service_definition)
```

The creator reads `base_url`, `auth` and `params` off the `ServiceDefinition` and returns the Tractus-X SDK object. Import the SDK inside the function, as the other creators do, and don't reimplement protocol logic the SDK already has.

## 3. Seed it at run start

In `player/execution/infrastructure_seeder.py`, register a service when the capability is bound. The registration follows the `sut.dtr` block:

```python
_SUT_DISCOVERY_FINDER_NAME = "__sut_discovery_finder__"

# inside seed_infrastructure_services():
finder = infrastructure.sut.discovery_finder
if finder.is_bound() and _SUT_DISCOVERY_FINDER_NAME not in already:
    _register(
        svc_mgr,
        context,
        ServiceDefinition(
            name=_SUT_DISCOVERY_FINDER_NAME,
            type=ServiceType.DISCOVERY_FINDER,
            base_url=finder.base_url,
        ),
        "infrastructure.sut.discovery_finder",
    )
```

Registration order decides which service a lookup by type finds first. SUT services are registered before the engine's own, because a step asking for "the registry" is asking about the system under test.

## 4. Give steps a typed way in

Steps don't call `ServiceManager` or pass service names. Describe the SDK surface they use as a `Protocol` in `contracts/services.py`:

```python
class DiscoveryFinder(Protocol):
    """The Discovery Finder calls steps make."""

    def find_discovery_urls(self, *args: Any, **kwargs: Any) -> Any: ...
```

Then expose it on `DataspaceAccess` in `player/execution/dataspace_access.py`:

```python
def discovery_finder(self) -> DiscoveryFinder:
    """The DISCOVERY_FINDER service the run was seeded with."""
    return self._first_of(ServiceType.DISCOVERY_FINDER)
```

A step now calls it through `sdk_call.run`, which also names a failure after the bound service:

```python
finder = context.dataspace.discovery_finder()
urls = await sdk_call.run(finder.find_discovery_urls, keys=["bpn"])
```

Writing that step is [Create a Step](create-a-step.md), under `steps/discovery/…` or whichever category its id names.

## 5. Test and regenerate

Extend the tests that already cover `dtr`. Each one checks a different surface:

| Test | Proves |
|---|---|
| `tests/unit/infrastructure/test_mapping.py` | the field has a config key, an env var and a context key, and a TCK can require it |
| `tests/unit/player/test_infrastructure_seeder.py` | a bound capability seeds a service, and an unbound one doesn't |
| `tests/unit/player/test_player_infrastructure.py` | a capability the TCK requires but nobody bound refuses the run |

```bash
poetry run pytest tests/unit/infrastructure tests/unit/player -q
poetry run testlab schema          # the TCK JSON Schemas are generated from the authoring models
poetry run testlab schema --check
```

Last, document the capability's fields in [Infrastructure Bindings](../developer/infrastructure-bindings.md). The model tree at the top of that page is written by hand.
