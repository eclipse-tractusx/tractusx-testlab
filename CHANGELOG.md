# Changelog

All notable changes to this repository will be documented in this file.
Further information can be found on the [README.md](README.md) file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- The wait steps let a test say what the person driving the system under test
  has to do, and `mock/wait/dataplane/http_request` lets it say which offer to
  find by what it is rather than by id. `with.brief` (both wait steps) takes a
  `message`, the `steps` to take in order and labelled `fields` to copy, and
  the run publishes it as `listener.brief`, for a viewer to show in place of
  what it would derive from the listener. `with.dct_type`, `with.dct_subject`
  and `with.version` describe the engine asset; they reach
  `listener.offer`, whose new `catalog_filters` is the EDC catalog filter that
  finds it (`'http://purl.org/dc/terms/type'.'@id'` and so on) — the asset id
  only when none is given. A system under test should never have to look an
  offer up by an asset id that carries the run's id.
- `testlab compile` (and `run` and `validate`, which compile or check the
  same way) says what it is doing while it does it. It used to print nothing
  until the package was written, so a slow compile looked like a stuck one.
  Each stage now gets a line with its time — reading the manifest, checking
  the tests (each named as it is checked, `2/5 tests/…`), the JSON-schema
  check, building the plan, bundling, sealing or encrypting — and in a
  terminal a spinner shows the stage under way. A stage that fails is marked
  `✗`. The report goes to stderr, so the summary on stdout is unchanged.
  It is coloured — a green `✓`, a red `✗` and failure, dim timings — and so
  are `validate`'s `[ERROR]` (red) and `[WARN ]` (yellow) and the verdict
  line, by the run report's rule: a terminal gets colour, `FORCE_COLOR`
  keeps it in a CI log (without the spinner), `NO_COLOR` drops it.
  `Compiler(progress=…)` takes any `CompileProgress` (`compiler.progress`);
  the default reports nowhere.
- A paused run is held (ADR-0026). Once it stops, it deletes every contract
  definition it created (assets and policies stay) and its mocks answer 404,
  so the system under test finds nothing to negotiate and nothing to call
  until the run resumes. On resume the definitions are posted again with the
  same ids. `mock/wait/*` no longer counts its timeout through a pause: it
  stops with the time it had left (`step_suspended`, `remaining_s`), and after
  the resume it waits that long again, announced by a fresh `step_waiting`.
  New events `job_held` / `job_restored` (`tck.held` / `tck.restored` in the
  trace) name what was withdrawn and put back. `JobManager.is_held(job_id)`
  tells a host serving a run's mocks to turn them away. A paused run that is
  cancelled puts its definitions back first, so its teardown deletes them as
  usual.
- `with.instructions` on a `with.source: register` variable: what the SUT
  operator has to do with the document the TCK hands them — where to register
  it, and how the run will read it back. `source: register` now reads as the
  general handover, on any verb: a certificate the SUT's certificate
  management holds and a pull test retrieves is a `variable/type/object`, not a
  connector document. The compiler rejects instructions that are not text, and
  instructions on a variable that is not handed over (the source was
  forgotten).
- `is_in` operator for `validate/assert`, `validate/field` and `flow/if`: the
  value under test, as text, occurs in `value` — `contains` turned around. An
  echoed id passes with or without its prefix
  (`value: "urn:uuid:${{ execution.mint_id.value }}"` accepts both
  `urn:uuid:<uuid>` and `<uuid>`), and the result's `actual` records which
  one arrived. A missing or empty value is in nothing.
- Sessions (labs): `async: true` on a `tests:` entry of `index.yaml` (with
  `extensions: [labs]`) marks a test to run on demand.
  `TestlabPlayer.open_session()` returns a `TckSession` that holds the run open
  between tests — infrastructure bound, services and mocks up, context kept.
  `run_scheduled()` runs every other test and announces the on-demand ones
  with the new `test_awaiting` event; `run_test(id)` runs one, as often as it
  is asked (`test_started` carries `attempt`, and a re-run forgets what the
  previous attempt published); `close()` tears down and gives the verdict from
  each test's latest attempt, reporting a test never run as skipped.
  `run_tck` is now a session that runs everything, so a plain run is unchanged.
  The compiled package's test entry carries `async: true`, and so does
  `TestInspection.on_demand`.

- `labs/mock/api/dynamic` — a mock that works out its reply per call. Its
  `process:` steps run for every call, on a copy of the run's context and on
  the run's event loop, and its `response_status`, `response_body` and
  `response_headers` are read once they have run. A failing step, a reply that
  names nothing, or steps slower than `process_timeout` (10 s) answer 500 with
  a fixed body and log why. Everything else — the key, the listener for
  `mock/wait/*`, the published address — is `mock/api`'s.
- Call-scoped references, `${{ *.<…> }}`, read per call and only inside
  `labs/mock/api/dynamic`: `*.request.body`, `.headers`, `.query`, `.method`
  and `.path` for the call, and `*.process.<id>.<field>` for what the mock's
  own steps returned. Unlike any other reference, one may reach into the value
  it names (`${{ *.request.body.header.messageId }}`). The compiler refuses
  them anywhere else, and a `process:` step's id is no phase name.
- `labs/util/now` — the current time in UTC, ISO 8601 with milliseconds and a
  `Z`, for a `sentDateTime` a test or a dynamic mock builds.
- A mock handler (`server.mock_registry.MockHandler`) may answer
  asynchronously; both mock routes await it.

- `connector/provider/create_mock_asset` offers one of the run's own mocks as
  an asset on the engine connector (the reflexive asset). The asset is
  described statically by a new variable type, `config/connector/mock_asset`
  (`asset_id`, `dct_type`, `dct_subject`, `version`, …); the data address —
  the mock's root, with path, method and body proxied, and the mock's key as
  `header:<name>` — comes from the `mock:` it is given, so a test never names
  the key. It always registers on the engine connector, and a 409 is an error:
  an asset left by an earlier run forwards that run's key. Give the id the run
  id (`${{ execution.id }}`).
- `hidden: true | false` on a `returns:` entry masks the value (`***`) in
  every record of the run: the execution trace, the events handed to an
  embedder's callbacks, and the console transcript — wherever it occurs, in a
  step input, a request body, a returned value or an inbound header. The value
  the run uses is untouched. Unset, the step decides: an output it marks secret
  is hidden.
- `connector/provider/create_asset` forwards `dct_subject`.

### Changed

- Every `mock/api` requires an API key: a call without it is refused with 401
  and never resolves a `mock/wait/*` step. The key is the run's, shared by all
  of its mocks, and is returned as `api_key` (hidden unless `hidden: false`,
  for a mock the system under test calls directly and whose operator needs
  it). `api_key_header` names the header (default `x-api-key`); `public: true`
  opts a mock out, for an engine step that cannot send a header. The key is a
  keyed BLAKE2b-256 digest (hex) of a 32-byte random nonce, the run id and a
  nanosecond timestamp, under a per-process random salt. A refused call
  is counted, and a wait that times out says how many there were.
  `mock/dtr` and `mock/discovery` do not require the key yet.
- A `mock/wait/*` step fails as soon as the call it waits for arrives in a form
  the mock turns away, instead of running out its timeout: no key (the call
  skipped the connector), another run's key, or — carrying the run's key, or
  on the awaited path — the wrong path or method. The error (code
  `MOCK_CALL_REFUSED`) says which, and for `mock/wait/dataplane/http_request`
  names the asset to negotiate; it never names the header or the key. A
  refusal only ends a wait that is still open, so a stray call after a run
  cannot fail the next one, and a mock registered again starts clean.

### Fixed

- A mistake in the TCK or the run's configuration is no longer reported as a
  failure of the system under test. `AuthoringError` inherited `origin: sut`,
  so an asset id the TCK reused across runs — the engine connector answering
  `connector/provider/create_mock_asset` with 409 — reached the trace as the
  SUT's failure. It now says `origin: authoring` with code `AUTHORING_ERROR`
  (ADR-0016), and the run summary adds a `Fix in:` line under a failure that
  is not the SUT's. A reference that resolves to nothing is `authoring`
  unless the run says otherwise: `*.request.…` reads what the SUT's call to a
  mock did not carry (`sut`, `STEP_FAILED`), and the output of a step that
  failed — or never ran because a failure stopped the test — follows from that
  failure and carries its origin, with the code that goes with it. A teardown
  that withdraws what setup never created, after setup was refused with 409,
  is `authoring` like the refusal. The runner records which steps passed,
  failed or were skipped (by `if:`, or in the `flow/if` branch not taken), so
  the output of one that passed without a `returns:` block, or was skipped, is
  the author's mistake rather than a failure. `InfrastructureError` carries
  `INFRASTRUCTURE_ERROR`, as `BoundServiceError` does, rather than inheriting
  the new code; an engine without a connector or a submodel server bound now
  raises it (it was an `AuthoringError` and a `StepConfigError`).
- `connector/provider/create_mock_asset`'s 409 message tells the author to
  write `${{ execution.id }}`; a missing `f` prefix printed
  `${{{{ execution.id }}}}`.
- `flow/if`, `flow/retry` and `labs/flow/for_each` report their sub-steps'
  checks. The sub-steps' `validate:` blocks were evaluated but only their
  outputs were kept: a check that passed was never reported, a check that
  failed surfaced as "assertion failed" without saying which, a `SOFT` failure
  vanished, and none of them reached the summary or the CAC coverage. They are
  now the flow step's own checks, each tagged with the sub-step it ran on
  (`AssertionResult.step_path`, `validations[].step` in the trace) — for a
  retry only the last attempt's, for a loop every item's under `[<index>]` —
  and the sub-steps' declared checks count towards the test's `declared`.
- A failing sub-step fails its flow step as a verdict (`origin: sut`, or the
  sub-step's own origin) rather than as an engine fault: the `RuntimeError`
  the flow steps raised was classified as a TestLab bug.
- A step's `if:` is checked at compile time. It used to be copied into the
  compiled test unread: an expression the player did not recognise
  (`vars.a == 'x' and success()`) ran its step unconditionally, and a
  variable with a typo read as empty and skipped it. The compiler now refuses
  an expression outside the grammar, a `vars.<phase>.<id>.<field>` naming a
  step that does not run before it or a field it does not list under
  `returns:`, a bare `vars.<name>` nothing in the manifest supplies,
  `steps.<id>.outcome` naming no earlier step of the phase or compared with
  anything but `success`/`failure`/`skipped`, the retired `${name}`
  spelling, and an `if:` on a teardown or nested step, neither of which is
  ever read. `vars.<phase>.<id>.<field>` — a field an earlier step returned —
  is now documented. The player logs the expressions it cannot read instead of
  running past them silently.
- `steps.<id>.outcome` reads the step with that exact id. It matched on a
  substring, so `steps.fetch.outcome` could answer with the outcome of a later
  `fetch_again`.
- A `validate:` entry's `severity` is read in any case — `soft` is `SOFT`,
  `Hard` is `HARD`. `severity: soft` used to stop the run with a `ValueError`.
  Any other value, such as `warning`, is now a compile error located at the
  entry (`validate[<n>].with.severity`, nested steps of `flow/*` and `labs/*`
  steps included); at run time it is a failed HARD check that names it.

- A test the operator skipped now carries its `test_id` in its result (and in
  `test_completed`); it was empty, so a viewer could not tell which row it was.

- `equals` / `not_equals` compare a boolean with text by its YAML spelling:
  `condition_result: True` equals `value: "true"` (in any case). Before this,
  the check fell back to `str(True)`, which is `"True"`, and failed with
  "Expected 'true', got True". Text that spells no boolean still never
  matches one, and text against text stays case-sensitive.
- A step nested in `flow/retry`, `flow/if` or `labs/flow/for_each` publishes
  its `returns:` under its phase and id, as a top-level step does, and the
  compiler knows those ids. The step after a DSP negotiation in the same
  retried sequence can read `${{ execution.<negotiation>.edr_token }}`; it used
  to be refused as naming nothing the TCK supplies, and at run time nothing was
  published under that name either. A retried or looped step leaves the value
  of its latest run.

### Security

- Hardened credential handling. A credential field of an infrastructure
  binding (`infrastructure.<side>.connector.api_key`) is published to a test
  as a handle instead of its value. It may be used only as the whole value of
  an `http/http_request` header sent to that binding's own origin; any other
  use is a compile error and fails the step (`CREDENTIAL_MISUSE`,
  `CREDENTIAL_ORIGIN_MISMATCH`). The connector and registry steps are
  unchanged. A request carrying a credential no longer follows redirects.
- `env.variables` entries take `secret: true`. The value is used as before
  and masked in every record; embedders read the flag as
  `VariableDefinition.secret` (also shown by `testlab inspect --variables`).
- New setting `credential_release` (`TESTLAB_CREDENTIAL_RELEASE`), default
  both sides, lets a host restrict which sides' credentials a test may send
  through `http/http_request` (`CREDENTIAL_NOT_RELEASED`).
- More values are shown as `***` in traces, live events, transcripts and the
  job API: bound credentials (also under a custom `api_key_header`), secret
  variables (`secret: true` on an `env.variables` entry, or a credential-like
  name), EDR tokens
  and data-address authorization, OAuth2 tokens and token-request secrets,
  credential-named fields of recorded request and response bodies, and the
  credential headers of inbound mock calls. A run's own secrets are no longer
  evicted from the masking registry while the run is open.
- Masking covers more spellings and more places. A secret is also masked in
  its escaped, percent-encoded and base64 forms; a declared secret from four
  characters, and in every string and number of an object or list value.
  Credential names are matched by what they contain (`client_assertion`,
  `sut_password`, `X-Vault-Token`) with names like `token_type` or
  `api_key_header` left visible. Inbound mock calls, step outputs, check
  values, URL query parameters (`?access_token=`), `util/log` lines and a body
  cut by the trace are redacted too, and the job API keeps a copy masked when
  the run ends. Whitespace around a secret input or a binding value is
  stripped. A run pins at most 256 values from `returns: … hidden: true`.
- The server a run starts for its mocks (`testlab run`, or a `TestlabPlayer`
  that finds no server to use) serves the mock and callback routes only. An
  embedding host gets the same from `create_app(config, mode="mock")` or the
  new setting `server_mode` (`TESTLAB_SERVER_MODE`: `full` or `mock`);
  `testlab serve` keeps the whole API. `POST /testlab/run/package` runs a
  `path` only when it lies in the server's package store, and answers `403`
  for any other.
- A run's mocks, their keys and the listeners its `mock/wait/*` steps wait on
  are its own: two runs in one process, of one TCK or of two, never answer or
  resolve each other's calls, and a run's mocks are removed when it ends.
  `base_mock_url` and `full_mock_url` carry the run's segment,
  `<root>/runs/<run id>`, unless the root names the run already (an engine's
  `<origin>/mock/<job id>`). A call on the bare path is still answered when it
  can be pinned on one run — the only one serving the path, or the one whose
  key it carries — and with `409` otherwise.
- `testlab config` shows set credentials (binding `api_key`,
  `vault.vault_token`) as `***`, with `--json` too, and `repr()` of the config
  and of the bindings leaves them out; a dump still carries them.
- The private keys `testlab keygen` writes and the compiler's own key are
  created `0600`, and a run's transcript, trace and log file `0600`, in
  directories created `0700`.
- Infrastructure bindings are settled from the run's inputs only. A value the
  TCK package carries (`env` value, shared variable, test data) never changes a
  binding, and the compiler refuses an `env.variables` id under
  `infrastructure.`. New setting `binding_overrides`
  (`TESTLAB_BINDING_OVERRIDES`), default both sides, limits which sides a run's
  inputs may override (`BINDING_OVERRIDE_REFUSED`). A run input that moves a
  connector's address to another origin drops its `api_key` unless it supplies
  one too. `infrastructure.*` is read-only once the run is bound
  (`SEALED_VARIABLE`).
- An EDR's token is a handle bound to its data plane. `edr_token` and the
  `authorization`/`authCode`/`refreshToken` of a `data_address` are sent by
  `connector/dataplane/http_request`, the registry consumer steps and the
  notification direct mode to their own data-plane origin only, and by
  `http/http_request` as a whole header to that origin; they cannot be
  interpolated, logged or put into a body. `token_prefix` shows 4 characters.
  `returns: … hidden: false` no longer shows an EDR or OAuth2 token, only
  outputs a step marks revealable (the `mock/api` key).
- Check paths and `returns:` names never read private attributes.

## [1.0.0a6] - 2026-09-25

### Added

- `labs/flow/for_each` (experimental, `extensions: [labs]`): runs its nested
  `steps:` once per entry of `items:`. A nested step reads the entry as
  `${{ each.item }}` and its position as `${{ each.index }}`; the compiler
  refuses both names outside a loop's steps.
- `labs/connector/provider/query_assets`, `query_policies` and
  `query_contract_definitions` (experimental): list the ids the provider
  connector holds, every page, keeping those that start with `id_prefix`. The
  contract-definition query also matches on `asset_id_prefix` and publishes the
  `policy_ids` and `asset_ids` the kept definitions bind — with `for_each` and
  the existing delete steps, a test withdraws an offer whose ids the connector
  generated.

### Changed

- The nested steps of `flow/retry` and `flow/if` are handed over as written and
  resolve their own `with:` when they run, instead of all at once when the flow
  step starts. A step declares such keys as `deferred_params`. A reference that
  names nothing now fails the nested step rather than the flow step.

### Fixed

- Teardown steps publish their outputs under `teardown.<id>`, as setup and
  execution steps do. The compiler already accepted
  `${{ teardown.<id>.<field> }}`, but the runner published nothing in
  teardown, so every such reference failed at run time as unresolved.

## [1.0.0a5] - 2026-09-25

### Added

- `mock/wait/dataplane/http_request`: waits like `mock/wait/http_request`, for a
  call that has to arrive through the engine connector's data plane. It takes
  the `asset_id` the system under test negotiates, and its `step_waiting`
  listener announces that offer — the asset and the engine connector's
  `dsp_url` and `participant_id` — instead of leaving the mock URL, which on
  that path is only the data plane's target, as the one thing to call.
- `${{ execution.id }}` (ADR-0010 §3.4): the id of the run — the job id an
  engine hands the player — seeded after every input so nothing can override
  it. For a test that has to name what it leaves in a shared system apart from
  another run's. `id` is therefore reserved as an execution step id.
- `Listener.via` (`direct` | `dataplane`) and `Listener.offer`
  (`ConnectorOffer`) on the listening, waiting and received events. A plain
  wait reports `via: direct`.

### Changed

- `Listener` and `ConnectorOffer` live in `models/runtime/listener.py`; both
  are still exported from `tractusx_testlab.models`.
- The E2E suite runs `mock/wait/dataplane/http_request` in a new
  `dataplane_callback.yaml`: this run's asset on the engine connector, visible
  to one BPN, negotiated and posted to through that connector's data plane.
  The workflow checks the waiting events announce `via` and the offer. A unit
  test now fails for any registered step no E2E test uses.

### Security

- A whole-string `${{ }}` reference's value is resolved again only when it is
  TCK-authored content (test data, static `env` values, shared defaults). Step
  outputs — which carry what a remote service answered — operator inputs and
  infrastructure bindings are passed on as data, so a `${{ }}` inside them is
  never expanded. Before, a hostile response could have a later step expand
  an operator credential (e.g. `infrastructure.*.connector.api_key`) into a
  URL or body of its choosing. Authored content may nest references at most
  16 deep; a cycle is a reportable error instead of a `RecursionError`.
  (GHSA-rxvc-664c-hcv4)
- Loading a `.tck` package no longer writes an archive entry outside the
  extraction directory. Entry names with a `..` segment, an absolute path, a
  drive, a backslash or a NUL byte — or that resolve outside through a
  symbolic link — are refused before anything is written, so a hostile
  package (uploaded through `POST /testlab/packages`, or handed over by
  another organisation) can no longer create or overwrite files as the engine
  user. The same check now guards the package paths the player reads: `tests:`
  ids and test data / schema `source` files. (GHSA-5982-hx9j-38f7)
- The server's package storage never writes or removes anything outside its
  own directory. An upload whose file name carries a path (`../x-1.0.tck`,
  `sub/x-1.0.tck`) is refused with `400` instead of being written wherever the
  path pointed, and a `package_id` that is not twelve hexadecimal digits names
  no package: `DELETE /testlab/packages/..` answers `404` instead of removing
  the whole `storage_dir`. Both routes are served by `testlab serve` and by the
  mock server every `testlab run` starts. (GHSA-p5h9-pmx4-4p58)

## [1.0.0a4] - 2026-09-24

### Added

- `mock_public_url` (`TESTLAB_MOCK_PUBLIC_URL`): the mock server's address as
  the system under test reaches it. `mock/api` builds `base_mock_url` and
  `full_mock_url` on it, so a SUT on another host — or an engine behind an
  ingress — is handed a callback it can dial. Unset, the URLs stay
  `http://localhost:<server_port>` as before.
- Experimental extensions (`tractusx_testlab.extensions`): additions that are
  not part of `v1-alpha` yet, which a TCK opts into with `extensions: [...]` in
  `index.yaml`. The compiler rejects an extension's keys, parameters and steps in any TCK
  that did not enable it, and warns about every one that did. Two ship:
  `cac` (the `cac:` key) and `labs` (steps under `labs/` still being tested).
  An extension can also add `with:` parameters to an existing step, declared
  and implemented in its own package with `@extends`. `labs` ships the first:
  `retry_on` on `connector/dataplane/http_request`, which calls again while the
  answer's status is listed. The e2e Umbrella TCK runs `cac` and `retry_on`
  against the live dataspace (`experimental_extensions.yaml`).
  See `docs/developer/extensions.md`

### Changed

- **Breaking.** `cac:` is now the experimental `cac` extension: a TCK using it
  must add `extensions: [cac]` to `index.yaml`
- **Breaking.** The Digital Twin Registry steps form one category,
  `digital-twin-registry`. The provider-side steps that were still under
  `digital-twin/` moved without an alias: `digital-twin/provider/*` is now
  `digital-twin-registry/provider/*` (including `provider/wizard/*`), and
  `digital-twin/submodel/{upload,delete}` is now
  `digital-twin-registry/submodel/{upload,delete}`. Their code lives in
  `tractusx_testlab.steps.digital_twin_registry` next to the consumer steps

## [1.0.0a3] - 2026-09-12

### Changed

- Dependencies are pinned to the versions cleared by the Eclipse Dash IP check,
  `DEPENDENCIES` records that tree, and the check runs in CI
- The package version is a PEP 440 release number (`1.0.0a3`, tagged
  `v1.0.0a3`), independent of the TCK syntax version (`v1-alpha`), which
  changes only when the format does. Earlier releases are superseded: their
  dependency trees predate the IP check
- The publish workflow skips distributions PyPI already holds instead of
  failing, since PyPI never overwrites a published file

### Added

- The E2E deploy watcher restarts an EDC runtime that logged ready but whose
  readiness probe never passes (`ci/restart_wedged_runtimes.py`), after
  fetching the probe paths from inside the cluster for the record. Two of the
  last forty runs sat out the 25-minute helm timeout on exactly that; the
  replacement pod is ready in under a minute
- `testlab run` ends with one result table per test and a run summary table,
  drawn in the same 80-column box the Tractus-X SDK's TCK runners print
  (`✓`/`✗`/`-` icons, RESULT and TIME columns, the verdict and step tally in
  the footer), with PASS, FAIL and SKIP coloured green, red and yellow on a
  terminal. The tally counts skipped steps as skipped; the old summary line
  counted them as failed
- `between`, `one_of`, `none_of`, `has_key`, `not_has_key`, `length_equals`,
  `length_gt` and `length_lt` are part of the ratified assertion operator set —
  the same twenty operators the IDE offers, resolved through one table shared by
  `validate/*` assertions, the registered `validate/*` steps and `flow/if`
  conditions
- `validate/assert/<operator>` is accepted as a spelling of `validate/assert`
  with `operator:`, giving the deleted `assert/<operator>` names a home in the
  surviving namespace
- The three connector delete steps and `digital-twin-registry/provider/delete_shell_descriptor`
  publish `status_code`, so a TCK can assert on a deletion's outcome (204 vs 404)
  instead of asserting on nothing
- `notification/consumer/send` honours `content` in SDK mode; a test writing
  it previously sent an empty notification and got a 200 back for it

- `security/oauth2/client_credentials`, `security/oauth2/password` and
  `security/oauth2/refresh_token` steps — one step per grant, matching the
  IDE's one-block-per-grant Security catalog. Each pins its grant, so the step
  name a test uses is the grant it gets; the former mixed
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
- `digital-twin-registry/submodel/delete` step, removing one submodel from the engine's
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
  `inputs`, the `with:` block as the test wrote it, and the terminal event
  carries `inputs` as they *resolved* next to `outputs`. A step that failed on
  what a reference resolved to could not be debugged from the test, which only
  says which reference was written

### Changed

- **A TCK is made of tests, and the code says so.** The engine called them
  scripts (`TestScript`, `ScriptResult`, `script_started`, the `Scripts`
  section of `testlab inspect`), the manifest called them tests (`tests:`,
  `skip_tests`) and the run summary used both. One word now: `Test`,
  `TestDefinition`, `TestResult`, `TestStatus`, `Tck.tests`, `run_test`,
  and the `tractusx_testlab.scripting` package is
  `tractusx_testlab.authoring`. Where "test" meant the whole package it
  says TCK: `testlab compile` and `testlab validate` take a TCK manifest,
  a job runs a TCK, and the server's routes are
  `/testlab/tck-execution/...`. On the event stream the IDE reads,
  `script_started` / `script_completed` are `test_started` /
  `test_completed`, the `script` field is `test_id`, and the result's
  `script_id` / `script_name` are `test_id` / `test_name`. No aliases are
  kept
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
  provider offered nor how it differed from what the test asked for — the
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
  `value`, the name the test already reads it by in `returns:` and
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
  the test wrote it, so a trace of a step reading
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
  it was handed, so an `Authorization` header a test set (an EDR token, a
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

- `digital-twin-registry/provider/wizard/create_submodel_descriptor` takes the endpoint's
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
- `digital-twin-registry/provider/wizard/create_submodel_descriptor` takes `asset_id` and
  `dsp_endpoint`, both required, and writes them into the descriptor's
  `subprotocolBody` (`id=…;dspEndpoint=…`, `subprotocol: DSP`, encoding `plain`).
  The guided step used to describe the submodel's endpoint with a bare `href`,
  so the descriptor it assembled told a consumer where the data sits but not
  which offer to negotiate for it
- `digital-twin-registry/submodel/upload` no longer takes `backend_base_url`. The
  submodel server is the engine's own, seeded as `submodel_backend_url`
  (`TESTLAB_SUBMODEL_BACKEND_URL`), so a test cannot redirect the upload
  somewhere the step never meant to write; an engine without one fails the step
  with a `StepConfigError` instead of posting nowhere
- **Breaking.** `digital-twin-registry/submodel/upload` requires `data`. The `{"test":
  true}` default let a test upload a placeholder and then assert against it —
  a test that passed without the provider's data ever being named
- `digital-twin-registry/submodel/upload` addresses a submodel the way the Industry Core
  does — `<server>/<percent-encoded semantic_id>/<submodel_id>`, so submodels of
  one aspect sit together and a data plane can be pointed at the aspect alone.
  The aspect segment is percent-encoded because a raw `#` in a URN would start a
  fragment and cut the id off the address; the id is written as it is, the way
  the TCK stores `.../urn:uuid:<uuid4>`. `semantic_id` is optional: data naming
  no aspect has nothing to group under and is stored at `<server>/<submodel_id>`
- `digital-twin-registry/submodel/upload` takes `submodel_id`, the id the data is stored
  under, and generates a fresh `urn:uuid:<uuid4>` when it is omitted. A
  descriptor written ahead of the upload, or a second run overwriting the first,
  decides the id; it is an id and not an address, so it cannot carry a scheme, a
  host or a `/`. The id is published as its own `submodel_id` output beside
  `path`, so a descriptor, a lookup or a delete names the submodel without
  cutting it back out of a URL it was buried in

### Removed

- `util/generate_bpn`. A BPN is not a value a conformance test invents: it
  identifies a real participant, and the one under test comes from the run's
  environment, not from a generator inside the test. A test that minted its
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
  `request_query_params` is unchanged: a test reading a callback's `state`
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
  test waited out its timeout on the address it did open, and every stray
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
