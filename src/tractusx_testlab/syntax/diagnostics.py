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

"""What a script author is told when a key is not allowed or a value is wrong.

Pydantic's own rendering is addressed to the person who wrote the model, not to
the person who wrote the YAML. ``execution.1.validate.0.name: Extra inputs are
not permitted`` names a list position instead of the step's id, states a rule of
the validation library instead of a rule of the syntax, and closes with a link to
errors.pydantic.dev — a page about Pydantic, for an author who has never heard of
it and cannot act on it. All of that is recoverable, because the document and
the model are both in hand at the moment the error is raised:

* the path is walked against the document, so a list position is followed by the
  id of the item sitting there;
* the path is walked against the model, so the keys that *are* allowed at that
  point can be listed, and a near-miss ("nmae") named as the likely typo;
* the document is composed a second time for line numbers, so the author is sent
  to a line rather than to a path they have to count out by hand.

What cannot be recovered is left as Pydantic wrote it. A message with no
authored form is passed through rather than paraphrased into something vaguer.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from tractusx_testlab.syntax.model_keys import keys_of, model_at, noun_for
from tractusx_testlab.syntax.yaml_marks import Path as DocPath
from tractusx_testlab.syntax.yaml_marks import line_index, nearest

#: Longer than this and an offending value is a wall of text, not a hint. The
#: author knows what they wrote; they need to be told where and why it is wrong.
_MAX_VALUE = 60


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One thing wrong with a document, said the way the author can act on it."""

    path: DocPath
    message: str
    hint: str | None = None
    line: int | None = None
    #: The path as the author reads it: list positions carry the id of the item
    #: sitting there, so a step is named rather than counted to.
    location: str = ""

    @property
    def where(self) -> str:
        """The location, ``line 76`` included when the document gave one up."""
        location = self.location or _format_path(self.path, None)
        return f"{location} (line {self.line})" if self.line else location

    def __str__(self) -> str:
        text = f"{self.where}: {self.message}" if (self.path or self.location) else self.message
        return f"{text} — {self.hint}" if self.hint else text


def explain(
    exc: ValidationError,
    *,
    model: type[BaseModel] | None = None,
    data: Any = None,
    text: str | None = None,
    source: Path | None = None,
) -> list[Diagnostic]:
    """Turn a Pydantic failure into diagnostics addressed to the script author.

    *model* is the class the document was validated against and is what makes
    "these are the keys you may use here" answerable; *data* is the loaded
    document, which turns list positions into step ids; *text* is the raw YAML,
    which turns paths into line numbers. Each is optional and each independently
    sharpens the result — with none of them the output is still better ordered
    and better worded than Pydantic's, just less specific. *source* is the file
    the document was read from and supplies *data* and *text* from it.
    """
    if source is not None:
        text = source.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    lines = line_index(text) if text else {}
    diagnostics: list[Diagnostic] = []
    for error in exc.errors():
        path = tuple(error["loc"])
        diagnostics.append(
            Diagnostic(
                path=path,
                message=_message(error, model),
                hint=_hint(error, model),
                line=nearest(lines, path) if lines else None,
                location=_format_path(path, data),
            )
        )
    # In file order: Pydantic reports the declared fields before the rejected
    # ones, so an unknown key at the top of a step was listed after a bad value
    # at the bottom of it. An author fixes a file downwards.
    return sorted(diagnostics, key=lambda d: (d.line or 1 << 30, d.path))


def unparseable(exc: yaml.YAMLError, source: Path) -> Diagnostic:
    """A document that is not YAML at all, said without a Python traceback.

    A misplaced dash used to reach the terminal as a 29 KB rich traceback of
    the compiler's own call stack, with the parser's one-line complaint buried
    in the middle of it. The parser already knows the line and the column; the
    author needs those and nothing else.
    """
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
    context = getattr(exc, "context", None)
    where = (
        f"{source.name} (line {mark.line + 1}, column {mark.column + 1})" if mark else source.name
    )
    detail = f"{context}, {problem}" if context else problem
    return Diagnostic(path=(), message=f"not valid YAML — {detail}", location=where)


def render(exc: ValidationError, **context: Any) -> str:
    """The diagnostics for *exc* as one indented block, one finding per line."""
    return "\n".join(f"  - {d}" for d in explain(exc, **context))


# -- Messages -----------------------------------------------------------------


def _message(error: ErrorDetails, model: type[BaseModel] | None) -> str:
    """State the finding in the vocabulary of the syntax, not of the validator."""
    kind = error["type"]
    path = tuple(error["loc"])
    context: dict[str, Any] = error.get("ctx") or {}

    if kind == "extra_forbidden":
        return f"'{path[-1]}' is not a key of {_subject(model, path[:-1])}"
    if kind == "missing":
        return f"required key '{path[-1]}' is missing from {_subject(model, path[:-1])}"
    if kind == "literal_error":
        expected = context.get("expected", "")
        return f"{_value(error)} is not allowed here — expected {expected}"
    if kind == "string_pattern_mismatch":
        pattern = context.get("pattern", "")
        return f"{_value(error)} does not have the required form '{pattern}'"
    if kind.endswith(("_type", "_parsing")):
        return f"{error['msg']} — got {_value(error)}"
    return error["msg"]


def _hint(error: ErrorDetails, model: type[BaseModel] | None) -> str | None:
    """For a rejected key, the keys that would have been accepted instead."""
    if error["type"] != "extra_forbidden" or model is None:
        return None
    owner = model_at(model, tuple(error["loc"])[:-1])
    if owner is None:
        return None
    allowed = keys_of(owner)
    if not allowed:
        return None
    written = str(error["loc"][-1])
    near = get_close_matches(written, allowed, n=1, cutoff=0.7)
    if near:
        return f"did you mean '{near[0]}'? Allowed here: {', '.join(allowed)}"
    return f"allowed here: {', '.join(allowed)}"


def _value(error: ErrorDetails) -> str:
    """The offending value, quoted, and only while it is short enough to help."""
    value = error.get("input")
    if isinstance(value, (dict, list)):
        return f"a {type(value).__name__}"
    rendered = repr(value)
    return rendered if len(rendered) <= _MAX_VALUE else f"{rendered[:_MAX_VALUE]}…"


def _subject(model: type[BaseModel] | None, path: DocPath) -> str:
    """Name the kind of block the key belongs to: "a step", "an assertion"."""
    owner = model_at(model, path) if model else None
    return noun_for(owner) if owner else "this block"


# -- Paths --------------------------------------------------------------------


def _format_path(path: DocPath, data: Any) -> str:
    """``execution[1] 'pull_dtr' → validate[0]`` — nesting, and what to look for.

    The position alone made the author count list items in their own file. The
    id of the item at that position is what they named it, so it is what they
    can search for.
    """
    parts: list[str] = []
    for depth, part in enumerate(path):
        if not isinstance(part, int):
            parts.append(str(part))
            continue
        segment = f"{parts[-1]}[{part}]" if parts else f"[{part}]"
        identifier = _id_at(data, path[: depth + 1]) if data is not None else None
        segment = f"{segment} '{identifier}'" if identifier else segment
        if parts:
            parts[-1] = segment
        else:
            parts.append(segment)
    return " → ".join(parts)


def _id_at(data: Any, path: DocPath) -> str | None:
    """The ``id`` of the item at *path*, which is how the author refers to it."""
    cursor = data
    for part in path:
        try:
            cursor = cursor[part]
        except (KeyError, IndexError, TypeError):
            return None
    if isinstance(cursor, dict):
        return str(cursor["id"]) if cursor.get("id") else None
    return None
