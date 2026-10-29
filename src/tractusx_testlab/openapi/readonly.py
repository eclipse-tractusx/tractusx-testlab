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

"""A parsed API document every reader shares, and none can change.

One parse of a document is handed to every step that references it
(``${{ env.apis.<id> }}``), in every test of the run. A step that edited its
copy in place — popped a key, appended to a list — would change what every later
step reads, and the run's outcome would depend on step order. Copying the
document per reference would cost a deep copy of up to 5 MB per step instead.

So the document is frozen once: a mapping is a :class:`FrozenDict`, a sequence
a :class:`FrozenList`. Both subclass the built-in types, so ``isinstance(x,
dict)``, ``json.dumps``, JSON Schema validation and Pydantic read them as they
read any parsed JSON; only the mutating methods refuse. Copying returns the
object itself (it cannot change, so a copy is the same value), and pickling
rebuilds it.
"""

from __future__ import annotations

from typing import Any, NoReturn

import yaml


def _refuse(*_args: object, **_kwargs: object) -> NoReturn:
    raise TypeError("An API document is read-only; build a new value instead of changing it.")


class FrozenDict(dict[str, Any]):
    """A ``dict`` that refuses every change after it is built."""

    __slots__ = ()

    __setitem__ = __delitem__ = __ior__ = _refuse
    clear = pop = popitem = setdefault = update = _refuse

    def __copy__(self) -> FrozenDict:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> FrozenDict:
        return self

    def __reduce__(self) -> tuple[type[FrozenDict], tuple[dict[str, Any]]]:
        return FrozenDict, (dict(self),)


class FrozenList(list[Any]):
    """A ``list`` that refuses every change after it is built."""

    __slots__ = ()

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _refuse
    append = clear = extend = insert = pop = remove = reverse = sort = _refuse

    def __copy__(self) -> FrozenList:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> FrozenList:
        return self

    def __reduce__(self) -> tuple[type[FrozenList], tuple[list[Any]]]:
        return FrozenList, (list(self),)


class RecordedDocument(FrozenDict):
    """A read-only document that a record of the run names instead of copying.

    A step handed a whole API document keeps all of it, but every record of
    the run — its inputs on ``step.start``, the step's result in the trace, the
    job a host keeps — would otherwise carry every byte of it, once per event,
    for every step it is handed to. :attr:`summary` is what they carry instead
    (``logging.wire.redaction`` reads it through :meth:`__recorded__`).
    """

    __slots__ = ("summary",)

    def __init__(self, content: dict[str, Any], summary: dict[str, Any]) -> None:
        super().__init__(content)
        self.summary = summary

    def __recorded__(self) -> dict[str, Any]:
        """What a record of the run shows for this document."""
        return dict(self.summary)

    def __reduce__(self) -> tuple[type[RecordedDocument], tuple[dict[str, Any], dict[str, Any]]]:  # type: ignore[override]
        return RecordedDocument, (dict(self), self.summary)


class BoundApiDocument(RecordedDocument):
    """An API file as a test names it: ``${{ env.apis.<id> }}`` (ADR-0030).

    The read-only document, plus the id the TCK declared it under and the
    digest of its file, so a step handed one knows which API it calls without
    being told twice. A record of the run shows its summary with the id added
    (``{"api_document": {"id", "openapi", "title", "version", "sha256"}}``).
    """

    __slots__ = ("api_id", "sha256")

    def __init__(self, content: dict[str, Any], api_id: str, sha256: str) -> None:
        own = getattr(content, "summary", None)
        described = (
            dict(own["api_document"]) if isinstance(own, dict) and "api_document" in own else {}
        )
        described.setdefault("openapi", str(content.get("openapi", "")))
        described["sha256"] = sha256
        super().__init__(content, {"api_document": {"id": api_id, **described}})
        self.api_id = api_id
        self.sha256 = sha256

    def __reduce__(self) -> tuple[Any, ...]:
        return BoundApiDocument, (
            RecordedDocument(dict(self), self.summary),
            self.api_id,
            self.sha256,
        )


def recorded(value: Any) -> Any:
    """*value* as a record shows it: every :class:`RecordedDocument` in it by its summary.

    Walks the mappings and sequences a step's parameters are made of, and
    returns *value* itself when nothing in it is a document — the common case
    costs no copy. A frozen document's own content is not walked.
    """
    if isinstance(value, RecordedDocument):
        return value.__recorded__()
    if isinstance(value, FrozenDict | FrozenList):
        return value
    if isinstance(value, dict):
        mapped = {key: recorded(item) for key, item in value.items()}
        return mapped if any(mapped[key] is not value[key] for key in value) else value
    if isinstance(value, list):
        items = [recorded(item) for item in value]
        changed = any(new is not old for new, old in zip(items, value, strict=True))
        return items if changed else value
    return value


def freeze(value: Any) -> Any:
    """*value* with every mapping and sequence in it made read-only.

    Iterative, so a document nested as deep as the parser allowed cannot run
    the interpreter out of stack. A container met twice (a YAML alias) is
    frozen once and shared, as the parser shared it.
    """
    if not isinstance(value, dict | list):
        return value
    done: dict[int, Any] = {}
    # Post-order: a container is built once all of its children are.
    stack: list[tuple[Any, bool]] = [(value, False)]
    while stack:
        node, children_done = stack.pop()
        if id(node) in done:
            continue
        children = node.values() if isinstance(node, dict) else node
        if not children_done:
            stack.append((node, True))
            stack.extend(
                (child, False)
                for child in children
                if isinstance(child, dict | list) and id(child) not in done
            )
            continue
        if isinstance(node, dict):
            done[id(node)] = FrozenDict({key: _frozen(item, done) for key, item in node.items()})
        else:
            done[id(node)] = FrozenList(_frozen(item, done) for item in node)
    return done[id(value)]


def _frozen(item: Any, done: dict[int, Any]) -> Any:
    return done[id(item)] if isinstance(item, dict | list) else item


# A record of the run written as YAML carries the document as plain data: the
# safe dumpers would refuse an unknown class, and the full ones would tag it.
for _dumper in (
    yaml.representer.SafeRepresenter,
    yaml.representer.Representer,
    yaml.SafeDumper,
    yaml.Dumper,
    getattr(yaml, "CSafeDumper", yaml.SafeDumper),
    getattr(yaml, "CDumper", yaml.Dumper),
):
    _dumper.add_representer(FrozenDict, yaml.representer.SafeRepresenter.represent_dict)
    _dumper.add_representer(FrozenList, yaml.representer.SafeRepresenter.represent_list)
    _dumper.add_representer(
        BoundApiDocument,
        lambda dumper, document: dumper.represent_dict(document.__recorded__()),
    )
