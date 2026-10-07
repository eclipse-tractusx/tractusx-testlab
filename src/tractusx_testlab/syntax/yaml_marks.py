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

"""Where each key of a YAML document sits in the file the author is editing.

A validator works on the loaded data, which has no memory of the file it came
from: by the time a key is rejected, the line it was written on is gone. The
author is then told a path — ``execution.1.validate.0.name`` — and has to count
list items by hand to find the line to fix.

So the document is composed a second time, into the node tree PyYAML builds
before it constructs Python objects, and every node's path is recorded against
its line. Composing rather than subclassing the loader is what keeps the data
clean: nothing is threaded through the parsed document, no ``__line__`` key
appears in a mapping that ``extra="forbid"`` would then reject, and a caller
that does not want positions pays nothing.

A key's own line is recorded, not its value's, because that is the line the
author's editor should land on: ``name:`` is the mistake, not the string after
it.
"""

from __future__ import annotations

import yaml

#: A path into a document: mapping keys as strings, sequence positions as ints.
#: The same shape Pydantic reports in ``error["loc"]``, so one can index the other.
Path = tuple[str | int, ...]


def line_index(text: str) -> dict[Path, int]:
    """Map every path in *text* to the 1-based line its key is written on.

    Returns an empty index when the text does not compose — a document that
    cannot be parsed has no positions to offer, and the parse error is the
    diagnostic the author needs first.
    """
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return {}
    if root is None:
        return {}

    index: dict[Path, int] = {}
    _walk(root, (), index)
    return index


def _walk(node: yaml.Node, path: Path, index: dict[Path, int]) -> None:
    """Record *node* at *path*, then descend into its children."""
    index.setdefault(path, node.start_mark.line + 1)

    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            child = (*path, key.value)
            _walk(value, child, index)
            # The value was recorded first so this overwrites it: the author is
            # sent to the key they wrote, not to the block hanging off it.
            index[child] = key.start_mark.line + 1
    elif isinstance(node, yaml.SequenceNode):
        for position, item in enumerate(node.value):
            _walk(item, (*path, position), index)


def nearest(index: dict[Path, int], path: Path) -> int | None:
    """The line for *path*, or for the closest ancestor of it that has one.

    An error can be reported against something the file never spelled out — a
    missing required key has no line, because the whole point is that it is not
    there. Pointing at its container is the honest answer: that is the block
    the author has to add it to.
    """
    for depth in range(len(path), -1, -1):
        line = index.get(path[:depth])
        if line is not None:
            return line
    return None
