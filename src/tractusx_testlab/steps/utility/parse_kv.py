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
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

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


@step("util/parse_kv")
class ParseKvStep(BaseStep):
    """Parse a delimited ``key=value`` string and optionally select one key.

    Params:
        input (str): The string to parse (e.g. an EDC ``subprotocolBody``).
        pair_separator (str): Separator between pairs. Defaults to ``;``.
        kv_separator (str): Separator between key and value. Defaults to ``=``.
        select (str, optional): Return only this key's value. When omitted, the
            whole parsed dict is returned.
        store_in_variable (str, optional): Context variable to store the result.

    Output:
        The selected value (str) when ``select`` is given, else the parsed dict.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput:
        raw = params.get("input")
        if raw is None:
            raise KeyError("util/parse_kv requires an 'input' param")
        if not isinstance(raw, str):
            raise TypeError(
                f"util/parse_kv expects a string input, got {type(raw).__name__}"
            )

        pair_sep = params.get("pair_separator", ";")
        kv_sep = params.get("kv_separator", "=")
        parsed = _parse(raw, pair_sep, kv_sep)

        select = params.get("select")
        if select is not None:
            if select not in parsed:
                raise KeyError(
                    f"Key {select!r} not found in parsed value; "
                    f"available keys: {sorted(parsed)}"
                )
            result: object = parsed[select]
        else:
            result = parsed

        store_in = params.get("store_in_variable")
        if store_in:
            context.set_variable(store_in, result)

        logger.debug("Parsed %d pair(s); selected %r", len(parsed), select)
        return StepOutput(value=result)
