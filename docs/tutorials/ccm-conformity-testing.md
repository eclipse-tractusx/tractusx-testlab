<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Catena-X Automotive Network e.V.
 Copyright (c) 2026 Contributors to the Eclipse Foundation

 Licensed under the Creative Commons Attribution 4.0 International License
 (the "License"); you may not use this file except in compliance with the
 License. You may obtain a copy of the License at

    https://creativecommons.org/licenses/by/4.0/

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 SPDX-License-Identifier: CC-BY-4.0
-->
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and tested by a human committer. -->

# CCM Conformity Testing

This is the test-by-test reference for the Certificate Management TCK, `certificate-management-tck-v0.0.1`, which checks CX-0135 v3.1.0. It lists every step, every check, and every value each test reads. It matches `docs/examples/certificate-management-v2/raw/`.

For why the suite is built this way, see the [Architecture Guide](ccm-architecture-guide.md). To run it, see the [Developer Guide](ccm-developer-guide.md).

## Summary

The tests run in this order. None is skippable, and none reads another test's outputs.

| # | Manifest entry | Test id | Name | Steps | Checks |
| --- | --- | --- | --- | --- | --- |
| 1 | `catalog_policy_validation.yaml` | `catalog-policy-validation` | Catalog Policy Validation | 1 | 2 |
| 2 | `request_certificate.yaml` | `request-certificate` | Request Certificate | 2 | 5 |
| 3 | `send_feedback_notification.yaml` | `send-feedback-notification` | Send Feedback Notification | 1 setup + 3 | 11 |
| 4 | `error_handling.yaml` | `error-handling` | Error Handling | 2 | 5 |

The first execution step is `pull_ccmapi_endpoint` in all four tests. It is the same [`connector/consumer/pull_data_filtered`](../api-reference/steps/connector/consumer.md#connector-consumer-pull_data_filtered) call each time. Only its `name` differs.

| Input | Value |
| --- | --- |
| `counter_party_address` | `${{ env.sut_counter_party_address }}` |
| `counter_party_id` | `${{ env.sut_counter_party_id }}` |
| `expected_policies` | `${{ env.ccm_usage_policy }}`: `UsagePurpose isAnyOf cx.ccm.base:1` **and** `FrameworkAgreement eq DataExchangeGovernance:1.0` |
| `filters` | EDC `type` = taxonomy `CCMAPI`; Dublin Core `subject` = taxonomy `CompanyCertificateManagementNotificationApi`; Catena-X common `version` = `3.0` (full IRIs in the test files) |

| Check | Passes when |
| --- | --- |
| `validate/assert` `edr_token` `not_null` | An offer matched, negotiation and transfer completed, and a token was issued |
| `validate/assert` `dataplane_url` `not_null` | The transfer produced a data-plane address |

The tables below write it as **pull**. The regex `UUID-URN` stands for `^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`.

## 1. Catalog Policy Validation

`tests/catalog_policy_validation.yaml`: the provider publishes a CCMAPI offer under the CX-0135 usage policy, and TestLab can negotiate it.

| Phase | Step id | `uses` | Checks |
| --- | --- | --- | --- |
| execution | `pull_ccmapi_endpoint` | `connector/consumer/pull_data_filtered` | **pull** |

The test's description says it validates "exactly one CCMAPI asset per BPNL". The step accepts the first offer that matches, and no check counts the offers, so the test does not enforce uniqueness.

## 2. Request Certificate

`tests/request_certificate.yaml`: a CX-0135 certificate request through the provider's data plane is answered.

| Phase | Step id | `uses` | Checks |
| --- | --- | --- | --- |
| execution | `pull_ccmapi_endpoint` | `connector/consumer/pull_data_filtered` | **pull** |
| execution | `request_certificate` | `connector/dataplane/http_request` | see below |

`request_certificate` sends `POST {dataplane_url}/companycertificate/request` with `Authorization: {edr_token}` and body `env.testdata.request_certificate_body`.

| Check | `input` | `path` | Operator | Expected |
| --- | --- | --- | --- | --- |
| `validate/field` | `status_code` | — | `equals` | `200` |
| `validate/field` | `response_body` | `header.messageId` | `matches_regex` | UUID-URN |
| `validate/schema` | `response_body` | — | — | `env.schemas.certificate_schema` |

`certificate_schema` is the Business Partner Certificate data model (`urn:samm:io.catenax.business_partner_certificate:3.1.0`, file name `…-v3.0.1.json`). It requires `businessPartnerNumber` and `certificateType` at the top level, and the check applies it to the whole `{header, content}` answer.

**Request body** (`testdata/request_certificate_body.json`): header context `CompanyCertificateManagement-CCMAPI-Request:1.0.0`, version `3.1.0`. It reads `consumer_bpn` (sender), `provider_bpn` (receiver and `certifiedBpn`), `testlab_dsp_url` (`senderFeedbackUrl`), `certificate_type` and `location_bpns`.

## 3. Send Feedback Notification

`tests/send_feedback_notification.yaml`: the provider accepts a CX-0135 status notification through its data plane and acknowledges it to TestLab.

| Phase | Step id | `uses` | Checks |
| --- | --- | --- | --- |
| setup | `mock_receive_ack` | `mock/api` | none (setup) |
| execution | `pull_ccmapi_endpoint` | `connector/consumer/pull_data_filtered` | **pull** |
| execution | `send_status_notification` | `connector/dataplane/http_request` | `status_code` `equals` `200` |
| execution | `wait_provider_ack` | `mock/wait/http_request` | see below |

- `mock_receive_ack` registers `POST /companycertificate/notification/receive` on the engine's mock server. It answers `200` with `env.testdata.send_feedback_body` and publishes `mock` and `full_mock_url`.
- `send_status_notification` sends `POST {dataplane_url}/companycertificate/status` with body `env.testdata.send_feedback_body`.
- `wait_provider_ack` waits up to 60 s for the provider to call the mock (`mock: ${{ setup.mock_receive_ack.mock }}`), then checks the request it received:

| Check | `input` | `path` | Operator | Expected |
| --- | --- | --- | --- | --- |
| `validate/assert` | `request_method` | — | `equals` | `POST` |
| `validate/field` | `request_body` | `header.messageId` | `matches_regex` | UUID-URN |
| `validate/field` | `request_body` | `header.context` | `equals` | `CompanyCertificateManagement-CCMAPI-Status:1.0.0` |
| `validate/field` | `request_body` | `header.sentDateTime` | `not_null` | — |
| `validate/field` | `request_body` | `header.senderBpn` | `matches_regex` | `^BPNL[0-9A-Z]{12}$` |
| `validate/field` | `request_body` | `header.receiverBpn` | `equals` | `${{ env.consumer_bpn }}` |
| `validate/field` | `request_body` | `header.version` | `equals` | `3.1.0` |
| `validate/field` | `request_body` | `content.certificateStatus` | `one_of` | `RECEIVED`, `ACCEPTED`, `REJECTED` |

**Notification body** (`testdata/send_feedback_body.json`): header context `CompanyCertificateManagement-CCMAPI-Status:1.0.0`, `certificateStatus: ACCEPTED`. It reads `consumer_bpn`, `provider_bpn`, `testlab_dsp_url`, `request_id` (as `relatedMessageId`), `document_id` and `location_bpns`.

The body carries `senderFeedbackUrl: ${{ env.testlab_dsp_url }}`, not the mock's `full_mock_url`. The provider must therefore know from elsewhere where to send the acknowledgement. That address must reach this host on `server_port` (default `8100`).

## 4. Error Handling

`tests/error_handling.yaml`: a request for an unknown certificate type gets a well-formed `REJECTED` answer.

| Phase | Step id | `uses` | Checks |
| --- | --- | --- | --- |
| execution | `pull_ccmapi_endpoint` | `connector/consumer/pull_data_filtered` | **pull** |
| execution | `send_unknown_cert_type` (`expects: fail`) | `connector/dataplane/http_request` | see below |

`send_unknown_cert_type` sends `POST {dataplane_url}/companycertificate/request` with body `env.testdata.error_unknown_cert_type_body`, which asks for `certificateType: NONEXISTENT_CERT_TYPE_XYZ`. `expects: fail` marks the step as a negative test, but it does not invert the result: the step passes when these checks pass.

| Check | `input` | `path` | Operator | Expected |
| --- | --- | --- | --- | --- |
| `validate/field` | `status_code` | — | `equals` | `200` |
| `validate/field` | `response_body` | `header.messageId` | `matches_regex` | UUID-URN |
| `validate/field` | `response_body` | `content.requestStatus` | `equals` | `REJECTED` |

**Request body** (`testdata/error_unknown_cert_type_body.json`): same header as the certificate request. It reads `consumer_bpn`, `provider_bpn`, `testlab_dsp_url` and `location_bpns`.

## Values a run reads

| Value | Declared in the manifest | Read by |
| --- | --- | --- |
| `infrastructure.engine.connector.*` | `infrastructure.engine.connector` (required) | All connector steps, through the services the engine builds |
| `infrastructure.sut.connector.dsp_url`, `.participant_id` | `infrastructure.sut.connector` (required) | Binding check; default counter-party |
| `sut_counter_party_id`, `sut_counter_party_address` | `env.variables`, `source: input` | **pull** in all tests |
| `ccm_usage_policy` | `env.variables`, `source: value` | **pull** in all tests |
| `certificate_schema` | `env.schemas` (`business_partner_certificate_schema-v3.0.1.json`) | `request_certificate` |
| `consumer_bpn`, `provider_bpn`, `testlab_dsp_url`, `location_bpns` | not declared | All three test data bodies; `consumer_bpn` also in a `wait_provider_ack` check |
| `certificate_type` | not declared | `request_certificate_body` |
| `request_id`, `document_id` | not declared | `send_feedback_body` |

The run refuses to start without the declared values. An undeclared value fails only at the step that reads it, with `'env.<name>' resolves to nothing`.
