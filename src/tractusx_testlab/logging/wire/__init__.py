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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.


"""The wire a run leaves behind: what was called, and what is written about it.

:mod:`~tractusx_testlab.logging.wire.recording` captures the calls — both
transports, through the SDK's tracer — and
:mod:`~tractusx_testlab.logging.wire.records` decides what a run writes down
about them, which is not the same thing as what it keeps (ADR-0016), with
:mod:`~tractusx_testlab.logging.wire.redaction` taking every credential out by
the name it is filed under — which names those are is
:mod:`~tractusx_testlab.logging.wire.secret_names`.
"""

from tractusx_testlab.logging.wire.recording import (
    ENGINE_CONTEXT,
    ExchangeRecorder,
    attach_to,
    recording,
)
from tractusx_testlab.logging.wire.records import (
    SECRET_HEADERS,
    Disclosure,
    as_kept,
    as_recorded,
    disclose,
    safe_headers,
)
from tractusx_testlab.logging.wire.redaction import (
    redact_secrets,
    redact_url,
    written,
)
from tractusx_testlab.logging.wire.secret_names import (
    is_secret_header,
    is_secret_key,
    register_secret_header,
    secret_headers,
)

__all__ = [
    "ENGINE_CONTEXT",
    "SECRET_HEADERS",
    "Disclosure",
    "ExchangeRecorder",
    "as_kept",
    "as_recorded",
    "attach_to",
    "disclose",
    "is_secret_header",
    "is_secret_key",
    "recording",
    "redact_secrets",
    "redact_url",
    "register_secret_header",
    "safe_headers",
    "secret_headers",
    "written",
]
