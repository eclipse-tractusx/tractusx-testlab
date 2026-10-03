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

"""What a test is told when it puts a credential handle where it may not go.

Kept apart from :mod:`tractusx_testlab.security.credentials` only for length;
every error is raised there and re-exported from there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models.primitives.exceptions import AuthoringError

if TYPE_CHECKING:
    from tractusx_testlab.security.credentials import Credential

__all__ = [
    "CredentialError",
    "CredentialMisuseError",
    "CredentialNotReleasedError",
    "CredentialOriginMismatchError",
]


class CredentialError(AuthoringError):
    """A test used a credential handle somewhere it may not go."""

    def __init__(self, credential_name: str, message: str) -> None:
        self.credential = credential_name
        self.diagnostics = {"credential": credential_name}
        super().__init__(message)


class CredentialMisuseError(CredentialError):
    """A handle was written anywhere but as the whole value of a request header."""

    code = "CREDENTIAL_MISUSE"

    def __init__(self, credential_name: str, where: str = "") -> None:
        at = f" ({where})" if where else ""
        super().__init__(
            credential_name,
            f"'${{{{ {credential_name} }}}}' is a credential and may only be the whole "
            f"value of a request header in http/http_request{at} — e.g. "
            f"'headers: {{ x-api-key: \"${{{{ {credential_name} }}}}\" }}'. It cannot be "
            "interpolated into text or passed to any other input.",
        )


class CredentialOriginMismatchError(CredentialError):
    """A handle was sent to a request whose origin is not the binding's own."""

    code = "CREDENTIAL_ORIGIN_MISMATCH"

    def __init__(self, credential: Credential, target: str) -> None:
        allowed = ", ".join(sorted(credential.origins)) or "nowhere (the binding has no URL)"
        super().__init__(
            credential.name,
            f"{credential.name} may only be sent to {allowed}; this request goes to {target}.",
        )
        self.diagnostics = {
            "credential": credential.name,
            "allowed": sorted(credential.origins),
            "target": target,
        }


class CredentialNotReleasedError(CredentialError):
    """A handle of a side this run does not release was put on the wire by a test."""

    code = "CREDENTIAL_NOT_RELEASED"

    def __init__(self, credential: Credential) -> None:
        super().__init__(
            credential.name,
            f"{credential.name} is not released to this run: the host allows only "
            f"the steps that use the {credential.side} binding themselves to send it. "
            "Use the connector/* or digital-twin-registry/* steps instead of a raw "
            "http/http_request.",
        )
