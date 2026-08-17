#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""security/oauth2/* — obtain a token from an OAuth2 authorization server.

Many services under test sit behind an identity provider (typically Keycloak in
Tractus-X deployments), so a script needs a bearer token before it can call
them.  These steps perform the RFC 6749 token request against a configurable
token endpoint and publish the response, so a later step reads
``@access_token`` — or asserts that a deliberately wrong credential is refused.

One step per grant — ``client_credentials``, ``password``, ``refresh_token`` —
mirroring the IDE, which offers one block per grant rather than one block with
a grant dropdown.  The request logic lives once in the unregistered base step;
the grant names are the public step names.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Optional

import requests
from pydantic import ConfigDict, Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import HttpTransportParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

#: Form fields whose values must never appear in the run report.
_SECRET_FIELDS = frozenset({"client_secret", "password", "refresh_token"})

_REDACTED = "***"


def _redacted(form: dict[str, str]) -> dict[str, str]:
    """The token request form with every credential value masked."""
    return {
        key: _REDACTED if key in _SECRET_FIELDS and value else value
        for key, value in form.items()
    }


class OAuth2GetTokenParams(HttpTransportParams):
    """The shared input contract of the ``security/oauth2/*`` steps.

    The grant is the step name, not an input: each registered step's params
    subclass pins ``grant_type`` as a class attribute, and declares the
    credential fields of that grant alone — the ``client_credentials`` step
    does not know a ``username`` exists.
    """

    #: The grant this params class requests — set by each registered subclass.
    grant_type: ClassVar[str]

    token_url: str = Field(
        description="Token endpoint URL of the authorization server, "
        "e.g. 'https://idp.example/realms/CX/protocol/openid-connect/token'.",
    )
    client_id: str = Field(default="", description="OAuth2 client identifier.")
    client_secret: str = Field(
        default="",
        description="OAuth2 client secret; omit for a public client.",
    )
    client_auth: Literal["post", "basic"] = Field(
        default="post",
        description="How the client authenticates: 'post' sends client_id/client_secret "
        "as form fields, 'basic' sends them in an HTTP Basic Authorization header.",
    )
    scope: str = Field(
        default="",
        description="Space-separated scopes to request; omitted from the request when empty.",
    )
    extra_fields: dict[str, str] = Field(
        default_factory=dict,
        description="Additional form fields merged into the token request, "
        "e.g. 'audience' or 'resource'.",
    )

    def credential_fields(self) -> dict[str, str]:
        """The grant-specific credentials, from the subclass that declares them."""
        return {}

    def form_fields(self) -> dict[str, str]:
        """The urlencoded body of the token request, per RFC 6749 §4."""
        form: dict[str, str] = {"grant_type": self.grant_type}
        if self.client_auth == "post" and self.client_id:
            form["client_id"] = self.client_id
            if self.client_secret:
                form["client_secret"] = self.client_secret
        if self.scope:
            form["scope"] = self.scope
        form.update(self.credential_fields())
        form.update(self.extra_fields)
        return form


class OAuth2TokenPayload(StepPayload):
    """A token endpoint's response, per RFC 6749 §5.1.

    The response is defined by the authorization server rather than by testlab,
    so the well-known keys scripts read are named here and anything else the
    server sends — Keycloak's ``refresh_expires_in``, an ``id_token`` — rounds
    through untouched.
    """

    model_config = ConfigDict(extra="allow")

    access_token: Optional[str] = Field(
        default=None, description="The bearer token to present to protected services."
    )
    token_type: Optional[str] = Field(
        default=None, description="Type of the issued token, normally 'Bearer'."
    )
    expires_in: Optional[int] = Field(
        default=None, description="Lifetime of the access token in seconds."
    )
    scope: Optional[str] = Field(
        default=None, description="Scopes the server actually granted."
    )
    refresh_token: Optional[str] = Field(
        default=None, description="Refresh token, when the server issues one."
    )


class OAuth2GetTokenStep(BaseStep[OAuth2GetTokenParams, OAuth2TokenPayload]):
    """Obtain an OAuth2 token from a configurable token endpoint.

    The unregistered base of the grant-specific steps below — the token request
    is the same for every grant, only the credentials differ.  On success the
    token response is published, so a later step reads ``@access_token``; on a
    refusal the step returns no value and records the server's response, so a
    script asserts on the status code instead of crashing — a wrong secret
    being rejected is a test result, not an execution error.  Credential values
    never appear in the recorded request.
    """

    params_model = OAuth2GetTokenParams
    output_model = OAuth2TokenPayload

    async def execute(
        self,
        params: OAuth2GetTokenParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[OAuth2TokenPayload]:
        timeout = params.timeout_or(context.config.default_timeout_s)
        form = params.form_fields()
        auth = (
            (params.client_id, params.client_secret)
            if params.client_auth == "basic"
            else None
        )

        resp = requests.post(
            params.token_url,
            data=form,
            auth=auth,
            headers=params.headers,
            timeout=timeout,
        )

        try:
            body: Any = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        request = HttpRequest(
            method="POST",
            url=params.token_url,
            headers=params.headers,
            body=_redacted(form),
        )
        response = HttpResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=body,
        )

        if not resp.ok or not isinstance(body, dict):
            logger.error(
                "Token request refused: url=%s grant=%s status=%s",
                params.token_url,
                params.grant_type,
                resp.status_code,
            )
            return StepOutput(value=None, request=request, response=response)

        return StepOutput(
            value=OAuth2TokenPayload.of(body), request=request, response=response
        )


# ---------------------------------------------------------------------------
# Grant-specific step names
# ---------------------------------------------------------------------------
#
# Each grant is its own step name, matching the IDE's one-block-per-grant
# catalog.  Each pins ``grant_type`` as a class attribute — not an input, so a
# script cannot name the ``client_credentials`` step and then ask it for a
# password grant — and declares only the credential fields its grant reads.


class OAuth2ClientCredentialsParams(OAuth2GetTokenParams):
    """Input contract of ``security/oauth2/client_credentials``."""

    grant_type: ClassVar[str] = "client_credentials"


class OAuth2PasswordParams(OAuth2GetTokenParams):
    """Input contract of ``security/oauth2/password``."""

    grant_type: ClassVar[str] = "password"

    username: str = Field(min_length=1, description="Resource-owner username.")
    password: str = Field(min_length=1, description="Resource-owner password.")

    def credential_fields(self) -> dict[str, str]:
        return {"username": self.username, "password": self.password}


class OAuth2RefreshTokenParams(OAuth2GetTokenParams):
    """Input contract of ``security/oauth2/refresh_token``."""

    grant_type: ClassVar[str] = "refresh_token"

    refresh_token: str = Field(
        min_length=1, description="Refresh token to exchange for a fresh access token."
    )

    def credential_fields(self) -> dict[str, str]:
        return {"refresh_token": self.refresh_token}


@step("security/oauth2/client_credentials")
class OAuth2ClientCredentialsStep(OAuth2GetTokenStep):
    """Obtain a token as the client itself — the machine-to-machine grant.

    The token request with the ``client_credentials`` grant pinned: the client
    id and secret are the whole credential, no resource owner is involved.
    """

    params_model = OAuth2ClientCredentialsParams


@step("security/oauth2/password")
class OAuth2PasswordStep(OAuth2GetTokenStep):
    """Obtain a token on behalf of a resource owner by username and password.

    The token request with the ``password`` grant pinned; ``username`` and
    ``password`` are required inputs.
    """

    params_model = OAuth2PasswordParams


@step("security/oauth2/refresh_token")
class OAuth2RefreshTokenStep(OAuth2GetTokenStep):
    """Exchange a refresh token for a fresh access token.

    The token request with the ``refresh_token`` grant pinned;
    ``refresh_token`` is a required input.
    """

    params_model = OAuth2RefreshTokenParams
