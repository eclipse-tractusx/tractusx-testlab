# 7. Complete Worked Example

## `index.yaml`

```yaml
kind: tck
syntax: v1-alpha

id: certificate-management-tck-v0.0.1

metadata:
  name: "Certificate Management TCK"
  version: "v0.0.1"
  description: >
    Validate CCMAPI certificate management workflow per CX-0135 v3.1.0:
    (1) Request certificate from provider
    (2) Validate certificate payload against schema
    (3) Await provider feedback callback
    (4) Send feedback notification and await acknowledgment
    (5) Expose TestLab as provider and verify SUT consumer behavior
  authors:
    - name: Certificate Management Expert Group
      email: ccm-eg@catena-x.net
      company: Catena-X Automotive Network e.V.
  copyright_holders:
    - "2026 Catena-X Automotive Network e.V."
  license: LicenseRef-Proprietary
  standards:
    - id: CX-0135
      version: v3.1.0
  tags:
    - CCM

dataspace:
  ecosystem: Catena-X
  version: saturn

infrastructure:
  engine:
    connector:
      required: true
      standard:
        id: CX-0018
        version: v4.2.0
  sut:
    connector:
      required: true
      standard:
        id: CX-0018
        version: v4.2.0
    dtr:
      required: true
      standard:
        id: CX-0002
        version: v1.0.5

env:
  variables:
    - id: sut_counter_party_id
      uses: variable/type/string
      with:
        source: input
      returns:
        value:
          type: string
    - id: sut_counter_party_address
      uses: variable/type/string
      with:
        source: input
      returns:
        value:
          type: string
    - id: ccm_usage_policy
      uses: config/connector/policy
      name: Required CCMAPI Usage Policy
      with:
        source: value
        value:
          permissions:
            - action: use
              constraints:
                and:
                  - left_operand: UsagePurpose
                    operator: isAnyOf
                    right_operand: "cx.ccm.base:1"
                  - left_operand: FrameworkAgreement
                    operator: eq
                    right_operand: "DataExchangeGovernance:1.0"
      returns:
        value:
          type: object
          class: Policy

  schemas:
    - id: certificate_schema
      source: business_partner_certificate_schema-v3.0.1.json

  testdata:
    - id: available_notification_body
      source: available_notification_body.json
      type: application/json
    - id: certificate_available_response
      source: certificate_available_response.json
      type: application/json
    - id: send_feedback_body
      source: send_feedback_body.json
      type: application/json
    - id: error_unknown_cert_type_body
      source: error_unknown_cert_type_body.json
      type: application/json

tests:
  - id: catalog_policy_validation.yaml
    name: Validate CX-0135 catalog policy constraints
  - id: request_certificate.yaml
    name: Request a certificate via CCMAPI
  - id: send_feedback_notification.yaml
    name: Send a feedback notification and await acknowledgment
```

## `tests/send_feedback_notification.yaml`

```yaml
kind: test
syntax: v1-alpha

namespace: certificate-management-tck-v0.0.1
id: send-feedback-notification

metadata:
  name: "Send Feedback Notification"
  version: "1.0.0"
  description: >
    Send a CX-0135 CCMAPI status notification to the provider via EDC dataplane
    and await the provider's acknowledgment on a TestLab mock endpoint.

execution:
  - id: pull_notification_endpoint
    uses: connector/consumer/pull_data_filtered
    name: Find CCMAPI endpoint and obtain dataplane credentials
    with:
      counter_party_address: "${{ env.sut_counter_party_address }}"
      counter_party_id: "${{ env.sut_counter_party_id }}"
      policy: "${{ env.ccm_usage_policy }}"
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CCMAPI"
        - operand_left: "http://purl.org/dc/terms/subject"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CompanyCertificateManagementNotificationApi"
        - operand_left: "https://w3id.org/catenax/ontology/common#version"
          operator: "="
          operand_right: "3.0"
    returns:
      edr_token:
        type: string
        class: AuthToken
      dataplane_url:
        type: string
        class: DataplaneUrl
    validate:
      - uses: validate/assert
        with: { input: edr_token, operator: not_null }
      - uses: validate/assert
        with: { input: dataplane_url, operator: not_null }

  - id: send_status_notification
    uses: connector/dataplane/http_request
    name: Call CX-0135 request api on the provider via dataplane
    with:
      method: POST
      dataplane_url: "${{ execution.pull_notification_endpoint.dataplane_url }}"
      path: "/companycertificate/request"
      edr_token: "${{ execution.pull_notification_endpoint.edr_token }}"
      headers:
        Content-Type: "application/json"
      body: "${{ env.testdata.send_feedback_body }}"
    returns:
      status_code:
        type: integer
        class: StatusCode
      response_body:
        type: object
        class: ResponseBody
    validate:
      - uses: validate/field
        with: { input: status_code, operator: equals, value: 200 }
      - uses: validate/field
        with:
          input: response_body
          path: "header.messageId"
          operator: matches_regex
          value: "^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
      - uses: validate/schema
        with:
          input: response_body
          schema: "${{ env.schemas.certificate_schema }}"
      - uses: validate/field
        with:
          input: request_body
          path: "content.certificateStatus"
          operator: one_of
          value: ["RECEIVED", "ACCEPTED", "REJECTED"]
```
