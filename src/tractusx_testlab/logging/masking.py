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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Secrets a run minted, and the one place that keeps them out of every record.

Header redaction (:mod:`tractusx_testlab.logging.wire.records`) works by name:
``x-api-key`` is a secret whatever it holds. That is not enough for a value the
run itself creates and then hands on. A mock's API key is minted by
``mock/api``, published as a step output, wired into an asset's data address,
sent to the connector's management API in a request *body*, and comes back in
the headers of the call the data plane forwards. Under a header name the tracer
knows it is caught; as ``"header:x-api-key"`` inside a JSON body, as a step
input, or as a returned value, it is not.

So a secret is registered here by value when it is minted, and every sink a
viewer can read — the CloudEvents trace, the events handed to an embedder's
callbacks, the console transcript — passes what it writes through :func:`mask`
first. The value the run keeps is untouched: the step that needs the key still
gets it, only what is written down loses it.

The registry is process-wide rather than per run. An engine runs several jobs
in one process, and one run's key showing up in another run's record would be
exactly as wrong as it showing up in its own. It is bounded, so a long-lived
engine does not mask against every key it ever minted: by the time
:data:`MAX_SECRETS` newer ones exist, the run that minted the oldest is over.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from typing import Any

from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

#: How many secrets are remembered before the oldest is forgotten.
MAX_SECRETS = 1024

#: Shorter values are not masked. A short string is far more likely to occur by
#: accident — in a path, a count, an id — and masking it would corrupt the
#: record while protecting nothing worth protecting.
MIN_SECRET_LENGTH = 8

_lock = threading.Lock()
_secrets: OrderedDict[str, None] = OrderedDict()
_pattern: re.Pattern[str] | None = None


def register_secret(value: str | None) -> None:
    """Mask *value* wherever a record of the run would otherwise carry it."""
    global _pattern
    if not isinstance(value, str) or len(value) < MIN_SECRET_LENGTH:
        return
    with _lock:
        _secrets.pop(value, None)
        _secrets[value] = None
        while len(_secrets) > MAX_SECRETS:
            _secrets.popitem(last=False)
        # Longest first, so a secret that contains another is masked whole.
        ordered = sorted(_secrets, key=len, reverse=True)
        _pattern = re.compile("|".join(re.escape(secret) for secret in ordered))


def forget_secrets() -> None:
    """Drop every registered secret. For tests; a run never needs to."""
    global _pattern
    with _lock:
        _secrets.clear()
        _pattern = None


def mask(value: Any) -> Any:
    """*value* with every registered secret replaced by the tracer's marker.

    Walks dicts, lists and tuples, and masks keys as well as values — a data
    address spells its extra headers as ``"header:<name>"`` keys, and nothing
    stops a test from building a key out of a value. Anything that is not a
    string or a container comes back as it was.
    """
    pattern = _pattern
    if pattern is None:
        return value
    return _masked(value, pattern)


def _masked(value: Any, pattern: re.Pattern[str]) -> Any:
    if isinstance(value, str):
        return pattern.sub(REDACTED_VALUE, value)
    if isinstance(value, dict):
        return {_masked(key, pattern): _masked(item, pattern) for key, item in value.items()}
    if isinstance(value, list):
        return [_masked(item, pattern) for item in value]
    if isinstance(value, tuple):
        return tuple(_masked(item, pattern) for item in value)
    return value
