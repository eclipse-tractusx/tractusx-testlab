# E2E: testlab against a real Tractus-X dataspace

`.github/workflows/e2e-umbrella.yml` runs testlab's compile → validate → run
pipeline against a real, ephemeral dataspace instead of mocks:

- **Two EDC connectors** (`provider` / `BPNL000000000001`, `consumer` /
  `BPNL000000000002`), Saturn protocol.
- **Two Tractus-X IdentityHub instances** — one per participant — handling
  DID/VC-based IATP trust between the connectors.
- **One Digital Twin Registry**, the provider's, shared by both
  participants: the TCK binds `infrastructure.sut.dtr` to it and never
  addresses a second, so `ci/umbrella.values.yaml` leaves the consumer's off.
- A BDRS directory service and an IssuerService, which the workflow drives
  through the credential-issuance flow so both participants end up holding the
  Catena-X `Membership` and `DataExchangeGovernance:1.0` VCs the TCK's ODRL
  policies check.

All of it comes from one Helm install of [Tractus-X
Umbrella](https://github.com/eclipse-tractusx/tractus-x-umbrella)'s
`values-adopter-decentralized-identityhub.yaml` profile, deployed into a
`kind` cluster created inside the GitHub Actions runner. Nothing is
persisted or shared across runs — no external cluster, no secrets — the
cluster is created and destroyed within the job.

## What runs

`tests/e2e/connector-dtr-smoke/` is a small TCK, purpose-built as testlab's
own CI signal (not a published certification TCK). Between them its thirteen
tests use every one of the 55 steps in the engine's catalogue
(`docs/api-reference/steps/`) and all three validation kinds —
`validate/assert`, `validate/field` and `validate/schema` — so no step ships
without having been run once against something real.

- `connector_negotiation.yaml` — provisions an asset + policies on the SUT
  (provider) connector, then drives the engine (consumer) connector through
  a real DSP catalog query, contract negotiation, transfer and data pull.
- `dsp_step_by_step.yaml` — the same journey as six separate steps instead of
  one. It is the test that fails if the runtime stops carrying a real value
  across a phase boundary — an offer into a negotiation, an EDR into a fetch —
  and it attributes the break to the step that caused it.
- `dtr_roundtrip.yaml` — writes a shell + submodel descriptor to the SUT's
  Digital Twin Registry and reads it back.
- `negative_paths.yaml` — asks the live dataspace for things that are not
  there and asserts on the answers. It is what says the engine reports absence
  as absence rather than inventing a result.
- `inbound_call.yaml` — the one test where the dataspace calls testlab. It
  opens a `mock/api` endpoint, registers an asset on the SUT whose backend is
  the mock server's root (with `proxyPath` on), pulls the mock's path through
  the SUT's data plane, and then reads the data plane's request back with
  `mock/wait/http_request`. The body the consumer receives must be the mock's
  canned answer and the path the mock saw must be the one the test sent, so
  the call provably came from the provider's data plane pod and not from the
  test. A second mock takes a POST: the test's JSON body goes through both
  data planes (`proxyMethod`, `proxyBody`) and the wait step checks the payload
  the mock received field by field.
- `external_callback.yaml` — the wait step, actually waiting. The call in
  `inbound_call.yaml` is a consequence of the test's own pull and has
  already arrived when the wait step runs. Here the test tells a stand-in
  SUT in the cluster (`ci/stub_caller.py`, deployed by the workflow behind
  `tck-stub.local`) to call the mock in three seconds, is acknowledged at
  once, and blocks on `mock/wait/http_request`. The call arrives from the
  stub's pod while the test is blocked, and `elapsed_ms` must show the wait
  lasted the delay.
- `catalog_variants.yaml` — the consumer catalogue the two DSP tests leave
  untouched: the unfiltered query, the query filtered by asset id, the
  one-shot `do_dsp`, and the pull that only accepts an offer made under a
  named policy. It also provisions the provider twice over, from a whole
  document and field by field, because only a live connector can say the two
  forms register the same thing.
- `bpn_discovery.yaml` — addresses the SUT by business partner number rather
  than by DSP URL, which is what a Catena-X consumer actually holds. It needs
  a directory service that really carries the mapping, so it is only provable
  against a deployment that runs one and has seeded both participants.
- `push_transfer.yaml` — the other branch of `initiate_transfer`, where the
  provider delivers to a destination the consumer nominates and there is no
  EDR at the end. The destination is testlab's own mock server, so what the
  transfer's state claims and what actually arrived are checked separately.
- `dtr_consumer_dataplane.yaml` — reads the registry the way Catena-X reads
  somebody else's twins: the registry is published as an asset, negotiated
  for, and every call travels through the provider's data plane with an EDR
  on it. Because the calls arrive that way, the registry answers as the
  consumer's partner and its visibility rules decide what comes back.
- `notification_roundtrip.yaml` — a Catena-X notification found in a catalog,
  negotiated for and posted, twice: once doing the whole journey itself, once
  spending an EDR a separate pull already negotiated. Both documents are read
  back where they landed, so what is asserted is the payload that survived two
  data planes rather than the status code the sender was handed.
- `industry_core_journey.yaml` — the whole Industry Core story in the order a
  provider and a consumer perform it: upload a submodel payload, front it with
  an EDC asset, register a twin whose descriptor names that asset, then work
  the chain backwards and pull the payload. The last step fails if any earlier
  link was decorative, because nothing else in the deployment could produce
  that document.
- `engine_toolbox.yaml` — everything that needs no dataspace at all: the flow
  steps, the utility steps, the OAuth2 steps and the two protocol-aware mocks,
  driven against the mock server the run starts rather than left uncovered. It
  takes no connector, no registry and no operator input, so it runs unchanged
  in any deployment.

The workflow runs the full suite, every test, on every event — pull requests
included. The cluster bring-up is where the job's minutes go and a run takes
seconds, so nothing is trimmed for a pull request. After the run, a step reads
the trace back and fails unless every `tck.test.step.received` event is there
(`inbound_call`, `external_callback`, `notification_roundtrip`,
`push_transfer`), the external one shows the wait step blocked for the stub's
delay, and both notifications arrived with their headers intact and with
different sender and receiver partners. Two subset runs of the same compiled
package follow — the registry alone, and `engine_toolbox.yaml` alone — plus a
selection the manifest does not permit, which must be refused. The subsets add
no coverage; they check that a test needing no connector journey runs without
one having happened first, and that runtime selection works against a real
SUT. The engine-only run is worth its seconds because it runs against a fully
deployed dataspace it never addresses: a step that had quietly grown a
dependency on a seeded service would pass in the offline suite and fail there.

They bind through the `infrastructure.engine.connector` / `sut.connector` /
`sut.dtr` / `engine.dtr` capabilities (ADR-0019); `ci/umbrella.vars.yaml`
supplies the concrete endpoints via `testlab run --config`, and the workflow
passes with `--var` whatever the chart does not pin. The manifest's inputs are:

- `mock_server_external_url` — the root of testlab's mock server *as a pod can
  reach it*, needed by `inbound_call.yaml`. `mock/api` reports the server at
  `localhost`, which is right for the engine and useless to a connector in a
  pod, so the workflow discovers the address from the kind node's gateway.
- `stub_caller_url` — the stub caller's ingress host, for
  `external_callback.yaml`.
- `sut_bpnl` / `engine_bpnl` — the two participants' business partner numbers.
  They are inputs rather than bindings because a Saturn connector identifies
  itself by DID, which is what the `participant_id` bindings carry, while the
  BPN is what a *caller* holds: the receiver of a Catena-X notification, and
  the input BPN-addressed discovery resolves through the dataspace's BPN-DID
  directory. Both are fixed by the profile, so `ci/umbrella.vars.yaml` pins
  them.
- `dtr_internal_url` — the registry's API root as the *provider's data plane*
  can reach it, which is a cluster Service address rather than the ingress the
  engine uses. `dtr_consumer_dataplane.yaml` registers an EDC asset with it.
  The Service port is a subchart default this profile does not pin, so the
  workflow reads it off the live Service and passes the address with `--var`.
- `infrastructure.engine.dtr.base_url` and
  `infrastructure.engine.dtr.submodel_base_url` — the engine's own registry and
  the payload store its entries point at. Both sides share one registry in this
  deployment, so the first is the provider's, discovered per run like the SUT's
  and passed with `--var`; binding the engine to it changes nothing at runtime,
  because a bare registry lookup resolves to the system under test's binding
  first. The submodel server's address is pinned, since the workflow chooses
  the hostname it deploys behind.

The submodel server is `ci/submodel_server.py`, a standard-library payload
store the workflow deploys as a pod behind `tck-submodel.local`. It exists
because the Umbrella profile switches off both `simple-data-backend` bundles:
nothing in the release serves a submodel payload, and
`digital-twin-registry/submodel/upload` / `delete` plus the whole Industry Core journey
would have no backend to address. A shell descriptor is only a pointer, and
something has to serve what it points at. The property that makes one server
serve both roles is its hostname: `tck-submodel.local` is in the workflow's
`DATASPACE_HOSTS`, so it resolves on the runner — where the engine uploads over
the ingress — *and* inside the cluster, where the provider's data plane fetches
the same payload as an EDC asset backend. The address the upload publishes is
therefore an address a pod can use unchanged.

## What `helm install` does not give you

A green `helm install --wait` is necessary but nowhere near sufficient. Four
things have to be true on top of it, and each one fails *silently* — every pod
reports itself healthy either way, and you only find out when a negotiation
never reaches `AGREED` or a DTR call answers 404.

1. **The dataspace hostnames must resolve inside the cluster.** Every
   participant addresses its peers by ingress hostname (`provider.local`,
   `consumer-dsp.local`, `issuerservice.local`, …) — that is how `did:web`
   resolution, STS token exchange and the DSP handshake are configured.
   `/etc/hosts` on your machine does not help pods. The workflow adds a `hosts`
   block to CoreDNS pointing every name at the ingress controller's ClusterIP.
2. **`nginx` must be the default IngressClass.** The IdentityHub, data-plane and
   IssuerService ingresses render *without* a class (the profile leaves
   `shared-configuration.ingress.className` empty), and ingress-nginx's kind
   manifest does not mark its class as the default — so nothing claims those
   routes.
3. **The participants' vaults must be seeded.** `tokenSignerPrivateKey`,
   `tokenSignerPublicKey` and `tokenEncryptionAesKey` are written by the
   connector bundle's `post-install-vault-setup` hook. That hook only renders
   while the *connector bundle* owns the vault (`install.vault: false` +
   `dataspace-connector-bundle.vault.enabled: true`); flip those and you get a
   vault with nothing in it, and every transfer fails to sign its EDR.
   `ci/umbrella.values.yaml` deliberately leaves the profile's wiring alone, and
   the workflow's manifest validation asserts both hooks are present.
4. **The credentials must actually be issued.** The chart seeds the
   IssuerService's *claim rows* (`custom_attestation_claims`) but never turns
   them into VCs held by the participants. That is an API flow the Umbrella docs
   ship as a Bruno collection for humans; `ci/issue_credentials.py` is the same
   flow, executed non-interactively.

## A runtime that boots but never reports ready

The release converges in under three minutes, every time, except when one of
its EDC-based runtimes (an IdentityHub, the IssuerService) comes up wedged: the
JVM logs `57 service extensions started` and `Runtime <id> ready`, every Jetty
context is bound, and from then on the readiness probe on
`/api/check/readiness` answers 404 while the liveness probe on the same port
passes. The container never crashes, so nothing restarts it, and
`helm install --wait` sits out its full 25-minute budget. Seen twice in forty
runs, on two different images (`issuerservice-memory:0.3.2` on 2026-09-10,
`identityhub-memory:0.4.0-SNAPSHOT` on 2026-09-12); the same image and
configuration boots cleanly outside the cluster, and a fresh boot inside it has
so far always come up clean.

The deploy watcher runs `ci/restart_wedged_runtimes.py` once every 30 seconds.
A pod that has been running for two minutes with its runtime logged ready and
its container still not ready is deleted, and its Deployment brings up a new
one in about forty seconds; the run gets a warning annotation naming the pod.
Before deleting, the script fetches the readiness and liveness paths from a
pod inside the cluster and prints status and body, which is the evidence an
upstream issue needs and which no probe event carries. A runtime that has not
logged ready is still booting or has crashed and is left alone, a Helm hook's
pod is never touched, and each owner is restarted at most twice, so a runtime
that is broken rather than wedged still ends in the helm timeout and the
diagnostics artifact.

## Reproducing locally

```bash
kind create cluster --name tck-e2e   # add the :80/:443 extraPortMappings — see the workflow
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl patch ingressclass nginx \
  -p '{"metadata":{"annotations":{"ingressclass.kubernetes.io/is-default-class":"true"}}}'

# Resolve the dataspace hostnames on your machine *and* inside the cluster.
# The full list lives in the workflow's DATASPACE_HOSTS; edit the coredns
# ConfigMap to add a `hosts` block for them pointing at:
#   kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.spec.clusterIP}'

helm repo add tractusx-dev https://eclipse-tractusx.github.io/charts/dev
helm install umbrella tractusx-dev/umbrella --version 26.03.00 \
  --namespace umbrella --create-namespace \
  -f https://raw.githubusercontent.com/eclipse-tractusx/tractus-x-umbrella/umbrella-26.03.00/charts/umbrella/values-adopter-decentralized-identityhub.yaml \
  -f tests/e2e/connector-dtr-smoke/ci/umbrella.values.yaml \
  --wait --timeout 25m

# Umbrella 26.03.00 ships the packaged chart without the nested
# tx-data-provider bundles; the workflow restores them before installing. See
# its "Prepare and validate pinned Umbrella chart" step if the install renders
# without the connectors.

# Issue the credentials, using the super-user key the IssuerService logs once.
# The log line is coloured, so capture only the key's alphabet — a trailing
# ANSI reset in the header is a 400 from the IssuerService.
poetry run python tests/e2e/connector-dtr-smoke/ci/issue_credentials.py \
  --super-user-key "$(kubectl logs -n umbrella deployment/umbrella-issuerservice \
      | sed -n 's/.*Please take note of the API Key: *\([A-Za-z0-9+\/=.]*\).*/\1/p' | tail -n 1)"

# The address pods use to reach your machine, for inbound_call.yaml. On Linux
# this is the kind node's gateway (the Docker bridge); on Docker Desktop use
# host.docker.internal instead. Port 8100 is testlab's mock server.
gateway="$(docker inspect tck-e2e-control-plane \
  -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}')"

# The registry as the provider's own data plane reaches it: the Service, not
# the ingress. The port is a subchart default, so read it rather than assume.
port="$(kubectl get svc provider-dtr -n umbrella -o jsonpath='{.spec.ports[0].port}')"

poetry run testlab run tests/e2e/connector-dtr-smoke/index.yaml \
  --config tests/e2e/connector-dtr-smoke/ci/umbrella.vars.yaml \
  --var infrastructure.sut.dtr.base_url=http://provider-dtr.local/semantics/registry \
  --var infrastructure.engine.dtr.base_url=http://provider-dtr.local/semantics/registry \
  --var "dtr_internal_url=http://provider-dtr.umbrella.svc.cluster.local:${port}/api/v3" \
  --var mock_server_external_url="http://${gateway}:8100" \
  --var stub_caller_url=http://tck-stub.local   # after deploying ci/stub_caller.py as in the workflow
# The Industry Core journey and the submodel steps also need ci/submodel_server.py
# deployed as a pod, Service and ingress behind tck-submodel.local — the same
# shape as the stub caller, from the workflow's "Deploy in-cluster submodel
# server" step. Its hostname must be in the coredns `hosts` block as well as
# your /etc/hosts, because both the engine and the provider's data plane dial it.
```

## Known soft spots

**DTR ingress path.** The registry is served under a rewritten prefix
(`/semantics/registry(/|$)(.*)` → `/$2`), so its API base URL is the host *plus*
that prefix — the bare host answers 404. That prefix is a subchart default, not
something the profile pins, so the workflow reads both the host and the path off
the live `provider-dtr` Ingress and derives the base URL from them, rather than
hardcoding either. See the "Discover DTR ingress host and base URL" step.

**Pods reaching the runner.** `inbound_call.yaml` has the provider's data
plane fetch from testlab's mock server, which binds `0.0.0.0:8100` on the
runner. Pod egress leaves through the kind node, whose default gateway is the
Docker bridge the node sits on — its host side is the runner — so that gateway
is the address the SUT is given. The workflow reads it off the node container
and, before the suite runs, dials it from a throwaway pod against a stand-in on
the same port; a wrong address or a blocked port fails there with its own
message instead of surfacing as the data plane answering 502 mid-suite.

**Runner capacity.** The release is ~125 resources and a dozen JVMs on a 4-vCPU
runner, all booting at once. The stock liveness delays (30s for the connectors,
100s for the DTRs) kill pods before they finish starting under that contention,
so `ci/umbrella.values.yaml` raises them to 240s and trims the over-provisioned
CPU requests. If a chart bump adds another JVM, expect to do the same for it.

**Chart drift.** If a chart upgrade breaks the DTR discovery, the vault-setup
hook assertion, or the values keys that switch off the consumer's DTR and
both `simple-data-backend`s, `helm show values tractusx-dev/umbrella --version <new>` against the
new version is the fastest way to find the renamed keys.

**Suite length.** The job's timeout is 75 minutes, raised from 60 when the
suite grew past twice its former length. A chart bump that slows the install,
or another test of the same size, will want that number looked at again before
it starts failing as a timeout rather than as whatever actually broke.

**Registry visibility rules.** `dtr_consumer_dataplane.yaml` depends on how the
Tractus-X registry decides who may see a twin: a twin is shown only to a
partner named in one of its specific asset IDs, and the `Edc-Bpn` header the
registry reads that name against is set by the provider's data plane from the
token, never by the test. Which spelling of the consumer's identity ends up
on that header depends on the deployment, so the twin names the consumer under
both its DID and its BPN and also carries the `PUBLIC_READABLE` wildcard. If
that test starts coming back with an empty lookup rather than an error, those
rules — or the identifier types the registry honours the wildcard for — are the
first place to look.
