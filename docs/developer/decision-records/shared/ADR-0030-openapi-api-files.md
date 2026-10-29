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

# ADR-0030: OpenAPI Documents as TCK API Files

## Status

Proposed

## Date

2026-10-29

## Implementation status

Built: §1–3 and §6 — `env.apis`, `${{ env.apis.<id> }}`, the compile-time
checks (`tractusx_testlab.openapi`), and `security/api_key` /
`security/basic`. Not built: §4 (schemas as types) and §5 (the `labs` steps).
A step handed a whole document keeps it, and every record of the run names it
by its summary (`api_document`: `openapi`, `title`, `version`, `sha256`)
instead of copying it.

## Context

A test that calls an HTTP API checks the answer against a JSON Schema, and that
schema is copied by hand out of the API's OpenAPI document into `schemas/`. The
copy drifts from the document it came from, loses the operation it belonged to
(method, path, parameters, status codes) and has to be redone for every release.

Generating the copies does not scale either. One real document, the Industry
Core Hub backend (54 operations), produced 170 generated files — schemas, test
data and tests — none of which a reviewer can check against the document.

The documents already exist. Partners publish them for their products, and the
Catena-X standards publish them for the APIs a participant must offer. A TCK
should be able to carry one as it is and let its tests name operations in it.

## Decision

### 1. A TCK declares API files in `env.apis`

```yaml
# index.yaml
env:
  apis:
    - id: ich                      # ^[a-z][a-z0-9_]{0,49}$
      source: industry-core-hub.yaml  # under apis/
      type: application/vnd.oai.openapi  # optional
```

- Files live under `apis/` next to `schemas/` and `testdata/`, and are packed
  with the other assets.
- `type` is one of four media types. Omitted, it is inferred from the
  extension:

  | `type` | Parsed as | Inferred for |
  |---|---|---|
  | `application/vnd.oai.openapi` | YAML | `.yaml`, `.yml` |
  | `application/vnd.oai.openapi+json` | JSON | `.json` |
  | `application/yaml` | YAML | — |
  | `application/json` | JSON | — |

- OpenAPI **3.0.x and 3.1.x** only. Swagger 2.0 is refused with a message
  that says to convert it.
- One **self-contained** file: every `$ref` is internal (`#/…`). An external
  `$ref` (another file, a URL) is refused.
- An entry says *what* the API is, never *how* it is reached. There is no base
  URL, no connector, no auth in `env.apis`: transport is decided by the steps
  of a test — the same document is called directly in one test and through a
  data plane in the next.

### 2. Tests reference a document as `${{ env.apis.<id> }}`

The reference resolves to the parsed document, read-only. It is a whole value:
a test passes the document to a step, it does not reach into it with
`${{ env.apis.<id>.paths… }}`.

### 3. The compiler validates every API file

For each entry, before anything is packed, with one precise message per
problem (`env.apis[ich] (apis/industry-core-hub.yaml): …`):

1. the file exists under `apis/` and does not leave it;
2. it is at most 5 MB;
3. it parses as its declared type — safe YAML (no tags beyond JSON's, no
   duplicate keys), strict JSON (no `NaN`, no duplicate keys);
4. it is an OpenAPI 3.0.x / 3.1.x document with `info` and `paths`
   (`paths`, `webhooks` or `components` in 3.1);
5. every `$ref` is internal and resolves, and no `$ref` chain is circular.

### 4. Component schemas become types (later phase)

`components.schemas.<Name>` of an API file becomes the type
`<api id>.<Name>` (`ich.CatalogPartCreate`), derived at compile time. A test
declares `returns: { part: { type: ich.CatalogPartRead } }` and the IDE offers
the fields. Not part of the first implementation.

### 5. Steps that read an API file

All ship under the `labs` extension first (`extensions: [labs]`) and lose the
prefix once ratified.

| Step | Inputs | Outputs |
|---|---|---|
| `labs/http/api_request` — call one operation | `api`, `operation` (operationId or `GET /path`), `base_url`, `path_params`, `query`, `headers`, `body`, `timeout` | `status_code`, `headers`, `body`, `operation` |
| `labs/connector/dataplane/api_request` — the same through a data plane | as above, minus `base_url`; `dataplane_url` + `edr_token` from an earlier step (`pull_data_filtered`, `negotiate` + `initiate_transfer`, or `get_edr`) | as above |
| `labs/validate/api_response` — the answer matches the operation | `input`, `api`, `operation`, `status` (optional) | pass/fail: status declared, content type declared, body valid against the response schema |
| `labs/validate/api_errors` — an error answer matches the declared error | `input`, `api`, `operation` | pass/fail: 4xx/5xx declared, body valid against its schema |
| `labs/http/api_sweep` — call many operations | `api`, `base_url`, `methods` (default `[GET, HEAD]`), `include` / `exclude`, `path_params`, `headers` | one result per operation; operations whose required parameters are not supplied are skipped and listed |
| `labs/mock/api_from_spec` — mock operations from the document | `api`, `operations`, `examples` | one `MockInstance` per operation; answers with the document's examples, requests validated against it |

A step records the API id and the operation, not the document, in its inputs.

### 6. Two auth steps for what OpenAPI security schemes declare

| Step | Inputs | Outputs |
|---|---|---|
| `security/api_key` | `key` (secret), `name` (e.g. `X-Api-Key`), `in` (`header` \| `query` \| `cookie`, default `header`) | `api_key` (`AuthToken`, secret), `headers`, `query`, `cookies` |
| `security/basic` | `username`, `password` (secret) | `authorization` = `Basic <base64>` (`AuthToken`, secret), `headers` |

`headers` and `query` plug into `http/http_request`'s `headers` and
`query_params` unchanged. Every output carrying the credential is hidden in
every record of the run; no `returns:` can reveal it.

## Consequences

### Positive

- A TCK carries the document the partner or standard publishes, unchanged;
  a new release is one file replaced, and the compiler says what broke.
- Tests name operations instead of copying schemas; nothing is generated.
- Calling directly or through a connector is a choice per test, not per TCK.

### Negative

- A document that splits itself across files must be bundled into one before
  it is added (`redocly bundle`, `swagger-cli bundle`).
- Swagger 2.0 documents must be converted.
- The `labs` steps are a second way to call HTTP next to `http/http_request`
  until one of them is retired; the ratification decides which.

### Neutral

- `env.apis` adds a fourth asset folder; the package digest already covers
  every packed file.

## Alternatives

| Alternative | Why not |
|---|---|
| Copy schemas into `schemas/` (today) | Drifts from the source, loses the operation, redone per release. |
| Generate schemas, test data and tests from the document | 170 files for one document; reviewers review the generator's output, not the API. |
| Inline the document in `index.yaml` | Mixes a third party's document into the manifest; a release diff becomes a manifest diff; size and license headers get lost. |
| Transport settings in `env.apis` (`base_url`, `via: dataplane`) | Ties a document to one way of reaching it; the same API is called directly and via a data plane in one TCK. |

## Security

- **No network at compile or load.** Nothing is fetched; an external `$ref` is
  refused instead of resolved, so a document cannot make the compiler or the
  engine call out, read a local file, or change after review.
- **Bounded input.** 5 MB per file, safe YAML without custom tags, strict
  JSON, a node budget against alias expansion ("billion laughs"), a nesting
  limit, and a `$ref` chain guard against cycles.
- **Contained paths.** `source` may not leave `apis/` (no `..`, no absolute
  path, no symbolic link out).
- **Secrets masked.** The auth steps register the credential the moment they
  run; `api_key`, `authorization`, `headers`, `query` and `cookies` are hidden
  in traces, reports, events and logs, and cannot be revealed by `returns:`.

## Performance

- Each file is read, hashed and parsed once per compile and once per run;
  parsed documents are cached by `(path, sha256)`, so the validator, the IR
  builder and the player share one parse, and an edited file is never served
  stale.
- The parsed document is read-only, so one instance is shared by every
  reference without copying.
- The operation index the `labs` steps need (`operationId` → method, path) is
  built lazily on first use, not at compile.
