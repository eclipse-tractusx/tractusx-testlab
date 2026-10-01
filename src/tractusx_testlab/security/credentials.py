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

"""A binding credential as a handle: usable where it belongs, unreadable everywhere else.

An infrastructure binding carries credentials — the management API key of the
engine's own connector, the key of a SUT connector an adopter runs both halves
of. The SDK services are built from the binding itself and get the value from
there. What a *test* gets is this handle, published in the variable namespace
under the same ``infrastructure.<side>.<capability>.<field>`` name the value
used to have.

The handle knows three things besides the value: the name it is published
under, the side of the topology it belongs to, and the origin it authenticates
against — the scheme, host and port of the binding's own URL. The value leaves
the handle through one door, :meth:`Credential.reveal_for`, which opens only for
a request to that origin and only when the run releases that side
(``TestlabConfig.credential_release``). Everything else a handle can be turned
into — ``str()``, ``repr()``, a pydantic dump, a JSON document, a trace line —
reads ``***``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any, NoReturn

import httpx
from pydantic_core import SchemaSerializer, core_schema
from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.models.primitives.exceptions import AuthoringError

__all__ = [
    "Credential",
    "CredentialError",
    "CredentialMisuseError",
    "CredentialNotReleasedError",
    "CredentialOriginMismatchError",
    "find_credential",
    "origin_of",
    "public_attr",
]

#: The port a scheme implies when the URL does not state one.
_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


def origin_of(url: object) -> str:
    """``scheme://host:port`` of *url*, lower-cased and with the port made explicit.

    Parsed the way the HTTP client parses it, so the origin compared here is the
    one the request actually goes to: ``https://connector.example.com@evil.io``
    is ``evil.io``, and ``https://connector.example.com.evil.io`` is not
    ``connector.example.com``. Answers ``""`` for anything that is not an
    absolute ``http``/``https`` URL, which no credential is ever bound to.
    """
    try:
        parsed = httpx.URL(str(url or "").strip())
    except (httpx.InvalidURL, TypeError, ValueError):
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.host.lower().rstrip(".")
    if scheme not in _DEFAULT_PORTS or not host:
        return ""
    return f"{scheme}://{host}:{parsed.port or _DEFAULT_PORTS[scheme]}"


class Credential:
    """One bound secret, as the variable namespace holds it.

    Immutable, and never equal to its own value: comparing a handle against a
    guess answers nothing, and no conversion of it yields the secret.
    """

    __slots__ = ("_name", "_origins", "_side", "_value")

    _name: str
    _origins: frozenset[str]
    _side: str
    _value: str

    #: How a handle serialises anywhere pydantic meets it, typed or not — a
    #: step's ``inputs``, a trace payload, a JSON report.
    __pydantic_serializer__ = SchemaSerializer(
        core_schema.any_schema(
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda _value: REDACTED_VALUE
            )
        )
    )

    def __init__(self, value: str, *, name: str, side: str, origins: Iterable[str]) -> None:
        object.__setattr__(self, "_value", str(value))
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_side", side)
        object.__setattr__(self, "_origins", frozenset(o for o in origins if o))

    @property
    def name(self) -> str:
        """The reference a test writes for it, e.g. ``infrastructure.engine.connector.api_key``."""
        return self._name

    @property
    def side(self) -> str:
        """The side of the topology the credential belongs to: ``engine`` or ``sut``."""
        return self._side

    @property
    def origins(self) -> frozenset[str]:
        """The origins a request carrying this credential may go to."""
        return self._origins

    def reveal_for(self, url: str, released: Collection[str]) -> str:
        """The secret, for a request to *url* in a run that releases *released* sides.

        The one way out of a handle, and the HTTP layer's alone. It refuses a
        side the run keeps back before it looks at the URL, so a run that
        withholds the engine's credentials says so whatever the test tried.

        Raises:
            CredentialNotReleasedError: the run does not release this side.
            CredentialOriginMismatchError: *url* is not this credential's origin.
        """
        if self._side not in released:
            raise CredentialNotReleasedError(self)
        target = origin_of(url)
        if not target or target not in self._origins:
            raise CredentialOriginMismatchError(self, target or str(url))
        return self._value

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __str__(self) -> str:
        return REDACTED_VALUE

    def __repr__(self) -> str:
        return f"Credential({self._name}={REDACTED_VALUE})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Credential):
            return NotImplemented
        return (self._name, self._side, self._origins, self._value) == (
            other._name,
            other._side,
            other._origins,
            other._value,
        )

    def __hash__(self) -> int:
        return hash((self._name, self._side, self._origins))

    def __copy__(self) -> Credential:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> Credential:
        return self

    def __reduce_ex__(self, protocol: object) -> NoReturn:
        raise TypeError(f"{self!r} cannot be pickled: a credential never leaves the run")

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: Any) -> core_schema.CoreSchema:
        """Admit a handle as itself in a typed field, and dump it as ``***``."""
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda _value: REDACTED_VALUE
            ),
        )


def find_credential(value: object) -> Credential | None:
    """The first handle *value* is or holds at any depth, or ``None``."""
    if isinstance(value, Credential):
        return value
    items: Iterable[object]
    if isinstance(value, dict):
        items = value.values()
    elif isinstance(value, list | tuple):
        items = value
    else:
        return None
    for item in items:
        found = find_credential(item)
        if found is not None:
            return found
    return None


def public_attr(obj: object, name: str, default: Any = None) -> Any:
    """``getattr`` for an attribute name a test wrote, which reaches only public data.

    A check path or a ``returns:`` name falls back to attributes when the value
    is not a document, and the name is the author's: ``x._value`` would read a
    handle's secret, ``x.__class__`` the code around it. A name starting with
    ``_`` answers *default*, and so does anything asked of a handle.
    """
    if not isinstance(name, str) or name.startswith("_") or isinstance(obj, Credential):
        return default
    return getattr(obj, name, default)


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
