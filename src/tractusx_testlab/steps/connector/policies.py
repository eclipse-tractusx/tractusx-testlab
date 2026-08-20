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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The policy a consumer-side connector step is given, in the shape the SDK takes.

The SDK's connector service compares catalog offers against *raw* ODRL policy
documents.  A script has three honest ways to say one — the document itself,
its JSON text, or the ``config/connector/policy`` manifest variable that holds
it — and two spellings for its rules, ODRL's and the testlab simplified one.
Folding all of them into the raw ODRL form happens here, once, so no step and
no script has to unwrap or translate a policy by hand.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import field_validator

from tractusx_testlab.steps.step_contract import StepParams

#: The key a policy document may carry itself under.  A manifest variable no
#: longer wraps one — it publishes the policy as its value, wired in whole as
#: ``${{ env.usage_policy }}`` — but a document that arrives nested under
#: ``policy`` still says the same policy, and unwrapping it here is what keeps
#: every step that takes one from having to know.
POLICY_ARTIFACT_KEY = "policy"

#: The testlab simplified policy spelling and its ODRL name.  The SDK compares
#: offers against the ODRL form alone, so a simplified policy is translated
#: before it ever reaches ``DspTools.filter_assets_and_policies``.
_ODRL_POLICY_KEYS: dict[str, str] = {
    "permissions": "permission",
    "prohibitions": "prohibition",
    "obligations": "obligation",
    "constraints": "constraint",
    "left_operand": "leftOperand",
    "right_operand": "rightOperand",
}


def as_odrl_policy[T](value: T) -> T:
    """Recursively rewrite a simplified testlab policy into ODRL spelling.

    ``permissions`` → ``permission``, ``constraints`` → ``constraint``,
    ``left_operand`` → ``leftOperand``, ``right_operand`` → ``rightOperand``.
    A policy already written in ODRL passes through unchanged.
    """
    if isinstance(value, dict):
        return {  # type: ignore[return-value]
            _ODRL_POLICY_KEYS.get(key, key): as_odrl_policy(val) for key, val in value.items()
        }
    if isinstance(value, list):
        return [as_odrl_policy(item) for item in value]  # type: ignore[return-value]
    return value


def as_raw_policy(value: Any) -> Any:
    """Read the policy definition out of whatever carries it.

    The SDK's connector service takes a raw policy — the document with
    ``permission`` / ``prohibition`` / ``obligation`` at its top level.  A
    script hands it one of three things: that document, the JSON text of it
    (a manifest variable declared with a ``value: |`` block), or a document
    nested under a ``policy`` key.  All three say the same policy, so the
    wrapper is peeled and the text parsed here rather than in every step that
    accepts one.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise ValueError(
                f"a policy given as text must be JSON, and this is not: {exc}"
            ) from exc
    while isinstance(value, dict) and isinstance(value.get(POLICY_ARTIFACT_KEY), dict | list | str):
        value = as_raw_policy(value[POLICY_ARTIFACT_KEY])
    return value


def as_policy_list(value: Any) -> list[dict] | None:
    """Normalise a policy input into the ODRL policy list the SDK expects.

    Accepts one policy or several, wrapped or raw, in ODRL or simplified
    spelling; ``None`` stays ``None``, which the SDK reads as "no preference"
    rather than as "match nothing".
    """
    if value is None:
        return None
    unwrapped = as_raw_policy(value)
    policies = unwrapped if isinstance(unwrapped, list) else [unwrapped]
    return [as_odrl_policy(as_raw_policy(policy)) for policy in policies]


class ExpectedPoliciesParams(StepParams):
    """Normalises ``expected_policies`` for every step that filters offers by policy.

    The field itself stays with the step — it is required for one step and
    optional for the next — but what a script may write into it is one contract:
    the raw ODRL document, the simplified testlab spelling, JSON text, a single
    policy or a list of them, and the ``config/connector/policy`` variable that
    holds any of those.  Whatever arrives, ``execute`` sees the raw ODRL
    policies the SDK's connector service takes.
    """

    @field_validator("expected_policies", mode="before", check_fields=False)
    @classmethod
    def _as_raw_odrl_policies(cls, value: Any) -> Any:
        return as_policy_list(value)
