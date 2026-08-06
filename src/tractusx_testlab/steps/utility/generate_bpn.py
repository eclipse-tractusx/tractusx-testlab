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

"""BPN generation step — produces a random, well-formed Business Partner Number."""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, field_validator

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BODY_LENGTH = 10
_CHECK_LENGTH = 2
_DEFAULT_PREFIX = "BPNL"

BpnPrefix = Literal["BPNL", "BPNS", "BPNA"]


def _compute_check_chars(body: str) -> str:
    """Derive 2 check characters from the body via a simple modular hash."""
    hash_val = int(hashlib.sha256(body.encode("utf-8")).hexdigest(), 16)
    c1 = _ALPHABET[hash_val % len(_ALPHABET)]
    c2 = _ALPHABET[(hash_val // len(_ALPHABET)) % len(_ALPHABET)]
    return f"{c1}{c2}"


def _random_bpn(prefix: str) -> str:
    """Generate a random BPN: prefix + 10 alphanumeric chars + 2 check chars."""
    digest = uuid.uuid4().hex.upper()
    body_chars = [ch for ch in digest if ch in _ALPHABET][:_BODY_LENGTH]
    while len(body_chars) < _BODY_LENGTH:
        body_chars.append("0")  # pragma: no cover — hex digest always yields enough
    body = "".join(body_chars)
    return f"{prefix}{body}{_compute_check_chars(body)}"


class GenerateBpnParams(StepParams):
    """Input contract of ``util/generate_bpn``."""

    prefix: BpnPrefix = Field(
        default=_DEFAULT_PREFIX,
        description="BPN type prefix: legal entity (BPNL), site (BPNS), or address (BPNA).",
    )

    @field_validator("prefix", mode="before")
    @classmethod
    def _normalise_prefix(cls, value: Any) -> Any:
        """Accept lowercase and empty prefixes, as the untyped step used to."""
        if not value:
            return _DEFAULT_PREFIX
        return value.upper() if isinstance(value, str) else value


class GenerateBpnOutput(StepPayload):
    """Output contract of ``util/generate_bpn``."""

    bpn: str = Field(description="The generated Business Partner Number.")


@step("util/generate_bpn")
class GenerateBpnStep(BaseStep[GenerateBpnParams, GenerateBpnOutput]):
    """Generate a random, well-formed Business Partner Number (BPN).

    The result is syntactically valid — prefix, ten alphanumeric characters and
    two derived check characters — but belongs to no real business partner, so
    it suits tests that need an identifier no live participant will collide
    with. A fresh BPN is produced on every call.
    """

    params_model = GenerateBpnParams
    output_model = GenerateBpnOutput

    async def execute(
        self,
        params: GenerateBpnParams,
        context: "StepContext",
        definition: StepDefinitionV2,
    ) -> StepOutput[GenerateBpnOutput]:
        return StepOutput(value=GenerateBpnOutput(bpn=_random_bpn(params.prefix)))
