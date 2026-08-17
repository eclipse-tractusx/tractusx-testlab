# TestLab step catalog (v1-alpha)

Generated 2026-08-17 from the tractusx-testlab step registry (`testlab docs --json`,
engine `v1-alpha1`). 57 steps. `**(required)**` marks mandatory params; everything
else is optional. Every output listed is published as a context variable under its
own name when the step runs.

Every step below has a visual block in the cx-test-suite IDE **except
`digital-twin/submodel/delete`**; there are no IDE-only steps.

## Shared parameter types

- **FilterExpression** (items of `filters:` lists): `operand_left` (string, required),
  `operator` (string, default `"="`), `operand_right` (any). Snake_case only —
  camelCase is a serialization detail, never authored.
- **DataAddressPayload** (the full EDR document, returned as `data_address`):
  `endpoint`, `authorization`, `authCode`.
- **Condition** (items of `flow/if` `conditions:` and step-level `if:`): `input`,
  `path` (dot-separated), `operator`, `value`.
- **StepDefinition**: nested steps inside `flow/if`/`flow/retry` use the exact same
  shape as top-level steps (`id`, `uses`, `with`, `returns`, `validate`, …).
- **SpecificAssetId** (digital-twin lookups): `name` (required), `value` (required).
- **MockInstance** (returned by `mock/*` steps): `endpoint_id`, `path`, `method`,
  `base_mock_url`, `full_mock_url`.

## Steps

### `connector/consumer/do_dsp`
Run the full DSP flow (catalog → negotiation → transfer) via the SDK.

Params:
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `expected_policies`: array[object] — ODRL policies the negotiation is allowed to accept.
Outputs:
- `dataplane_url`: string — Data-plane URL the negotiated data is fetched from.
- `edr_token`: string — Authorization token for that data-plane URL.

### `connector/consumer/do_dsp_with_bpnl`
Run the full DSP flow using BPNL-based connector discovery via the SDK.

Params:
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
- `bpnl`: string **(required)** — BPN used to discover the counter-party's connector.
- `counter_party_address`: string — DSP endpoint; when omitted it is resolved from the BPN by discovery.
- `expected_policies`: array[object] — ODRL policies the negotiation is allowed to accept.
Outputs:
- `dataplane_url`: string — Data-plane URL the negotiated data is fetched from.
- `edr_token`: string — Authorization token for that data-plane URL.

### `connector/consumer/extract_dataset`
Extract the first matching dataset from catalog offers by `dct:type`.

Params:
- `datasets`: array[object] **(required)** — Dataset offers returned by a catalog query.
- `dct_type`: string **(required)** — The 'dct:type' @id used to select the dataset.
Outputs:
- `dataset`: object — The first dataset whose 'dct:type' matched.
- `offer_id`: string — Policy/offer ID of the first match.
- `asset_id`: string — Asset ID of the first match.

### `connector/consumer/get_edr`
Retrieve the EDR data address for a completed transfer.

Params:
- `transfer_id`: string — Transfer process to read the EDR of; falls back to the 'transfer_id' context variable.
- `verify`: any — TLS verification passed through to the SDK; None keeps its default.
Outputs:
- `dataplane_url`: string — Data-plane URL the negotiated data is fetched from.
- `edr_token`: string — Authorization token for that data-plane URL.
- `data_address`: DataAddressPayload — The full EDR data address document, unchanged.

### `connector/consumer/initiate_transfer`
Start a data transfer for a contract that has already been negotiated.

Params:
- `transfer_type`: string (default: `"HttpData-PULL"`) — How the data moves: 'HttpData-PULL' (the consumer fetches it) or a '-PUSH' type such as 'HttpData-PUSH' or 'AmazonS3-PUSH'.
- `negotiation_id`: string — PULL only — negotiation to collect the EDR for; falls back to the 'negotiation_id' context variable.
- `agreement_id`: string — PUSH only — contract agreement the transfer runs under; falls back to the 'agreement_id' context variable.
- `data_destination`: object — PUSH only — the EDC data address the provider pushes to.
- `counter_party_address`: string (default: `""`) — PUSH only — DSP endpoint of the provider; falls back to 'provider_address'.
- `max_wait`: number (default: `60.0`) — PUSH only — seconds to wait for the transfer to reach a final state.
- `poll_interval`: number (default: `1.0`) — PUSH only — seconds between two transfer state reads.
- `verify`: any — TLS verification passed through to the SDK; None keeps its default.
Outputs:
- `transfer_id`: string — ID of the transfer process.
- `state`: string — State the transfer settled at, e.g. 'STARTED' or 'COMPLETED'.
- `edr_entry`: object — PULL only — the EDR entry the negotiation produced.
- `dataplane_url`: string — PULL only — data-plane URL the data is fetched from.
- `edr_token`: string — PULL only — authorization token for that data-plane URL.
- `data_address`: DataAddressPayload — PULL only — the full data address document, for assertions on its other keys.

### `connector/consumer/negotiate`
Negotiate a contract with the provider and wait for the outcome.

Params:
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `asset_id`: any — Asset ID to negotiate for; falls back to the 'catalog_asset_id' context variable.
- `policy`: any — ODRL policy to negotiate under; falls back to the 'catalog_policy' context variable.
- `max_wait`: number (default: `60.0`) — Seconds to wait for the negotiation to reach a final state.
- `poll_interval`: number (default: `1.0`) — Seconds between two negotiation state reads.
Outputs:
- `negotiation_id`: string — ID of the started negotiation.
- `agreement_id`: string — ID of the contract agreement, once the negotiation finalised.
- `state`: string — State the negotiation settled at, e.g. 'FINALIZED' or 'TERMINATED'.

### `connector/consumer/pull_data_filtered`
Run the full DSP flow in one step, optionally constrained to one policy.

Params:
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `max_wait`: number (default: `60.0`) — Seconds to wait for the transfer to complete.
- `poll_interval`: number (default: `1.0`) — Seconds between transfer-state polls.
- `expected_policies`: any — Policies the offer must satisfy, in ODRL or the testlab simplified form, as one document or a list; omitted means the SDK picks the first offer.
Outputs:
- `dataplane_url`: string — Data-plane URL the negotiated data is fetched from.
- `edr_token`: string — Authorization token for that URL.
- `token_prefix`: string — First characters of the token, safe to log or assert on.
- `catalog`: object — Catalog document the offer was taken from.
- `datasets`: array[object] — Dataset offers in that catalog.
- `asset_id`: string — Asset ID of the first offer.
- `negotiation_id`: string — ID of the negotiation the flow ran.
- `agreement_id`: string — ID of the contract agreement the negotiation produced.
- `transfer_id`: string — ID of the transfer process the flow ran.

### `connector/consumer/pull_data_filtered_by_policy`
Run the full DSP flow, accepting an offer that matches any of several policies.

Params:
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `max_wait`: number (default: `60.0`) — Seconds to wait for the transfer to complete.
- `poll_interval`: number (default: `1.0`) — Seconds between transfer-state polls.
- `expected_policies`: array[object] **(required)** — ODRL policies, any one of which the negotiated offer must satisfy.
Outputs:
- `dataplane_url`: string — Data-plane URL the negotiated data is fetched from.
- `edr_token`: string — Authorization token for that URL.
- `token_prefix`: string — First characters of the token, safe to log or assert on.
- `catalog`: object — Catalog document the offer was taken from.
- `datasets`: array[object] — Dataset offers in that catalog.
- `asset_id`: string — Asset ID of the first offer.
- `negotiation_id`: string — ID of the negotiation the flow ran.
- `agreement_id`: string — ID of the contract agreement the negotiation produced.
- `transfer_id`: string — ID of the transfer process the flow ran.

### `connector/consumer/query_catalog`
Query a provider's catalog via the SDK connector consumer service.

Params:
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
Outputs:
- `catalog`: CatalogPayload — The provider's catalog document, unchanged.
- `datasets`: array[object] — Dataset offers from the catalog, always as a list.

### `connector/consumer/query_catalog_by_asset_id`
Query the catalog filtered by a specific asset ID.

Params:
- `counter_party_id`: string **(required)** — BPN of the counter-party.
- `counter_party_address`: string **(required)** — DSP endpoint of the counter-party connector.
- `asset_id`: string **(required)** — Asset ID the catalog is filtered by.
- `expected_policies`: array[object] — Policies accepted for the returned offer; the first match is exported.
Outputs:
- `catalog`: CatalogPayload — The provider's catalog document, unchanged.
- `datasets`: array[object] — Dataset offers from the catalog, always as a list.
- `catalog_asset_id`: any — Asset ID of the first offer whose policy is expected.
- `catalog_policy`: any — The accepted ODRL policy of that offer.

### `connector/consumer/query_catalog_by_bpnl`
Query the catalog using BPNL-based connector discovery.

Params:
- `bpnl`: string **(required)** — BPN used to discover the counter-party's connector.
- `counter_party_address`: string — DSP endpoint; when omitted it is resolved from the BPN by discovery.
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
Outputs:
- `catalog`: CatalogPayload — The provider's catalog document, unchanged.
- `datasets`: array[object] — Dataset offers from the catalog, always as a list.

### `connector/consumer/query_catalog_with_filters`
Query a provider's catalog with multiple filter expressions via the SDK.

Params:
- `filters`: array[FilterExpression] — Filter criteria applied to the catalog request.
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
Outputs:
- `catalog`: CatalogPayload — The provider's catalog document, unchanged.
- `datasets`: array[object] — Dataset offers from the catalog, always as a list.

### `connector/dataplane/http_request`
Fetch data from a data-plane endpoint using an EDR token.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `method`: string (default: `"GET"`) — HTTP method.
- `body`: any — Request body; dicts are sent as JSON.
- `dataplane_url`: any — Data-plane URL, or a data address object to read it from; falls back to the 'dataplane_url' context variable.
- `path`: string (default: `""`) — Path appended to the data-plane URL.
- `edr_token`: string — EDR authorization token; falls back to the 'edr_token' context variable.

### `connector/discover/digital-twin-registry/auth`
Get authorization to a counterparty's Digital Twin Registry.

Params:
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `dct_type`: string (default: `"https://w3id.org/catenax/taxonomy#DigitalTwinRegistry"`) — `dct:type` the registry asset is offered under in the catalog.
- `expected_policies`: array[object] — ODRL policies the negotiation is allowed to accept.
Outputs:
- `dataplane_url`: string — Data-plane URL the negotiated data is fetched from.
- `edr_token`: string — Authorization token for that data-plane URL.

### `connector/provider/create_asset`
Register an asset at the provider connector.

Params:
- `asset`: object — The whole asset definition, as declared by a 'config/connector/asset' manifest variable and referenced as '${{ env.<id>.asset }}'. Carries 'base_url', 'dct_type' or 'properties', 'version', 'semantic_id', 'proxy_params', 'headers', 'private_properties' and an optional '@context'.
Outputs:
- `asset_id`: string — ID of the asset that now exists at the provider.

### `connector/provider/create_contract_definition`
Publish assets by binding them to an access and a contract policy.

Params:
- `contract_definition_id`: string (default: `""`) — Contract definition ID; a fresh UUID is used when omitted.
- `contract_policy_id`: any (default: `""`) — Policy governing what the consumer may do with the data.
- `access_policy_id`: any (default: `""`) — Policy governing who may see the offer at all.
- `asset_id`: any (default: `""`) — Single asset the contract definition offers; ignored when 'asset_selector' is given.
- `asset_selector`: array[FilterExpression] — Criteria selecting which assets the definition offers, for a definition that covers more than one. Wins over 'asset_id'.
Outputs:
- `contract_definition_id`: string — ID of the contract definition that now exists at the provider.

### `connector/provider/create_policy`
Register an ODRL policy definition at the provider connector.

Params:
- `policy`: object — The whole ODRL policy, as declared by a 'config/connector/policy' manifest variable and referenced as '${{ env.<id>.policy }}'. Carries 'permissions', 'prohibitions', 'obligations', an optional '@context' and an optional 'policy_id'; a fresh UUID names the policy without one.
Outputs:
- `policy_id`: string — ID of the policy that now exists at the provider.

### `connector/provider/delete_asset`
Delete an asset from the provider connector.

Params:
- `asset_id`: string (default: `""`) — Asset to delete; falls back to the 'asset_id' context variable.
Outputs:
- `status_code`: integer — HTTP status the delete was answered with.

### `connector/provider/delete_contract_definition`
Delete a contract definition from the provider connector.

Params:
- `contract_definition_id`: string (default: `""`) — Contract definition to delete; falls back to the 'contract_definition_id' context variable.
Outputs:
- `status_code`: integer — HTTP status the delete was answered with.

### `connector/provider/delete_policy`
Delete a policy definition from the provider connector.

Params:
- `policy_id`: string (default: `""`) — Policy to delete; falls back to the 'policy_id' context variable.
Outputs:
- `status_code`: integer — HTTP status the delete was answered with.

### `connector/provider/wizard/create_asset`
Register an asset described field by field rather than as a document.

Params:
- `asset_id`: string (default: `""`) — Asset ID; derived from 'name', or a fresh UUID, when omitted.
- `name`: string **(required)** — Human-readable asset name.
- `description`: string (default: `""`) — What the asset offers.
- `base_url`: string **(required)** — URL of the data source behind the asset.
- `content_type`: string (default: `""`) — MIME type of the data, e.g. 'application/json'.
- `properties`: object — Further EDC asset properties, e.g. 'dct:type' or 'cx-common:version'.
Outputs:
- `asset_id`: string — ID of the asset that now exists at the provider.

### `connector/provider/wizard/create_policy`
Register an ODRL policy written as rule lists rather than as a document.

Params:
- `policy_id`: string (default: `""`) — Policy ID; a fresh UUID is used when omitted.
- `permissions`: array[object] **(required)** — ODRL permission rules: what the consumer is allowed to do.
- `prohibitions`: array[object] — ODRL prohibition rules.
- `obligations`: array[object] — ODRL obligation rules.
Outputs:
- `policy_id`: string — ID of the policy that now exists at the provider.

### `digital-twin-registry/consumer/dataplane/get_shell_descriptor`
Retrieve one of a counterparty's shell descriptors by ID.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `dataplane_url`: string (default: `""`) — Data-plane URL of the counterparty's registry; falls back to the 'dataplane_url' context variable.
- `edr_token`: string (default: `""`) — EDR authorization token; falls back to the 'edr_token' context variable.
- `aas_identifier`: string **(required)** — Identifier of the AAS shell descriptor.
Outputs:
- `id`: string — Identifier of the descriptor.
- `idShort`: string — Short, human-readable name.

### `digital-twin-registry/consumer/dataplane/get_shell_descriptors`
List a counterparty's shell descriptors over a negotiated data plane.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `dataplane_url`: string (default: `""`) — Data-plane URL of the counterparty's registry; falls back to the 'dataplane_url' context variable.
- `edr_token`: string (default: `""`) — EDR authorization token; falls back to the 'edr_token' context variable.
- `limit`: integer — Maximum number of entries the registry may return in one page; its own default applies when omitted.
- `cursor`: string — Cursor a previous page returned, to read the page after it.
Outputs:
- `shell_ids`: array[string] — Identifiers of the shells that matched.
- `shell_descriptors`: array[object] — The descriptor document of each matching shell.
- `cursor`: string — Cursor of the next page, or null when this was the last one.

### `digital-twin-registry/consumer/dataplane/lookup_shell`
Search a counterparty's registry for shells matching specific asset IDs.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `dataplane_url`: string (default: `""`) — Data-plane URL of the counterparty's registry; falls back to the 'dataplane_url' context variable.
- `edr_token`: string (default: `""`) — EDR authorization token; falls back to the 'edr_token' context variable.
- `specific_asset_ids`: array[SpecificAssetId] **(required)** — Criteria the shell must match; all of them have to.
Outputs:
- `shell_ids`: array[string] — Identifiers of the shells that matched.
- `shell_descriptors`: array[object] — The descriptor document of each matching shell.

### `digital-twin-registry/consumer/dataplane/lookup_shells_by_asset_link`
Search a counterparty's registry through `POST /lookup/shellsByAssetLink`.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `dataplane_url`: string (default: `""`) — Data-plane URL of the counterparty's registry; falls back to the 'dataplane_url' context variable.
- `edr_token`: string (default: `""`) — EDR authorization token; falls back to the 'edr_token' context variable.
- `limit`: integer — Maximum number of entries the registry may return in one page; its own default applies when omitted.
- `cursor`: string — Cursor a previous page returned, to read the page after it.
- `specific_asset_ids`: array[SpecificAssetId] **(required)** — Criteria the shell must match; all of them have to.
Outputs:
- `shell_ids`: array[string] — Identifiers of the shells that matched.
- `shell_descriptors`: array[object] — The descriptor document of each matching shell.
- `cursor`: string — Cursor of the next page, or null when this was the last one.

### `digital-twin/provider/create_shell_descriptor`
Create an AAS shell descriptor in the Digital Twin Registry.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `shell_descriptor`: object **(required)** — The AAS shell descriptor document to register.
Outputs:
- `id`: string — Identifier of the descriptor.
- `idShort`: string — Short, human-readable name.

### `digital-twin/provider/create_submodel_descriptor`
Create a submodel descriptor under an AAS shell.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `aas_identifier`: string **(required)** — Identifier of the AAS shell descriptor.
- `submodel_descriptor`: object **(required)** — The submodel descriptor document to register under the shell.
Outputs:
- `id`: string — Identifier of the descriptor.
- `idShort`: string — Short, human-readable name.

### `digital-twin/provider/delete_shell_descriptor`
Delete an AAS shell descriptor.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `aas_identifier`: string **(required)** — Identifier of the AAS shell descriptor.
Outputs:
- `status_code`: integer — HTTP status the delete was answered with.

### `digital-twin/provider/get_shell_descriptor`
Retrieve an AAS shell descriptor by ID.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `aas_identifier`: string **(required)** — Identifier of the AAS shell descriptor.
Outputs:
- `id`: string — Identifier of the descriptor.
- `idShort`: string — Short, human-readable name.

### `digital-twin/provider/lookup_shells`
Search the run's own registry for shells matching specific asset IDs.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `specific_asset_ids`: array[SpecificAssetId] **(required)** — Criteria the shell must match; all of them have to.
Outputs:
- `shell_ids`: array[string] — Identifiers of the shells that matched.
- `shell_descriptors`: array[object] — The descriptor document of each matching shell.

### `digital-twin/provider/wizard/create_shell_descriptor`
Register a shell descriptor described field by field.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `id`: string (default: `""`) — Shell identifier; a fresh URN UUID when omitted.
- `id_short`: string **(required)** — Short, human-readable name for the shell.
- `global_asset_id`: string (default: `""`) — Global asset ID the twin represents, as a URN.
- `specific_asset_ids`: array[object] — Identifiers the shell can be looked up by, as {name, value} pairs.
- `submodel_descriptors`: array[object] — Submodel descriptors to attach as the shell is created.
Outputs:
- `id`: string — Identifier of the descriptor.
- `idShort`: string — Short, human-readable name.

### `digital-twin/provider/wizard/create_submodel_descriptor`
Attach a submodel descriptor described field by field.

Params:
- `bpn`: string — BPN the registry request is made on behalf of.
- `aas_identifier`: string **(required)** — Identifier of the AAS shell descriptor.
- `id`: string (default: `""`) — Submodel identifier; a fresh URN UUID when omitted.
- `id_short`: string (default: `""`) — Short, human-readable name for the submodel. CX-0002 does not require one, so an omitted name is left out of the descriptor.
- `semantic_id`: string **(required)** — URN of the aspect model the submodel follows.
- `href`: string **(required)** — URL the submodel's data is served from, written to the endpoint's 'href'. Give the bare data URL: the '$'-suffix the chosen interface calls for is this step's to write.
- `asset_id`: string **(required)** — Asset ID the submodel is offered as — the subprotocol body's 'id'.
- `dsp_endpoint`: string **(required)** — DSP URL of the provider control plane the asset is negotiated through — the subprotocol body's 'dspEndpoint'.
- `interface`: string (default: `"SUBMODEL-3.0"`) — AAS interface the endpoint implements — SUBMODEL-3.X, or SUBMODEL-VALUE-3.X when the href is directly callable as given.
Outputs:
- `id`: string — Identifier of the descriptor.
- `idShort`: string — Short, human-readable name.

### `digital-twin/submodel/delete`
Delete one submodel from the engine's submodel server.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `path`: string **(required)** — Path of the submodel to delete under the submodel server, relative to it — the 'path' the upload published.
Outputs:
- `status_code`: integer — HTTP status the delete was answered with.

### `digital-twin/submodel/upload`
Upload sample data to the engine's submodel server, under its aspect and its id.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `data`: any **(required)** — Payload to upload, sent as JSON. Required: an upload with no payload of its own would store a placeholder the test then asserts against.
- `semantic_id`: string — URN of the aspect model the payload follows, e.g. 'urn:samm:io.catenax.serial_part:3.0.0#SerialPart'. Percent-encoded into the storage path when given; the submodel is stored directly under the server when omitted.
- `submodel_id`: string — Id to store the submodel under; a unique 'urn:uuid:<uuid4>' is generated when omitted.
Outputs:
- `backend_url`: string — Full backend URL the data was uploaded to — server and path together.
- `source_url`: string — Base URL of the submodel server the data now lives on, without the path — the data source an EDC asset is created against.
- `path`: string — Path the data landed on under the server — the percent-encoded aspect URN and the submodel id, or the submodel id alone when no aspect was given.
- `submodel_id`: string — Id the submodel was stored under, as given or as generated — the 'urn:uuid:<uuid4>' a descriptor and a lookup name it by.
- `semantic_id`: string — URN of the aspect model the uploaded payload follows — the same URN the submodel descriptor pointing at it must carry; null when none was given.
- `response`: any — Backend response body, parsed as JSON when it is JSON.

### `flow/delay`
Pause test execution for a fixed duration.

Params:
- `seconds`: number (default: `1`) — Seconds to wait.

### `flow/if`
Run one of two nested sequences depending on a set of conditions.

Params:
- `conditions`: array[Condition] **(required)** — Comparisons evaluated before a branch is chosen.
- `match`: string (default: `"all"`) — Whether every condition must hold ('all') or just one ('any').
- `then`: array[StepDefinition] **(required)** — Nested step definitions run when the condition holds — the same shape used at the top level of a script.
- `else`: array[StepDefinition] — Nested step definitions run when it does not; omitted means the step does nothing in that case.
Outputs:
- `condition_result`: boolean — How the condition evaluated.
- `branch_taken`: string — The branch that ran; 'none' when the condition was false and no 'else' was given.
- `outputs`: array[any] — Outputs of the nested steps that ran, in order.

### `flow/retry`
Run a nested list of steps, retrying the whole sequence on failure.

Params:
- `steps`: array[StepDefinition] **(required)** — Nested step definitions ('uses', 'with', 'validate', …) — the same shape used at the top level of a script. A nested step may itself be 'flow/retry'.
- `max_attempts`: integer (default: `3`) — Maximum number of attempts.
- `delay_s`: number (default: `1`) — Seconds to wait between attempts.

### `http/http_request`
Execute a plain HTTP request.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `method`: string (default: `"GET"`) — HTTP method.
- `body`: any — Request body; dicts are sent as JSON.
- `url`: string **(required)** — Target URL.
- `query_params`: object — Query string parameters appended to the URL.

### `mock/api`
Register a mock HTTP endpoint that returns a canned response.

Params:
- `id`: string (default: `""`) — Identifier for the registered mock; also the variable its URL is stored under.
- `path`: string **(required)** — URL path to register, e.g. '/companycertificate/request'.
- `method`: string (default: `"POST"`) — HTTP method the mock answers on.
- `response_status`: integer (default: `200`) — Status code the mock returns.
- `response_body`: any — JSON body the mock returns; '@name' strings resolve to context variables.
- `response_headers`: object — Headers the mock returns alongside the body.
Outputs:
- `mock`: MockInstance — The registered mock, as 'mock/wait/http_request' takes it.
- `base_mock_url`: string — Root URL of the testlab mock server.
- `full_mock_url`: string — Address to hand the system under test — root plus the mock's path.

### `mock/discovery`
Register a BPN Discovery Finder mock returning configured EDC endpoints.

Params:
- `id`: string **(required)** — Unique identifier for the registered mock.
- `mappings`: object **(required)** — BPN to EDC endpoint mapping, or a list of {bpn, endpoint} entries.

### `mock/dtr`
Register a protocol-aware AAS Digital Twin Registry mock.

Params:
- `id`: string **(required)** — Unique identifier for the registered mock.
- `shells`: array[object] — Shell descriptors the registry starts with, each carrying an 'id' and optionally 'specificAssetIds'.

### `mock/wait/http_request`
Wait for an inbound HTTP request on a previously-registered mock endpoint.

Params:
- `mock`: MockInstance **(required)** — The mock to wait on, as returned by the step that registered it.
- `timeout_s`: number (default: `30.0`) — Seconds to wait before failing.
Outputs:
- `request_method`: string — HTTP method of the inbound request.
- `request_path`: string — Path the request arrived on.
- `request_headers`: object — Headers of the inbound request.
- `request_query_params`: object — Query string parameters of the inbound request.
- `request_body`: any — Body of the inbound request.
- `elapsed_ms`: integer — Milliseconds spent waiting before the request arrived.

### `notification/consumer/discover_assets`
Discover notification assets in a provider catalog.

Params:
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `timeout`: number (default: `60`) — Discovery timeout in seconds.

### `notification/consumer/send`
Send a notification through the dataspace.

Params:
- `counter_party_address`: string (default: `""`) — DSP endpoint of the counter-party connector.
- `counter_party_id`: string (default: `""`) — BPN of the counter-party.
- `notification`: object — The notification document to send.
- `endpoint_path`: string (default: `""`) — Notification API path appended to the endpoint.
- `dataplane_url`: string — Direct mode: data-plane URL to POST to; its presence selects that mode.
- `edr_token`: string (default: `""`) — Direct mode: authorization token for that data-plane URL.
- `content`: object — Older spelling of 'notification' — the document to send.
- `timeout`: number (default: `30`) — Request timeout in seconds.
Outputs:
- `status_code`: integer — Status code the receiver answered with.
- `response_body`: any — Body the receiver answered with.
- `response_headers`: object — Headers the receiver answered with.

### `security/oauth2/client_credentials`
Obtain a token as the client itself — the machine-to-machine grant.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `token_url`: string **(required)** — Token endpoint URL of the authorization server, e.g. 'https://idp.example/realms/CX/protocol/openid-connect/token'.
- `client_id`: string (default: `""`) — OAuth2 client identifier.
- `client_secret`: string (default: `""`) — OAuth2 client secret; omit for a public client.
- `client_auth`: string (default: `"post"`) — How the client authenticates: 'post' sends client_id/client_secret as form fields, 'basic' sends them in an HTTP Basic Authorization header.
- `scope`: string (default: `""`) — Space-separated scopes to request; omitted from the request when empty.
- `extra_fields`: object — Additional form fields merged into the token request, e.g. 'audience' or 'resource'.
Outputs:
- `access_token`: string — The bearer token to present to protected services.
- `token_type`: string — Type of the issued token, normally 'Bearer'.
- `expires_in`: integer — Lifetime of the access token in seconds.
- `scope`: string — Scopes the server actually granted.
- `refresh_token`: string — Refresh token, when the server issues one.

### `security/oauth2/password`
Obtain a token on behalf of a resource owner by username and password.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `token_url`: string **(required)** — Token endpoint URL of the authorization server, e.g. 'https://idp.example/realms/CX/protocol/openid-connect/token'.
- `client_id`: string (default: `""`) — OAuth2 client identifier.
- `client_secret`: string (default: `""`) — OAuth2 client secret; omit for a public client.
- `client_auth`: string (default: `"post"`) — How the client authenticates: 'post' sends client_id/client_secret as form fields, 'basic' sends them in an HTTP Basic Authorization header.
- `scope`: string (default: `""`) — Space-separated scopes to request; omitted from the request when empty.
- `extra_fields`: object — Additional form fields merged into the token request, e.g. 'audience' or 'resource'.
- `username`: string **(required)** — Resource-owner username.
- `password`: string **(required)** — Resource-owner password.
Outputs:
- `access_token`: string — The bearer token to present to protected services.
- `token_type`: string — Type of the issued token, normally 'Bearer'.
- `expires_in`: integer — Lifetime of the access token in seconds.
- `scope`: string — Scopes the server actually granted.
- `refresh_token`: string — Refresh token, when the server issues one.

### `security/oauth2/refresh_token`
Exchange a refresh token for a fresh access token.

Params:
- `headers`: object — Extra HTTP headers merged into the request.
- `timeout`: number — Request timeout in seconds; the script's default is used when omitted.
- `token_url`: string **(required)** — Token endpoint URL of the authorization server, e.g. 'https://idp.example/realms/CX/protocol/openid-connect/token'.
- `client_id`: string (default: `""`) — OAuth2 client identifier.
- `client_secret`: string (default: `""`) — OAuth2 client secret; omit for a public client.
- `client_auth`: string (default: `"post"`) — How the client authenticates: 'post' sends client_id/client_secret as form fields, 'basic' sends them in an HTTP Basic Authorization header.
- `scope`: string (default: `""`) — Space-separated scopes to request; omitted from the request when empty.
- `extra_fields`: object — Additional form fields merged into the token request, e.g. 'audience' or 'resource'.
- `refresh_token`: string **(required)** — Refresh token to exchange for a fresh access token.
Outputs:
- `access_token`: string — The bearer token to present to protected services.
- `token_type`: string — Type of the issued token, normally 'Bearer'.
- `expires_in`: integer — Lifetime of the access token in seconds.
- `scope`: string — Scopes the server actually granted.
- `refresh_token`: string — Refresh token, when the server issues one.

### `util/base64`
Encode or decode a string with base64 / base64url.

Params:
- `store_in_variable`: string (default: `""`) — Name of a context variable to also store the result in.
- `input`: string **(required)** — The string to encode or decode.
- `mode`: string (default: `"encode"`) — Direction of the conversion.
- `url_safe`: boolean (default: `false`) — Use the URL-safe alphabet ('-'/'_' instead of '+'/'/'). Required for AAS/DTR identifiers.
- `strip_padding`: boolean (default: `false`) — When encoding, drop trailing '=' padding. Ignored when decoding, where padding is always restored.

### `util/generate_uuid`
Generate a random UUID v4.

Params: none

### `util/json_path_extract`
Extract a value out of nested data by dot-notation path.

Params:
- `store_in_variable`: string (default: `""`) — Name of a context variable to also store the result in.
- `input`: any **(required)** — Either the name of the context variable holding the data (e.g. 'datasets'), or the data itself when a '${{ }}' expression is passed — it resolves before the step runs.
- `path`: string **(required)** — Dot-notation path to the desired value, e.g. 'datasets.0.id'.

### `util/log`
Write a resolved value to stdout and the run log.

Params:
- `value`: any — The value to show — typically a '${{ }}' expression.
- `message`: string (default: `""`) — Label printed before the value; defaults to the step id.

### `util/parse_kv`
Parse a delimited `key=value` string and optionally select one key.

Params:
- `store_in_variable`: string (default: `""`) — Name of a context variable to also store the result in.
- `input`: string **(required)** — The string to parse, e.g. an EDC 'subprotocolBody'.
- `pair_separator`: string (default: `";"`) — Separator between pairs.
- `kv_separator`: string (default: `"="`) — Separator between key and value.
- `select`: string — Return only this key's value; omit to return the whole parsed mapping.

### `util/validate_path`
Extract a value from a step output by dot-path, for a `validate:` block to assert on.

Params:
- `store_in_variable`: string (default: `""`) — Name of a context variable to also store the result in.
- `input`: any **(required)** — Either the name of the context variable holding the data (e.g. 'datasets'), or the data itself when a '${{ }}' expression is passed — it resolves before the step runs.
- `path`: string **(required)** — Dot-notation path to the desired value, e.g. 'datasets.0.id'.

### `validate/assert`
Assert that a value satisfies an operator condition.

Params:
- `input`: any — The value to validate.
- `operator`: string (default: `"not_null"`) — Comparison applied to the value.
- `value`: any — Expected value; required for the operators that compare two operands.

### `validate/field`
Assert that a field at a dot-separated path satisfies an operator condition.

Params:
- `input`: any — The value to validate.
- `operator`: string (default: `"not_null"`) — Comparison applied to the value.
- `value`: any — Expected value; required for the operators that compare two operands.
- `path`: string (default: `""`) — Dot-separated key path to the field, e.g. 'header.messageId'. Empty asserts on the whole object.

### `validate/schema`
Validate a JSON payload against a JSON Schema document.

Params:
- `input`: any — The payload to validate — an object, a list, or a JSON string.
- `schema`: any **(required)** — A JSON Schema document, typically '${{ env.schemas.<id> }}', which the player seeds from the TCK 'env.schemas' block.

