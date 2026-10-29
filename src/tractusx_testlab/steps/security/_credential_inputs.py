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

"""What a credential must look like to be sent where ``security/*`` steps put it.

The ``security/api_key`` and ``security/basic`` steps call nothing: they build
the header, query parameter or cookie a later request carries. A value that
request could not carry as it is — a line break in a header, a semicolon in a
cookie — is refused here, when the step runs, with a message that names the
problem and never the value.
"""

from __future__ import annotations

import re

#: An HTTP field (header) name — RFC 9110 §5.1, a ``token``.
HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")

#: Characters no header value may carry: control characters other than a tab.
#: A line break in one would end the header and start another.
_HEADER_UNSAFE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")

#: What a cookie value may hold — RFC 6265 §4.1.1 ``cookie-octet``.
_COOKIE_VALUE = re.compile(r"^[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*$")


def is_header_safe(value: str) -> bool:
    """Whether *value* can be sent as a header value as it is."""
    return _HEADER_UNSAFE.search(value) is None


def is_cookie_safe(value: str) -> bool:
    """Whether *value* can be sent as a cookie value without quoting."""
    return _COOKIE_VALUE.match(value) is not None
