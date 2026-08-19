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

"""Checking that each ``env.variables`` entry declares something the run can seed.

``variables:`` was the one block nothing checked. Its schema is ``Any``, so a
verb that does not exist, a ``returns:`` naming a key no variable publishes, or
a value the manifest never supplies all compiled, and the TCK then failed at the
first step that read the variable — as an unresolved reference several files
away from the declaration that caused it.

Every rule here is bound to the entry's ``uses:`` verb
(:mod:`tractusx_testlab.syntax.variables`), because the verb is what decides
what the variable publishes and of what type.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from tractusx_testlab.models.primitives.exceptions import VariableTypeError
from tractusx_testlab.syntax import keys, patterns
from tractusx_testlab.syntax.variables import (
    VALUE_FIELDS,
    VALUE_KEY,
    VariableVerb,
    known_uses,
    read_as_declared,
    verb_for,
)

#: What ``with.source`` may say. ``value`` is the default, so an entry that
#: names no source carries its value in the manifest.
_SOURCES: frozenset[str] = frozenset({"input", "value", "generated"})

#: Namespaces a variable may not name, and what to write instead. ``generate/``
#: parses — it has since the first verb-form grammar — but nothing in the engine
#: produces a generated variable, so the value is never seeded and every
#: reference to it fails at run time. A value the run makes up is a step's
#: output, which the run does produce.
_UNSUPPORTED_NAMESPACES: tuple[tuple[str, str], ...] = (
    (
        "generate/",
        "the engine seeds variables, it does not generate them — nothing would "
        "supply a value. Produce it with a step instead ('util/generate_uuid') "
        "and read it as '${{ execution.<step-id>.value }}', or ask the operator "
        "for it with 'uses: variable/type/string' and 'with.source: input'",
    ),
)


def validate_variable_declarations(env_data: dict[str, Any]) -> list[str]:
    """Return every problem in the manifest's ``env.variables`` block.

    Every entry is checked and every rule runs, so an author sees the whole
    block's problems at one compile rather than the first one repeatedly.
    """
    variables = env_data.get("variables")
    if variables is None:
        return []
    if not isinstance(variables, list):
        return [
            "env.variables must be a list of entries, each with an 'id', a 'uses' "
            f"and a 'returns', not a {type(variables).__name__}."
        ]

    errors: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(variables):
        if not isinstance(entry, dict):
            errors.append(f"env.variables[{index}] is not a mapping — write it as 'id: …' entry.")
            continue
        errors.extend(_check_entry(entry, index, seen))
    return errors


def _check_entry(entry: dict[str, Any], index: int, seen: set[str]) -> Iterator[str]:
    """Check one entry: its id, its verb, and what it says it publishes."""
    var_id = str(entry.get(keys.ID) or "")
    if not var_id:
        yield f"env.variables[{index}] has no 'id'. It is the name every reference uses."
        return
    if var_id in seen:
        yield (
            f"Variable '{var_id}' is declared twice. The second declaration silently "
            f"replaces the first, so a reference to it reads whichever the file "
            f"happened to end with."
        )
    seen.add(var_id)

    uses = str(entry.get(keys.USES) or "")
    if not uses:
        yield (
            f"Variable '{var_id}' has no 'uses'. It says what the variable is and "
            f"what it publishes — one of: {', '.join(known_uses())}."
        )
        return

    verb = verb_for(uses)
    if verb is None:
        yield _unknown_verb(var_id, uses)
        return

    yield from _check_source(entry, var_id)
    yield from _check_value(entry, var_id, verb)
    yield from _check_returns(entry, var_id, verb)


def _unknown_verb(var_id: str, uses: str) -> str:
    """Say why *uses* is not a variable type, in the terms of what to write instead."""
    for namespace, reason in _UNSUPPORTED_NAMESPACES:
        if uses.startswith(namespace):
            return f"Variable '{var_id}' uses '{uses}', but {reason}."
    return (
        f"Variable '{var_id}' names an unknown type '{uses}'. "
        f"Valid types are: {', '.join(known_uses())}."
    )


def _check_source(entry: dict[str, Any], var_id: str) -> Iterator[str]:
    """Check that the entry says where its value comes from, and can supply it."""
    with_block = entry.get(keys.WITH) or {}
    if not isinstance(with_block, dict):
        yield f"Variable '{var_id}' has a 'with' that is not a mapping."
        return

    source = with_block.get(keys.SOURCE)
    if source is not None and str(source) not in _SOURCES:
        yield (
            f"Variable '{var_id}' has an unrecognized source '{source}'. "
            f"Valid values are: {', '.join(sorted(_SOURCES))}."
        )
        return

    # ``value`` is the default: an entry naming no source carries its own value.
    if source is None or str(source) == "value":
        if keys.VALUE not in with_block:
            yield (
                f"Variable '{var_id}' has no 'with.value' and does not ask the "
                f"operator for one. Nothing would seed it, so every "
                f"'${{{{ env.{var_id} }}}}' fails at run time. Write the value under "
                f"'with.value', or 'with.source: input' to have it supplied at "
                f"run start."
            )


def _check_value(entry: dict[str, Any], var_id: str, verb: VariableVerb) -> Iterator[str]:
    """Check that a value written in the manifest reads as what the verb publishes.

    A policy pasted with a comma missing is text that is not a policy, and it
    used to compile: nothing read the value until the run seeded it, so the
    author met the parse error after the runner had started. It is read here
    with the run's own reader, so the finding is the same one, at compile time.
    """
    with_block = entry.get(keys.WITH)
    if not isinstance(with_block, dict) or keys.VALUE not in with_block:
        return
    _, problem = read_as_declared(with_block[keys.VALUE], verb.type)
    if problem is not None:
        yield str(VariableTypeError(var_id, verb.type, problem))


def _check_returns(entry: dict[str, Any], var_id: str, verb: VariableVerb) -> Iterator[str]:
    """Check that ``returns:`` declares ``value``, of the type the verb publishes."""
    returns = entry.get(keys.RETURNS)
    if returns is None:
        yield f"Variable '{var_id}' has no 'returns'. Write '{verb.declaration()}'."
        return
    if not isinstance(returns, dict):
        yield f"Variable '{var_id}' has a 'returns' that is not a mapping."
        return

    wrong_keys = sorted(key for key in returns if key != VALUE_KEY)
    if wrong_keys:
        yield (
            f"Variable '{var_id}' publishes under '{', '.join(wrong_keys)}'. "
            f"Every variable publishes under '{VALUE_KEY}', whatever its type, so "
            f"the whole variable is '${{{{ env.{var_id} }}}}' and nothing has to be "
            f"looked up to reference it. Write '{verb.declaration()}'."
        )
        return
    if VALUE_KEY not in returns:
        yield f"Variable '{var_id}' declares an empty 'returns'. Write '{verb.declaration()}'."
        return

    yield from _check_value_field(returns[VALUE_KEY], var_id, verb)


def _check_value_field(value_def: Any, var_id: str, verb: VariableVerb) -> Iterator[str]:
    """Check the ``returns.value`` block against what the verb publishes."""
    if not isinstance(value_def, dict):
        yield f"Variable '{var_id}' has a 'returns.value' that is not a mapping."
        return

    unknown = sorted(key for key in value_def if key not in VALUE_FIELDS)
    if unknown:
        yield (
            f"Variable '{var_id}' declares '{', '.join(unknown)}' under "
            f"'returns.value', which takes only {', '.join(sorted(VALUE_FIELDS))}."
        )

    declared_type = value_def.get(keys.TYPE)
    if declared_type is None:
        yield f"Variable '{var_id}' declares no 'returns.value.type'. Write '{verb.declaration()}'."
    elif str(declared_type) != verb.type:
        yield (
            f"Variable '{var_id}' is a '{verb.uses}', which publishes a "
            f"{verb.type}, but declares 'type: {declared_type}'. Write "
            f"'{verb.declaration()}'."
        )

    declared_class = value_def.get("class")
    if verb.class_ is None and declared_class is not None:
        yield (
            f"Variable '{var_id}' declares 'class: {declared_class}', but a "
            f"'{verb.uses}' publishes a plain {verb.type}. Write '{verb.declaration()}'."
        )
    elif verb.class_ is not None and str(declared_class or "") != verb.class_:
        yield (
            f"Variable '{var_id}' is a '{verb.uses}', which publishes a "
            f"{verb.class_}, but declares "
            f"'class: {declared_class if declared_class is not None else '(none)'}'. "
            f"Write '{verb.declaration()}'."
        )


def declared_variable_ids(env_data: dict[str, Any]) -> frozenset[str]:
    """The ids of every variable the manifest declares."""
    variables = env_data.get("variables")
    if not isinstance(variables, list):
        return frozenset()
    return frozenset(
        str(entry[keys.ID]) for entry in variables if isinstance(entry, dict) and entry.get(keys.ID)
    )


def validate_variable_references(
    test_data: dict[str, Any],
    variable_ids: frozenset[str],
    source_label: str,
) -> list[str]:
    """Reject a reference that reaches into a variable instead of naming it.

    ``${{ env.usage_policy.policy }}`` named the artifact key the verb used to
    choose, and ``${{ env.usage_policy.value }}`` names the key that replaced
    it. Both are a path into a value the id already names whole, and the run
    resolves neither — so both are answered here, at the line that has to
    change, rather than as an unresolved reference in the middle of a test.
    """
    return [
        f"{source_label}: '${{{{ {reference} }}}}' reaches into variable "
        f"'{var_id}' for '{field}'. A variable is one value and its id names all "
        f"of it — write '${{{{ env.{var_id} }}}}'."
        for reference in _references_in(test_data)
        for var_id, field in [_env_field(reference)]
        if var_id in variable_ids and field
    ]


def _env_field(reference: str) -> tuple[str, str]:
    """Split ``env.<id>.<field…>`` into its variable id and the rest."""
    parts = reference.strip().split(".")
    if len(parts) < 2 or parts[0] != "env":
        return "", ""
    return parts[1], ".".join(parts[2:])


def _references_in(node: Any) -> Iterator[str]:
    """Yield every ``${{ … }}`` expression anywhere in a parsed YAML document."""
    if isinstance(node, str):
        for match in patterns.EXPR_REF.finditer(node):
            yield match.group(1)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _references_in(value)
    elif isinstance(node, list):
        for item in node:
            yield from _references_in(item)
