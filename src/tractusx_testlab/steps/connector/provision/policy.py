#################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Registering a policy — ``connector/provider/create_policy`` and its wizard."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator
from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.connector.policies import as_odrl_policy
from tractusx_testlab.steps.connector.provision._shared import (
    _config_object,
    _create_or_conflict,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# connector/provider/create_policy
# ---------------------------------------------------------------------------


class CreatePolicyParams(StepParams):
    """Input contract of ``connector/provider/create_policy``.

    The policy arrives as one object rather than as separate rule lists: it is
    declared once in the manifest's ``env.variables`` with
    ``uses: config/connector/policy`` and wired in as
    ``policy: ${{ env.<id> }}``.
    """

    policy: dict = Field(
        default_factory=dict,
        description=(
            "The whole ODRL policy, as declared by a 'config/connector/policy' "
            "manifest variable and referenced as '${{ env.<id> }}'. Carries "
            "'permissions', 'prohibitions', 'obligations', an optional '@context' "
            "and an optional 'policy_id'; a fresh UUID names the policy without one. "
            "The rules are read in the same two spellings the consumer steps read "
            "them in — the testlab simplified one and ODRL's own."
        ),
    )

    @field_validator("policy", mode="before")
    @classmethod
    def _unwrap_policy(cls, value: Any) -> Any:
        return _config_object(value, "policy")


class CreatePolicyOutput(StepPayload):
    """Output contract of ``connector/provider/create_policy``."""

    policy_id: str = Field(description="ID of the policy that now exists at the provider.")


@step("connector/provider/create_policy")
class CreatePolicyStep(BaseStep[CreatePolicyParams, CreatePolicyOutput]):
    """Register an ODRL policy definition at the provider connector.

    The rules are not written into the step: the policy is configured once in
    the manifest's ``env.variables`` and handed to the step as a single
    ``policy`` input, so the same policy can be reused across tests.

    As with ``create_asset``, a 409 from the connector is reported as success
    against the existing policy rather than failing the step.
    """

    params_model = CreatePolicyParams
    output_model = CreatePolicyOutput

    async def execute(
        self, params: CreatePolicyParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[CreatePolicyOutput]:
        policy_id = str(params.policy.get("policy_id") or "")
        return _register_policy(context, policy_id, params.policy)


def _register_policy(
    context: StepContext, policy_id: str, policy: dict
) -> StepOutput[CreatePolicyOutput]:
    """Create a policy definition at the provider and report what happened.

    The one place either policy step reaches the connector, so the raw step and
    its wizard sibling cannot drift apart in what they register.

    The policy is rewritten into ODRL spelling first, exactly as the consumer
    steps rewrite the one they match offers against. The connector reads a
    policy as JSON-LD: a rule whose conditions sit under ``constraints`` rather
    than ``constraint`` carries no constraint the connector can see, and it
    answers "policy must contain at least one permission" about a policy the
    script plainly wrote one into. One variable is registered here and matched
    there, so both sides have to read the same two spellings.
    """
    provider = context.dataspace.provider()
    url = context.dataspace.provider_endpoint_url("policies")
    policy_id = policy_id or str(uuid.uuid4())

    document = as_odrl_policy(policy)
    rules = {
        "context": document.get("@context", document.get("context")),
        "permissions": document.get("permission", []),
        "prohibitions": document.get("prohibition", []),
        "obligations": document.get("obligation", []),
    }

    # Build the model to capture the serialized payload for debugging.
    policy_model = ModelFactory.get_policy_model(
        dataspace_version=provider.dataspace_version, oid=policy_id, **rules
    )
    request_body = json.loads(policy_model.to_data())

    result, http_status = _create_or_conflict(provider.create_policy, policy_id=policy_id, **rules)

    return StepOutput(
        value=CreatePolicyOutput(policy_id=policy_id),
        request=HttpRequest(method="POST", url=url, body=request_body),
        response=HttpResponse(
            status_code=http_status,
            body={"policy_id": policy_id, **(result if isinstance(result, dict) else {})},
        ),
    )


# ---------------------------------------------------------------------------
# connector/provider/wizard/create_policy
# ---------------------------------------------------------------------------


class WizardCreatePolicyParams(StepParams):
    """Input contract of ``connector/provider/wizard/create_policy``.

    The same ODRL policy as ``connector/provider/create_policy`` registers,
    written as its three rule lists instead of as one document.
    """

    policy_id: str = Field(default="", description="Policy ID; a fresh UUID is used when omitted.")
    permissions: list[dict] = Field(
        description="ODRL permission rules: what the consumer is allowed to do."
    )
    prohibitions: list[dict] = Field(default_factory=list, description="ODRL prohibition rules.")
    obligations: list[dict] = Field(default_factory=list, description="ODRL obligation rules.")

    def policy_document(self) -> dict:
        """The ODRL policy these rule lists describe."""
        return {
            "permissions": self.permissions,
            "prohibitions": self.prohibitions,
            "obligations": self.obligations,
        }


@step("connector/provider/wizard/create_policy")
class WizardCreatePolicyStep(BaseStep[WizardCreatePolicyParams, CreatePolicyOutput]):
    """Register an ODRL policy written as rule lists rather than as a document.

    The guided sibling of ``connector/provider/create_policy``, registering
    through the same call.
    """

    params_model = WizardCreatePolicyParams
    output_model = CreatePolicyOutput

    async def execute(
        self,
        params: WizardCreatePolicyParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[CreatePolicyOutput]:
        return _register_policy(context, params.policy_id, params.policy_document())
