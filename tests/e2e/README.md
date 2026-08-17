# E2E: testlab against a real Tractus-X dataspace

`.github/workflows/e2e-umbrella.yml` runs testlab's compile → validate → run
pipeline against a real, ephemeral dataspace instead of mocks:

- **Two EDC connectors** (`provider` / `BPNL000000000001`, `consumer` /
  `BPNL000000000002`), Saturn protocol.
- **Two Tractus-X IdentityHub instances** — one per participant — handling
  DID/VC-based IATP trust between the connectors.
- **Two Digital Twin Registries** — one per participant.
- A BDRS directory + issuer service, pre-seeded with the Catena-X
  `Membership` and `DataExchangeGovernance:1.0` VC claims both participants
  need to pass ODRL policy checks out of the box.

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

## Reproducing locally

```bash
kind create cluster --name tck-e2e
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

helm repo add tractusx-dev https://eclipse-tractusx.github.io/charts/dev
helm install umbrella tractusx-dev/umbrella --namespace umbrella --create-namespace \
  -f https://raw.githubusercontent.com/eclipse-tractusx/tractus-x-umbrella/main/charts/umbrella/values-adopter-decentralized-identityhub.yaml \
  --set edc-consumer.tx-data-provider.digital-twin-bundle.enabled=true \
  --set edc-consumer.tx-data-provider.data-persistence-layer-bundle.enabled=true \
  --wait --timeout 20m

# /etc/hosts: 127.0.0.1 provider.local provider.intranet consumer.local consumer.intranet
# find the DTR ingress host: kubectl get ingress -n umbrella | grep -i dtr

poetry run testlab run tests/e2e/connector-dtr-smoke/index.yaml \
  --config tests/e2e/connector-dtr-smoke/ci/umbrella.vars.yaml \
  --var infrastructure.sut.dtr.base_url=http://<discovered-dtr-host>
```

## Known soft spots

The umbrella chart's subchart internals (ingress paths for the DTR
specifically) aren't pinned by the values file the same way hostnames, BPNs
and the management API key are, and can shift between chart releases. The
workflow discovers the DTR ingress host at deploy time rather than
hardcoding it, and fails with a clear diagnostic instead of a confusing
downstream error when it can't find one — see the "Discover DTR ingress
host" step. If a chart upgrade breaks that discovery or the `--set`
overrides that enable the consumer's DTR, `helm show values
tractusx-dev/umbrella` against the new version is the fastest way to find
the renamed keys.
