# Architect Knowledge Base — Tractus-X TestLab

> This file is the living architectural memory of `testlab-architect`.
> It is read at the start of every session and updated whenever new architectural knowledge is gained.
> Organized by category. Append new entries — never delete old ones (use strikethrough if superseded).

---

## Architectural Decisions

<!-- Format: ### AD-{n}: {Title} | Date: YYYY-MM-DD | Status: Active | Superseded | Deprecated -->

### AD-1: Block definitions are JSON, never TypeScript
- **Date**: 2025
- **Status**: Active
- **Decision**: Block definitions live in `ide/public/blocks/{category}/{block}.json`. TypeScript only loads them at runtime via `blockDefinitions.ts`. Never hardcode block structure in `.tsx` or `.ts` files.
- **Rationale**: Separates content from code. Non-developers can add blocks without touching TypeScript.
- **Consequences**: `ide/public/blocks/index.json` is the manifest; all tooling must respect it.

### AD-2: Python testlab is a thin orchestration layer
- **Date**: 2025
- **Status**: Active
- **Decision**: `tractusx_testlab` delegates all protocol logic to `tractusx-sdk>=0.7.0`. Never reimplement EDC connector logic, DSP flows, or AAS operations in the testlab itself.
- **Rationale**: SDK is the canonical implementation of Tractus-X protocols. Duplication creates drift.
- **Consequences**: Any protocol change requires an SDK upgrade, not a testlab change.

### AD-3: ~~Variable syntax is `@variable_name` in YAML~~
- **Date**: 2025
- **Status**: Superseded by AD-6
- **Decision**: ~~All variable references in test YAML use `@variable_name` syntax.~~
- **Rationale**: ~~Unambiguous, simple to parse, consistent across all test cases.~~

### AD-6: YAML Syntax v2 — Scoped variable system (GHA-inspired)
- **Date**: 2026-05-20
- **Status**: Active (ADR-0010)
- **Decision**: Variable references use `${{ vars.x }}` for step-output variables and `${{ env.x }}` for environment/TCK-global variables. Keywords change: `type`→`uses`, `params`→`with`, `store_in_memory`→`returns`. No backward compatibility with `@` syntax.
- **Rationale**: GHA-style is familiar to developers, scoped references enable compile-time ambiguity detection, typed `returns` integrates with the class system (AD-5).
- **Consequences**: Full migration required across IDE + backend. Migration CLI needed for existing YAML files. See `docs/developer/yaml-v2-variable-migration-plan.md`.

### AD-7: ~~Environment and services managed at TCK level (ADR-0011)~~
- **Date**: 2026-05-20
- **Status**: Partially superseded by AD-9 (§ service config moved to engine bindings)
- **Decision**: ~~All services and env variables are declared in the TCK manifest `env:` block with full config (URL, auth).~~ Service *configuration* now lives at engine level (AD-9); the TCK declares abstract *requirements*. Env-variable management at TCK level still stands.
- **Rationale**: One configuration point per TCK avoids duplication, enables compile-time validation of all references, and maps 1:1 to the IDE Environment Editor.
- **Consequences**: Tests are never self-contained — they always need a parent TCK manifest. Manual variables introduce async complexity (runtime pauses). Service type registry must be maintained.

### AD-9: Service Requirements (TCK) vs Engine Bindings (operator) — ADR-0019
- **Date**: 2026-06-04
- **Status**: Proposed (ADR-0019, amends ADR-0011 §1–§4)
- **Decision**: Two top-level blocks replace `env.services`. (1) `dataspace:` = ecosystem **context** (`ecosystem` e.g. Catena-X, `version` e.g. saturn) — NOT a bindable service; it supplies the default `version` constraints inherit. (2) `infrastructure:` names two bindable **sides**: `engine` (embedding host operates — TestLab as a library, named generically for host-agnosticism) and `sut` (System Under Test must provide). Side keys are plain identifiers (no hyphens) so they stay valid in `${{ }}` dot-paths. Under each side, capabilities are keyed (`connector`, `dtr`); value = object with explicit `required: true|false` (the required/optional marker) plus an optional `standard` constraint — an object with `id` (e.g. CX-0018) and `version` (e.g. 2.1.3), where `standard.version` inherits from `dataspace.version`. The old `metadata.dataspace_version` is REMOVED — `dataspace.version` is the single source, nothing duplicates it. Constraints are the EXCEPTION not the rule — only write them where the TCK genuinely certifies a specific version (usually the SUT under test); common case is bare `required: true`. No `name`/`role` fields, no list. Operator supplies `bindings` mirroring the `infrastructure` shape; secrets live only there. Engine matches keys, validates constraints, fails fast; unbound `sut` capability = unmet precondition (unifies with ADR-0018). Steps reference `${{ infrastructure.<side>.<capability> }}`; IDE class filtering keys off capability. A capability GATES its blocks — a block whose capability is not `required: true` cannot be used; using it fails fast in the IDE and at compile time with a typed error (no silent runtime no-op). Rationale for `required: true|false`: not every certification needs every capability — e.g. Discovery Finder, BPN/EDC discovery, shared services (BPDM) authorize via IAM (OAuth2/OIDC), NOT connector contract authorization, so those TCKs mark `connector: { required: false }` and the engine neither demands a connector binding nor offers connector blocks. Direction (provider/consumer, "inbound/outbound") is NOT modelled — it is per-step; one capability = one instance per side. Two distinct connectors on one side deliberately deferred. Mock server is NOT a bindable capability — it is the engine's own built-in component (never declared/bound). Shared dataspace operator services (discovery finder, identity, BPN/EDC discovery) deliberately NOT modelled as bindable capabilities — over-engineering rejected (human, 2026-06-04): pinning versions on services the operator can't upgrade is a brittle gate.
- **Rationale**: Separates portable "what a TCK needs" from volatile "how it is deployed" — the Helm/npm peerDependencies & ports-and-adapters pattern. Removes per-TCK config duplication, keeps secrets out of portable test content, and turns the near-universal "SUT must expose a connector" need into a first-class declared requirement instead of repeated config.
- **Consequences**: TCKs become deployment-portable (swap binding profile). New maintained surfaces: capability registry + binding-profile schema/loader. Migration converts existing `env.services` → `requires`/`sut` keys + default binding profile. Open: binding-profile location (CLI flag / engine config / env injection).

### AD-10: Frontend vendors its own copy of the policy JSON Schemas (Option A)
- **Date**: 2026-06-08
- **Status**: Active (ADR-0020)
- **Decision**: The policy JSON Schemas are duplicated into the frontend at `ide/schemas/policies/{saturn,jupiter}/` (build-time data dir — NOT `public/`, NOT `src/`). The codegen `ide/tests/generate-constraint-registry/index.ts` reads only from inside `ide/` (`resolve(scriptDir, "../../schemas/policies")`); no path climbs to `../../src`. The backend keeps its own copy at `src/tractusx_testlab/schemas/policies/` as the Python-player runtime contract. The two independent copies are kept byte-identical by a blocking CI diff guard (`diff -r`), with NO shared package.
- **Rationale**: Frontend and backend must be independent — neither codebase may reach across the boundary. The codegen is build-only (the browser never fetches the schemas), so the schemas belong in a non-served, non-bundled data dir.
- **Consequences**: Drift risk accepted, mitigated by CI diff. 30 saturn JSONs stay flat (5-file rule is source-code-only). Only the emitted `saturnSource`/`jupiterSource` provenance strings change in the generated registry; constraint data is byte-identical. The un-vendored dspace `contract-schema.json` refs are unaffected (codegen never resolves them).
- **Refinement (2026-06-08, see AD-11)**: AD-10 established the independent-copies boundary; AD-11 refines *how versions are declared* on top of it (config-driven manifest). AD-10 is NOT superseded — the vendoring + independence decision stands; AD-11 builds on it.

### AD-11: Config-driven manifest model for policy versions (refines AD-10/ADR-0020)
- **Date**: 2026-06-08
- **Status**: Active (ADR-0020, refinement of AD-10)
- **Decision**: Dataspace versions are declared as DATA in `ide/schemas/policies/manifest.json` (per-version `id`, schema folder, ref-resolution `strategy`, optional editorial overlay). The codegen `ide/tests/generate-constraint-registry/` ITERATES the manifest and never names a version literally. Ref resolution is pluggable via two registered STRATEGIES: `catenax-atomic-buckets` (saturn-style external + per-constraint `$ref`s) and `selfcontained-defs` (jupiter-style internal `$defs`). Generated output is keyed by version: `PolicyVersion` union from manifest ids, `POLICY_VERSIONS`, `VERSION_SCHEMAS`, `VERSION_BUCKETING`, `CONSTRAINTS_BY_VERSION`; `preconditionTypes.ts` re-exports the generated union. Consumers read keyed/manifest-derived data, never hardcoded version lists. Per-version overlay is OPTIONAL with sane defaults. **Zero-code new-version contract**: a version fitting an existing strategy = drop schema folder (both vendored copies) + one manifest entry + `npm run generate:registry` → ZERO code. The single documented exception: a genuinely new ref-resolution shape needs one new strategy function.
- **Rationale**: Imperatively naming versions in the codegen and hardcoding version lists in consumers made every new version a code change. Making the version set data-driven turns the common case into pure configuration and keeps "one way to do things".
- **Consequences**: Two CI guards in `.github/workflows/test.yml` job `frontend-checks`: `verify:registry` (regen-clean) and `verify:schemas` (per-version frontend↔backend `diff -r` + manifest↔backend parity). The schema guard iterates the manifest, so it scales to N versions with no workflow edit. Independence/no-cross-boundary is now a guarded invariant. Verified green on landing: tsc 0, build, 27 goldens, regen-clean.
- **Refinement (2026-06-08) — 1:1 upstream mirror**: Where an upstream folder exists, the vendored copy is a VERBATIM byte-for-byte, folder-for-folder mirror — not just the files codegen reads. SATURN now mirrors upstream CX-0152 `assets/` (catenax-eV/catenax-ev.github.io, pinned SHA `85f1ad8acdb6a835a40a3422119c3ecd2a1ec055`): root atomic/context/policy schemas + `PROVENANCE.txt`; `constraint/` (27); `context/` (`context.jsonld`, `odrl.jsonld`); `samples/` (31). `context/` + `samples/` are carried even though codegen ignores them, so a spec bump is a RE-DOWNLOAD not a reshuffle. Frontend + backend saturn copies are byte-identical (recursive `verify:schemas`, now covering nested dirs). **constraintDir mechanism**: codegen tolerates upstream nesting via a new OPTIONAL manifest field `constraintDir` (`"constraint"` for saturn, ABSENT for jupiter) — nesting versions set it, flat ones omit it; "new version = data only" contract preserved. jupiter (our own schema, no upstream) stays FLAT/self-contained. **sync:schemas**: opt-in test (`ide/tests/sync-schemas/`) re-downloads the upstream tree at the pinned SHA, prunes files no longer upstream, rewrites `PROVENANCE.txt`; NOT in CI (codegen never needs network) → future bump is one command. **Deliberate divergence-drop**: vendored copy carries NOTHING beyond upstream — local-only constraints `managed-legal-entity-bpnl` + `managed-legal-entity-region` were DROPPED (27 upstream vs our prior 29); saturn `usage_permission` 24→22. Human rationale: "official schema = source of truth, clean, no backward compat." (`cx.sharing.managedLegalEntity:1` survives as an enum VALUE of `confidential-information-sharing` — upstream, unrelated to the dropped left-operands.) **Headers**: vendored upstream JSON carry NO Apache/AI headers (third-party data, even though same-org hosted); provenance lives in `PROVENANCE.txt`. Verified green: tsc 0, vite build, 27 goldens, `verify:schemas` PASS, python 320 passed.

### AD-4: No source-code file exceeds 300 lines
- **Date**: 2025 (revised 2026-05-29)
- **Status**: Active
- **Decision**: Every source-code file (Python, TypeScript) must stay under 300 lines. Split into modules when approaching the limit. **Documentation files (Markdown — ADRs, specifications, guides) are EXEMPT**: prefer splitting long pages into sub-pages for readability, but a self-contained reference may exceed 300 lines when splitting would harm comprehension.
- **Modularity directive**: The 300-line limit is a symptom check, not the goal. Code must be written modular from the start — small single-responsibility units with typed boundaries. When a file is split, extract **reusable** units along responsibility seams (hooks, pure functions, helper modules, one step/class per file), not arbitrary fragments. Shared logic is extracted into importable helpers; never duplicated.
- **Rationale**: The limit keeps code readable, reviewable, and single-responsibility. Documentation has different constraints — a cohesive reference (e.g. an ADR or spec) is often more useful kept whole than fragmented across pages.

### AD-5: Typed variable class system for block I/O
- **Date**: 2026-05-19
- **Status**: Active (ADR-0009 Accepted)
- **Decision**: Block outputs declare a `class` (semantic type). Block inputs declare `accepts` (list of compatible classes). The IDE filters dropdowns by class compatibility. A class registry at `ide/public/blocks/classes.json` is the canonical taxonomy. Both fields are optional for backward compatibility.
- **Rationale**: Unfiltered variable dropdowns cause user errors. Typing makes block contracts explicit and enables auto-link improvements.
- **Consequences**: One-time migration of all block JSONs. Taxonomy must be maintained. "Show all" override prevents over-constraining.

### AD-8: Unified Variables model — preconditions become complex variables
- **Date**: 2026-06-04
- **Status**: Active (ADR-0018 Accepted, finalized by ADR-0021 — the backward-compatible precondition path is removed, see AD-12)
- **Decision**: Unify preconditions and variables into one `Variable` discriminated union (`kind: simple | complex`). Simple is discriminated again on `source: value | input | generated`; complex (= today's preconditions) carries `builder`, canonical `payload` JSON and an optional `formula` authoring lens. Runtime classification rule: `input`→REQUEST, `value`→KNOWN, `generated`→GENERATE. A new resolution phase seeds `StepContext` before steps; the existing `@name` resolver is reused unchanged. Generators live in a backend registry exposed via `GET /generators` (catalog like blocks/index.json); IDE consumes via `useGeneratorCatalog()`. Legacy `preconditions` field + `PreconditionLog` kept; `to_variable()` converter + parser synthesis preserve back-compat.
- **Rationale**: Two authoring models + two runtime code paths for one user intent ("prepare the run") violate "one way to do things". Reuse-first: precondition editor becomes the complex-variable editor.
- **Consequences**: Converter/parser-synthesis layer maintained until legacy field deprecated. Two persisted reps (payload canonical + formula lens) need sync rules. New maintained surfaces: generator registry + format catalog.

### AD-12: Precondition concept removed entirely — unified variables only
- **Date**: 2026-06-08
- **Status**: Active (ADR-0021 Accepted)
- **Decision**: The precondition concept is removed as an intentional breaking change (not a deprecation). Removed: the `precondition/*` step family, the `preconditions:` manifest block, the `PRECONDITION` execution phase + runner, and all related models/schema/IDE blocks/docs. Legacy `precondition/*` YAML is rejected by the compiler, not translated. Prerequisites are declared once as complex variables in `index.yaml` `env.variables` (`uses: config/connector/policy`) and referenced via `${{ env.<id>.<field> }}`. ADR-0021 supersedes ADR-0004, ADR-0007, ADR-0013 and finalizes ADR-0018 by removing the backward-compatible precondition path 0018 had retained.
- **Rationale**: Two authoring models + two runtime paths for one intent ("prepare the run") violate "one way to do things". The unified-variables approach was proven end-to-end on the `certificate-management-v2.0` example (zero preconditions remain).
- **Consequences**: Breaking for existing precondition YAML — must migrate before compile/run. Historical compiled artifacts/traces with `precondition/*` no longer reflect the model. Less surface area: no separate phase, runner, block family, or schema branch. ADR-0004/0007/0013 removed from the published mkdocs nav (files retained for history); index registry keeps them marked Superseded.
- **Refinement (2026-06-09) — deprecated ADRs live in a subfolder**: Superseded/deprecated ADRs are physically relocated to `docs/developer/decision-records/deprecated/` (via `git mv`, history preserved). ADR-0004, 0007, 0013 (Superseded) and ADR-0006 (Deprecated) now live there. Inbound links from active ADRs + `index.md` gained a `deprecated/` prefix; the moved files' outbound links gained `../`. They stay OUT of the mkdocs nav but remain in the index registry table (links point into `deprecated/`). Convention for future superseded/deprecated ADRs: move the file into `deprecated/`, keep the registry row, remove it from the nav, fix relative links both directions.
- **Refinement (2026-06-09) — deprecated ADRs EXCLUDED from the published site**: Off-nav was not enough (mkdocs still built them as orphan pages). `mkdocs.yml` now has a top-level `exclude_docs` block (gitignore-style) listing `developer/decision-records/deprecated/` and `developer/backup.md` (a declined draft). Excluded files are NOT built, so every inbound link to them was DE-LINKED to plain text (kept as readable `ADR-NNNN — Title (not published)`): index.md registry rows for 0004/0006/0007/0013, ADR-0021 "Supersedes" list, ADR-0018 "Builds on", ADR-0014 reference. Verified: `mkdocs build` exit 0, zero warnings mentioning the excluded paths, no `site/.../deprecated/` or `site/developer/backup*` emitted. Convention: when removing an ADR/page from the published site, add it to `exclude_docs` AND de-link every inbound reference (links to excluded files are validation warnings). `git mv` preserves the file for history.
- **Refinement (2026-06-09) — execution-trace format aligned to variables (ADR-0016/0017 + examples)**: AD-12 removed preconditions from authoring/runtime but the *proposed* trace-format ADRs still emitted `tck.precondition.*` events. Aligned them: ADR-0016 now emits `tck.variable.*` resolution events (`resolve.start`/`resolved`/`resolve.failed`/`resolve.skipped`/`input.required`/`input.received`, keyed by disposition `known|request|generate` per ADR-0018), and reclassifies engine/SUT infrastructure prerequisites as `tck.boot.binding.*` boot events (per ADR-0019). `source` convention: variable events use the variable's `uses` value or `testlab/player/variables`; binding events use `testlab/player/boot`. `id` scopes added: Variable = `<tckid>/<varname>/<type>/<hash>`, Boot binding = `<tckid>/<side>.<capability>/<type>/<hash>`. ADR-0017 renamed precondition→variable throughout (event types, "One Input Per Variable", JWT/nonce flow, trace examples). The `certificate-management-v2` reference traces (`execution/` + `plain/`, byte-identical) regenerated 36→34 events: 4 infra-precondition events collapsed into 2 `tck.boot.binding.*` events, `tck.boot.passed` moved after bindings (`services`→`bindings`), 5 prerequisite events converted to variable-resolution events, all test-lifecycle sequences renumbered −2. Open item (deliberately NOT harmonized, in scope-minimal mode): ADR-0016 still uses `correlation_id` while ADR-0017 says a JWT callback token replaces it — flagged for a future pass. **LESSON**: when a model-level concept is removed (AD-12), audit ALL *proposed* ADRs and example artifacts that reference it — observability/trace specs and fixtures lag the model and must be swept too, not just the authoring/runtime ADRs.
- **Refinement (2026-06-09) — steps reference ONLY variables; infrastructure/bindings never step-facing (ADR-0019)**: ADR-0019 §4 previously exposed a SECOND step-facing namespace — `${{ infrastructure.engine.connector }}` / `${{ infrastructure.sut.connector }}` — alongside variables, contradicting "one way to do things" and the unified variables model. Human directive: a step's ONLY reference surface is a **variable**. Rewrote §4 ("Steps reference variables, never infrastructure or bindings"): the `infrastructure:`/`bindings:` blocks remain as topology declaration (author) + operator config, but they are engine-internal and NEVER referenced by steps. The two sides resolve differently — **engine side = hidden boot plumbing** (player drives it implicitly, validated via `tck.boot.binding.*`, never reaches a step, honours "hide plumbing"); **SUT side surfaces as a variable** (`known` when operator pre-bound, `request` when unbound → operator fills at run start), and steps reference its fields, e.g. `${{ env.sut_connector.counter_party_address }}`. Also swept the last precondition language out of ADR-0019 (§3 "unmet preconditions"→"unresolved `request` variables", Context, `sut:` YAML comment, Consequences "precondition model"→"variables model"). Class-based IDE filtering (ADR-0009) still keys off the capability to decide WHICH blocks are offered; what a block REFERENCES is always a variable. **PATTERN**: capability/topology decides block availability (IDE/compile-time gating); variables are the only runtime data a step consumes — keep these two axes separate. Note: `live-execution.md` still lists a `PRECONDITION` execution phase (stale per ADR-0021) — flagged, NOT yet swept (user-facing IDE doc, separate pass).
- **Refinement (2026-06-09) — engine EDC/DTR config injection happens once at boot, secrets encrypted (ADR-0019 §4 + ADR-0016)**: Follow-on to the step-references-only-variables decision — if steps don't name the engine connector/dtr, *how* does a `connector/*`/`dtr/*` step get its EDC/DTR config? Human decision (3 forks, all option A): (1) **implicit injection by capability** — the player resolves the engine binding from the operator profile and injects it by the step's `uses` capability (`connector/*`→`engine.connector`, `dtr/*`→`engine.dtr`); the `connector_service`/`dtr_service` handle is REMOVED from authored steps entirely. (2) **Surfaces once at boot** via `tck.boot.binding.passed` per engine capability — non-secret config (`dsp_url`/`management_url`/`bpn`/`version` for connector; `base_url`/`version` for dtr) in event `outputs`; secret fields (`auth`/`api_key`/`client_secret`/credentials) JWE-encrypted per ADR-0016 Secret Protection, NEVER plaintext in logs. Compiled artifact uses a capability-keyed binding, not per-step `$ref`s. (3) **Spec only** this pass — added a "Boot Binding Events" subsection to ADR-0016 (table of clear vs `$jwe` fields per engine capability) and expanded ADR-0019 §4 + Consequences. **DEFERRED** (NOT done): regenerating the stale `certificate-management-v2` example bundle — it's TWO generations behind: 10 `raw/tests/*.yaml` still write `connector_service: ${{ infrastructure.engine.connector }}` + `uses: precondition/provide`; `plain/tck-execution.json` still has `$ref: infrastructure.engine.connector`/`infrastructure.sut.connector.*` + a `precondition/provide` instruction; `compiled-test-backup.json` is even older (`env.services.*`, ADR-0011 model); traces have NO `engine.dtr` binding event. **SECURITY LESSON**: "inject config into logs" is a redaction trap — any binding/credential written to a trace MUST route through the existing JWE Secret Protection; surface this flag whenever someone asks to log infra/config.
- **Refinement (2026-06-09) — boot announces requirements + service lifecycle events (ADR-0016 + ADR-0019 + example)**: Human request — the trace must (1) announce that the SUT needs a connector and a DTR (each capability has an enabled/disabled config), and (2) log when the engine starts a service (e.g. the connector client, the mock server). Two new event families added to ADR-0016 and demonstrated in the example trace. (a) **`tck.boot.requirements`** — emitted ONCE right after `tck.boot.start`, before bindings/services; `data = {dataspace, infrastructure}` mirrors the manifest's resolved topology; `required:true` = enabled, `required:false` = declared-but-disabled. Tells operator/IDE up front what each side (esp. the SUT) must provide. (b) **`tck.boot.service.{start,ready,failed}`** — engine-OPERATED components the player starts itself (built-in **mock-server** = no binding; **connector** client = has BOTH a `binding` + a `service`, since binding validates the external endpoint and service is the engine-side client using injected config). Distinct from `tck.boot.binding.*` (which only validates an external endpoint). `start data={service, capability?, side?}`; `ready` adds `outputs?` (e.g. mock-server `{base_url, port}`) + `duration_ms`. `tck.boot.passed` now carries SEPARATE `bindings:[]` and `services:[]` lists (mock-server moved out of `bindings` — it was never a binding). Boot order: start → requirements → binding.start/passed → service.start/ready (per service, after its binding) → passed. **Example wiring**: `raw/index.yaml` infrastructure now declares `engine{connector:true, dtr:false}` + `sut{connector:true, dtr:true}` (demonstrates BOTH enabled and disabled, and that the SUT needs connector+dtr); the trace gained a `tck.boot.requirements` event, 4 service events (mock-server + connector start/ready), a `sut_dtr` **known**-disposition variable (DTR url + JWE-encrypted auth), and a corrected `tck.boot.passed`. Both `plain/` and `execution/` traces grew 34→41 events and stay byte-identical. **STILL DEFERRED**: the 10 `raw/tests/*.yaml`, `tck-execution.json`, `compiled-test-backup.json` remain on the old precondition/`infrastructure.*`-handle model.
- **Refinement (2026-06-09) — config variables emit their config-schema `$ref` (ADR-0016 + example)**: Human request — "emit the policies that need to be configured (as variables) using the variables config schema as we specified". The *specified* schema is the ONLY schema dir, `ide/schemas/policies/`, selected by `dataspace_version` via `policies/manifest.json` (saturn → `atomic-constraint-schemas.json`, `$id https://w3id.org/catenax/2025/9/policy/schema/atomic-constraint-schemas.json`; jupiter → `$id urn:tractusx:testlab:policy:jupiter`). **Gap**: `config/connector/policy` variables (e.g. the `ccm_policy` KNOWN var) emitted NO schema, while `request` variables already carried a full `schema` in `tck.variable.input.required`. **Decision**: a variable bound to a config capability that publishes a schema MUST carry a `schema` in its resolution events, ALWAYS as a JSON-Schema `{"$ref":"<config schema $id>"}` (never an inline ad-hoc copy) so author, operator, and trace validate the policy against ONE source of truth (the same variables config schema the IDE authoring uses). Disposition map: `known`/`generate` → `schema` on `tck.variable.resolve.start`; `request` → the same `$ref` as `input.required.schema`. Vars with no published config schema omit it. **PATTERN**: domain config that the IDE already validates against a published schema must be REFERENCED by `$id` in the trace, not re-described inline — keep one schema, three consumers (author/operator/trace). **Edits**: ADR-0016 `resolve.start` row → `{name, uses?, disposition, schema?}` + new "Config Variable Schema" subsection (saturn/jupiter `$id` table + disposition mapping); both traces added the `$ref` to `ccm_policy` resolve.start (still 41 lines, byte-identical, valid JSON). Build exit 0, 53-warning baseline unchanged.
- **Refinement (2026-06-09) — mock server is part of the testlab backend, NOT a per-run boot service (ADR-0016 + example)**: Human correction to Phase 5 — "the mock server is part of the test lab backend not a separate service." Phase 5 had wrongly modeled `mock-server` as a `tck.boot.service.*` component (start/ready) and listed it in `tck.boot.passed.services`. **Corrected model**: the mock server is already running before any run begins (it ships inside the backend), so it emits **no** `tck.boot.service.*` events and never appears in `tck.boot.passed.services`; its endpoints surface where they are used, not at boot. The ONLY remaining boot service is the **connector** (the engine-side client that consumes the injected EDC config) — a capability-backed service (`side: engine`, `capability: connector`) whose `start` follows its binding. **DISTINCTION that matters**: "engine-operated component the player starts per run" (connector client) vs. "always-on part of the backend itself" (mock server) — only the former is a boot service. **Edits**: rewrote ADR-0016 "Boot Service Events" subsection (dropped the mock-server table row, added an explicit paragraph stating the mock server is backend-resident not a boot service), changed the id-convention example from `mock-server` to `connector`; both traces removed the 2 mock-server events, set `services:["connector"]`, renumbered 41→39 contiguous (byte-identical, valid JSON, mock-server count 0). Build exit 0, baseline unchanged.
- **Refinement (2026-06-09) — every trace `id` segment mirrors the manifest YAML declaration path (ADR-0016 + example)**: Human directive across three turns — "should we not reference like infrastructure, so like it is described in the yaml?", "can we not do tckid/infrastructure/engine.connector", "same way with the variables like environment/variable/...". **PRINCIPLE**: the structured `id` path must mirror exactly where the thing is declared in the manifest YAML, so a reader can map any trace event straight back to the authored source. Two applications: (1) **Boot binding + service** — `id` is now `<tckid>/infrastructure/<side>.<capability>/<type>/<hash>` (was `<tckid>/<side>.<capability>/...`); `data` stays `{side, capability}`; `tck.boot.passed.bindings` and `.services` lists are now `["infrastructure.engine.connector"]` (full path), and the earlier free-form `service: "connector"` name was DROPPED so a capability-backed service is addressed by the **same** `infrastructure.<side>.<capability>` path as its binding (appears once under `bindings` = endpoint validated, once under `services` = client started). (2) **Variables** — declared under `env.variables:` in YAML and referenced `${{ env.<NAME> }}`, so `id` is now `<tckid>/env/variables/<varname>/<type>/<hash>` (was `<tckid>/<varname>/...`); the `source` convention is unchanged (variable's `uses` value or `testlab/player/variables`). **PATTERN (reusable)**: trace `id` = `<tckid>/<yaml-declaration-path>/<type>/<hash>` — the id path is a pointer into the manifest, never a free-form label. **Edits**: ADR-0016 id-convention table rows (boot binding/service → `infrastructure/<side>.<capability>`, variable → `env/variables/<varname>`) + Boot Service Events prose; both traces updated 4 boot ids + 2 lists + 8 variable ids (still 39 lines, byte-identical, valid JSON). Build exit 0, 53-warning baseline unchanged.

---

## Established Patterns

<!-- Patterns that have proven effective and should be reused -->

### PAT-1: Step outputs become draggable variables
- Blockly blocks expose typed outputs. After a step runs, its output auto-appears as a variable block that can be dropped into subsequent steps. Never require manual variable declaration.

### PAT-2: Auto-link on drop
- When a block is dragged into the workspace, inputs are auto-filled from the nearest compatible output above. This reduces friction for non-technical users.

### PAT-3: Hide plumbing in test_root
- Connector URLs, API base addresses, and infrastructure config come from `test_root` configuration, never from individual block fields. Blocks only contain business-level parameters.

### PAT-4: Setup → Execution → Teardown phases
- Every test case has three first-class phases. Prerequisites are explicit and ordered. Teardown runs even on failure to avoid resource leaks.

### PAT-5: Reuse-first for blocks and capabilities
- Before creating a new block, check if an existing block can be parameterized. Shared blocks across test cases reduce maintenance burden.

### PAT-6: Agent team split by codebase boundary
- Frontend work (`ide/`) → `testlab-ide-master`. Backend work (`src/`) → `testlab-master`. Tests (`tests/`) → `testlab-test-master`. Docs (`docs/`) → `testlab-docs-master`. Never mix agents across boundaries in the same work package.

### PAT-7: Vendor shared external data per-codebase + CI diff guard
- **Date**: 2026-06-08
- When two independent codebases both need the same external contract data (e.g. official JSON Schemas), give each its own checked-in copy and keep them honest with a blocking CI `diff -r` guard — never a shared package or a cross-boundary path read. Independence at the code level, drift protection at the CI level. Vendored data is build/runtime input, not source code: keep it flat, out of `public/` if build-only, out of `src/`.
- **Refinement (2026-06-08) — mirror upstream verbatim when it exists**: when the external data has an upstream folder, vendor a 1:1 byte-for-byte / folder-for-folder mirror (incl. files codegen never reads, e.g. `context/`, `samples/`) so a version bump is a re-download not a reshuffle; pin provenance to an upstream commit SHA in `PROVENANCE.txt` + an opt-in `sync:schemas` refresh test (NOT in CI); tolerate upstream nesting in tooling via an OPTIONAL config field (e.g. manifest `constraintDir`) so flat versions stay flat; carry NOTHING beyond upstream (drop local supersets — official schema is the source of truth); vendored upstream JSON carry no Apache/AI headers (third-party data).

### PAT-8: ADRs organized by responsibility boundary, numbering stays global
- **Date**: 2026-06-09
- Decision records live in three subfolders under `docs/developer/decision-records/`: `frontend/` (IDE-internal), `backend/` (player/compiler/server-internal), `shared/` (an IDE↔backend contract/format both sides must agree on). `index.md` registry and `ADR-0000-template.md` stay at the folder root; `deprecated/` and `comparisons/` are unchanged. **ADR numbers remain globally sequential and immutable** — the folder is the category, the number is never reused or rewritten (renumbering would break every cross-reference and the ADR convention itself).
- **Classification heuristic** (the borderline calls are the hard part — confirm with the human before moving): contract/interchange-format ADRs that both sides depend on go to `shared/` even if one side "emits" and the other "consumes" (e.g. 0010 YAML syntax, 0011 environment/services authored in YAML, 0003 SSE transport); an ADR goes to `backend/`/`frontend/` only when the *other* side genuinely needn't know it (e.g. 0016 execution-trace internals, 0017 callback endpoint mechanics, 0001 toolbox grouping, 0020 vendored schemas).
- **Move mechanics** (delegate to `testlab-docs-master`): use `git mv` (preserve history); rewrite inter-ADR links by recomputing per source/target folder (same folder → bare `ADR-NNNN-*.md`, sibling → `../<folder>/ADR-NNNN-*.md`); a depth change of +1 ALSO breaks every NON-ADR relative link in the moved file (`../foo.md` → `../../foo.md`) and every INBOUND link from unmoved siblings (e.g. `comparisons/` → `../<folder>/ADR-NNNN`) — fix both or the build warning count rises. Update `index.md` (group into H3 sections + folder-prefix links), `mkdocs.yml` nav (grouped sub-sections, subfolder paths), and all full-path external referrers. Verify with `mkdocs build`: exit 0 and warning count must not increase over baseline.
- Recorded as a convention (KB), not a standalone ADR — consistent with the earlier `deprecated/` subfolder convention which was also KB-only.

---

## Anti-Patterns

<!-- Things that have been tried and should NOT be done -->

### ANTI-1: Hardcoding block structure in TypeScript
- Blocks defined inline in `.tsx` files break the JSON-driven block catalog and make tooling discovery impossible.

### ANTI-2: Using `print()` in Python source
- All logging must go through `logging.getLogger(__name__)`. `print()` bypasses structured logging and disappears in production.

### ANTI-3: Catching bare `Exception`
- Always catch the narrowest exception type. Bare `except Exception:` swallows unexpected errors and makes debugging impossible.

### ANTI-4: Reimplementing SDK protocols
- Any attempt to reimplement EDC catalog negotiation, DSP flows, or DTR operations directly in testlab code creates an unmaintainable fork.

### ANTI-5: Parallel abandoned UI implementations
- **Date**: 2026-06-01
- The precondition configurator has THREE overlapping trees: the active `features/preconditions/` panel (renders `with` as raw `JSON.stringify` in plain inputs), a dead schema-aware editor `shared/ui/PreconditionsDialog/` (pill toggles, version schemas, constraint registry — never rendered), and a half-ported `features/preconditions/rules/` (`RuleSection` only exported, never consumed). Rebuilding a feature from scratch instead of moving the existing structured editor left two dead trees and shipped the worst UX. Before building a "new" view, search for an existing implementation of the same concept and relocate it.

---

## Known Risks

<!-- Recurring risks to flag in every plan -->

### RISK-1: 300-line limit violations during feature expansion
- Large features frequently push files over the limit. Always check line counts in acceptance criteria.

### RISK-2: SDK version drift
- `tractusx-sdk` is a moving dependency. New testlab features may assume SDK APIs that don't exist yet in the pinned version. Always verify against the installed SDK version.

### RISK-3: Block catalog desync
- `ide/public/blocks/index.json` must stay in sync with the actual block files. A missing or wrong path in the manifest silently breaks block loading.

### RISK-4: ~~YAML variable reference errors~~
- ~~Using `${var}` instead of `@var` in YAML generates no parse error but produces wrong runtime behavior.~~ Superseded by AD-6 — only `${{ }}` syntax is valid now.

### RISK-6: YAML v2 migration breakage
- **Date**: 2026-05-20
- The v2 migration touches every layer (models, parser, resolver, compiler, IDE serialization). Shipping frontend before backend (or vice versa) creates a window where generated YAML is rejected. Must ship atomically or behind feature flag.

### RISK-5: Block catalog class taxonomy drift
- **Date**: 2026-05-19
- As new blocks are added, contributors may forget to assign `class`/`accepts` fields or use non-registry classes. CI validation should check all outputs reference valid classes from `ide/public/blocks/classes.json`.

### RISK-7: Vendored schema-copy drift (frontend vs backend)
- **Date**: 2026-06-08
- The policy schemas now exist twice (`ide/schemas/policies/` + `src/tractusx_testlab/schemas/policies/`). Silent divergence between the IDE's enumerated constraints and the player's validation is a nasty bug class. Mitigation: blocking CI `diff -r` guard. Also watch the generated registry's `saturnSource`/`jupiterSource` provenance strings — they are emitted into the file, so a source-path change produces a (small, expected) diff that must be committed.

---

## Lessons Learned

<!-- Specific lessons from past work — what went wrong and what worked -->

_No entries yet. Append lessons here as they are discovered._

### LESSON-1: Check for an existing implementation before building a "new" view
- **Date**: 2026-06-01
- The precondition gap analysis revealed a fully schema-aware editor already existed (`shared/ui/PreconditionsDialog/`, matching the mockup) but was abandoned when the `features/preconditions/` panel was rebuilt with raw-JSON inputs. The fix is mostly *relocation + wiring*, not new construction. Always grep for the concept (`Precondition`, `Policy`, `Constraint`) across `features/` AND `shared/` before scoping a rebuild.

### LESSON-2: A `git grep "ide/"` dependency gate misses paths built from string segments
- **Date**: 2026-06-09
- During the IDE-frontend removal, a pre-delete verification WP used `git grep -n "ide/"` to prove no backend code depends on `ide/`. It returned GREEN — a false negative. Two backend tests built the path as `Path(...) / "ide" / "public" / "examples" / ...`, so the literal substring `ide/` never appears. Deleting `ide/` then broke 22 tests with `FileNotFoundError`.
- **Rule**: when proving "nothing references directory X" before a delete, grep for the **leaf path segment as a bare token** (e.g. `"ide"` with word boundaries, and the distinctive child names like `"examples"`, `"public"`) AND grep for the segmented-path idiom (`/ "ide"`, `"ide" /`), not just the slash-joined literal. Better still: move the directory aside (or `git stash`/rename) and run the full test suite BEFORE the hard delete, so a hidden dependency surfaces as a failure you can recover from.

### LESSON-3: Backend test fixtures had been hidden under `ide/public/examples/` (duplicate of the docs reference example)
- **Date**: 2026-06-09
- The CCM example (`certificate-management`) existed in TWO places: a stale `ide/public/examples/certificate-management-v2.0/` consumed by backend tests, and the canonical, actively-regenerated `docs/examples/certificate-management-v2/raw/` reference. Backend test fixtures living under a frontend-served dir is a misplacement that only surfaced when the frontend was deleted. After removal, repoint the tests to the single canonical copy under `docs/examples/.../raw/`. Expected step/assertion counts may differ because the canonical copy is post-precondition-removal (AD-12) — reconcile counts to the canonical reality only after confirming the YAMLs still parse with valid step types (mismatch = expected content evolution, not corruption).

---

## Module Map

<!-- High-level map of which modules own which concerns -->

### Python (`src/tractusx_testlab/`)

| Module | Owns |
|--------|------|
| `compiler/` | YAML → internal model compilation, validation |
| `player/` | Test execution engine, phase runner |
| `steps/` | Individual step executors (one class per step type) |
| `server/` | Mock server (FastAPI) for inbound callbacks |
| `models/` | Pydantic value objects, test case schema |
| `authoring/` | YAML parser, builder utilities |
| `cli/` | Typer CLI commands (`testlab run`, `compile`, `validate`) |
| `services/` | Service manager, lifecycle |
| `config/` | Environment and configuration loading |
| `security/` | Crypto key generation |

### Frontend (`ide/src/`)

| Module | Owns |
|--------|------|
| `components/` | React UI components |
| `hooks/` | Custom hooks (logic extracted from components) |
| `stores/` | Zustand state slices |
| `blockDefinitions.ts` | Runtime block catalog loading |
| `sync/` | workspace → model → YAML sync pipeline |

### Block Catalog (`ide/public/blocks/`)

Category order: Mock → Wait → Function → Flow → EDC Connector → Digital Twin Registry → Discovery Finder → HTTP → Notification → Validation

---

## Open Architectural Questions

<!-- Questions not yet decided — update with decision when resolved -->

_No open questions. Add here when unresolved trade-offs arise._
