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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""util/base64 — encode or decode a string with base64 / base64url.

The motivating case is the AAS DTR, whose API requires an ``aas_identifier``
(and ``submodel_identifier``) to be base64url-encoded before it is placed in a
request path.  Decoding is the inverse — turning such an identifier, or an
encoded ``subprotocolBody`` field, back into readable text.
"""

from __future__ import annotations

import base64
import binascii
import logging
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import StoreInVariableParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_ENCODINGS = "utf-8"


def _encode(text: str, *, url_safe: bool, strip_padding: bool) -> str:
    """Encode *text* (UTF-8) to a base64 string."""
    raw = text.encode(_ENCODINGS)
    data = base64.urlsafe_b64encode(raw) if url_safe else base64.b64encode(raw)
    encoded = data.decode("ascii")
    return encoded.rstrip("=") if strip_padding else encoded


def _decode(text: str, *, url_safe: bool) -> str:
    """Decode a base64 string back to UTF-8 text.

    Padding is restored automatically, so an unpadded base64url value (as
    produced with ``strip_padding``) decodes without the caller re-adding
    ``=`` characters.
    """
    padded = text + "=" * (-len(text) % 4)
    try:
        raw = (
            base64.urlsafe_b64decode(padded)
            if url_safe
            else base64.b64decode(padded)
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Input is not valid base64: {exc}") from exc
    return raw.decode(_ENCODINGS)


# ---------------------------------------------------------------------------
# util/base64
# ---------------------------------------------------------------------------


class Base64Params(StoreInVariableParams):
    """Input contract of ``util/base64``."""

    input: str = Field(description="The string to encode or decode.")
    mode: Literal["encode", "decode"] = Field(
        default="encode", description="Direction of the conversion."
    )
    url_safe: bool = Field(
        default=False,
        description=(
            "Use the URL-safe alphabet ('-'/'_' instead of '+'/'/'). "
            "Required for AAS/DTR identifiers."
        ),
    )
    strip_padding: bool = Field(
        default=False,
        description=(
            "When encoding, drop trailing '=' padding. Ignored when decoding, "
            "where padding is always restored."
        ),
    )


class Base64Output(StepValue[str]):
    """The encoded or decoded string."""


@step("util/base64")
class Base64Step(BaseStep[Base64Params, Base64Output]):
    """Encode or decode a string with base64 / base64url.

    The motivating case is the AAS Digital Twin Registry, whose API wants an
    identifier base64url-encoded before it goes into a request path.
    """

    params_model = Base64Params
    output_model = Base64Output

    async def execute(
        self, params: Base64Params, context: StepContext, definition: StepDefinition,
    ) -> StepOutput[Base64Output]:
        if params.mode == "encode":
            result = _encode(
                params.input, url_safe=params.url_safe, strip_padding=params.strip_padding
            )
        else:
            result = _decode(params.input, url_safe=params.url_safe)

        if params.store_in_variable:
            context.set_variable(params.store_in_variable, result)

        logger.debug(
            "base64 %s (url_safe=%s) -> %d chars", params.mode, params.url_safe, len(result)
        )
        return StepOutput(value=Base64Output(result))
