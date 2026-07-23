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
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

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


@step("util/base64", aliases=["base64"])
class Base64Step(BaseStep):
    """Encode or decode a string with base64 / base64url.

    Params:
        input (str): The string to encode or decode.
        mode (str): ``encode`` (default) or ``decode``.
        url_safe (bool): Use the URL-safe alphabet (``-``/``_`` instead of
            ``+``/``/``). Required for AAS/DTR identifiers. Defaults to ``False``.
        strip_padding (bool): When encoding, drop trailing ``=`` padding.
            Ignored when decoding (padding is always restored). Defaults to
            ``False``.
        store_in_variable (str, optional): Context variable to store the result.

    Output:
        The encoded or decoded string.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2,
    ) -> StepOutput:
        raw = params.get("input")
        if raw is None:
            raise KeyError("util/base64 requires an 'input' param")
        if not isinstance(raw, str):
            raise TypeError(
                f"util/base64 expects a string input, got {type(raw).__name__}"
            )

        mode = params.get("mode", "encode")
        url_safe = bool(params.get("url_safe", False))

        if mode == "encode":
            result = _encode(
                raw, url_safe=url_safe, strip_padding=bool(params.get("strip_padding", False))
            )
        elif mode == "decode":
            result = _decode(raw, url_safe=url_safe)
        else:
            raise ValueError(
                f"util/base64 'mode' must be 'encode' or 'decode', got {mode!r}"
            )

        store_in = params.get("store_in_variable")
        if store_in:
            context.set_variable(store_in, result)

        logger.debug("base64 %s (url_safe=%s) -> %d chars", mode, url_safe, len(result))
        return StepOutput(value=result)
