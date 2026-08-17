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

"""util/parse_kv — parse a delimited ``key=value`` string into a dict.

The motivating case is the EDC ``subprotocolBody`` carried in a DTR endpoint,
e.g. ``dspEndpoint=https://provider/api/dsp;id=urn:uuid:1234`` — a
semicolon-separated list of ``key=value`` pairs from which a test typically
needs a single field (the asset ``id``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Union

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import StoreInVariableParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


def _parse(text: str, pair_sep: str, kv_sep: str) -> dict[str, str]:
    """Parse *text* into an ordered dict of ``key`` → ``value``.

    Pairs are split on *pair_sep*; each pair on the **first** *kv_sep* only, so
    a value may itself contain the separator (a URL with a query string, a
    base64 payload).  Surrounding whitespace is trimmed and empty pairs are
    skipped.  A pair with no *kv_sep* contributes a key with an empty value.
    """
    result: dict[str, str] = {}
    for pair in text.split(pair_sep):
        pair = pair.strip()
        if not pair:
            continue
        key, sep, value = pair.partition(kv_sep)
        result[key.strip()] = value.strip() if sep else ""
    return result


# ---------------------------------------------------------------------------
# util/parse_kv
# ---------------------------------------------------------------------------


class ParseKvParams(StoreInVariableParams):
    """Input contract of ``util/parse_kv``."""

    input: str = Field(description="The string to parse, e.g. an EDC 'subprotocolBody'.")
    pair_separator: str = Field(default=";", description="Separator between pairs.")
    kv_separator: str = Field(default="=", description="Separator between key and value.")
    select: str | None = Field(
        default=None,
        description="Return only this key's value; omit to return the whole parsed mapping.",
    )


class ParseKvOutput(StepValue[Union[str, dict[str, str]]]):
    """The selected key's value when 'select' is given, else every parsed pair."""


@step("util/parse_kv")
class ParseKvStep(BaseStep[ParseKvParams, ParseKvOutput]):
    """Parse a delimited ``key=value`` string and optionally select one key.

    Pairs split on ``pair_separator`` and each pair on the *first*
    ``kv_separator`` only, so a value may itself contain that separator — a URL
    with a query string survives intact.
    """

    params_model = ParseKvParams
    output_model = ParseKvOutput

    async def execute(
        self, params: ParseKvParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ParseKvOutput]:
        parsed = _parse(params.input, params.pair_separator, params.kv_separator)

        if params.select is not None:
            if params.select not in parsed:
                raise KeyError(
                    f"Key {params.select!r} not found in parsed value; "
                    f"available keys: {sorted(parsed)}"
                )
            result: str | dict[str, str] = parsed[params.select]
        else:
            result = parsed

        if params.store_in_variable:
            context.set_variable(params.store_in_variable, result)

        logger.debug("Parsed %d pair(s); selected %r", len(parsed), params.select)
        return StepOutput(value=ParseKvOutput(result))
