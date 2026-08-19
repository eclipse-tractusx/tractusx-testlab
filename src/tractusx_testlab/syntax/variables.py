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
## It was reviewed and tested by a human committer.

"""The ``uses:`` verbs an ``env.variables`` entry may name, and what each publishes.

A manifest variable is a declaration, not a step: the engine does not run it, it
seeds it. What it seeds — the type of the value and, where the value is a
domain object, its class — follows from the verb alone, so the verb is the
single source of truth and everything else reads it from here.

**Every variable publishes under one key, ``value``.** It used to differ per
verb — ``config/connector/policy`` published ``policy``, ``config/connector/asset``
published ``asset`` — so writing a reference meant knowing which verb had chosen
which noun, and ``${{ env.usage_policy.policy }}`` was a different name for the
same thing an author had already named once. One key means the whole variable is
``${{ env.<id> }}`` and nothing has to be looked up to write it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

#: The one key every variable publishes under, and the only key a ``returns:``
#: block may name.
VALUE_KEY = "value"

#: The declared types whose value is a structure rather than a scalar. A
#: variable publishing one of these is parsed when the manifest wrote it as
#: text, so a ``value: |`` block and an inline mapping seed the same object.
STRUCTURED_TYPES: dict[str, type] = {"object": dict, "array": list}

#: What a ``returns.value`` entry may say about the value. ``type`` and ``class``
#: are the verb's own, checked against it; ``format`` is the author's note about
#: the shape of a value the operator supplies (``bpn``, ``uuid``), which no verb
#: can know.
VALUE_FIELDS: frozenset[str] = frozenset({"type", "class", "format"})


@dataclass(frozen=True, slots=True)
class VariableVerb:
    """One ``uses:`` verb: what it is for, and what it publishes.

    *type* and *class_* are what a matching ``returns.value`` block must say —
    not a default it may override. A variable whose declaration disagrees with
    its verb describes a value the run will not have.
    """

    uses: str
    type: str
    purpose: str
    class_: str | None = None

    def declaration(self) -> str:
        """The ``returns:`` block this verb requires, as it is written in YAML."""
        fields = f"type: {self.type}"
        if self.class_:
            fields = f"{fields}, class: {self.class_}"
        return f"returns: {{ {VALUE_KEY}: {{ {fields} }} }}"


#: Every verb a manifest may name. The simple ones carry a scalar or a document
#: the author writes out; the ``config/`` ones carry a domain object the
#: connector steps take whole, which is why they name a class as well as a type.
CATALOG: tuple[VariableVerb, ...] = (
    VariableVerb("variable/type/string", "string", "A text value"),
    VariableVerb("variable/type/integer", "integer", "A whole number"),
    VariableVerb("variable/type/number", "number", "A decimal number"),
    VariableVerb("variable/type/boolean", "boolean", "True or false"),
    VariableVerb("variable/type/object", "object", "A structured document"),
    VariableVerb("variable/type/array", "array", "A list of values"),
    VariableVerb(
        "config/connector/policy",
        "object",
        "An ODRL policy, provisioned by the provider steps and matched by the consumer ones",
        class_="Policy",
    ),
    VariableVerb(
        "config/connector/asset",
        "object",
        "An asset definition the provider steps register",
        class_="Asset",
    ),
)

_BY_USES: dict[str, VariableVerb] = {verb.uses: verb for verb in CATALOG}


def verb_for(uses: str) -> VariableVerb | None:
    """Return the verb *uses* names, or ``None`` when it names none."""
    return _BY_USES.get(uses)


def known_uses() -> tuple[str, ...]:
    """Every verb a manifest may name, in the order an author reads them."""
    return tuple(verb.uses for verb in CATALOG)


def read_as_declared(value: Any, declared: str | None) -> tuple[Any, str | None]:
    """Read *value* as the type its variable publishes, or say why it cannot be.

    The declared type is what every step reading the variable is promised, and
    YAML alone cannot keep that promise: a policy written as a ``value: |`` block
    is text, and seeding it as text under a declaration saying ``object`` puts a
    JSON string where the manifest said there was a document. So a variable
    publishing an ``object`` or an ``array`` whose value arrived as text is
    parsed here, once, and everything else is passed through exactly as YAML
    parsed it — a scalar never coerces, because a string that says ``string`` is
    already what it claims.

    The text is read as YAML, which parses the JSON document a connector's API
    hands back as readily as the block someone unindented one level too far.
    Both say the same structure, and refusing one of them would be refusing a
    policy for how it was pasted rather than for what it says.

    Returns the value to seed and ``None``, or ``None`` and the reason it cannot
    be read — a phrase completing "its value …". The compiler and the player
    both read a value through here, so a value the run would refuse is refused
    at compile time instead, for the same reason and in the same words.
    """
    expected = STRUCTURED_TYPES.get(declared or "")
    if expected is None or not isinstance(value, str):
        return value, None
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError as exc:
        return None, _unreadable(exc)
    if not isinstance(parsed, expected):
        return None, f"reads as {type(parsed).__name__}, not {declared}"
    return parsed, None


def _unreadable(exc: yaml.YAMLError) -> str:
    """Why the text does not parse, as one line the author can act on.

    The parser's own message is four lines of its internal view — the document
    it was handed is ``"<unicode string>"``, and the caret it draws points into
    a copy of the value nobody is looking at. What it knows and the author
    needs is the complaint and where in the value it happened; a compile report
    lists one finding per line, so it is said on one.
    """
    problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
    context = getattr(exc, "context", None)
    mark = getattr(exc, "problem_mark", None)
    detail = f"{context}, {problem}" if context else problem
    where = f" (line {mark.line + 1}, column {mark.column + 1} of the value)" if mark else ""
    return f"is not valid JSON or YAML — {detail}{where}"
