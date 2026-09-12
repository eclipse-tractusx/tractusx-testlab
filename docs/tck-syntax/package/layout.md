# 1. Package Layout

**[SPEC]** An uncompiled TCK is a directory. The Test Suite Frontend generates it when building a TCK; it can
also be written by hand.

```
certificate-management-v2.0/
├── index.yaml                      # TCK manifest — input to compilation
├── tests/                          # one YAML file per test case
│   ├── catalog_policy_validation.yaml
│   ├── request_certificate.yaml
│   ├── validate_payload.yaml
│   ├── push_certificate.yaml
│   ├── available_notification.yaml
│   ├── send_feedback.yaml
│   ├── expose_testlab_asset.yaml
│   ├── certificate_asset_validation.yaml
│   └── error_handling.yaml
├── testdata/                       # payloads/fixtures — any format, not only JSON
│   ├── request_certificate_body.json
│   ├── push_certificate_body.json
│   ├── send_feedback_body.json
│   ├── available_notification_body.json
│   ├── expose_available_notification_body.json
│   ├── certificate_available_response.json
│   ├── expose_certificate_data_response.json
│   └── error_unknown_cert_type_body.json
└── schemas/                        # JSON Schemas for request/response validation
    ├── bpc-v3.1.0.json
    └── business_partner_certificate_schema.json
```

| Path | Contents |
|---|---|
| `index.yaml` | Manifest: metadata, dataspace + infrastructure requirements, environment config, ordered test list. |
| `tests/` | Test case declarations imported by `index.yaml`. |
| `testdata/` | Data usable across tests. **Does not need to be JSON** — hence the `type:` field on each entry. |
| `schemas/` | JSON Schemas used to validate requests and responses. |

**Compilation** produces a single `.tck` archive, optimised for execution, with optional encryption.

## Naming conventions **[PROP]**

- Directory: `<standard-short-name>-v<tck-version>` (e.g. `certificate-management-v2.0`).
- Test files: `snake_case.yaml`, named after the behaviour tested, not the sequence number — order lives in
  `index.yaml`, so renumbering never touches filenames.
- Test data / schema files: `snake_case.json`; include the model version where one exists
  (`business_partner_certificate_schema-v3.0.1.json`).
