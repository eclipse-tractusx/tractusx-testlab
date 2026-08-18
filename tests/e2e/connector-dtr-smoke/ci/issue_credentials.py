################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################

"""Issue the Catena-X verifiable credentials the e2e dataspace needs.

``helm install`` gives you two connectors, two IdentityHubs and an
IssuerService, but it does **not** give the participants any credentials — the
Umbrella chart only seeds the *claim rows* the IssuerService reads from
(``custom_attestation_claims``, via ``attestationClaimSeeding``). Turning those
rows into signed VCs held by each participant is an API-driven flow that the
Umbrella docs ship as a Bruno collection for humans to click through:

    tractus-x-umbrella/docs/common/api/bruno/
        Data-exchange-decentralized-identityhub/Issuance/

Until both IdentityHubs hold a ``MembershipCredential`` and a
``DataExchangeGovernanceCredential``, every contract negotiation in
``tests/connector_negotiation.yaml`` fails its ODRL policy checks — the
connectors come up healthy and the negotiation simply never reaches AGREED.
This script is that Bruno collection, executed non-interactively:

  1. create the issuer's participant context (super-user credentials)
  2. register the ``database`` attestation over ``custom_attestation_claims``
  3. define the four credential types the profile's claim rows can satisfy
  4. register both participants as holders
  5. ask each participant's IdentityHub to request those credentials
  6. poll each IdentityHub until the credentials are actually held

Every identifier here is fixed by
``charts/umbrella/values-adopter-decentralized-identityhub.yaml`` (DIDs, BPNs,
IdentityHub API keys), which the workflow pins by chart version — so they are
constants, not configuration. Only the IssuerService super-user API key is
generated at runtime; it is read from the IssuerService log by the workflow and
passed in with ``--super-user-key``.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from dataclasses import dataclass

import httpx

# The IssuerService's own participant context. `did` must match the
# `trustedIssuers` entry both connectors are configured with; `context_id` is
# an opaque local handle, base64-encoded into the admin API's URLs.
ISSUER_DID = "did:web:issuerservice.local:BPNL000000000003"
ISSUER_CONTEXT_ID = "issuer"
ISSUER_PRIVATE_KEY_ALIAS = "issuer-privatekey-alias"

# The attestation the IssuerService evaluates when a holder asks for a
# credential: a SQL table whose rows the chart seeded, read through the
# `customattestations` datasource declared in the IssuerService config map.
ATTESTATION_ID = "attestation-id"
ATTESTATION_DATASOURCE = "customattestations"
ATTESTATION_TABLE = "custom_attestation_claims"

CREDENTIAL_FORMAT = "VC1_0_JWT"
CREDENTIAL_VALIDITY = 10_000_000_000_000

_HOLDER_ID = {"input": "holder_id", "output": "credentialSubject.id", "required": True}
_HOLDER_IDENTIFIER = {
    "input": "bpn",
    "output": "credentialSubject.holderIdentifier",
    "required": True,
}


def _mapping(input_column: str, output_claim: str) -> dict:
    return {"input": input_column, "output": output_claim, "required": True}


# id -> (credentialType, extra claim mappings beyond holder id/identifier).
# The mappings must line up with the columns `attestationClaimSeeding` inserts.
CREDENTIAL_DEFINITIONS: dict[str, tuple[str, list[dict]]] = {
    "membershipCredential-id": (
        "MembershipCredential",
        [_mapping("member_of", "credentialSubject.memberOf")],
    ),
    "BpnCredential-id": (
        "BpnCredential",
        [_mapping("bpn", "credentialSubject.bpn")],
    ),
    "usagePurposeCredential-id": ("UsagePurposeCredential", []),
    "dataExchangeGovernanceCredential-id": (
        "DataExchangeGovernanceCredential",
        [
            _mapping("group_name", "credentialSubject.group"),
            _mapping("use_case", "credentialSubject.useCase"),
            _mapping("contract_template", "credentialSubject.contractTemplate"),
            _mapping("contract_version", "credentialSubject.contractVersion"),
        ],
    ),
}


@dataclass(frozen=True)
class Participant:
    """A dataspace participant that must end up holding the credentials."""

    name: str
    did: str
    # The IdentityHub's private "identity" API, exposed on `<name>.intranet`.
    identity_api: str
    # `identityhub.iatp.sts.oauth.client.x_api_key` from the profile.
    api_key: str

    @property
    def context_id(self) -> str:
        """The participant context id as the IdentityHub URLs encode it."""
        return base64.b64encode(self.did.encode()).decode()


PARTICIPANTS = (
    Participant(
        name="provider",
        did="did:web:provider.local:identityhub:BPNL000000000001",
        identity_api="http://provider.intranet/identityhub/api/identity/v1alpha",
        api_key=(
            "ZGlkOndlYjpwcm92aWRlci5sb2NhbDppZGVudGl0eWh1YjpCUE5MMDAwMDAwMDAwMDAx.randomChars"
        ),
    ),
    Participant(
        name="consumer",
        did="did:web:consumer.local:identityhub:BPNL000000000002",
        identity_api="http://consumer.intranet/identityhub/api/identity/v1alpha",
        api_key=(
            "ZGlkOndlYjpjb25zdW1lci5sb2NhbDppZGVudGl0eWh1YjpCUE5MMDAwMDAwMDAwMDAy.randomChars"
        ),
    ),
)

EXPECTED_CREDENTIAL_TYPES = frozenset(
    credential_type for credential_type, _ in CREDENTIAL_DEFINITIONS.values()
)


class IssuanceError(RuntimeError):
    """Raised when the dataspace cannot be brought to a usable state."""


def _log(message: str) -> None:
    print(message, flush=True)


def _post(
    client: httpx.Client,
    url: str,
    *,
    api_key: str,
    payload: dict,
    description: str,
) -> httpx.Response:
    """POST ``payload``, treating "already exists" as success.

    The whole script is idempotent so it can be re-run against a half-seeded
    dataspace (a retried workflow step, or a local cluster you are iterating
    on) without having to tear the release down first.
    """
    response = client.post(url, json=payload, headers={"x-api-key": api_key})
    if response.status_code == httpx.codes.CONFLICT:
        _log(f"  {description}: already present")
        return response
    if response.is_error:
        raise IssuanceError(
            f"{description} failed: POST {url} -> {response.status_code} {response.text.strip()}"
        )
    _log(f"  {description}: ok")
    return response


def _create_issuer_context(client: httpx.Client, issuer_url: str, super_user_key: str) -> str:
    """Create the issuer's participant context and return its API key."""
    payload = {
        "active": True,
        "did": ISSUER_DID,
        "key": {
            "keyGeneratorParams": {"algorithm": "Ec", "curve": "secp256r1"},
            "keyId": f"{ISSUER_DID}#key-1",
            "type": "JsonWebKey2020",
            "privateKeyAlias": ISSUER_PRIVATE_KEY_ALIAS,
        },
        "participantContextId": ISSUER_CONTEXT_ID,
        "roles": ["ROLE_ADMIN", "admin"],
        "serviceEndpoints": [
            {
                "id": "issuerservice.local#credential-service",
                "type": "IssuerService",
                "serviceEndpoint": (
                    f"{issuer_url}/api/issuance/v1alpha/participants/"
                    f"{base64.b64encode(ISSUER_CONTEXT_ID.encode()).decode()}"
                ),
            }
        ],
        "apiKeyAlias": "apiKeyAliasTest",
    }
    response = _post(
        client,
        f"{issuer_url}/api/identity/v1alpha/participants",
        api_key=super_user_key,
        payload=payload,
        description=f"issuer participant context '{ISSUER_CONTEXT_ID}'",
    )
    if response.status_code == httpx.codes.CONFLICT:
        raise IssuanceError(
            f"Issuer participant context '{ISSUER_CONTEXT_ID}' already exists, so its "
            "API key cannot be recovered — the key is only returned at creation "
            "time. Reinstall the release before re-running."
        )
    api_key = response.json().get("apiKey")
    if not api_key:
        raise IssuanceError(
            "IssuerService did not return an apiKey for the new participant context: "
            f"{response.text.strip()}"
        )
    return api_key


def _seed_issuer(client: httpx.Client, issuer_url: str, issuer_key: str) -> None:
    """Register the attestation, credential definitions and holders."""
    admin = (
        f"{issuer_url}/api/admin/v1alpha/participants/"
        + base64.b64encode(ISSUER_CONTEXT_ID.encode()).decode()
    )

    _post(
        client,
        f"{admin}/attestations",
        api_key=issuer_key,
        payload={
            "attestationType": "database",
            "configuration": {
                "dataSourceName": ATTESTATION_DATASOURCE,
                "tableName": ATTESTATION_TABLE,
            },
            "id": ATTESTATION_ID,
        },
        description=f"attestation '{ATTESTATION_ID}'",
    )

    for definition_id, (credential_type, extra_mappings) in CREDENTIAL_DEFINITIONS.items():
        _post(
            client,
            f"{admin}/credentialdefinitions",
            api_key=issuer_key,
            payload={
                "attestations": [ATTESTATION_ID],
                "credentialType": credential_type,
                "format": CREDENTIAL_FORMAT,
                "id": definition_id,
                "jsonSchema": "{}",
                "jsonSchemaUrl": "test",
                "mappings": [_HOLDER_ID, _HOLDER_IDENTIFIER, *extra_mappings],
                "validity": CREDENTIAL_VALIDITY,
            },
            description=f"credential definition '{credential_type}'",
        )

    for participant in PARTICIPANTS:
        _post(
            client,
            f"{admin}/holders",
            api_key=issuer_key,
            payload={
                "did": participant.did,
                "holderId": participant.did,
                "name": participant.name,
            },
            description=f"holder '{participant.name}'",
        )


def _request_credentials(client: httpx.Client, participant: Participant) -> None:
    """Have a participant's IdentityHub request its credentials from the issuer."""
    credentials = [
        {"format": CREDENTIAL_FORMAT, "id": definition_id, "type": credential_type}
        for definition_id, (credential_type, _) in CREDENTIAL_DEFINITIONS.items()
    ]
    _post(
        client,
        f"{participant.identity_api}/participants/{participant.context_id}/credentials/request",
        api_key=participant.api_key,
        payload={
            "credentials": credentials,
            "holderPid": ISSUER_DID,
            "issuerDid": ISSUER_DID,
        },
        description=f"{participant.name} credential request",
    )


def _held_credential_types(client: httpx.Client, participant: Participant) -> set[str]:
    """Return the credential types the participant's IdentityHub currently holds."""
    response = client.get(
        f"{participant.identity_api}/participants/{participant.context_id}/credentials",
        headers={"x-api-key": participant.api_key},
    )
    response.raise_for_status()
    held: set[str] = set()
    for resource in response.json():
        credential = resource.get("verifiableCredential", {}).get("credential", {})
        held.update(credential.get("type", []))
        # Older IdentityHub payloads expose the type on the resource itself.
        if credential_type := resource.get("credentialType"):
            held.add(credential_type)
    return held


def _await_credentials(client: httpx.Client, timeout: float, interval: float) -> None:
    """Poll both IdentityHubs until every expected credential is held."""
    deadline = time.monotonic() + timeout
    outstanding = {participant.name: participant for participant in PARTICIPANTS}
    last_seen: dict[str, set[str]] = {}

    while outstanding and time.monotonic() < deadline:
        for name, participant in list(outstanding.items()):
            try:
                held = _held_credential_types(client, participant)
            except httpx.HTTPError as error:
                _log(f"  {name}: IdentityHub not answering yet ({error})")
                continue
            last_seen[name] = held
            if held >= EXPECTED_CREDENTIAL_TYPES:
                _log(f"  {name}: holds {', '.join(sorted(EXPECTED_CREDENTIAL_TYPES))}")
                del outstanding[name]
            else:
                missing = ", ".join(sorted(EXPECTED_CREDENTIAL_TYPES - held))
                _log(f"  {name}: waiting for {missing}")
        if outstanding:
            time.sleep(interval)

    if outstanding:
        detail = "; ".join(
            f"{name} holds {sorted(last_seen.get(name, set())) or 'nothing'}"
            for name in outstanding
        )
        raise IssuanceError(
            f"Credentials were not issued within {timeout:.0f}s — {detail}. "
            "Check the IssuerService and IdentityHub logs: the usual causes are a "
            "missing claim row in custom_attestation_claims, or the IdentityHub "
            "being unable to resolve the issuer's did:web document."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--issuer-url",
        default="http://issuerservice.local",
        help="Base URL of the IssuerService ingress.",
    )
    parser.add_argument(
        "--super-user-key",
        required=True,
        help=(
            "The IssuerService's generated super-user API key, printed once at "
            "startup by its SuperUserSeedExtension."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for issuance to complete on both IdentityHubs.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between IdentityHub credential polls.",
    )
    arguments = parser.parse_args(argv)

    issuer_url = arguments.issuer_url.rstrip("/")

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            _log(f"Creating the issuer's participant context on {issuer_url}")
            issuer_key = _create_issuer_context(client, issuer_url, arguments.super_user_key)

            _log("Registering the attestation, credential definitions and holders")
            _seed_issuer(client, issuer_url, issuer_key)

            _log("Requesting credentials from each participant's IdentityHub")
            for participant in PARTICIPANTS:
                _request_credentials(client, participant)

            _log("Waiting for the credentials to land in both IdentityHubs")
            _await_credentials(client, arguments.timeout, arguments.poll_interval)
    except (IssuanceError, httpx.HTTPError) as error:
        print(f"::error::{error}", file=sys.stderr, flush=True)
        return 1

    _log("Both participants hold the Catena-X credentials the TCK's policies require.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
