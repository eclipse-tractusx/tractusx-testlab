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

### Changed

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
