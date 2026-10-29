<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This work is made available under the terms of the
 Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
 which is available at
 https://creativecommons.org/licenses/by/4.0/legalcode.

 SPDX-License-Identifier: CC-BY-4.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5). -->
<!-- It was reviewed and tested by a human committer. -->

# API Files (`env.apis`)

**[SPEC]** A TCK can carry the OpenAPI document of an API it tests, unchanged, as published by the partner or the
standard ([ADR-0030](../../developer/decision-records/shared/ADR-0030-openapi-api-files.md)). Tests reference
the document instead of copying schemas out of it.

```
my-tck/
├── index.yaml
├── tests/
└── apis/
    └── industry-core-hub.yaml
```

```yaml title="index.yaml"
env:
  apis:
    - id: ich                              # how tests reference it
      source: industry-core-hub.yaml       # the file under apis/
      # type: application/vnd.oai.openapi  # optional, inferred from the extension
```

| Key | Required | Rule |
|---|---|---|
| `id` | yes | `^[a-z][a-z0-9_]{0,49}$` — one segment of `${{ env.apis.<id> }}`, unique within `env.apis`. |
| `source` | yes | File name under `apis/`. It may not leave `apis/` (no `..`, no absolute path). |
| `type` | no | One of the media types below. Omitted, it is inferred from the extension. |

| `type` | Read as | Inferred for |
|---|---|---|
| `application/vnd.oai.openapi` | YAML | `.yaml`, `.yml` |
| `application/vnd.oai.openapi+json` | JSON | `.json` |
| `application/yaml` | YAML | — |
| `application/json` | JSON | — |

An entry says **what** an API is, never how it is reached: there is no base URL, connector or credential in
`env.apis`. The steps of a test decide that — call it directly, or through a data plane.

## What the compiler checks

`testlab validate` and `testlab compile` check every API file and report every problem at once, each as
`API file apis/<source> (env.apis[<id>]) …`. Nothing is fetched from the network.

| Check | Refused, for example |
|---|---|
| The file exists inside `apis/` | `not found.` · `must name a file inside apis/: …` |
| At most 5 MiB | `is larger than 5 MiB, the limit for an API file.` |
| Parses as its `type` | `is not valid YAML: … (line 3, column 1).` — safe YAML only: no tags beyond JSON's (`!!python/…`, `!!binary`, `!!timestamp`), no duplicate keys, no `.nan`; strict JSON: no `NaN`, no duplicate keys |
| OpenAPI 3.0.x or 3.1.x | `is Swagger 2.0, which is not supported; convert it to OpenAPI 3.0 or 3.1 first (e.g. with swagger2openapi).` · `is OpenAPI 3.2.0; only 3.0.x and 3.1.x are supported.` · `declares 'openapi: 3.0' as a number; quote it` |
| `info.title`, `info.version`, and `paths` (3.1: `paths`, `webhooks` or `components`) | `has no 'paths'.` |
| Self-contained: every `$ref` starts with `#` | `has $ref 'common.yaml#/X' at /components/schemas/A that points outside the file; an API file must be self-contained — bundle it into one file first.` |
| Every `$ref` resolves, no circular chain | `has $ref '#/components/schemas/B' at /components/schemas/A that is circular: …` |
| Bounded shape | more than 1,000,000 nodes once YAML aliases expand, nesting deeper than 128, a YAML alias that contains itself |

A document split over several files is bundled into one first (`redocly bundle`, `swagger-cli bundle`). A
`$ref` inside sample data — `example`, `default`, `enum`, `const`, an Example Object's `value`, a schema's list of
`examples`, an `x-` extension — is part of the sample and is not checked.

## Referencing a document

`${{ env.apis.<id> }}` is the parsed document, read-only, shared by every step that reads it. It is a whole value:
a reference that reaches into it (`${{ env.apis.ich.info.title }}`) is refused at compile time — hand the
document to a step and let the step read it.

```yaml
- id: title
  uses: util/json_path_extract
  with:
    input: ${{ env.apis.ich }}
    path: info.title
```

The document is data, not part of the test: a `${{ … }}` written in one of its descriptions is text.
Every record of the run — the step's inputs on `step.start`, the trace, the report, the job a host keeps — names a
document by its summary instead of copying it:

```json
{"input": {"api_document": {"openapi": "3.0.3", "title": "DotAAS Part 2 | …", "version": "V3.1.0_SSP-001", "sha256": "15fa0d64…"}}}
```

Keep what a step extracts from a document small: the extracted value is an ordinary output and is recorded as it is.

## Authenticating as the API's security scheme says

Two steps build the credential an OpenAPI security scheme names. Neither calls anything; both return maps that go
into [`http/http_request`](../../api-reference/steps/http/index.md) unchanged.

**`apiKey` scheme** — [`security/api_key`](../../api-reference/steps/security/index.md#security-api_key):

```yaml
- id: auth
  uses: security/api_key
  with:
    key: ${{ env.ich_api_key }}     # a secret: true input
    name: X-Api-Key                 # the scheme's `name`, default X-Api-Key
    in: header                      # the scheme's `in`: header (default), query or cookie

- id: list_parts
  uses: http/http_request
  with:
    url: "${{ env.ich_url }}/v1/part-management/catalog-part"
    headers: ${{ execution.auth.headers }}   # in: header or cookie
    # query_params: ${{ execution.auth.query }}   # in: query
```

**`http` scheme with `scheme: basic`** — [`security/basic`](../../api-reference/steps/security/index.md#security-basic):

```yaml
- id: auth
  uses: security/basic
  with:
    username: ${{ env.sut_user }}
    password: ${{ env.sut_password }}

- id: list_parts
  uses: http/http_request
  with:
    url: "${{ env.sut_url }}/v1/parts"
    headers: ${{ execution.auth.headers }}  # {Authorization: Basic …}
```

The key, the password and every output carrying them (`api_key`, `authorization`, `headers`, `query`, `cookies`)
show as `***` in every record of the run — traces, reports, events and logs, including the step's start event and a
refusal of the value itself — and no `returns:` can reveal them. A connector API key bound by the operator
(`${{ infrastructure.<side>.connector.api_key }}`) is a credential handle and goes into `http/http_request`'s
`headers` directly, not through these steps.

## Calling and checking operations (`labs`)

Five steps read an API file and name its operations. They are experimental — the TCK needs
`extensions: [labs]` — and are documented in the [step reference](../../api-reference/steps/labs/index.md).

| Step | Does |
|---|---|
| `labs/http/api_request` | Calls one operation at `base_url` and returns `status_code`, `response_body`, `response_headers` and `operation` (`{api, id, method, path}`) |
| `labs/connector/dataplane/api_request` | The same through a data plane: `dataplane_url` and `edr_token` from an earlier step unless given, `edr_token: ''` for none |
| `labs/validate/api_response` | Checks an answer against its operation; under `validate:` of a call it reads the step's own answer |
| `labs/validate/api_errors` | Judges the test's error answers together: one format, no leaks, no 5xx for a request sent wrong on purpose |
| `labs/http/api_sweep` | Calls many operations (GET and HEAD unless told otherwise) and checks each answer |

```yaml
extensions: [labs]   # index.yaml

- id: partner
  uses: labs/http/api_request
  with:
    api: ${{ env.apis.ich }}
    operation: GET /v1/partner-management/business-partner/{business_partner_number}  # or the operationId
    base_url: ${{ env.ich_url }}
    path_params: { business_partner_number: BPNL000000000001 }
    headers: ${{ execution.auth.headers }}
    expect: 200          # a status, '4XX', 'success' or 'error'; another answer fails the step
  validate:
    - uses: labs/validate/api_response
```

**Naming an operation.** `operation` is an `operationId` or `METHOD /path` with the path exactly as the document
writes it. The compiler checks it against the document, with the closest names when it does not exist, and checks
`path_params`, required query parameters and a required body when they are written in the test.

**Building the request.** Path values are percent-encoded as one segment each (`a/b` stays one segment; `.` and
`..` are refused); query values are encoded by the client, a list repeating the parameter. A required parameter or
body that is missing, a header name that is not a token, or a value carrying CR, LF or NUL fails the step before
anything is sent. `Accept` defaults to the media types documented for the 2XX answers, `Content-Type` to the
operation's first documented one (JSON when documented).

**Where it goes.** `base_url`, or the document's first `servers` URL when that is a literal absolute http(s) URL — a
templated server (`{protocol}://{host_name}`) is the author's example, never a target. Per-operation `servers` are
never followed, nor are redirects (a 3xx is the answer), and an answer larger than 10 MiB (decoded) fails the step
unread. Through a data plane, the operation's path is appended to the data plane URL; `base_path` (default: the path
of the first server URL, `/api/v3`) is stripped first when the document's paths repeat it.

**What `labs/validate/api_response` checks**, every problem reported, in order:

1. the status is documented — exactly (`404`), by class (`4XX`) or by `default`;
2. it is `expect`, when given;
3. the `Content-Type` is documented for that status (`application/*` and `*/*` match), and a body arrives exactly
   when one is documented (none for `HEAD` or `204`);
4. the body validates against that status and media type's schema — JSON Schema 2020-12 for OpenAPI 3.1, and for
   3.0 with 3.0's meaning (`nullable`, boolean `exclusiveMinimum`/`exclusiveMaximum`, a `$ref` replacing its
   siblings);
5. every response header the status declares `required` is there.

A body problem says where it is in the body, which keyword failed and where that keyword is in the document, and
quotes at most 80 characters of what was received — never a value under a credential's name, never a registered
secret:

```text
/share: 'x' is not of type 'number', 'null' (keyword 'type' at #/components/schemas/Material/properties/share/type; received "x")
```

With `data_plane: true` a 401/403 (the data plane refused the EDR) or 502/504 (it could not reach the API) is
reported as the data plane's — the API was never asked — unless `expect` names it.

**`labs/validate/api_errors`** reads every answer the test's labs API calls received (or only those of `steps`, or
the `responses` given) and checks the error answers (400 and up): each body has one format — `schema`, RFC 9457
problem details (`format: problem+json`) or by default the schema its operation documents; no body gives away a
stack trace, an exception class, SQL, a source file path, a private address or a cluster-internal host name; and a
request sent wrong on purpose (`expect` of a 4xx, `4XX` or `error`) was not answered with a 5xx. The leak patterns
have no nested quantifiers and read at most 64 KiB of each body.

**`labs/http/api_sweep`** calls each operation that passes `operations`, `tags`, `methods` (default `[GET, HEAD]`)
and `exclude`. A write is called only with `include_writes: true` *and* its own entry in `operations`. Required path
and query parameters come from `params` (by name), header parameters from `headers`, bodies from `bodies` (by
`operationId`); an operation missing one is skipped with the reason. At most `concurrency` calls run at once (4,
at most 16), each within `timeout`, all within `budget_s`. The output is one row per operation — `operation`,
`status`, `verdict` (`passed`, `failed`, `skipped`, `error`), `problems`, `duration_ms` — and the step fails when an
answer is not documented.

In every record of the run a step names the API by its summary with the id (`{"api_document": {"id": "ich", …}}`),
the operation and the request it sent — never the document.

**[PROP]** A mock that answers from the document (`labs/mock/api_from_spec`) and component schemas as types
`<id>.<Schema>` are proposed in ADR-0030 and not built yet.
