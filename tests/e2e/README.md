# E2E: testlab against a real Tractus-X dataspace

`.github/workflows/e2e-umbrella.yml` runs testlab's compile → validate → run
pipeline against a real, ephemeral dataspace instead of mocks:

- **Two EDC connectors** (`provider` / `BPNL000000000001`, `consumer` /
  `BPNL000000000002`), Saturn protocol.
- **Two Tractus-X IdentityHub instances** — one per participant — handling
  DID/VC-based IATP trust between the connectors.
- **Two Digital Twin Registries** — one per participant.
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
own CI signal (not a published certification TCK):

- `connector_negotiation.yaml` — provisions an asset + policies on the SUT
  (provider) connector, then drives the engine (consumer) connector through
  a real DSP catalog query, contract negotiation, transfer and data pull.
- `dtr_roundtrip.yaml` — writes a shell + submodel descriptor to the SUT's
  Digital Twin Registry and reads it back.

Both bind through the `infrastructure.engine.connector` / `sut.connector` /
`sut.dtr` capabilities (ADR-0019); `ci/umbrella.vars.yaml` supplies the
concrete endpoints via `testlab run --config`.

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

# Issue the credentials, using the super-user key the IssuerService logs once:
poetry run python tests/e2e/connector-dtr-smoke/ci/issue_credentials.py \
  --super-user-key "$(kubectl logs -n umbrella deployment/umbrella-issuerservice \
      | sed -n 's/.*Please take note of the API Key: *\([^ ]*\).*/\1/p' | tail -n 1)"

poetry run testlab run tests/e2e/connector-dtr-smoke/index.yaml \
  --config tests/e2e/connector-dtr-smoke/ci/umbrella.vars.yaml \
  --var infrastructure.sut.dtr.base_url=http://provider-dtr.local/semantics/registry
```

## Known soft spots

**DTR ingress path.** The registry is served under a rewritten prefix
(`/semantics/registry(/|$)(.*)` → `/$2`), so its API base URL is the host *plus*
that prefix — the bare host answers 404. That prefix is a subchart default, not
something the profile pins, so the workflow reads both the host and the path off
the live `provider-dtr` Ingress and derives the base URL from them, rather than
hardcoding either. See the "Discover DTR ingress host and base URL" step.

**Runner capacity.** The release is ~125 resources and a dozen JVMs on a 4-vCPU
runner, all booting at once. The stock liveness delays (30s for the connectors,
100s for the DTRs) kill pods before they finish starting under that contention,
so `ci/umbrella.values.yaml` raises them to 240s and trims the over-provisioned
CPU requests. If a chart bump adds another JVM, expect to do the same for it.

**A stuck deploy gives up on itself.** `helm install --wait` cannot tell "still
starting" from "will never start" — it waits on a container in
`CrashLoopBackOff` exactly as patiently as on one that is halfway through
booting, so a broken image used to cost the full 25m `HELM_TIMEOUT` and report
nothing beyond a deadline. The deploy step supervises the install instead: every
30s it lists what is still outstanding, and once a container has been in a
reason the kubelet cannot recover from (`CrashLoopBackOff`, `ImagePullBackOff`,
`CreateContainerConfigError`, …) for `STUCK_GRACE_POLLS` consecutive polls — 5
minutes by default — it dumps that pod's logs and `describe`, kills Helm and
fails. One healthy poll resets the count, because services waiting on a slow
Postgres do crash-loop briefly and that is not a fault. Raise
`STUCK_GRACE_POLLS` if a chart bump makes legitimate startup crash-looping
longer than five minutes. Every step also carries its own `timeout-minutes`, so
a hang is attributed to the step that caused it rather than silently consuming
the job's 90-minute budget — which would take the diagnostics and artifact
uploads down with it.

**Chart drift.** If a chart upgrade breaks the DTR discovery, the vault-setup
hook assertion, or the values keys that enable the consumer's DTR and data
backend, `helm show values tractusx-dev/umbrella --version <new>` against the
new version is the fastest way to find the renamed keys.
