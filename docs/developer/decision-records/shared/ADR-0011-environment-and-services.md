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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0011: Environment and Services Specification

## Status

Proposed

## Date

2026-05-21

## Context

Testing against real Tractus-X dataspaces requires configured infrastructure services (connector connectors, DTRs, Discovery Finders) and runtime variables (BPNs, URLs, credentials). ADR-0010 introduced the `env:` block in TCK manifests with service definitions following the step-like pattern (`name` + `uses` + `with`). This ADR formalizes:

- How services are declared, configured, and referenced
- How services produce typed variables for step consumption
- How variables are acquired (static, runtime prompt, auto-generation)
- How secrets are handled
- The scoping rule: tests consume but never declare services or env variables

### Forces

- Certification testers must configure services once per TCK, not per test.
- Some values are known before execution (URLs), some are entered during execution (OTP codes), some are generated (UUIDs).
- Services have different auth mechanisms (API key, OAuth2) depending on type and deployment.
- Secrets must never leak into logs, exports, or YAML serialization.
- Services are steps — they follow the same `uses` + `with` vocabulary as all other steps.

## Decision

### 1. Services Live at TCK Level Only

All service declarations belong in the TCK manifest under `env.services`. Individual test files (`kind: test`) CANNOT declare their own services. Tests reference services by name via `with: { service: "name" }` or `${{ env.services.name }}`.

**Rationale:** A TCK represents one test environment. Services are infrastructure — they don't change between test cases within the same TCK.

### 2. Service Definition Pattern

Services follow the same pattern as steps: `name` + `uses` + `with`. The `uses` field references a type from the `service/` namespace in the uses registry. The `with` block contains ALL configuration for that service type, including authentication.

```yaml
env:
  services:
    - name: provider
      uses: service/connector_service
      with:
        base_url: ${{ env.provider_url }}
        management_path: /management/v3
        dsp_path: /api/v1/dsp
        dataspace_version: ${{ metadata.dataspace_version }}
        auth:
          type: api_key
          api_key: ${{ env.provider_api_key }}
          api_key_header: "X-Api-Key"
      returns:
        connector_service:
          type: class
          class: ConnectorService
```

**Field specification:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Service identifier. Pattern: `^[a-z][a-z0-9_]{0,49}$`. Becomes the variable handle. |
| `uses` | Yes | Service type from `service/` namespace (e.g., `service/connector_service`). |
| `with` | Yes | Typed inputs for the service, including `auth`. Schema depends on service type. |

### 3. Service Type Registry

Each `uses` value in the `service/` namespace defines its own input schema:

| Uses | Description | Required `with` fields |
|------|-------------|------------------------|
| `service/connector_service` | Eclipse Dataspace Connector | `base_url`, `management_path`, `dsp_path`, `dataspace_version`, `auth` |
| `service/mock_server` | TestLab built-in mock server | `port` |
| `service/dtr` | Digital Twin Registry | `base_url`, `lookup_path`, `auth` |
| `service/discovery_service` | Discovery Finder service | `base_url`, `auth` |

### 4. Authentication Inside `with`

Auth is a nested object inside `with:` — not a separate top-level block. Each service type defines whether auth is required or optional.

**API Key:**
```yaml
with:
  base_url: "https://connector.local"
  auth:
    type: api_key
    api_key: ${{ env.provider_api_key }}
    api_key_header: "X-Api-Key"
```

**OAuth2:**
```yaml
with:
  base_url: "https://connector.local"
  auth:
    type: oauth2
    token_url: "https://auth.local/token"
    client_id: ${{ env.client_id }}
    client_secret: ${{ env.client_secret }}
```

**No auth:**
```yaml
with:
  base_url: "http://localhost:4243"
  auth:
    type: none
```

Supported auth types: `api_key`, `oauth2`, `none`.

### 5. Implicit Returns — Services as Typed Variables

Each service **implicitly generates a return variable** when declared. The variable:

- Has the service `name` as its identifier
- Has `type: object`
- Has `class` derived from the `uses` action name (e.g., `service/connector_service` → class `connector_service`)

This means steps that accept a `service` input can use class-based filtering (ADR-0009) to accept only compatible services. For example, a step that expects `class: connector_service` accepts connector services, not mock servers.

**Referencing services in steps:**

```yaml
- id: create_asset_1
  uses: connector/provider/create_asset
  with:
    connector_service: ${{ env.services.provider.connector_service}}                         # 
    asset_id: ${{ vars.generated_id }}
```

The compiler validates that `connector_service: ${{ env.services.provider.connector_service}}` references an existing entry in `env.services`.

### 6. Dataspace Version via Metadata Reference

Services that need the dataspace version reference it from metadata using the `${{ metadata.dataspace_version }}` expression — no duplication:

```yaml
metadata:
  dataspace_version: saturn

env:
  services:
    - name: provider
      uses: service/connector_service
      with:
        base_url: ${{ env.provider_url }}
        dataspace_version: ${{ metadata.dataspace_version }}
        auth:
          type: api_key
          api_key: "test-key"
          api_key_header: "X-Api-Key"
      returns:
        connector_service:
          type: class
          class: ConnectorService
```

### 7. Variable Acquisition Types

Each variable in `env.variables` has a value that may come from different sources:

| Source | Description | Resolution Time |
|--------|-------------|-----------------|
| Static literal | Hardcoded value in YAML | Compile time |
| `${{ execution.x }}` | Injected at runtime | Pre-execution |
| User-prompted | Marked for runtime user input | Mid-execution (pauses) |
| Generated | Auto-generated by runtime function | Pre-execution |

For v1-alpha, all variables are static literals or expression references. Runtime prompting and generation are future extensions (tracked separately).

### 8. Secrets Handling

Variables with `secret: true` in their metadata:

- Are masked in all log output (`***`)
- Are stored in memory only (never written to disk during execution)
- Are excluded from YAML export/serialization of results

In the YAML, secrets are just regular variables — the `secret` flag is runtime metadata, not a YAML field.

### 9. Scoping Rule

Tests (`kind: test`) CANNOT declare `env:` blocks. All environment configuration is inherited from the parent TCK manifest via namespace resolution. Tests consume:

- Variables via `${{ env.x }}`
- Services via `with: { service: "name" }` or `${{ env.services.name }}`
- Schemas via `${{ env.schemas.name }}`
- Metadata via `${{ metadata.x }}`

### 10. Resolution Order

Within the `env:` block, resolution follows declaration order:

1. `env.variables` — resolved first (static values and `${{ execution.x }}` references)
2. `metadata.*` — always available (declared above `env:`)
3. `env.services` — resolved second (may reference `env.variables` and `metadata.*`)
4. `env.schemas` / `env.testdata` — resolved last (file path validation)

This means services can reference variables (`${{ env.provider_url }}`), but variables cannot reference services.

## Complete Example

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

metadata:
  name: "Certificate Management TCK"
  version: "v0.0.1"
  description: >
    Validate certificate management workflow per CX-0135 v3.1.0.
  authors:
    - name: Mathias Moser
      email: mathias.moser@catena-x.net
      company: Catena-X Automotive Network e.V.
  copyright_holders:
    - "2026 Catena-X Automotive Network e.V."
  license: Apache-2.0
  standards:
    - id: CX-0135
      version: v3.1.0
  tags:
    - CCM
  dataspace_version: saturn

env:
  variables:
    provider_url: "https://provider.local/management"
    consumer_url: "https://consumer.local/management"
    provider_bpn: "BPNL000000000001"
    consumer_bpn: "BPNL000000000002"
    provider_api_key: "test-api-key"
    consumer_api_key: "test-api-key"
    callback_url: "https://testlab.local/callback"

  services:
    - name: provider
      uses: service/connector_service
      with:
        base_url: ${{ env.provider_url }}
        management_path: /management/v3
        dsp_path: /api/v1/dsp
        dataspace_version: ${{ metadata.dataspace_version }}
        auth:
          type: api_key
          api_key: ${{ env.provider_api_key }}
          api_key_header: "X-Api-Key"

    - name: consumer
      uses: service/connector_service
      with:
        base_url: ${{ env.consumer_url }}
        management_path: /management/v3
        dsp_path: /api/v1/dsp
        dataspace_version: ${{ metadata.dataspace_version }}
        auth:
          type: api_key
          api_key: ${{ env.consumer_api_key }}
          api_key_header: "X-Api-Key"

    - name: mock_server
      uses: service/mock_server
      with:
        port: 8090

  schemas:
    certificate_schema:
      file: business_partner_certificate.json
    notification_header_schema:
      file: notification_header.json

  testdata:
    available_notification:
      file: available_notification.json
      type: application/json

preconditions:
  - id: health_provider
    uses: connector/health_check
    name: Provider health check
    with:
      connector_service: ${{ env.services.provider.connector_service}}
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200

  - id: health_consumer
    uses: connector/health_check
    name: Consumer health check
    with:
      connector_service: ${{ env.services.consumer.connector_service}}
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200

tests:
  - request-certificate.yaml
  - available-notification.yaml
```

## Compiler Validation Rules

| Rule | Error Message |
|------|---------------|
| Service missing `name` | `Service at index {n} is missing required field 'name'` |
| Service missing `uses` | `Service '{name}' is missing required field 'uses'` |
| Service missing `with` | `Service '{name}' is missing required field 'with'` |
| Invalid `uses` namespace | `Service '{name}' uses '{value}' — must start with 'service/'` |
| Unknown service type | `Unknown service type '{value}' in service '{name}'` |
| Duplicate service name | `Duplicate service name '{name}' — first defined at index {n}` |
| Missing required field | `Service '{name}' ({uses}): missing required field '{field}' in 'with'` |
| Step references unknown service | `Step '{id}' references service '{name}' — not defined in env.services` |
| Circular reference | `Circular reference in env: service '{name}' references variable that references service` |

## Consequences

### Positive

- Services follow the same vocabulary as steps (`uses` + `with`) — one pattern to learn
- Typed variables from services enable class-based filtering of step inputs
- Auth inside `with` means each service type fully defines its own input schema
- `${{ metadata.dataspace_version }}` eliminates duplication across services
- Compile-time validation catches misconfigured services before execution

### Negative

- Tests cannot be self-contained — they always require a parent TCK manifest
- Adding a new service type requires updating the type registry
- `service/` namespace prefix is slightly more verbose than bare type names

### Risks

| Risk | Mitigation |
|------|-----------|
| Service type proliferation | Registry is curated — new types require ADR amendment |
| Auth credentials in YAML | Secrets handling + log masking + never serialize to exports |
| Breaking change from ADR-0011 draft | No production code depends on the draft yet — clean slate |

## Impact on Backend

The runtime handles:

1. **Compile-time**: Validate all service references, required fields, and variable interpolation
2. **Pre-execution**: Resolve `env.variables`, then interpolate into `env.services`
3. **Service instantiation**: Create SDK service objects from resolved service configs
4. **Variable injection**: Service `name` registered as typed variable (`class: {action_name}`)
5. **Secret masking**: Logger filters any value marked as secret from output

## Related

- [ADR-0010](ADR-0010-yaml-syntax-v2.md) — YAML Syntax v2 (parent syntax specification, defines `service/` namespace)
- [ADR-0009](ADR-0009-typed-variable-class-system.md) — Typed Variable Class System (`class` field for returns)
