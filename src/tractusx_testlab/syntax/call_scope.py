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

"""Call-scoped references — ``${{ *.<name> }}``. **Experimental.**

A reference that starts with ``*.`` names something that exists only while a
mock answers one call: the call itself (``*.request.*``) and what the steps the
mock runs for it published (``*.process.<id>.<field>``). They are read by
``labs/mock/api/dynamic``, the one step that runs steps per call, and nowhere
else — the compiler refuses them outside it, and at run time nothing else has
them in scope.

The ``*`` says *when* a reference is read, not what it names: every other
``${{ }}`` is read when its step runs, and a call-scoped one when a call
arrives, once per call. A mock's reply can therefore mix both — ``env.*`` for
what the test knows, ``*.request.*`` for what the caller sent.

Unlike every other reference, a call-scoped one may reach into the value it
names: ``${{ *.request.body.header.messageId }}``. A request body is always a
nested document, and taking it apart field by field with one extraction step
each was most of what a mock's steps did.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

#: What every call-scoped reference starts with.
PREFIX = "*."
#: The call being answered.
REQUEST = "*.request"
#: What the mock's steps published for the call, by step id.
PROCESS = "*.process"

#: The parts of a call a mock's steps can read, as ``*.request.<field>``.
#: ``headers`` are keyed by lower-case name, as HTTP servers hand them over;
#: ``query`` carries one value per name, as ``mock/wait`` publishes it.
REQUEST_FIELDS: tuple[str, ...] = ("body", "headers", "query", "method", "path")

#: How many segments name what a call-scoped reference reads —
#: ``*.request.<field>`` or ``*.process.<step id>``. The rest is a path into it.
ROOT_SEGMENTS = 3

#: Returned by :func:`lookup` when nothing is found, as ``None`` is a value.
MISSING = object()


def is_call_scoped(reference: str) -> bool:
    """Whether *reference* is read per call rather than when its step runs."""
    return reference.startswith(PREFIX)


def request_variable(field: str) -> str:
    """The context variable a mock's steps read ``*.request.<field>`` from."""
    return f"{REQUEST}.{field}"


def request_roots() -> frozenset[str]:
    """Every ``*.request.<field>`` a mock's steps may read."""
    return frozenset(request_variable(field) for field in REQUEST_FIELDS)


def process_root(step_id: str) -> str:
    """The root a mock's step with *step_id* publishes under."""
    return f"{PROCESS}.{step_id}"


def lookup(
    reference: str,
    has: Callable[[str], bool],
    get: Callable[[str], object],
) -> object:
    """The value *reference* names, reaching into the longest variable it starts with.

    Variables are stored flat (``*.process.answer.value``), so the longest
    prefix of the reference that is a variable is the value, and the rest is a
    path into it: dictionary keys, and list positions written as numbers.
    Answers :data:`MISSING` when no prefix is a variable or the path leads
    nowhere.
    """
    parts = reference.split(".")
    for end in range(len(parts), ROOT_SEGMENTS - 1, -1):
        name = ".".join(parts[:end])
        if has(name):
            return _walk(get(name), parts[end:])
    return MISSING


def _walk(value: object, path: Sequence[str]) -> object:
    for segment in path:
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        elif isinstance(value, list) and segment.isdigit() and int(segment) < len(value):
            value = value[int(segment)]
        else:
            return MISSING
    return value
