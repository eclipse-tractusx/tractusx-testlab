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

**[PROP]** Steps that call, sweep, mock and validate operations of an API file, and component schemas as types
`<id>.<Schema>`, are proposed in ADR-0030 and not built yet.
