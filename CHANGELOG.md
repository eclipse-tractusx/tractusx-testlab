# Changelog

All notable changes to this repository will be documented in this file.
Further information can be found on the [README.md](README.md) file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- `between`, `one_of`, `none_of`, `has_key`, `not_has_key`, `length_equals`,
  `length_gt` and `length_lt` are part of the ratified assertion operator set —
  the same twenty operators the IDE offers, resolved through one table shared by
  `validate/*` assertions, the registered `validate/*` steps and `flow/if`
  conditions
- `validate/assert/<operator>` is accepted as a spelling of `validate/assert`
  with `operator:`, giving the deleted `assert/<operator>` names a home in the
  surviving namespace
- The three connector delete steps and `digital-twin/provider/delete_shell_descriptor`
  publish `status_code`, so a TCK can assert on a deletion's outcome (204 vs 404)
  instead of asserting on nothing
- `notification/consumer/send` honours `content` in SDK mode; a script writing
  it previously sent an empty notification and got a 200 back for it

- `security/oauth2/client_credentials`, `security/oauth2/password` and
  `security/oauth2/refresh_token` steps — one step per grant, matching the
  IDE's one-block-per-grant Security catalog. Each pins its grant, so the step
  name a script uses is the grant it gets; the former mixed
  `security/oauth2/get_token` step (grant selected by a `grant_type`
  parameter) is removed in their favour
- `digital-twin-registry/consumer/dataplane/get_shell_descriptors` takes the
  AAS v3 paging controls `limit` and `cursor`, and hands the next page's
  cursor back alongside the descriptors — the same paging
  `lookup_shells_by_asset_link` already offered
- Initial repository setup following TRG 2.03 release guidelines
- `validate/schema` step performing full JSON Schema validation of a payload
  against a schema declared in `env.schemas`
- `env.schemas` files are now seeded into the runtime context, resolvable via
  `${{ env.schemas.<id> }}` (both raw and compiled package layouts)
- `json_path_extract` predicate filters (`items[key=value]`), array traversal
  without an index, and nested/dotted predicate keys
- `util/parse_kv` step for parsing delimited `key=value` strings such as an EDC
  `subprotocolBody`
- `util/base64` step for encoding/decoding strings with base64 / base64url, e.g.
  building a base64url `aas_identifier` for the AAS DTR
- `util/log` step for echoing a resolved value while authoring a test
- `digital-twin-registry/consumer/dataplane/lookup_shells_by_asset_link` step,
  searching a counterparty's registry through `POST /lookup/shellsByAssetLink`.
  The same search `lookup_shell` performs, with the criteria in the request body
  instead of base64url-encoded `assetIds` query values, so a lookup with many
  criteria is no longer bounded by the URL length; the paged answer's cursor
  comes back alongside the identifiers and their descriptors, and `limit` /
  `cursor` read the page after it. `mock/dtr` serves the endpoint too
- `digital-twin/submodel/delete` step, removing one submodel from the engine's
  submodel server. It takes the `path` the upload published — the address the
  data actually landed on — and publishes the status the server answered with,
  so a teardown can tell a submodel that was there (204) from one that was
  already gone (404)

### Added

- `step_call` / `tck.test.step.call` — one event per call a step makes,
  published **as soon as its answer comes back** rather than accumulated and
  dumped when the step ends. A DSP pull is a catalog query, a negotiation and a
  poll loop that can run for a minute; the calls now arrive while it runs, in
  order, each naming in `context` the SDK method that made it. The step's
  terminal event carries the verdict, not a transcript of what it had been doing
  (ADR-0016)
- Steps report **what went in and what came out**: `tck.test.step.start` carries
  `inputs`, the `with:` block as the script wrote it, and the terminal event
  carries `inputs` as they *resolved* next to `outputs`. A step that failed on
  what a reference resolved to could not be debugged from the script, which only
  says which reference was written

### Changed

- **Every transcript line names the event it was written from, and a call says
  which call it was.** A step is many calls, and on the console they were many
  identical lines: `step.call [dtr-filterability]`, fourteen times for one
  `connector/consumer/pull_data_filtered`, naming neither the step that was
  calling nor what it called. A call line now carries the step, its position
  within the step, the SDK method that made it
  (`CatalogController.get_catalog`) or `testlab/http_client` when the engine
  called out itself, and the request and the answer. Every line — a call, a
  check, a step outcome, a job event — ends with `id=` and the id of the
  CloudEvent it reports, so the transcript is an index of the trace: take the id
  off the line and the whole exchange, headers and bodies included, is one `jq`
  away. The bodies stay out of the console, where a poll loop would bury the
  run. The event a consumer receives over SSE is unchanged — the id goes to the
  transcript only

- **A variable's value is read as the type it declares at compile time.** A
  `config/connector/policy` written as a `value: |` block with one comma missing
  is text that is not a policy, and it compiled: nothing read the value until
  the run seeded it, so the author met the parse error after the runner had
  started, counted against a line inside the block rather than in the file. The
  compiler now reads every `env.variables` value through the reader the player
  uses (`syntax.variables.read_as_declared`), so `testlab validate` and the
  compile step of `testlab run` refuse it where it is written, alongside every
  other finding in the manifest. The parser's own four-line complaint is stated
  as one line naming the problem and where in the value it is — in the compile
  report and at run start alike, since a compile report lists one finding per
  line and the other three lines were being dropped

- **A DSP step that finds no acceptable offer names the condition that refused
  it.** The SDK reports a catalog whose offers were all turned down as "no valid
  policy was found for any item in the list", which says neither what the
  provider offered nor how it differed from what the script asked for — the
  reader had to fetch the catalog and diff two JSON-LD trees by eye. Both sides
  are now read down to their atomic ODRL conditions and the difference is
  reported as a set: the offers that were compared, what the provider *also*
  requires, and what it does not offer. A provider that added `Membership eq
  active` to a policy a TCK never listed now says exactly that, in the console
  and — structurally, under the step error's `context` — in the trace, for the
  IDE to render (ADR-0016). The failure also stops being reported as an engine
  fault: an offer the provider did not make is a verdict about the deployment,
  so it carries `origin: "sut"` and the code `POLICY_MISMATCH`.
  `connector/consumer/pull_data_filtered`, `pull_data_filtered_by_policy`,
  `do_dsp`, `do_dsp_with_bpnl` and `connector/discover/digital-twin-registry/auth`
  all report it. Every other failure of those steps — a refused connection, a
  negotiation that never finalised — is untouched
- **`data.outputs` in the trace names every output.** A step with several
  outputs was published as a mapping; a step whose whole output is one value —
  `util/base64`, `util/json_path_extract` — published it naked, so the trace
  carried a bare string with nothing saying which output it was, and a reader
  could not treat the two shapes alike. The bare value is now published under
  `value`, the name the script already reads it by in `returns:` and
  `${{ execution.<step>.value }}`. A step that produced nothing still says
  `null`
- **A step error carries its own code and the evidence behind it.** The trace's
  `errors[]` had one code per origin (`STEP_FAILED` / `ENGINE_FAULT`) and no way
  to say more; an error may now name itself and publish structured diagnostics
  under `errors[].context`, which is the shape ADR-0016 always specified and
  nothing filled in
- **Every `env.variables` entry publishes one value, under `value`.** A variable
  used to publish under a noun its verb had chosen — `config/connector/policy`
  published `policy`, `config/connector/asset` published `asset` — so writing a
  reference meant knowing which verb picked which word, and
  `${{ env.usage_policy.policy }}` was a second name for what
  `${{ env.usage_policy }}` already said. The whole variable is now its id, for
  every type. `returns:` naming any other key is a compile error that quotes the
  block to write instead, and so is a reference that reaches into a variable at
  all — `${{ env.usage_policy.value }}` included, since the id already names all
  of it. The player binds the id and nothing beside it, so what compiles is what
  resolves. The TCKs, examples, specification and skills in the repository are
  migrated
- **`env.variables` is validated.** It was the one block nothing checked — its
  schema was `Any` — so a `uses:` verb that does not exist, a type the verb does
  not publish, a `class:` on a plain value, an unrecognized `with.source`, a
  duplicate id, and a variable that neither carries a `with.value` nor asks the
  operator for one all compiled, and the TCK then failed at the first step that
  read the variable. Every rule is bound to the entry's `uses:` verb, which is
  the single source of truth for what the variable publishes
  (`syntax/variables.py`), and every problem in the block is reported at one
  compile. `uses: generate/*` is rejected with what to write instead: the engine
  seeds variables, it does not generate them, so nothing ever supplied a value
  for one
- **`step.start` reports the values, not the templates.** The event a step opens
  with carries its `with:` block with every `${{ … }}` reference already
  substituted for what the run seeded or produced. It used to carry the block as
  the script wrote it, so a trace of a step reading
  `expected_policies: ${{ env.usage_policy }}` named the manifest variable and
  never said what it held — the one thing the reader opened the trace for. The
  block is resolved once, before the event, and handed to the runner rather than
  resolved again. A reference that names nothing in scope is unchanged: the
  block is published as written and the terminal event reports the unresolved
  reference as the step's failure (ADR-0016)
- The terminal step event no longer repeats the wire: `request`, `response` and
  `exchanges[]` are gone from `tck.test.step.passed` / `.failed`, because every
  call was already published as it happened. A 64-call poll loop was writing its
  conversation twice; a catalog answer of 1.6 kB was written four times
- **What the trace, the stream and the transcript show is what was sent.** A step
  driving the SDK writes its own `request`/`response` — the URL its client would
  have used, its parameters as the body, a `200` inferred from not having raised
  — and that account was what the CloudEvents carried, so a trace read to debug a
  SUT described a request nobody sent. The record now carries the call the SDK
  really made (the last one, which is the one that failed when a step failed),
  and `exchanges[]` carries the rest of the conversation from two calls up. The
  result the run keeps is unchanged, so `returns:` and assertions still read what
  the step declared (ADR-0016)
- Credential-bearing headers are masked in the step-named `request`/`response`
  too, not only in the recorded exchanges. A step builds that summary from what
  it was handed, so an `Authorization` header a script set (an EDR token, a
  bearer) reached the transcript, the SSE stream and the trace in clear. The
  masking is applied on the way out; the result the run keeps is unchanged, so a
  `returns: {response_headers: ...}` still reads what the SUT sent
- Every request a step sends and every answer it gets is recorded through the
  SDK's tracing API (`tractusx_sdk.dataspace.tools`, from `tractusx-sdk`
  0.8.2-rc1) instead of by patching `requests.adapters.HTTPAdapter.send`. One
  tracer is activated per step, the engine's own `httpx` calls record through the
  same `trace_call` seam as the SDK's, and each exchange now names in `context`
  the method that sent it — the SDK method for a call the SDK made
  (`CatalogController.get_catalog`), `testlab/http_client` for one the engine
  made. `HttpRequest` also carries the `params` sent alongside the URL
  (ADR-0016)

- **Breaking.** `validate/*` is the whole assertion vocabulary. The `assert/*`
  family (`assert/equals`, `assert/not_null`, `assert/status_code`, …) and the
  flat `NOT_NULL` / `EQUALS` spellings are removed; `validate/assert`,
  `validate/field` and `validate/schema` are what a `validate:` block writes.
  Per [ADR-0025](docs/developer/decision-records/shared/ADR-0025-assertions-read-declared-returns.md)
- **Breaking.** `util/generate_uuid` publishes `uuid` only; the duplicate
  `generated_id` key for the same value is removed. One output, one key
- **Breaking.** The null operator is spelled `is_null`, and the ordered
  comparisons are `gt` / `gte` / `lt` / `lte` — the operator names the IDE
  already emits. `null`, `greater_than`, `less_than`, `greater_or_equal` and
  `less_or_equal` are no longer accepted
- `max_wait` defaults to 60 seconds and `poll_interval` to 1 across every step
  that polls, matching what the IDE's blocks show. The two constant modules that
  declared the same names with different values now derive from one declaration
- `steps/assertions.py` is now the `steps/assertions/` package — the operator
  table, the `uses:` vocabulary and the engine are separate modules

- `digital-twin/provider/wizard/create_submodel_descriptor` takes the endpoint's
  `interface` — the one key CX-0002 leaves a choice in — as an optional param
  defaulting to `SUBMODEL-3.0`. The rest of the endpoint is fixed by the
  standard and written rather than asked for: `endpointProtocol` (`HTTP`),
  `endpointProtocolVersion` (`["1.1"]`), `subprotocol` (`DSP`) and
  `subprotocolBodyEncoding` (`plain`). Its `endpoint_url` is renamed `href`,
  the name CX-0002 and the descriptor it writes both use, and the href now
  follows the chosen interface: a `SUBMODEL-VALUE-3.X` interface appends
  `/submodel/$value` to it (just `/$value` when the URL already ends in
  `/submodel`, nothing when it already carries a `$`-segment), and a
  `SUBMODEL-3.X` interface strips a pasted `$`-suffix back off, so the
  descriptor reaches the registry in the spelling CX-0002 mandates either way.
  `id_short` is optional, and an omitted one leaves `idShort` out of the
  descriptor rather than writing an empty name. A step naming no interface
  produces the exact document it did before
- `digital-twin/provider/wizard/create_submodel_descriptor` takes `asset_id` and
  `dsp_endpoint`, both required, and writes them into the descriptor's
  `subprotocolBody` (`id=…;dspEndpoint=…`, `subprotocol: DSP`, encoding `plain`).
  The guided step used to describe the submodel's endpoint with a bare `href`,
  so the descriptor it assembled told a consumer where the data sits but not
  which offer to negotiate for it
- `digital-twin/submodel/upload` no longer takes `backend_base_url`. The
  submodel server is the engine's own, seeded as `submodel_backend_url`
  (`TESTLAB_SUBMODEL_BACKEND_URL`), so a script cannot redirect the upload
  somewhere the step never meant to write; an engine without one fails the step
  with a `StepConfigError` instead of posting nowhere
- **Breaking.** `digital-twin/submodel/upload` requires `data`. The `{"test":
  true}` default let a script upload a placeholder and then assert against it —
  a test that passed without the provider's data ever being named
- `digital-twin/submodel/upload` addresses a submodel the way the Industry Core
  does — `<server>/<percent-encoded semantic_id>/<submodel_id>`, so submodels of
  one aspect sit together and a data plane can be pointed at the aspect alone.
  The aspect segment is percent-encoded because a raw `#` in a URN would start a
  fragment and cut the id off the address; the id is written as it is, the way
  the TCK stores `.../urn:uuid:<uuid4>`. `semantic_id` is optional: data naming
  no aspect has nothing to group under and is stored at `<server>/<submodel_id>`
- `digital-twin/submodel/upload` takes `submodel_id`, the id the data is stored
  under, and generates a fresh `urn:uuid:<uuid4>` when it is omitted. A
  descriptor written ahead of the upload, or a second run overwriting the first,
  decides the id; it is an id and not an address, so it cannot carry a scheme, a
  host or a `/`. The id is published as its own `submodel_id` output beside
  `path`, so a descriptor, a lookup or a delete names the submodel without
  cutting it back out of a URL it was buried in

### Removed

- `util/generate_bpn`. A BPN is not a value a conformance test invents: it
  identifies a real participant, and the one under test comes from the run's
  environment, not from a generator inside the script. A test that minted its
  own asserted against a partner nobody is.

### Fixed

- **`mock/dtr` reads `GET /lookup/shells` the way the AAS v3 API defines it**,
  and the way the engine's own consumer steps send it: one `assetIds` value per
  criterion, each a base64url-encoded `SpecificAssetId` object. It read one
  value holding the whole list, so pointing
  `digital-twin-registry/consumer/dataplane/lookup_shell` at it raised
  `AttributeError: 'str' object has no attribute 'get'` — each side was tested
  only against its own belief and nothing crossed them. A value holding the list
  is now refused with a 400 naming the encoding to use, and the crossing case is
  a test
- **A mock handler sees every value of a repeated query parameter.** The server
  built `MockRequest.query_params` with `dict(request.query_params)`, which
  keeps the last value for a name and drops the rest — so a lookup with two
  criteria arrived as a lookup with one, silently matching too much. The field
  is the multimap HTTP actually carries, read through `query()` for a
  single-valued parameter and `query_all()` for a repeatable one. `mock/wait`'s
  `request_query_params` is unchanged: a script reading a callback's `state`
  wants the value, not a list holding it
- `connector/consumer/pull_data_filtered` reads its pre-fetched catalog in both
  DSP dialects. It looked only under `dataset`, so a counter-party a generation
  behind — which writes `dcat:dataset` — produced an empty `datasets` and an
  empty `asset_id` from a catalog that was not empty at all
- An `env` variable is seeded as the type it publishes, not as the type YAML
  happened to write. A policy declared `config/connector/policy` and written as
  a `with.value: |` block was seeded as the block's text, so the trace recorded
  a JSON string where the manifest said there was a document and each step that
  cared parsed it again on its own; text under a verb publishing an `object` or
  an `array` is now parsed once, at seeding — as YAML, so a JSON document pasted
  from a connector's API and a block unindented one level too far both land as
  the same structure — and text that is not the structure it declares is refused
  by name instead of travelling on. Operator
  values — a run config or `--var` — are read the same way, and scalars are
  never coerced
- An inbound call to a path no step registered is refused with 404. The mock
  server buffered it and answered 200 instead: a system under test calling a
  callback address that does not exist was told it had succeeded, while the
  script waited out its timeout on the address it did open, and every stray
  request accumulated in the buffer where a later listener on the same path
  could pick it up
- `${{ … }}` references inside a `validate:` block are resolved before the
  comparison runs. Only a step's own `with:` was resolved, so an assertion
  comparing against an earlier step's return — or naming a schema with
  `${{ env.schemas.<id> }}`, the form the IDE emits — received its own template
  text and reported a mismatch against a string nobody wrote
- `validate/schema` inside a `validate:` block validates the payload against the
  schema. It was unrecognised inline and fell back to an exact comparison
  against `None`, so a conforming payload failed with a misleading message
- `validate/field` descends its `path` inside `input`. The path was read and
  discarded, so the assertion checked the whole output rather than the field
  the author named
- An assertion naming an unknown check or an unknown operator is a compile
  error, and a failure that names the vocabulary at run time. Both previously
  fell back to an exact comparison that frequently passed
- A `returns:` name the step never publishes is a compile error naming what the
  step does publish. It previously compiled and resolved to nothing, surfacing
  as an empty variable several steps later

- Path extraction no longer drops predicate values containing `.`/`;`/`#` and
  can traverse into lists after the first segment
- `json_path_extract` accepts a resolved object (a `${{ }}` expression) as its
  `source`, not only a variable name
