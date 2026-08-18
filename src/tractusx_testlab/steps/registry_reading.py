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

"""Reading what a Digital Twin Registry answers with.

Both registry step families need these: the provider side reads
descriptors back from a registry the engine operates, and the consumer
side reads them across a data plane. They were in one 1,063-line module
with everything else, so splitting that module by namespace left the
readers on one side and half their callers on the other.
"""

from __future__ import annotations

import logging
from typing import Any

from tractusx_sdk.dataspace.tools import encode_as_base64_url_safe

from tractusx_testlab.steps import http_client

logger = logging.getLogger(__name__)


def _result_page(response: Any, what: str) -> list:
    """Read the entries out of a collection answer, in either shape it comes in.

    AAS v3 pages its collections as ``{"paging_metadata": …, "result": […]}``;
    older registries answer with the bare list.
    """
    if response.status_code != 200:
        logger.error("%s failed with status %s", what, response.status_code)
        return []
    try:
        body = response.json()
    except ValueError:
        logger.error("%s answered with a body that is not JSON", what)
        return []
    return list((body.get("result", []) if isinstance(body, dict) else body) or [])



def _shell_ids(response: Any) -> list[str]:
    """Read the identifiers out of a lookup answer."""
    return [str(entry) for entry in _result_page(response, "Shell lookup")]



def _next_cursor(response: Any) -> str | None:
    """Read the next-page cursor out of a paged answer, when there is one.

    Absent from a registry that answered with the bare list, and absent from the
    last page of one that pages — both read as ``None``.
    """
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    cursor = (body.get("paging_metadata") or {}).get("cursor")
    return str(cursor) if cursor else None



async def _get_shell_descriptor(
    base: str, shell_id: str, headers: dict, timeout: float
) -> tuple[str, Any]:
    """GET one shell descriptor by identifier, base64url-encoded as the AAS API expects.

    The one place any consumer-side step reads a descriptor, whether a script
    asked for it by identifier or a lookup surfaced it.
    """
    url = f"{base}/shell-descriptors/{encode_as_base64_url_safe(shell_id)}"
    return url, await http_client.request("GET", url, headers=headers, timeout=timeout)



async def _shell_descriptor(
    base: str, shell_id: str, headers: dict, timeout: float
) -> dict | None:
    """Read one shell descriptor by identifier, or ``None`` when it cannot be read.

    A shell the lookup named but the registry will not hand over is reported by
    its absence from ``shell_descriptors``; the identifier is still in
    ``shell_ids``, so a script can assert on the difference.
    """
    _, response = await _get_shell_descriptor(base, shell_id, headers, timeout)
    if response.status_code != 200:
        logger.warning("Shell descriptor %s could not be read (%s)", shell_id, response.status_code)
        return None
    try:
        return response.json()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# digital-twin-registry/consumer/dataplane/get_shell_descriptors
# ---------------------------------------------------------------------------

