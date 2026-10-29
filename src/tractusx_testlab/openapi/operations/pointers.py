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

"""JSON Pointers into an API document, and the internal ``$ref`` they follow.

Every ``$ref`` of an API file is internal and resolves (the loader refuses any
other, ADR-0030 §3), so following one is a walk of the document and nothing
else: no file is opened and no URL is fetched.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

#: How many ``$ref`` hops a chain may take before it is called circular. The
#: loader already refused cycles; this only bounds a walk over a document that
#: did not come through it.
MAX_HOPS = 32


class PointerError(LookupError):
    """A pointer that names nothing in the document."""


def escape(token: object) -> str:
    """*token* as one segment of a JSON Pointer (RFC 6901)."""
    return str(token).replace("~", "~0").replace("/", "~1")


def unescape(token: str) -> str:
    """One JSON Pointer segment back to the key it names."""
    return token.replace("~1", "/").replace("~0", "~")


def pointer(*tokens: object) -> str:
    """The URI fragment ``#/a/b`` naming *tokens* from the document root."""
    return "#" + "".join(f"/{escape(token)}" for token in tokens)


def child(parent: str, *tokens: object) -> str:
    """*parent* (``#/a``) extended by *tokens*."""
    return parent + "".join(f"/{escape(token)}" for token in tokens)


def resolve(document: Mapping[str, Any], fragment: str) -> Any:
    """The value at *fragment* (``#/components/schemas/X``) in *document*.

    Raises:
        PointerError: the fragment is not internal or names nothing.
    """
    if not fragment.startswith("#"):
        raise PointerError(f"'{fragment}' is not a reference inside the document")
    node: Any = document
    path = fragment[1:]
    if not path:
        return node
    if not path.startswith("/"):
        raise PointerError(f"'{fragment}' is not a JSON Pointer")
    for raw in path[1:].split("/"):
        token = unescape(raw)
        if isinstance(node, Mapping) and token in node:
            node = node[token]
        elif isinstance(node, Sequence) and not isinstance(node, str) and token.isdigit():
            index = int(token)
            if index >= len(node):
                raise PointerError(f"'{fragment}' names nothing in the document")
            node = node[index]
        else:
            raise PointerError(f"'{fragment}' names nothing in the document")
    return node


def follow(document: Mapping[str, Any], node: Any, at: str) -> tuple[Any, str]:
    """*node* (found at *at*) with its ``$ref`` chain followed, and where it ended.

    An object that is not a reference is returned as it is, with *at*.
    """
    for _ in range(MAX_HOPS):
        if not (isinstance(node, Mapping) and isinstance(node.get("$ref"), str)):
            return node, at
        at = node["$ref"]
        node = resolve(document, at)
    raise PointerError(f"'{at}' is a $ref chain longer than {MAX_HOPS} hops")
