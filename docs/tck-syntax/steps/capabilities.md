# 5.3 Capability Naming **[SPEC]**

```
<root-capability> [ / <module> [ / <sub-module> ] ] / <function>
```

Modularisation is optional; sub-modules are permitted.

| Key | Effect |
|---|---|
| `connector/provider/create_asset` | Creates an asset in the EDC you specify |
| `http/http_request` | Executes an HTTP request to a URL you configure |
| `mock/api` | Mocks an API HTTP response |
| `connector/consumer/pull_data_filtered` **[OBS]** | Finds an endpoint by catalog filter and obtains dataplane credentials (EDR) |
| `connector/dataplane/http_request` **[OBS]** | Calls an API on the provider via the dataplane |

**Backend binding [SPEC]** — a step key maps to an annotated class in the Engine:

```python
class CreateAssetParams(ServiceParams):
    """Input contract of ``connector/provider/create_asset``."""

    asset_id: str = Field(default="", description="ID to register the asset under.")
    base_url: str = Field(default="", description="Backend URL the asset points at.")


class CreateAssetOutput(StepPayload):
    """Output contract of ``connector/provider/create_asset``."""

    asset_id: str = Field(description="ID of the asset that now exists at the provider.")


@step("connector/provider/create_asset")
class CreateAssetStep(BaseStep[CreateAssetParams, CreateAssetOutput]):
    """Register an asset at the provider connector."""

    params_model = CreateAssetParams
    output_model = CreateAssetOutput

    async def execute(self, params: CreateAssetParams, context: "StepContext",
                      definition: StepDefinition) -> StepOutput[CreateAssetOutput]:
        provider = context.get_provider_service(params.service_name())
        url = f"{context.get_provider_base_url()}/v3/assets"
        result, http_status = _create_or_conflict(
            provider.create_asset, asset_id=params.asset_id, base_url=params.base_url,
        )
        return StepOutput(
            value=CreateAssetOutput(asset_id=params.asset_id),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=http_status,
                body={"asset_id": params.asset_id, **(result if isinstance(result, dict) else {})},
            ),
        )
```

Note that `StepOutput` carries the captured `request` and `response` — this is what populates the debug event
log ([§8](../execution-logs.md)).

**Root capabilities, `v1-alpha` [PROP]** — reserved so authors can predict where a capability lives:

| Root | Scope |
|---|---|
| `connector` | EDC operations. Modules: `provider`, `consumer`, `dataplane`. |
| `http` | Generic HTTP. Escape hatch for anything not yet modelled. |
| `mock` | Mock server provisioning — the Engine acting as a counterparty the SUT calls. |
| `dtr` | Digital Twin Registry operations (CX-0002). |
| `dataspace` | Core/identity services (Keycloak, portal, BPN resolution). |
| `variable` / `config` | Manifest-only definitions ([§3.5.1](../manifest/env.md#351-envvariables)), not usable as test steps. |
| `validate` | Validation functions ([§5.4](validations.md)). |
| `util` | Waits, polling, value extraction, formatting. |
